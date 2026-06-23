from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin, require_mutation_rights, get_current_admin_or_leader
from app.core.datetime_utils import get_now
from app.services.event_trigger_service import fire_event_background
from app.schemas.team_enterprise import (
    TeamAttendanceCreate, TeamAttendanceInDB,
    TeamWorkLogCreate, TeamWorkLogInDB,
    TeamPerformanceCreate, TeamPerformanceInDB,
    TeamLeaveCreate, TeamLeaveInDB,
    TeamPayrollCreate, TeamPayrollInDB,
)

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# ── TEAM DASHBOARD ──
@router.get("/dashboard")
async def get_team_dashboard(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    total_members = await db["admins"].count_documents({})
    active_members = await db["admins"].count_documents({"status": "Active"})
    from app.core.datetime_utils import get_now
    import datetime
    today_start = get_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + datetime.timedelta(days=1)

    present_today = await db["team_attendance"].count_documents({
        "date": {"$gte": today_start, "$lt": today_end},
        "status": "Present"
    })
    on_leave = await db["team_attendance"].count_documents({
        "date": {"$gte": today_start, "$lt": today_end},
        "status": "Leave"
    })

    # Attendance rate
    total_attendance = await db["team_attendance"].count_documents({})
    present_count = await db["team_attendance"].count_documents({"status": "Present"})
    attendance_rate = (present_count / total_attendance * 100) if total_attendance > 0 else 0

    # Avg performance
    perf_agg = await db["team_performance"].aggregate([
        {"$group": {"_id": None, "avg_score": {"$avg": "$overall_score"}}}
    ]).to_list(None)
    avg_performance = perf_agg[0]["avg_score"] if perf_agg else 0

    # Pending leaves
    pending_leaves = await db["team_leaves"].count_documents({"status": "Pending"})

    # Total hours logged
    hours_agg = await db["team_work_logs"].aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$hours"}}}
    ]).to_list(None)
    total_hours = hours_agg[0]["total"] if hours_agg else 0

    # Recent members (new joiners)
    new_joiners = await db["admins"].find({}).sort("created_at", -1).to_list(5)

    return {
        "total_members": total_members,
        "active_members": active_members,
        "present_today": present_today,
        "on_leave": on_leave,
        "attendance_rate": round(attendance_rate, 1),
        "avg_performance": round(avg_performance, 1),
        "pending_leaves": pending_leaves,
        "total_hours_logged": total_hours,
        "new_joiners": new_joiners,
    }

# ── ATTENDANCE ──
@router.get("/attendance", response_model=List[TeamAttendanceInDB])
async def list_attendance(employee_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"employee_id": employee_id} if employee_id else {}
    return await db["team_attendance"].find(query).sort("date", -1).to_list(1000)

@router.post("/attendance", response_model=TeamAttendanceInDB, status_code=201)
async def create_attendance(att_in: TeamAttendanceCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = att_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["team_attendance"].insert_one(doc)
    created = await db["team_attendance"].find_one({"_id": result.inserted_id})
    fire_event_background("team_attendance_logged", "team_attendance", str(result.inserted_id), admin.email, doc, db)
    return created

@router.put("/attendance/{id}")
async def update_attendance(id: str, data: dict, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    data["updated_at"] = get_now()
    result = await db["team_attendance"].find_one_and_update({"_id": _parse_id(id)}, {"$set": data}, return_document=True)
    if not result: raise HTTPException(status_code=404, detail="Attendance record not found")
    fire_event_background("team_attendance_updated", "team_attendance", id, admin.email, data, db)
    return result

@router.delete("/attendance/{id}")
async def delete_attendance(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["team_attendance"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Not found")
    fire_event_background("team_attendance_deleted", "team_attendance", id, admin.email, {}, db)
    return {"status": "success"}

# ── WORK LOGS ──
@router.get("/work-logs", response_model=List[TeamWorkLogInDB])
async def list_work_logs(employee_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"employee_id": employee_id} if employee_id else {}
    return await db["team_work_logs"].find(query).sort("log_date", -1).to_list(1000)

@router.post("/work-logs", response_model=TeamWorkLogInDB, status_code=201)
async def create_work_log(log_in: TeamWorkLogCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    doc = log_in.model_dump()
    doc["created_at"] = get_now()
    result = await db["team_work_logs"].insert_one(doc)
    created = await db["team_work_logs"].find_one({"_id": result.inserted_id})
    fire_event_background("team_work_log_created", "team_work_logs", str(result.inserted_id), admin.email, doc, db)
    return created

@router.delete("/work-logs/{id}")
async def delete_work_log(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["team_work_logs"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Not found")
    fire_event_background("team_work_log_deleted", "team_work_logs", id, admin.email, {}, db)
    return {"status": "success"}

# ── PERFORMANCE ──
@router.get("/performance", response_model=List[TeamPerformanceInDB])
async def list_performance(employee_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"employee_id": employee_id} if employee_id else {}
    return await db["team_performance"].find(query).sort("created_at", -1).to_list(1000)

@router.post("/performance", response_model=TeamPerformanceInDB, status_code=201)
async def create_performance(perf_in: TeamPerformanceCreate, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    now = get_now()
    doc = perf_in.model_dump()
    scores = [doc.get("attendance_score", 0), doc.get("productivity_score", 0), doc.get("quality_score", 0), doc.get("teamwork_score", 0), doc.get("deadlines_met_score", 0)]
    doc["overall_score"] = sum(scores) / len(scores)
    doc.update({"created_at": now, "updated_at": now})
    result = await db["team_performance"].insert_one(doc)
    created = await db["team_performance"].find_one({"_id": result.inserted_id})
    fire_event_background("team_performance_logged", "team_performance", str(result.inserted_id), admin.email, doc, db)
    return created

# ── LEAVES ──
@router.get("/leaves", response_model=List[TeamLeaveInDB])
async def list_leaves(employee_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"employee_id": employee_id} if employee_id else {}
    return await db["team_leaves"].find(query).sort("from_date", -1).to_list(1000)

@router.post("/leaves", response_model=TeamLeaveInDB, status_code=201)
async def create_leave(leave_in: TeamLeaveCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = leave_in.model_dump()
    doc.update({"approved_by": None, "created_at": now, "updated_at": now})
    result = await db["team_leaves"].insert_one(doc)
    created = await db["team_leaves"].find_one({"_id": result.inserted_id})
    fire_event_background("team_leave_requested", "team_leaves", str(result.inserted_id), admin.email, doc, db)
    return created

@router.put("/leaves/{id}")
async def update_leave(id: str, data: dict, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    data["updated_at"] = get_now()
    result = await db["team_leaves"].find_one_and_update({"_id": _parse_id(id)}, {"$set": data}, return_document=True)
    if not result: raise HTTPException(status_code=404, detail="Leave not found")
    fire_event_background("team_leave_updated", "team_leaves", id, admin.email, data, db)
    return result

@router.delete("/leaves/{id}")
async def delete_leave(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["team_leaves"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Not found")
    fire_event_background("team_leave_deleted", "team_leaves", id, admin.email, {}, db)
    return {"status": "success"}

# ── PAYROLL ──
@router.get("/payroll", response_model=List[TeamPayrollInDB])
async def list_payroll(employee_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"employee_id": employee_id} if employee_id else {}
    return await db["team_payroll"].find(query).sort("month", -1).to_list(1000)

@router.post("/payroll", response_model=TeamPayrollInDB, status_code=201)
async def create_payroll(pay_in: TeamPayrollCreate, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    now = get_now()
    doc = pay_in.model_dump()
    doc["net_pay"] = doc.get("basic_salary", 0) + doc.get("bonus", 0) - doc.get("deductions", 0)
    doc.update({"created_at": now, "updated_at": now})
    result = await db["team_payroll"].insert_one(doc)
    created = await db["team_payroll"].find_one({"_id": result.inserted_id})
    fire_event_background("team_payroll_processed", "team_payroll", str(result.inserted_id), admin.email, doc, db)
    return created

@router.delete("/payroll/{id}")
async def delete_payroll(id: str, db=Depends(get_db), admin=Depends(get_current_admin_or_leader)):
    result = await db["team_payroll"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0: raise HTTPException(status_code=404, detail="Not found")
    fire_event_background("team_payroll_deleted", "team_payroll", id, admin.email, {}, db)
    return {"status": "success"}
