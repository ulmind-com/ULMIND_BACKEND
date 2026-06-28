from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.task import TaskCreate, TaskUpdate, TaskInDB
from app.services.email_service import send_task_assignment_email
from app.services.twilio_service import send_task_sms_and_whatsapp
from app.services.event_trigger_service import fire_event_background
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


async def _generate_task_id(db) -> str:
    """Generate sequential task ID: TASK-UL-001, TASK-UL-002, etc."""
    counter = await db["counters"].find_one_and_update(
        {"_id": "task_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter["seq"]
    return f"TASK-UL-{seq:03d}"


async def _recalculate_project_progress(db, project_id: str):
    """Recalculate project progress based on task completion."""
    if not project_id:
        return
    tasks = await db["tasks"].find({"project_id": project_id}).to_list(1000)
    if not tasks:
        return

    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "Completed")
    in_progress = sum(1 for t in tasks if t.get("status") == "In Progress")
    review = sum(1 for t in tasks if t.get("status") == "Review")

    # Weighted progress: Completed=100%, Review=80%, In Progress=40%
    weighted = (completed * 100 + review * 80 + in_progress * 40) / total if total > 0 else 0
    progress = round(min(weighted, 100), 1)
    completion = round((completed / total * 100) if total > 0 else 0, 1)

    try:
        await db["projects"].update_one(
            {"_id": _parse_id(project_id)},
            {"$set": {
                "progress": progress,
                "completion_percent": completion,
                "updated_at": get_now()
            }}
        )
    except Exception:
        pass  # project_id might not be a valid ObjectId


async def _auto_notify_assignees(db, task: dict, admin_email: str, admin_name: str):
    """Send email notifications to all assignees."""
    assignee_ids = []
    if task.get("assigned_to"):
        assignee_ids.append(task["assigned_to"])
    if task.get("assigned_to_multiple"):
        assignee_ids.extend(task["assigned_to_multiple"])

    # Deduplicate
    assignee_ids = list(set(assignee_ids))

    for assignee_id in assignee_ids:
        try:
            assignee = await db["admins"].find_one({"_id": ObjectId(assignee_id)})
            if not assignee or not assignee.get("email"):
                continue

            project_name = task.get("project_name", "Unknown Project")
            if task.get("project_id") and project_name == "Unknown Project":
                try:
                    project = await db["projects"].find_one({"_id": ObjectId(task["project_id"])})
                    if project:
                        project_name = project.get("name", "Unknown Project")
                except Exception:
                    pass

            due_date = "No due date"
            if task.get("due_date"):
                try:
                    due_date = task["due_date"].strftime("%B %d, %Y")
                except Exception:
                    due_date = str(task["due_date"])

            due_countdown = ""
            if task.get("due_date"):
                from datetime import datetime
                try:
                    due = task["due_date"]
                    if isinstance(due, str):
                        due = datetime.fromisoformat(due.replace('Z', '+00:00'))
                    delta = due.date() - datetime.now().date()
                    if delta.days == 0:
                        due_countdown = "Today"
                    elif delta.days == 1:
                        due_countdown = "Tomorrow"
                    elif delta.days > 1:
                        due_countdown = f"{delta.days} days left"
                    elif delta.days < 0:
                        due_countdown = f"Overdue by {abs(delta.days)} days"
                except Exception:
                    pass

            try:
                await send_task_assignment_email(
                    recipient=assignee["email"],
                    assignee_name=assignee.get("full_name", "Team Member"),
                    task_title=task.get("title", "Untitled Task"),
                    task_description=task.get("description", "No description provided."),
                    project_name=project_name,
                    priority=task.get("priority", "Medium"),
                    due_date=due_date,
                    assigned_by=admin_name,
                    task_id=task.get("task_id", ""),
                    estimated_hours=task.get("estimated_hours", 0),
                    due_countdown=due_countdown,
                )
                logger.info(f"Task email sent to {assignee['email']}")
            except Exception as email_err:
                logger.error(f"Email failed for {assignee.get('email')}: {email_err}")
            
            # 2.5 second delay between individual emails to bypass Zoho's strict burst spam filter
            await asyncio.sleep(2.5)
                
        except Exception as e:
            logger.error(f"Failed to notify assignee {assignee_id}: {e}")


@router.get("/", response_model=List[TaskInDB])
async def list_tasks(project_id: str = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {}
    if project_id:
        query["project_id"] = project_id
    tasks = await db["tasks"].find(query).sort("created_at", -1).to_list(length=1000)
    for t in tasks:
        t["_id"] = str(t["_id"])
    return tasks


@router.post("/", response_model=TaskInDB, status_code=201)
async def create_task(task_in: TaskCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()

    # Auto-generate task ID
    task_id = await _generate_task_id(db)

    # Resolve project name and client if not provided
    project_name = task_in.project_name
    client_name = task_in.client_name
    if task_in.project_id and (not project_name or not client_name):
        try:
            project = await db["projects"].find_one({"_id": ObjectId(task_in.project_id)})
            if project:
                project_name = project_name or project.get("name", "Unknown Project")
                client_name = client_name or project.get("client_name", "Unknown")
        except Exception:
            pass

    doc = task_in.model_dump()
    doc.update({
        "task_id": task_id,
        "project_name": project_name,
        "client_name": client_name,
        "comments": [],
        "created_at": now,
        "updated_at": now
    })

    # Convert checklist/deliverables to dicts
    if doc.get("checklist"):
        doc["checklist"] = [item if isinstance(item, dict) else item.model_dump() for item in doc["checklist"]]
    if doc.get("deliverables"):
        doc["deliverables"] = [item if isinstance(item, dict) else item.model_dump() for item in doc["deliverables"]]

    result = await db["tasks"].insert_one(doc)
    created = await db["tasks"].find_one({"_id": result.inserted_id})

    # Fire integrations automatically
    fire_event_background(
        event_type="TASK_CREATED",
        resource_type="tasks",
        resource_id=str(result.inserted_id),
        user_email=_admin.email,
        data=doc,
        db=db
    )

    # Auto-recalculate project progress
    asyncio.create_task(_recalculate_project_progress(db, task_in.project_id))

    # Auto-notify assignees
    asyncio.create_task(_auto_notify_assignees(db, doc, _admin.email, _admin.full_name))

    return created


@router.put("/{id}", response_model=TaskInDB)
async def update_task(id: str, task_in: TaskUpdate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    update_data = task_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    update_data["updated_at"] = get_now()

    # Get old task for comparison
    old_task = await db["tasks"].find_one({"_id": _parse_id(id)})
    if not old_task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db["tasks"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )

    # Fire integrations automatically
    fire_event_background(
        event_type="TASK_UPDATED",
        resource_type="tasks",
        resource_id=id,
        user_email=_admin.email,
        data=update_data,
        db=db
    )

    # Auto-recalculate project progress if status changed
    project_id = result.get("project_id") or old_task.get("project_id")
    if project_id:
        asyncio.create_task(_recalculate_project_progress(db, project_id))

    return result


@router.delete("/{id}")
async def delete_task(id: str, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    task = await db["tasks"].find_one({"_id": _parse_id(id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    project_id = task.get("project_id")
    await db["tasks"].delete_one({"_id": _parse_id(id)})

    fire_event_background(
        event_type="TASK_DELETED",
        resource_type="tasks",
        resource_id=id,
        user_email=_admin.email,
        data={"deleted_id": id},
        db=db
    )

    # Recalculate project progress after deletion
    if project_id:
        asyncio.create_task(_recalculate_project_progress(db, project_id))

    return {"status": "success", "message": "Task deleted"}


@router.post("/{id}/notify")
async def notify_task_assignee(
    id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin),
):
    """Send an ultra-premium task assignment email to the assignee(s)."""
    task = await db["tasks"].find_one({"_id": _parse_id(id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Collect all assignees
    assignee_ids = []
    if task.get("assigned_to"):
        assignee_ids.append(task["assigned_to"])
    if task.get("assigned_to_multiple"):
        assignee_ids.extend(task["assigned_to_multiple"])

    if not assignee_ids:
        raise HTTPException(status_code=400, detail="Task has no assignee")

    # Deduplicate
    assignee_ids = list(set(assignee_ids))

    # Look up project name
    project_name = task.get("project_name", "Unknown Project")
    if task.get("project_id") and project_name == "Unknown Project":
        try:
            project = await db["projects"].find_one({"_id": ObjectId(task["project_id"])})
            if project:
                project_name = project.get("name", "Unknown Project")
        except Exception:
            pass

    # Format due date
    due_date = "No due date"
    if task.get("due_date"):
        try:
            due_date = task["due_date"].strftime("%B %d, %Y")
        except Exception:
            due_date = str(task["due_date"])

    sent_to = []
    for assignee_id in assignee_ids:
        try:
            assignee = await db["admins"].find_one({"_id": ObjectId(assignee_id)})
            if not assignee:
                continue

            await send_task_assignment_email(
                recipient=assignee["email"],
                assignee_name=assignee.get("full_name", "Team Member"),
                task_title=task.get("title", "Untitled Task"),
                task_description=task.get("description", "No description provided."),
                project_name=project_name,
                priority=task.get("priority", "Medium"),
                due_date=due_date,
                assigned_by=current_admin.full_name,
            )
            
            # Send Fast2SMS SMS / WhatsApp if phone is present
            if assignee.get("phone"):
                asyncio.create_task(send_task_sms_and_whatsapp(
                    phone=assignee["phone"],
                    task_title=task.get("title", "Untitled Task"),
                    project_name=project_name,
                    assigned_by=current_admin.full_name
                ))
            
            sent_to.append(assignee["email"])
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))

    return {
        "status": "success",
        "message": f"Task notification sent to {', '.join(sent_to)}"
    }


# ══════════════════════════════════════════════════════════════════════════════
#  EMPLOYEE LOOKUP FOR TASK ASSIGNMENT
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/employees/search")
async def search_employees(
    q: str = "",
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Search employees for task assignment. Returns id, name, email, position, employee_id."""
    import re
    if not q:
        # Return all active employees
        employees = await db["admins"].find(
            {"status": "Active"},
            {"full_name": 1, "email": 1, "position": 1, "employee_id": 1, "profile_photo": 1}
        ).to_list(100)
    else:
        regex = {"$regex": re.escape(q), "$options": "i"}
        employees = await db["admins"].find(
            {"status": "Active", "$or": [
                {"full_name": regex},
                {"email": regex},
                {"employee_id": regex},
                {"position": regex},
            ]},
            {"full_name": 1, "email": 1, "position": 1, "employee_id": 1, "profile_photo": 1}
        ).to_list(20)

    return [{
        "_id": str(e["_id"]),
        "full_name": e.get("full_name", ""),
        "email": e.get("email", ""),
        "position": e.get("position", ""),
        "employee_id": e.get("employee_id", ""),
        "profile_photo": e.get("profile_photo"),
    } for e in employees]
