"""
Manager Tasks — Enterprise Task Tracking with 8-Stage Workflow
================================================================
Full CRUD for enterprise-grade tasks with status transitions,
dependencies, subtasks, comments, and automatic audit logging.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from bson import ObjectId
import uuid

from app.db.database import get_db
from app.api.deps import get_current_admin_or_leader, get_current_active_admin
from app.core.datetime_utils import get_now
from app.services.event_trigger_service import fire_event_background
from app.schemas.manager_schemas import (
    EnterpriseTaskCreate, EnterpriseTaskUpdate, EnterpriseTaskInDB,
    TaskCommentCreate, SubtaskCreate,
)

router = APIRouter()


def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


VALID_STAGES = [
    "Pending", "Assigned", "Accepted", "In Progress",
    "Review", "Approved", "Completed", "Archived"
]

VALID_PRIORITIES = ["Low", "Medium", "High", "Urgent", "Critical"]

VALID_REVIEW_STATUSES = [
    "Not Submitted", "Pending Review", "Changes Requested", "Approved", "Rejected"
]


# ═══════════════════════════════════════════════════════════════
#  ENTERPRISE TASKS CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("/tasks", response_model=List[EnterpriseTaskInDB])
async def list_tasks(
    stage: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    project_id: Optional[str] = None,
    db=Depends(get_db),
    admin=Depends(get_current_active_admin)
):
    """List enterprise tasks with optional filters."""
    query = {}
    if stage:
        query["stage"] = stage
    if priority:
        query["priority"] = priority
    if assigned_to:
        query["assigned_to"] = assigned_to
    if project_id:
        query["project_id"] = project_id

    tasks = await db["manager_tasks"].find(query).sort("updated_at", -1).to_list(1000)
    return tasks


@router.post("/tasks", response_model=EnterpriseTaskInDB, status_code=201)
async def create_task(
    task_in: EnterpriseTaskCreate,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Create a new enterprise task."""
    if task_in.priority and task_in.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {VALID_PRIORITIES}")

    now = get_now()
    doc = task_in.model_dump()
    doc.update({
        "assigned_by": str(admin.id),
        "assigned_by_name": admin.full_name or admin.email,
        "actual_hours": 0,
        "completion_percent": 0,
        "subtasks": [],
        "comments": [],
        "created_at": now,
        "updated_at": now,
    })

    # Auto-set stage to Assigned if someone is assigned
    if doc.get("assigned_to") and doc["stage"] == "Pending":
        doc["stage"] = "Assigned"

    result = await db["manager_tasks"].insert_one(doc)
    created = await db["manager_tasks"].find_one({"_id": result.inserted_id})

    fire_event_background(
        "manager_task_created", "manager_tasks",
        str(result.inserted_id), admin.email, doc, db
    )

    return created


@router.get("/tasks/{id}")
async def get_task(
    id: str,
    db=Depends(get_db),
    admin=Depends(get_current_active_admin)
):
    """Get a single enterprise task by ID."""
    task = await db["manager_tasks"].find_one({"_id": _parse_id(id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task["_id"] = str(task["_id"])
    return task


@router.put("/tasks/{id}")
async def update_task(
    id: str,
    task_in: EnterpriseTaskUpdate,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Update an enterprise task (stage, priority, assignment, etc.)."""
    update_data = task_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    # Validate stage transition
    if "stage" in update_data and update_data["stage"] not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Must be one of: {VALID_STAGES}")

    if "priority" in update_data and update_data["priority"] not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail=f"Invalid priority. Must be one of: {VALID_PRIORITIES}")

    if "review_status" in update_data and update_data["review_status"] not in VALID_REVIEW_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid review status.")

    update_data["updated_at"] = get_now()

    # Auto-set completion percent based on stage
    stage = update_data.get("stage")
    if stage:
        stage_progress = {
            "Pending": 0, "Assigned": 5, "Accepted": 10,
            "In Progress": 30, "Review": 70, "Approved": 90,
            "Completed": 100, "Archived": 100
        }
        update_data["completion_percent"] = stage_progress.get(stage, 0)

    result = await db["manager_tasks"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    fire_event_background(
        "manager_task_updated", "manager_tasks",
        id, admin.email, update_data, db
    )

    result["_id"] = str(result["_id"])
    return result


@router.put("/tasks/{id}/assign")
async def assign_task(
    id: str,
    assigned_to: str,
    assigned_to_name: Optional[str] = None,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Assign or reassign a task to an employee."""
    now = get_now()
    update = {
        "assigned_to": assigned_to,
        "assigned_to_name": assigned_to_name or "",
        "assigned_by": str(admin.id),
        "assigned_by_name": admin.full_name or admin.email,
        "stage": "Assigned",
        "updated_at": now,
        "completion_percent": 5,
    }

    result = await db["manager_tasks"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    fire_event_background(
        "manager_task_assigned", "manager_tasks",
        id, admin.email, {"assigned_to": assigned_to, "assigned_to_name": assigned_to_name}, db
    )

    result["_id"] = str(result["_id"])
    return result


@router.delete("/tasks/{id}")
async def delete_task(
    id: str,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Delete an enterprise task."""
    result = await db["manager_tasks"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")

    fire_event_background(
        "manager_task_deleted", "manager_tasks",
        id, admin.email, {}, db
    )
    return {"status": "success", "message": "Task deleted"}


# ═══════════════════════════════════════════════════════════════
#  COMMENTS
# ═══════════════════════════════════════════════════════════════

@router.post("/tasks/{id}/comments")
async def add_comment(
    id: str,
    comment: TaskCommentCreate,
    db=Depends(get_db),
    admin=Depends(get_current_active_admin)
):
    """Add a comment to a task."""
    now = get_now()
    comment_doc = {
        "id": str(uuid.uuid4()),
        "author_id": str(admin.id),
        "author_name": admin.full_name or admin.email,
        "author_email": admin.email,
        "content": comment.content,
        "mentions": comment.mentions,
        "attachments": comment.attachments,
        "created_at": now,
    }

    result = await db["manager_tasks"].find_one_and_update(
        {"_id": _parse_id(id)},
        {
            "$push": {"comments": comment_doc},
            "$set": {"updated_at": now}
        },
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    fire_event_background(
        "manager_task_comment_added", "manager_tasks",
        id, admin.email, {"comment": comment.content}, db
    )

    result["_id"] = str(result["_id"])
    return result


# ═══════════════════════════════════════════════════════════════
#  SUBTASKS
# ═══════════════════════════════════════════════════════════════

@router.get("/tasks/{id}/subtasks")
async def get_subtasks(
    id: str,
    db=Depends(get_db),
    admin=Depends(get_current_active_admin)
):
    """Get subtasks of a task."""
    task = await db["manager_tasks"].find_one({"_id": _parse_id(id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.get("subtasks", [])


@router.post("/tasks/{id}/subtasks")
async def add_subtask(
    id: str,
    subtask: SubtaskCreate,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Add a subtask to a task."""
    now = get_now()
    subtask_doc = {
        "id": str(uuid.uuid4()),
        "title": subtask.title,
        "assigned_to": subtask.assigned_to,
        "due_date": subtask.due_date,
        "priority": subtask.priority,
        "status": "Pending",
        "completed_at": None,
        "created_at": now,
    }

    result = await db["manager_tasks"].find_one_and_update(
        {"_id": _parse_id(id)},
        {
            "$push": {"subtasks": subtask_doc},
            "$set": {"updated_at": now}
        },
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")

    fire_event_background(
        "manager_subtask_added", "manager_tasks",
        id, admin.email, {"subtask": subtask.title}, db
    )

    result["_id"] = str(result["_id"])
    return result


@router.put("/tasks/{task_id}/subtasks/{subtask_id}")
async def update_subtask(
    task_id: str,
    subtask_id: str,
    status: str,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Update subtask status."""
    now = get_now()
    task = await db["manager_tasks"].find_one({"_id": _parse_id(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    subtasks = task.get("subtasks", [])
    updated = False
    for st in subtasks:
        if st["id"] == subtask_id:
            st["status"] = status
            if status == "Completed":
                st["completed_at"] = now
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Subtask not found")

    await db["manager_tasks"].update_one(
        {"_id": _parse_id(task_id)},
        {"$set": {"subtasks": subtasks, "updated_at": now}}
    )

    return {"status": "success", "subtask_status": status}
