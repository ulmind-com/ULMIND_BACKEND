from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin, require_mutation_rights, get_current_admin_or_leader
from app.core.datetime_utils import get_now
from app.services.event_trigger_service import fire_event_background
from app.schemas.pm_enterprise import (
    PMTaskCreate, PMTaskInDB,
    PMMilestoneCreate, PMMilestoneInDB,
    PMTimeLogCreate, PMTimeLogInDB,
    PMFileCreate, PMFileInDB,
    PMFeedbackCreate, PMFeedbackInDB,
    PMExpenseCreate, PMExpenseInDB,
)

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# ── DASHBOARD STATS ──
@router.get("/dashboard")
async def get_pm_dashboard(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    total = await db["projects"].count_documents({})
    active = await db["projects"].count_documents({"status": "Active"})
    completed = await db["projects"].count_documents({"status": "Completed"})
    delayed = await db["projects"].count_documents({"status": "On Hold"})

    total_tasks = await db["pm_tasks"].count_documents({})
    overdue_tasks = await db["pm_tasks"].count_documents({"due_date": {"$lt": get_now()}, "status": {"$nin": ["Completed", "Archived"]}})

    hours_agg = await db["pm_time_logs"].aggregate([{"$group": {"_id": None, "total": {"$sum": "$hours"}}}]).to_list(None)
    total_hours = hours_agg[0]["total"] if hours_agg else 0

    budget_agg = await db["projects"].aggregate([{"$group": {"_id": None, "total_budget": {"$sum": "$cost"}}}]).to_list(None)
    total_budget = budget_agg[0]["total_budget"] if budget_agg else 0

    expense_agg = await db["pm_expenses"].aggregate([{"$group": {"_id": None, "total_spent": {"$sum": "$amount"}}}]).to_list(None)
    total_spent = expense_agg[0]["total_spent"] if expense_agg else 0

    upcoming_milestones = await db["pm_milestones"].find({"status": {"$ne": "Completed"}}).sort("due_date", 1).to_list(5)
    formatted_milestones = []
    for m in upcoming_milestones:
        m["id"] = str(m["_id"])
        m.pop("_id", None)
        formatted_milestones.append(m)

    return {
        "total_projects": total,
        "active_projects": active,
        "completed_projects": completed,
        "delayed_projects": delayed,
        "total_tasks": total_tasks,
        "overdue_tasks": overdue_tasks,
        "total_hours": total_hours,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "upcoming_milestones": formatted_milestones,
    }

# ── TASKS ──
@router.get("/tasks", response_model=List[PMTaskInDB])
async def list_tasks(project_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"project_id": project_id} if project_id else {}
    tasks = await db["pm_tasks"].find(query).sort("order", 1).to_list(1000)
    return tasks

@router.post("/tasks", response_model=PMTaskInDB, status_code=201)
async def create_task(task_in: PMTaskCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = task_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["pm_tasks"].insert_one(doc)
    created = await db["pm_tasks"].find_one({"_id": result.inserted_id})
    fire_event_background("pm_task_created", "pm_tasks", str(result.inserted_id), admin.email, doc, db)
    return created

@router.put("/tasks/{id}", response_model=PMTaskInDB)
async def update_task(id: str, task_in: dict, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    task_in["updated_at"] = get_now()
    result = await db["pm_tasks"].find_one_and_update({"_id": _parse_id(id)}, {"$set": task_in}, return_document=True)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    fire_event_background("pm_task_updated", "pm_tasks", id, admin.email, task_in, db)
    return result

@router.delete("/tasks/{id}")
async def delete_task(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["pm_tasks"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    fire_event_background("pm_task_deleted", "pm_tasks", id, admin.email, {}, db)
    return {"status": "success", "message": "Task deleted"}

# ── MILESTONES ──
@router.get("/milestones", response_model=List[PMMilestoneInDB])
async def list_milestones(project_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"project_id": project_id} if project_id else {}
    return await db["pm_milestones"].find(query).sort("due_date", 1).to_list(1000)

@router.post("/milestones", response_model=PMMilestoneInDB, status_code=201)
async def create_milestone(ms_in: PMMilestoneCreate, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    now = get_now()
    doc = ms_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["pm_milestones"].insert_one(doc)
    created = await db["pm_milestones"].find_one({"_id": result.inserted_id})
    fire_event_background("pm_milestone_created", "pm_milestones", str(result.inserted_id), admin.email, doc, db)
    return created

@router.delete("/milestones/{id}")
async def delete_milestone(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["pm_milestones"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Milestone not found")
    fire_event_background("pm_milestone_deleted", "pm_milestones", id, admin.email, {}, db)
    return {"status": "success", "message": "Milestone deleted"}

# ── TIME LOGS ──
@router.get("/time-logs", response_model=List[PMTimeLogInDB])
async def list_time_logs(project_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"project_id": project_id} if project_id else {}
    return await db["pm_time_logs"].find(query).sort("log_date", -1).to_list(1000)

@router.post("/time-logs", response_model=PMTimeLogInDB, status_code=201)
async def create_time_log(log_in: PMTimeLogCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    doc = log_in.model_dump()
    doc["created_at"] = get_now()
    result = await db["pm_time_logs"].insert_one(doc)
    created = await db["pm_time_logs"].find_one({"_id": result.inserted_id})
    fire_event_background("pm_time_log_created", "pm_time_logs", str(result.inserted_id), admin.email, doc, db)
    return created

# ── FILES ──
@router.get("/files", response_model=List[PMFileInDB])
async def list_files(project_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"project_id": project_id} if project_id else {}
    return await db["pm_files"].find(query).sort("created_at", -1).to_list(1000)

@router.post("/files", response_model=PMFileInDB, status_code=201)
async def create_file(file_in: PMFileCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = file_in.model_dump()
    doc.update({"uploaded_by": admin.email, "created_at": now, "updated_at": now})
    result = await db["pm_files"].insert_one(doc)
    created = await db["pm_files"].find_one({"_id": result.inserted_id})
    fire_event_background("pm_file_uploaded", "pm_files", str(result.inserted_id), admin.email, doc, db)
    return created

@router.delete("/files/{id}")
async def delete_file(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["pm_files"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="File not found")
    fire_event_background("pm_file_deleted", "pm_files", id, admin.email, {}, db)
    return {"status": "success", "message": "File deleted"}

# ── FEEDBACK ──
@router.get("/feedback", response_model=List[PMFeedbackInDB])
async def list_feedback(project_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"project_id": project_id} if project_id else {}
    return await db["pm_feedback"].find(query).sort("created_at", -1).to_list(1000)

@router.post("/feedback", response_model=PMFeedbackInDB, status_code=201)
async def create_feedback(fb_in: PMFeedbackCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = fb_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["pm_feedback"].insert_one(doc)
    created = await db["pm_feedback"].find_one({"_id": result.inserted_id})
    fire_event_background("pm_feedback_created", "pm_feedback", str(result.inserted_id), admin.email, doc, db)
    return created

# ── EXPENSES (Budget) ──
@router.get("/expenses", response_model=List[PMExpenseInDB])
async def list_expenses(project_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"project_id": project_id} if project_id else {}
    return await db["pm_expenses"].find(query).sort("date", -1).to_list(1000)

@router.post("/expenses", response_model=PMExpenseInDB, status_code=201)
async def create_expense(exp_in: PMExpenseCreate, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    doc = exp_in.model_dump()
    doc["created_at"] = get_now()
    result = await db["pm_expenses"].insert_one(doc)
    created = await db["pm_expenses"].find_one({"_id": result.inserted_id})
    fire_event_background("pm_expense_logged", "pm_expenses", str(result.inserted_id), admin.email, doc, db)
    return created

@router.delete("/expenses/{id}")
async def delete_expense(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["pm_expenses"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    fire_event_background("pm_expense_deleted", "pm_expenses", id, admin.email, {}, db)
    return {"status": "success", "message": "Expense deleted"}
