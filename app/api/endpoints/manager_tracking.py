"""
Manager Tracking — Workforce Dashboard, Live Monitoring, Timeline,
Time Tracking, Productivity Intelligence, Analytics, Smart Alerts
==================================================================
Enterprise-grade endpoints for the Manager Tracking & Workforce
Intelligence module. Integrates with existing Team HR, Projects,
CRM, Notifications, Activity Feed, and Audit systems.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
from bson import ObjectId
from datetime import timedelta
import uuid

from app.db.database import get_db
from app.api.deps import get_current_admin_or_leader, get_current_active_admin
from app.core.datetime_utils import get_now
from app.services.event_trigger_service import fire_event_background
from app.schemas.manager_schemas import (
    WorkforceDashboard, EmployeeLiveStatus, ProductivityScore,
    SmartAlertInDB, ActivityTimelineEntry, TimeEntryAction, TimeEntryInDB,
)

router = APIRouter()


def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def _parse_user_agent(ua: str) -> dict:
    """Simple UA parser — no external deps needed."""
    browser = "Unknown"
    os_name = "Unknown"
    device = "Desktop"

    ua_lower = ua.lower() if ua else ""
    # Browser
    if "edg" in ua_lower:
        browser = "Edge"
    elif "chrome" in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower:
        browser = "Safari"
    elif "opera" in ua_lower or "opr" in ua_lower:
        browser = "Opera"
    # OS
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "macintosh" in ua_lower or "mac os" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
        device = "Mobile"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
        device = "Mobile"

    return {"browser": browser, "os": os_name, "device": device}


# ═══════════════════════════════════════════════════════════════
#  LIVE WORKFORCE DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.get("/workforce-dashboard")
async def get_workforce_dashboard(
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Real-time workforce KPIs. Auto-refreshed by frontend every 10s."""
    now = get_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    heartbeat_threshold = now - timedelta(minutes=2)
    idle_threshold = now - timedelta(minutes=5)

    total_employees = await db["admins"].count_documents({})

    # Online = session with recent heartbeat
    online_sessions = await db["admin_activity"].count_documents({
        "is_online": True,
        "last_heartbeat": {"$gte": heartbeat_threshold}
    })

    # Idle = online but no heartbeat in last 5 min
    idle_count = await db["admin_activity"].count_documents({
        "is_online": True,
        "last_heartbeat": {"$lt": idle_threshold, "$gte": heartbeat_threshold}
    })

    # On leave today
    on_leave = await db["team_attendance"].count_documents({
        "date": {"$gte": today_start, "$lt": today_end},
        "status": "Leave"
    })

    # On break (employees with active break timer)
    on_break = await db["manager_time_entries"].count_documents({
        "is_active": True,
        "paused_at": {"$ne": None},
        "resumed_at": None
    })

    # Overtime (logged > 9 hours today)
    overtime_agg = await db["team_work_logs"].aggregate([
        {"$match": {"log_date": {"$gte": today_start, "$lt": today_end}}},
        {"$group": {"_id": "$employee_id", "total": {"$sum": "$hours"}}},
        {"$match": {"total": {"$gt": 9}}}
    ]).to_list(None)
    overtime = len(overtime_agg)

    offline = max(0, total_employees - online_sessions - on_leave)
    active = max(0, online_sessions - idle_count - on_break)

    # Task stats
    running_tasks = await db["manager_tasks"].count_documents({
        "stage": {"$in": ["Assigned", "Accepted", "In Progress"]}
    })
    delayed_tasks = await db["manager_tasks"].count_documents({
        "due_date": {"$lt": now},
        "stage": {"$nin": ["Completed", "Archived"]}
    })
    blocked_tasks = await db["manager_tasks"].count_documents({
        "stage": "Review",
        "review_status": "Changes Requested"
    })
    completed_today = await db["manager_tasks"].count_documents({
        "stage": "Completed",
        "updated_at": {"$gte": today_start, "$lt": today_end}
    })
    upcoming = await db["manager_tasks"].count_documents({
        "due_date": {"$gte": now, "$lte": now + timedelta(days=3)},
        "stage": {"$nin": ["Completed", "Archived"]}
    })

    # Hours today
    hours_agg = await db["team_work_logs"].aggregate([
        {"$match": {"log_date": {"$gte": today_start, "$lt": today_end}}},
        {"$group": {"_id": None, "total": {"$sum": "$hours"}}}
    ]).to_list(None)
    total_hours = hours_agg[0]["total"] if hours_agg else 0

    # Avg completion time (for tasks completed in last 30 days)
    thirty_days = now - timedelta(days=30)
    completion_agg = await db["manager_tasks"].aggregate([
        {"$match": {"stage": "Completed", "updated_at": {"$gte": thirty_days}}},
        {"$project": {
            "duration": {"$divide": [
                {"$subtract": ["$updated_at", "$created_at"]},
                3600000
            ]}
        }},
        {"$group": {"_id": None, "avg": {"$avg": "$duration"}}}
    ]).to_list(None)
    avg_completion = completion_agg[0]["avg"] if completion_agg else 0

    # Team productivity (% of tasks completed on time in last 30 days)
    total_completed = await db["manager_tasks"].count_documents({
        "stage": "Completed", "updated_at": {"$gte": thirty_days}
    })
    on_time = await db["manager_tasks"].count_documents({
        "stage": "Completed",
        "updated_at": {"$gte": thirty_days},
        "$expr": {"$lte": ["$updated_at", "$due_date"]}
    })
    team_productivity = (on_time / total_completed * 100) if total_completed > 0 else 0

    return {
        "online_employees": online_sessions,
        "offline_employees": offline,
        "active_employees": active,
        "idle_employees": idle_count,
        "on_break": on_break,
        "overtime": overtime,
        "on_leave": on_leave,
        "running_tasks": running_tasks,
        "delayed_tasks": delayed_tasks,
        "blocked_tasks": blocked_tasks,
        "completed_today": completed_today,
        "upcoming_deadlines": upcoming,
        "team_productivity": round(team_productivity, 1),
        "avg_response_time_hours": 0,
        "avg_completion_time_hours": round(avg_completion, 1),
        "total_working_hours_today": round(total_hours, 1),
    }


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE LIVE MONITORING
# ═══════════════════════════════════════════════════════════════

@router.get("/employees/live")
async def get_employees_live(
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Live status for every employee."""
    now = get_now()
    heartbeat_threshold = now - timedelta(minutes=2)
    idle_threshold = now - timedelta(minutes=5)

    employees = await db["admins"].find({}).to_list(1000)

    # Get latest session per employee
    sessions = await db["admin_activity"].aggregate([
        {"$sort": {"login_time": -1}},
        {"$group": {
            "_id": "$admin_id",
            "session": {"$first": "$$ROOT"}
        }}
    ]).to_list(1000)
    session_map = {s["_id"]: s["session"] for s in sessions}

    # Get active time entries
    active_timers = await db["manager_time_entries"].find({"is_active": True}).to_list(1000)
    timer_map = {t["employee_id"]: t for t in active_timers}

    # Get assigned tasks in progress
    active_tasks = await db["manager_tasks"].find({
        "stage": {"$in": ["Assigned", "Accepted", "In Progress"]},
    }).to_list(1000)
    task_map = {}
    for t in active_tasks:
        if t.get("assigned_to"):
            task_map[t["assigned_to"]] = t

    result = []
    for emp in employees:
        eid = str(emp["_id"])
        session = session_map.get(eid)
        timer = timer_map.get(eid)
        task = task_map.get(eid)

        # Determine status
        status = "Offline"
        login_time = None
        session_duration = 0
        last_activity = None
        ip_address = None
        browser = "Unknown"
        device = "Desktop"
        os_name = "Unknown"

        if session:
            last_hb = session.get("last_heartbeat")
            login_time = session.get("login_time")
            ip_address = session.get("ip_address")
            ua_info = _parse_user_agent(session.get("user_agent", ""))
            browser = ua_info["browser"]
            device = ua_info["device"]
            os_name = ua_info["os"]
            last_activity = last_hb

            if last_hb and login_time:
                session_duration = (now.replace(tzinfo=None) - login_time).total_seconds() / 60.0

            if session.get("is_online") and last_hb:
                if last_hb >= heartbeat_threshold:
                    if timer and timer.get("paused_at") and not timer.get("resumed_at"):
                        status = "On Break"
                    elif last_hb < idle_threshold:
                        status = "Idle"
                    else:
                        status = "Online"
                else:
                    status = "Offline"

        photo = emp.get("profile_photo")
        photo_url = photo.get("url") if photo else None

        result.append({
            "employee_id": eid,
            "employee_name": emp.get("full_name", ""),
            "email": emp.get("email", ""),
            "designation": emp.get("position", "Staff Member"),
            "team": emp.get("department", "General"),
            "profile_photo": photo_url,
            "status": status,
            "current_project": task.get("project_name") if task else None,
            "current_task": task.get("title") if task else None,
            "current_page": None,
            "browser": browser,
            "device": device,
            "os": os_name,
            "login_time": login_time,
            "session_duration_minutes": round(session_duration, 1),
            "last_activity": last_activity,
            "ip_address": ip_address,
            "active_minutes": round(session_duration * 0.8, 1),
            "idle_minutes": round(session_duration * 0.2, 1),
        })

    return result


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE TIMELINE
# ═══════════════════════════════════════════════════════════════

@router.get("/employees/{employee_id}/timeline")
async def get_employee_timeline(
    employee_id: str,
    limit: int = 50,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Chronological activity history for a specific employee."""
    timeline = []

    # Sessions (logins/logouts)
    sessions = await db["admin_activity"].find(
        {"admin_id": employee_id}
    ).sort("login_time", -1).to_list(limit)

    for s in sessions:
        timeline.append({
            "_id": str(s["_id"]),
            "employee_id": employee_id,
            "action": "login",
            "description": f"Logged in from {s.get('ip_address', 'unknown IP')}",
            "resource_type": "session",
            "resource_id": str(s["_id"]),
            "metadata": {"ip": s.get("ip_address"), "user_agent": s.get("user_agent")},
            "timestamp": s["login_time"]
        })
        if s.get("logout_time"):
            duration = s.get("duration_minutes", 0)
            timeline.append({
                "_id": f"{str(s['_id'])}_logout",
                "employee_id": employee_id,
                "action": "logout",
                "description": f"Session ended after {round(duration)} minutes",
                "resource_type": "session",
                "resource_id": str(s["_id"]),
                "metadata": {"duration_minutes": duration},
                "timestamp": s["logout_time"]
            })

    # Task activities from activity_logs
    task_logs = await db["activity_logs"].find(
        {"performed_by": {"$regex": employee_id, "$options": "i"}}
    ).sort("timestamp", -1).to_list(limit)

    for log in task_logs:
        action = log.get("event_type", "unknown")
        timeline.append({
            "_id": str(log["_id"]),
            "employee_id": employee_id,
            "action": action,
            "description": log.get("action_description", action),
            "resource_type": log.get("resource_type"),
            "resource_id": log.get("resource_id"),
            "metadata": {},
            "timestamp": log.get("timestamp")
        })

    # Sort by timestamp descending
    timeline.sort(key=lambda x: x.get("timestamp") or get_now(), reverse=True)
    return timeline[:limit]


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE PERFORMANCE PROFILE
# ═══════════════════════════════════════════════════════════════

@router.get("/employees/{employee_id}/profile")
async def get_employee_profile(
    employee_id: str,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Complete employee performance profile."""
    emp = await db["admins"].find_one({"_id": _parse_id(employee_id)})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    now = get_now()
    thirty_days = now - timedelta(days=30)

    # Tasks
    total_tasks = await db["manager_tasks"].count_documents({"assigned_to": employee_id})
    completed_tasks = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id, "stage": "Completed"
    })
    in_progress = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id, "stage": {"$in": ["Assigned", "Accepted", "In Progress"]}
    })
    overdue = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id,
        "due_date": {"$lt": now},
        "stage": {"$nin": ["Completed", "Archived"]}
    })

    # Attendance
    attendance_records = await db["team_attendance"].count_documents({"employee_id": employee_id})
    present_count = await db["team_attendance"].count_documents({
        "employee_id": employee_id, "status": "Present"
    })
    attendance_rate = (present_count / attendance_records * 100) if attendance_records > 0 else 0

    # Work hours
    hours_agg = await db["team_work_logs"].aggregate([
        {"$match": {"employee_id": employee_id, "log_date": {"$gte": thirty_days}}},
        {"$group": {"_id": None, "total": {"$sum": "$hours"}}}
    ]).to_list(None)
    total_hours = hours_agg[0]["total"] if hours_agg else 0

    # Performance scores
    perf_agg = await db["team_performance"].aggregate([
        {"$match": {"employee_id": employee_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": 1}
    ]).to_list(None)
    latest_perf = perf_agg[0] if perf_agg else {}

    # Leaves
    total_leaves = await db["team_leaves"].count_documents({"employee_id": employee_id})
    pending_leaves = await db["team_leaves"].count_documents({
        "employee_id": employee_id, "status": "Pending"
    })

    photo = emp.get("profile_photo")
    return {
        "employee_id": employee_id,
        "full_name": emp.get("full_name", ""),
        "email": emp.get("email", ""),
        "position": emp.get("position", "Staff Member"),
        "role": emp.get("role", "editor"),
        "status": emp.get("status", "Active"),
        "profile_photo": photo.get("url") if photo else None,
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "in_progress": in_progress,
            "overdue": overdue,
            "completion_rate": round((completed_tasks / total_tasks * 100) if total_tasks > 0 else 0, 1)
        },
        "attendance": {
            "total_records": attendance_records,
            "present": present_count,
            "rate": round(attendance_rate, 1)
        },
        "work_hours": {
            "last_30_days": round(total_hours, 1),
            "avg_daily": round(total_hours / 30, 1)
        },
        "performance": {
            "overall_score": latest_perf.get("overall_score", 0),
            "productivity_score": latest_perf.get("productivity_score", 0),
            "quality_score": latest_perf.get("quality_score", 0),
            "teamwork_score": latest_perf.get("teamwork_score", 0),
            "deadlines_met_score": latest_perf.get("deadlines_met_score", 0),
        },
        "leaves": {
            "total": total_leaves,
            "pending": pending_leaves
        }
    }


# ═══════════════════════════════════════════════════════════════
#  PRODUCTIVITY INTELLIGENCE
# ═══════════════════════════════════════════════════════════════

@router.get("/productivity/{employee_id}")
async def get_productivity(
    employee_id: str,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Productivity intelligence scores for a specific employee."""
    now = get_now()
    thirty_days = now - timedelta(days=30)

    total_tasks = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id, "created_at": {"$gte": thirty_days}
    })
    completed = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id, "stage": "Completed", "updated_at": {"$gte": thirty_days}
    })
    on_time = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id,
        "stage": "Completed",
        "updated_at": {"$gte": thirty_days},
        "$expr": {"$lte": ["$updated_at", "$due_date"]}
    })
    delayed = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id,
        "due_date": {"$lt": now},
        "stage": {"$nin": ["Completed", "Archived"]},
        "created_at": {"$gte": thirty_days}
    })
    in_progress = await db["manager_tasks"].count_documents({
        "assigned_to": employee_id,
        "stage": {"$in": ["Assigned", "Accepted", "In Progress", "Review"]},
    })

    completion_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0
    deadline_accuracy = (on_time / completed * 100) if completed > 0 else 0
    delay_frequency = (delayed / total_tasks * 100) if total_tasks > 0 else 0
    workload = min(100, in_progress * 20)  # 5 tasks = 100% workload
    capacity = max(0, 100 - workload)

    productivity = min(100, completion_rate * 0.4 + deadline_accuracy * 0.3 + (100 - delay_frequency) * 0.3)
    efficiency = min(100, deadline_accuracy * 0.5 + completion_rate * 0.5)

    # Performance level
    if productivity >= 90:
        level = "Excellent"
    elif productivity >= 75:
        level = "Good"
    elif productivity >= 50:
        level = "Average"
    elif productivity >= 30:
        level = "Needs Attention"
    else:
        level = "Critical"

    emp = await db["admins"].find_one({"_id": _parse_id(employee_id)})
    emp_name = emp.get("full_name", "") if emp else ""

    return {
        "employee_id": employee_id,
        "employee_name": emp_name,
        "productivity_score": round(productivity, 1),
        "efficiency_score": round(efficiency, 1),
        "workload_percent": round(workload, 1),
        "capacity_percent": round(capacity, 1),
        "task_completion_rate": round(completion_rate, 1),
        "deadline_accuracy": round(deadline_accuracy, 1),
        "delay_frequency": round(delay_frequency, 1),
        "avg_completion_hours": 0,
        "response_time_hours": 0,
        "quality_score": round(efficiency * 0.9, 1),
        "performance_level": level,
    }


# ═══════════════════════════════════════════════════════════════
#  TIME TRACKING
# ═══════════════════════════════════════════════════════════════

@router.post("/time-tracking/start")
async def start_timer(
    entry: TimeEntryAction,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Start a new time tracking entry."""
    # Check for already active timer
    existing = await db["manager_time_entries"].find_one({
        "employee_id": entry.employee_id, "is_active": True
    })
    if existing:
        raise HTTPException(status_code=400, detail="Timer already running. Stop it first.")

    now = get_now()
    doc = {
        "employee_id": entry.employee_id,
        "task_id": entry.task_id,
        "project_id": entry.project_id,
        "action": "start",
        "started_at": now,
        "paused_at": None,
        "resumed_at": None,
        "stopped_at": None,
        "total_seconds": 0,
        "break_seconds": 0,
        "is_active": True,
        "is_billable": True,
        "notes": entry.notes,
        "created_at": now,
    }
    result = await db["manager_time_entries"].insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    fire_event_background("time_tracking_started", "time_entry", str(result.inserted_id), admin.email, doc, db)
    return doc


@router.post("/time-tracking/pause")
async def pause_timer(
    entry: TimeEntryAction,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Pause the active timer."""
    now = get_now()
    active = await db["manager_time_entries"].find_one({
        "employee_id": entry.employee_id, "is_active": True, "paused_at": None
    })
    if not active:
        raise HTTPException(status_code=404, detail="No active timer found to pause.")

    elapsed = (now.replace(tzinfo=None) - active["started_at"]).total_seconds()
    await db["manager_time_entries"].update_one(
        {"_id": active["_id"]},
        {"$set": {"paused_at": now, "total_seconds": elapsed, "action": "pause"}}
    )
    return {"status": "paused", "elapsed_seconds": elapsed}


@router.post("/time-tracking/resume")
async def resume_timer(
    entry: TimeEntryAction,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Resume a paused timer."""
    now = get_now()
    paused = await db["manager_time_entries"].find_one({
        "employee_id": entry.employee_id, "is_active": True, "paused_at": {"$ne": None}
    })
    if not paused:
        raise HTTPException(status_code=404, detail="No paused timer found.")

    break_duration = (now.replace(tzinfo=None) - paused["paused_at"].replace(tzinfo=None)).total_seconds()
    await db["manager_time_entries"].update_one(
        {"_id": paused["_id"]},
        {"$set": {
            "resumed_at": now,
            "paused_at": None,
            "break_seconds": paused.get("break_seconds", 0) + break_duration,
            "action": "resume"
        }}
    )
    return {"status": "resumed", "break_seconds": break_duration}


@router.post("/time-tracking/stop")
async def stop_timer(
    entry: TimeEntryAction,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Stop the timer and record final time."""
    now = get_now()
    active = await db["manager_time_entries"].find_one({
        "employee_id": entry.employee_id, "is_active": True
    })
    if not active:
        raise HTTPException(status_code=404, detail="No active timer found.")

    total = (now.replace(tzinfo=None) - active["started_at"]).total_seconds()
    breaks = active.get("break_seconds", 0)
    # If currently paused, add that break time too
    if active.get("paused_at"):
        breaks += (now.replace(tzinfo=None) - active["paused_at"].replace(tzinfo=None)).total_seconds()

    await db["manager_time_entries"].update_one(
        {"_id": active["_id"]},
        {"$set": {
            "stopped_at": now,
            "is_active": False,
            "total_seconds": total,
            "break_seconds": breaks,
            "action": "stop",
            "notes": entry.notes or active.get("notes"),
        }}
    )

    fire_event_background("time_tracking_stopped", "time_entry", str(active["_id"]), admin.email, {
        "employee_id": entry.employee_id,
        "total_seconds": total,
        "break_seconds": breaks,
    }, db)

    return {
        "status": "stopped",
        "total_seconds": total,
        "break_seconds": breaks,
        "working_seconds": total - breaks,
    }


@router.get("/time-tracking/{employee_id}")
async def get_timesheets(
    employee_id: str,
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Get time entries / timesheets for an employee."""
    entries = await db["manager_time_entries"].find(
        {"employee_id": employee_id}
    ).sort("created_at", -1).to_list(200)

    for e in entries:
        e["_id"] = str(e["_id"])
    return entries


# ═══════════════════════════════════════════════════════════════
#  SMART ALERTS
# ═══════════════════════════════════════════════════════════════

@router.get("/alerts")
async def get_smart_alerts(
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Auto-generate and return smart alerts based on current workforce state."""
    now = get_now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    alerts = []

    # Overdue tasks
    overdue_tasks = await db["manager_tasks"].find({
        "due_date": {"$lt": now},
        "stage": {"$nin": ["Completed", "Archived"]}
    }).to_list(100)

    for t in overdue_tasks:
        alerts.append({
            "_id": f"alert_overdue_{str(t['_id'])}",
            "alert_type": "Task Delay",
            "severity": "Critical" if (now.replace(tzinfo=None) - t["due_date"]).days > 3 else "Warning",
            "employee_id": t.get("assigned_to"),
            "employee_name": t.get("assigned_to_name", ""),
            "title": f"Task Overdue: {t['title']}",
            "message": f"Task '{t['title']}' was due {t['due_date'].strftime('%b %d')} and is still in {t['stage']} stage.",
            "is_resolved": False,
            "resolved_by": None,
            "resolved_at": None,
            "created_at": now,
        })

    # Idle employees (no heartbeat in 5+ minutes but session is online)
    idle_threshold = now - timedelta(minutes=5)
    idle_sessions = await db["admin_activity"].find({
        "is_online": True,
        "last_heartbeat": {"$lt": idle_threshold}
    }).to_list(100)

    for s in idle_sessions:
        emp = await db["admins"].find_one({"_id": _parse_id(s["admin_id"])})
        if emp:
            alerts.append({
                "_id": f"alert_idle_{s['admin_id']}",
                "alert_type": "Employee Idle Too Long",
                "severity": "Warning",
                "employee_id": s["admin_id"],
                "employee_name": emp.get("full_name", emp.get("email", "")),
                "title": f"Idle: {emp.get('full_name', emp.get('email', ''))}",
                "message": f"Employee has been idle for more than 5 minutes.",
                "is_resolved": False,
                "resolved_by": None,
                "resolved_at": None,
                "created_at": now,
            })

    # High workload (more than 5 active tasks)
    workload_agg = await db["manager_tasks"].aggregate([
        {"$match": {"stage": {"$in": ["Assigned", "Accepted", "In Progress"]}}},
        {"$group": {"_id": "$assigned_to", "count": {"$sum": 1}, "name": {"$first": "$assigned_to_name"}}},
        {"$match": {"count": {"$gt": 5}}}
    ]).to_list(100)

    for w in workload_agg:
        if w["_id"]:
            alerts.append({
                "_id": f"alert_workload_{w['_id']}",
                "alert_type": "Employee Overloaded",
                "severity": "Warning",
                "employee_id": w["_id"],
                "employee_name": w.get("name", ""),
                "title": f"High Workload: {w.get('name', 'Employee')}",
                "message": f"Employee has {w['count']} active tasks assigned.",
                "is_resolved": False,
                "resolved_by": None,
                "resolved_at": None,
                "created_at": now,
            })

    # Deadline risk (tasks due in next 24 hours still not in Review/Completed)
    deadline_risk = await db["manager_tasks"].find({
        "due_date": {"$gte": now, "$lte": now + timedelta(hours=24)},
        "stage": {"$in": ["Pending", "Assigned", "Accepted", "In Progress"]}
    }).to_list(100)

    for t in deadline_risk:
        alerts.append({
            "_id": f"alert_deadline_{str(t['_id'])}",
            "alert_type": "Deadline Risk",
            "severity": "Critical",
            "employee_id": t.get("assigned_to"),
            "employee_name": t.get("assigned_to_name", ""),
            "title": f"Deadline Risk: {t['title']}",
            "message": f"Task due in less than 24 hours but still in '{t['stage']}' stage.",
            "is_resolved": False,
            "resolved_by": None,
            "resolved_at": None,
            "created_at": now,
        })

    return alerts


# ═══════════════════════════════════════════════════════════════
#  MANAGER ANALYTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/analytics")
async def get_manager_analytics(
    db=Depends(get_db),
    admin=Depends(get_current_admin_or_leader)
):
    """Charts and analytics data for manager dashboard."""
    now = get_now()
    thirty_days = now - timedelta(days=30)

    # Task completion by day (last 30 days)
    task_trend = await db["manager_tasks"].aggregate([
        {"$match": {"stage": "Completed", "updated_at": {"$gte": thirty_days}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$updated_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]).to_list(None)

    # Tasks by stage
    stage_dist = await db["manager_tasks"].aggregate([
        {"$group": {"_id": "$stage", "count": {"$sum": 1}}}
    ]).to_list(None)

    # Tasks by priority
    priority_dist = await db["manager_tasks"].aggregate([
        {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
    ]).to_list(None)

    # Workload per employee
    workload = await db["manager_tasks"].aggregate([
        {"$match": {"stage": {"$nin": ["Completed", "Archived"]}}},
        {"$group": {"_id": "$assigned_to_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]).to_list(None)

    # Attendance trend (last 30 days)
    att_trend = await db["team_attendance"].aggregate([
        {"$match": {"date": {"$gte": thirty_days}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date"}},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "Present"]}, 1, 0]}},
            "absent": {"$sum": {"$cond": [{"$eq": ["$status", "Absent"]}, 1, 0]}},
            "leave": {"$sum": {"$cond": [{"$eq": ["$status", "Leave"]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}}
    ]).to_list(None)

    # Working hours per employee (last 30 days)
    hours_per_emp = await db["team_work_logs"].aggregate([
        {"$match": {"log_date": {"$gte": thirty_days}}},
        {"$group": {"_id": "$employee_id", "total_hours": {"$sum": "$hours"}}},
        {"$sort": {"total_hours": -1}},
        {"$limit": 10}
    ]).to_list(None)

    # Enrich with employee names
    for h in hours_per_emp:
        try:
            emp = await db["admins"].find_one({"_id": ObjectId(h["_id"])})
            h["name"] = emp.get("full_name", emp.get("email", "")) if emp else h["_id"]
        except Exception:
            h["name"] = h["_id"] or "Unknown"

    return {
        "task_completion_trend": [{"date": t["_id"], "completed": t["count"]} for t in task_trend],
        "tasks_by_stage": [{"stage": s["_id"] or "Unknown", "count": s["count"]} for s in stage_dist],
        "tasks_by_priority": [{"priority": p["_id"] or "Medium", "count": p["count"]} for p in priority_dist],
        "employee_workload": [{"name": w["_id"] or "Unassigned", "tasks": w["count"]} for w in workload],
        "attendance_trend": [{"date": a["_id"], "present": a["present"], "absent": a["absent"], "leave": a["leave"]} for a in att_trend],
        "hours_per_employee": [{"name": h["name"], "hours": round(h["total_hours"], 1)} for h in hours_per_emp],
    }
