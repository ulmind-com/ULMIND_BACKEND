from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from app.core.datetime_utils import get_now
from bson import ObjectId
import uuid
import logging
import re

from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectSummaryResponse,
    DeploymentCreate, DeploymentUpdate, DeploymentInDB,
    EnvVarCreate, EnvVarUpdate, EnvVarInDB,
)
from app.services.event_trigger_service import fire_event_background

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "projects"


# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")


async def _generate_project_id(db) -> str:
    """Generate sequential project ID: PROJ-UL-001, PROJ-UL-002, etc."""
    counter = await db["counters"].find_one_and_update(
        {"_id": "project_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    seq = counter["seq"]
    return f"PROJ-UL-{seq:03d}"


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

    await db[COLLECTION].update_one(
        {"_id": _parse_id(project_id) if not isinstance(project_id, ObjectId) else project_id},
        {"$set": {
            "progress": progress,
            "completion_percent": completion,
            "updated_at": get_now()
        }}
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT CRUD  (all admin-protected)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[ProjectSummaryResponse])
async def list_projects(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """List all projects (summary view — no env_vars / deployments)."""
    projects = await db[COLLECTION].find(
        {},
        # Exclude heavy sub-documents from list view for performance
        {"env_vars": 0, "deployments": 0},
    ).to_list(length=500)
    return projects


@router.get("/search")
async def search_projects(
    q: str = Query("", description="Search query (project name, ID, or client)"),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Auto-suggest search for projects by name, project_id, or client_name."""
    if not q or len(q) < 1:
        return []

    regex = {"$regex": re.escape(q), "$options": "i"}
    query = {"$or": [
        {"name": regex},
        {"project_id": regex},
        {"client_name": regex},
        {"client_company": regex},
    ]}

    projects = await db[COLLECTION].find(
        query,
        {"name": 1, "project_id": 1, "client_name": 1, "status": 1, "team_members": 1,
         "project_manager": 1, "start_date": 1, "end_date": 1, "budget": 1}
    ).limit(10).to_list(10)

    results = []
    for p in projects:
        results.append({
            "_id": str(p["_id"]),
            "name": p.get("name", ""),
            "project_id": p.get("project_id", ""),
            "client_name": p.get("client_name", "Unknown"),
            "status": p.get("status", "Planning"),
            "team_members": p.get("team_members", []),
            "project_manager": p.get("project_manager"),
            "start_date": p.get("start_date"),
            "end_date": p.get("end_date"),
            "budget": p.get("budget", 0),
        })

    return results


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_in: ProjectCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Create a new project with auto-generated PROJ-UL-XXX ID."""
    now = get_now()

    # Auto-generate project ID
    project_id = await _generate_project_id(db)

    # Assign UUIDs to each embedded sub-document
    deployments = [
        {**dep.model_dump(), "id": str(uuid.uuid4())}
        for dep in project_in.deployments
    ]
    env_vars = [
        {**ev.model_dump(), "id": str(uuid.uuid4())}
        for ev in project_in.env_vars
    ]

    # Convert milestones to dicts with IDs
    milestones = []
    for ms in project_in.milestones:
        ms_dict = ms.model_dump() if hasattr(ms, 'model_dump') else ms
        if not ms_dict.get("id"):
            ms_dict["id"] = str(uuid.uuid4())
        milestones.append(ms_dict)

    doc = {
        **project_in.model_dump(exclude={"deployments", "env_vars", "milestones"}),
        "project_id": project_id,
        "milestones": milestones,
        "deployments": deployments,
        "env_vars": env_vars,
        "created_at": now,
        "updated_at": now,
    }

    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})

    # Trigger AI event
    fire_event_background(
        event_type="project_created",
        resource_type="projects",
        resource_id=str(result.inserted_id),
        user_email=_admin.email,
        data={**project_in.model_dump(), "project_id": project_id},
        db=db
    )

    return created


@router.get("/{id}", response_model=ProjectResponse)
async def get_project(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Get full project details including all env vars and deployments."""
    project = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{id}", response_model=ProjectResponse)
async def update_project(
    id: str,
    project_in: ProjectUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update project details (does not touch env_vars or deployments)."""
    update_data = project_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    update_data["updated_at"] = get_now()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Fire event
    fire_event_background(
        event_type="project_updated",
        resource_type="projects",
        resource_id=id,
        user_email=_admin.email,
        data=update_data,
        db=db
    )
    
    return result


@router.delete("/{id}")
async def delete_project(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Permanently delete a project and all its data."""
    result = await db[COLLECTION].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "success", "message": "Project deleted successfully"}


# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT TASK STATS  — Dashboard for tasks per project
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{id}/task-stats")
async def get_project_task_stats(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Get task statistics for a specific project."""
    project = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = await db["tasks"].find({"project_id": id}).to_list(1000)
    now = get_now()

    total = len(tasks)
    pending = sum(1 for t in tasks if t.get("status") == "Pending")
    in_progress = sum(1 for t in tasks if t.get("status") == "In Progress")
    review = sum(1 for t in tasks if t.get("status") == "Review")
    completed = sum(1 for t in tasks if t.get("status") == "Completed")
    blocked = sum(1 for t in tasks if t.get("status") == "Blocked")
    overdue = sum(1 for t in tasks if t.get("due_date") and t["due_date"] < now and t.get("status") not in ["Completed", "Archived"])
    total_estimated = sum(t.get("estimated_hours", 0) for t in tasks)
    total_actual = sum(t.get("actual_hours", 0) for t in tasks)

    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "review": review,
        "completed": completed,
        "blocked": blocked,
        "overdue": overdue,
        "total_estimated_hours": total_estimated,
        "total_actual_hours": total_actual,
        "tasks": tasks,  # Full task list for display
    }


# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT FINANCE LINKAGE
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{id}/finance")
async def get_project_finance(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Get finance data linked to a specific project."""
    project = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    invoices = await db["invoices"].find({"project_id": id}).to_list(100)
    payments = await db["payments"].find({
        "invoice_id": {"$in": [str(inv["_id"]) for inv in invoices]}
    }).to_list(100) if invoices else []
    expenses = await db["pm_expenses"].find({"project_id": id}).to_list(100)

    total_invoiced = sum(inv.get("total", 0) for inv in invoices)
    total_paid = sum(pay.get("amount", 0) for pay in payments)
    total_expenses = sum(exp.get("amount", 0) for exp in expenses)
    outstanding = total_invoiced - total_paid
    budget = project.get("budget", 0)
    budget_utilization = round((total_expenses / budget * 100) if budget > 0 else 0, 1)

    return {
        "budget": budget,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_expenses": total_expenses,
        "outstanding": outstanding,
        "profit": total_paid - total_expenses,
        "budget_utilization": budget_utilization,
        "invoices": invoices,
        "payments": payments,
        "expenses": expenses,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
#  DEPLOYMENTS SUB-RESOURCE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{id}/deployments", response_model=ProjectResponse)
async def add_deployment(
    id: str,
    dep_in: DeploymentCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Add a new deployment entry to the project."""
    obj_id = _parse_id(id)
    new_dep = {**dep_in.model_dump(), "id": str(uuid.uuid4())}

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {
            "$push": {"deployments": new_dep},
            "$set": {"updated_at": get_now()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.put("/{id}/deployments/{dep_id}", response_model=ProjectResponse)
async def update_deployment(
    id: str,
    dep_id: str,
    dep_in: DeploymentUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update a specific deployment entry by its ID."""
    obj_id = _parse_id(id)
    update_data = dep_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    set_fields = {f"deployments.$.{k}": v for k, v in update_data.items()}
    set_fields["updated_at"] = get_now()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id, "deployments.id": dep_id},
        {"$set": set_fields},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project or deployment not found")
    return result


@router.delete("/{id}/deployments/{dep_id}", response_model=ProjectResponse)
async def delete_deployment(
    id: str,
    dep_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Remove a deployment entry from the project."""
    obj_id = _parse_id(id)

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {
            "$pull": {"deployments": {"id": dep_id}},
            "$set": {"updated_at": get_now()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result
