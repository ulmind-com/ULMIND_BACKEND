"""
Hardware Monitor — Camera Monitoring Events API
=================================================
Endpoints for receiving and querying real-time camera
detection events from the browser-side AI.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.db.database import get_db
from app.core.datetime_utils import get_now

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
#  MONITORING EVENTS
# ═══════════════════════════════════════════════════════════════

@router.post("/event")
async def log_monitoring_event(
    event_data: dict,
    db=Depends(get_db)
):
    """
    Log a camera detection event from the browser AI.
    Called by the frontend whenever TF.js detects something.
    """
    required = ["session_id", "employee_id", "event_type"]
    for field in required:
        if field not in event_data:
            raise HTTPException(status_code=400, detail=f"'{field}' is required")
    
    # Determine severity
    event_type = event_data["event_type"]
    severity = "info"
    critical_events = ["camera_covered", "sleeping_detected", "unauthorized_person", "camera_frozen"]
    warning_events = ["mobile_detected", "face_absent", "head_down", "looking_away", "internet_disconnected", "multiple_persons", "yawning", "idle_detected"]
    
    if event_type in critical_events:
        severity = "critical"
    elif event_type in warning_events:
        severity = "warning"
    
    now = get_now()
    doc = {
        "session_id": event_data["session_id"],
        "employee_id": event_data["employee_id"],
        "employee_db_id": event_data.get("employee_db_id", ""),
        "event_type": event_type,
        "confidence": event_data.get("confidence", 0.0),
        "severity": severity,
        "details": event_data.get("details", {}),
        "timestamp": now,
    }
    
    result = await db["hw_monitoring_events"].insert_one(doc)
    
    # Update session counters based on event type
    session_id = event_data["session_id"]
    session_update = {}
    
    if event_type == "mobile_detected":
        session_update = {"$inc": {"mobile_detected_count": 1}}
    elif event_type == "sleeping_detected":
        session_update = {"$inc": {"sleeping_detected_count": 1}}
    
    if session_update:
        try:
            await db["hw_sessions"].update_one(
                {"_id": ObjectId(session_id)},
                session_update
            )
        except Exception:
            pass
    
    return {
        "status": "success",
        "event_id": str(result.inserted_id),
        "severity": severity
    }


@router.post("/events/batch")
async def log_monitoring_events_batch(
    data: dict,
    db=Depends(get_db)
):
    """
    Log multiple monitoring events at once (for periodic batch uploads).
    """
    events = data.get("events", [])
    if not events:
        return {"status": "success", "inserted": 0}
    
    now = get_now()
    docs = []
    mobile_count = 0
    sleeping_count = 0
    session_id = None
    
    for event in events:
        event_type = event.get("event_type", "")
        severity = "info"
        if event_type in ["camera_covered", "sleeping_detected", "unauthorized_person"]:
            severity = "critical"
        elif event_type in ["mobile_detected", "face_absent", "head_down", "looking_away"]:
            severity = "warning"
        
        if event_type == "mobile_detected":
            mobile_count += 1
        elif event_type == "sleeping_detected":
            sleeping_count += 1
        
        if not session_id:
            session_id = event.get("session_id")
        
        docs.append({
            "session_id": event.get("session_id", ""),
            "employee_id": event.get("employee_id", ""),
            "employee_db_id": event.get("employee_db_id", ""),
            "event_type": event_type,
            "confidence": event.get("confidence", 0.0),
            "severity": severity,
            "details": event.get("details", {}),
            "timestamp": datetime.fromisoformat(event["timestamp"]) if "timestamp" in event else now,
        })
    
    if docs:
        await db["hw_monitoring_events"].insert_many(docs)
    
    # Update session counters
    if session_id and (mobile_count > 0 or sleeping_count > 0):
        inc_update = {}
        if mobile_count > 0:
            inc_update["mobile_detected_count"] = mobile_count
        if sleeping_count > 0:
            inc_update["sleeping_detected_count"] = sleeping_count
        try:
            await db["hw_sessions"].update_one(
                {"_id": ObjectId(session_id)},
                {"$inc": inc_update}
            )
        except Exception:
            pass
    
    return {"status": "success", "inserted": len(docs)}


@router.get("/events/{employee_id}")
async def get_monitoring_events(
    employee_id: str,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, le=500),
    skip: int = 0,
    db=Depends(get_db)
):
    """Get monitoring events for an employee, optionally filtered by session/type."""
    query = {"employee_id": employee_id}
    if session_id:
        query["session_id"] = session_id
    if event_type:
        query["event_type"] = event_type
    if severity:
        query["severity"] = severity
    
    events = await db["hw_monitoring_events"].find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    
    for event in events:
        event["_id"] = str(event["_id"])
    
    total = await db["hw_monitoring_events"].count_documents(query)
    
    return {
        "status": "success",
        "events": events,
        "total": total,
        "limit": limit,
        "skip": skip
    }


# ═══════════════════════════════════════════════════════════════
#  HEARTBEAT
# ═══════════════════════════════════════════════════════════════

@router.post("/heartbeat")
async def monitor_heartbeat(
    data: dict,
    db=Depends(get_db)
):
    """
    Periodic heartbeat from the browser to keep session alive
    and update live monitoring status.
    """
    session_id = data.get("session_id")
    employee_id = data.get("employee_id")
    
    if not session_id or not employee_id:
        raise HTTPException(status_code=400, detail="session_id and employee_id required")
    
    now = get_now()
    
    # Update session heartbeat
    update_data = {
        "last_heartbeat": now,
        "camera_state": data.get("camera_state", "on"),
        "face_detected": data.get("face_detected", False),
        "is_active": data.get("is_active", True),
    }
    
    # Add duration increments (sent every ~5 seconds)
    inc_data = {}
    detection_summary = data.get("detection_summary", {})
    
    if detection_summary.get("face_present_seconds", 0) > 0:
        inc_data["face_present_seconds"] = detection_summary["face_present_seconds"]
    if detection_summary.get("mobile_seconds", 0) > 0:
        inc_data["mobile_detected_seconds"] = detection_summary["mobile_seconds"]
    if detection_summary.get("sleeping_seconds", 0) > 0:
        inc_data["sleeping_detected_seconds"] = detection_summary["sleeping_seconds"]
    if detection_summary.get("absent_seconds", 0) > 0:
        inc_data["total_absent_seconds"] = detection_summary["absent_seconds"]
    if detection_summary.get("idle_seconds", 0) > 0:
        inc_data["total_idle_seconds"] = detection_summary["idle_seconds"]
    if detection_summary.get("active_seconds", 0) > 0:
        inc_data["total_active_seconds"] = detection_summary["active_seconds"]
    if detection_summary.get("looking_away_seconds", 0) > 0:
        inc_data["looking_away_seconds"] = detection_summary["looking_away_seconds"]
    if detection_summary.get("camera_covered_seconds", 0) > 0:
        inc_data["camera_covered_seconds"] = detection_summary["camera_covered_seconds"]
    
    update_op = {"$set": update_data}
    if inc_data:
        update_op["$inc"] = inc_data
    
    try:
        await db["hw_sessions"].update_one(
            {"_id": ObjectId(session_id)},
            update_op
        )
    except Exception:
        pass
    
    # Update or create live status
    await db["hw_live_status"].update_one(
        {"employee_id": employee_id},
        {"$set": {
            "employee_id": employee_id,
            "session_id": session_id,
            "status": "online" if data.get("is_active") else "idle",
            "camera_state": data.get("camera_state", "on"),
            "face_detected": data.get("face_detected", False),
            "mobile_detected": detection_summary.get("mobile_detected", False),
            "sleeping_detected": detection_summary.get("sleeping_detected", False),
            "current_event": detection_summary.get("current_event"),
            "last_heartbeat": now,
        }},
        upsert=True
    )
    
    return {"status": "success", "timestamp": now.isoformat()}


# ═══════════════════════════════════════════════════════════════
#  CAMERA STATUS
# ═══════════════════════════════════════════════════════════════

@router.post("/camera-status")
async def update_camera_status(
    data: dict,
    db=Depends(get_db)
):
    """Update camera state for an employee session."""
    session_id = data.get("session_id")
    employee_id = data.get("employee_id")
    camera_state = data.get("camera_state", "on")
    
    if not session_id or not employee_id:
        raise HTTPException(status_code=400, detail="session_id and employee_id required")
    
    now = get_now()
    
    await db["hw_sessions"].update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"camera_state": camera_state}}
    )
    
    # Log camera state change as event if it's concerning
    if camera_state in ["off", "covered", "frozen", "permission_denied"]:
        await db["hw_monitoring_events"].insert_one({
            "session_id": session_id,
            "employee_id": employee_id,
            "event_type": f"camera_{camera_state}",
            "confidence": 1.0,
            "severity": "critical" if camera_state in ["covered", "off"] else "warning",
            "details": {"camera_state": camera_state, "reason": data.get("details")},
            "timestamp": now,
        })
    
    return {"status": "success", "camera_state": camera_state}


# ═══════════════════════════════════════════════════════════════
#  INTERNET STATUS
# ═══════════════════════════════════════════════════════════════

@router.post("/internet-status")
async def update_internet_status(
    data: dict,
    db=Depends(get_db)
):
    """Log internet connectivity changes."""
    session_id = data.get("session_id")
    employee_id = data.get("employee_id")
    is_online = data.get("is_online", True)
    
    if not session_id or not employee_id:
        raise HTTPException(status_code=400, detail="session_id and employee_id required")
    
    now = get_now()
    
    event_type = "internet_reconnected" if is_online else "internet_disconnected"
    severity = "info" if is_online else "warning"
    
    await db["hw_monitoring_events"].insert_one({
        "session_id": session_id,
        "employee_id": employee_id,
        "event_type": event_type,
        "confidence": 1.0,
        "severity": severity,
        "details": {"is_online": is_online},
        "timestamp": now,
    })
    
    return {"status": "success", "event_type": event_type}


# ═══════════════════════════════════════════════════════════════
#  LIVE STATUS (ADMIN VIEW)
# ═══════════════════════════════════════════════════════════════

@router.get("/live-status")
async def get_live_status(
    db=Depends(get_db)
):
    """Get live monitoring status of all employees."""
    # Get all employees
    employees = await db["hw_employees"].find({"status": "Active"}).to_list(100)
    
    live_statuses = []
    now = get_now()
    online_count = 0
    idle_count = 0
    alert_count = 0
    lunch_count = 0
    total_hours = 0
    total_productivity = 0
    
    for emp in employees:
        emp_id = emp["employee_id"]
        
        # Get live status
        live = await db["hw_live_status"].find_one({"employee_id": emp_id})
        
        # Get active session
        session = await db["hw_sessions"].find_one({
            "employee_db_id": str(emp["_id"]),
            "status": {"$in": ["active", "lunch_break"]}
        })
        
        status_data = {
            "employee_id": emp_id,
            "employee_db_id": str(emp["_id"]),
            "name": emp["name"],
            "email": emp["email"],
            "designation": emp["designation"],
            "status": "offline",
            "session_id": None,
            "camera_state": "off",
            "face_detected": False,
            "current_event": None,
            "login_time": None,
            "session_duration_seconds": 0,
            "active_seconds": 0,
            "idle_seconds": 0,
            "mobile_detected": False,
            "sleeping_detected": False,
            "last_heartbeat": None,
            "productivity_score": emp.get("avg_productivity_score", 0),
        }
        
        if session:
            login_time = session["login_time"]
            if login_time.tzinfo is None:
                login_time = login_time.replace(tzinfo=timezone.utc)
            duration = (now - login_time).total_seconds()
            
            status_data["session_id"] = str(session["_id"])
            status_data["login_time"] = login_time.isoformat()
            status_data["session_duration_seconds"] = duration
            status_data["active_seconds"] = session.get("total_active_seconds", 0)
            status_data["idle_seconds"] = session.get("total_idle_seconds", 0)
            total_hours += duration / 3600
            
            # Dynamic AI Score based on face presence
            face_seconds = session.get("face_present_seconds", status_data["active_seconds"])
            if duration > 10:
                live_score = min(100.0, max(0.0, (face_seconds / duration) * 100))
                status_data["productivity_score"] = round(live_score, 1)
            else:
                status_data["productivity_score"] = 100.0
            
            if session.get("status") == "lunch_break":
                status_data["status"] = "lunch"
                lunch_count += 1
            else:
                # Determine last known activity time
                hb = None
                if live and live.get("last_heartbeat"):
                    hb = live["last_heartbeat"]
                else:
                    hb = session["login_time"]
                    
                if hb and hb.tzinfo is None:
                    hb = hb.replace(tzinfo=timezone.utc)
                
                # Consider offline if no heartbeat for > 45 seconds
                is_stale = (now - hb).total_seconds() > 45 if hb else True
                
                if is_stale:
                    status_data["status"] = "offline"
                else:
                    status_data["status"] = live.get("status", "online") if live else "online"
                    status_data["camera_state"] = live.get("camera_state", "on") if live else "on"
                    status_data["face_detected"] = live.get("face_detected", False) if live else True
                    status_data["current_event"] = live.get("current_event") if live else None
                    status_data["mobile_detected"] = live.get("mobile_detected", False) if live else False
                    status_data["sleeping_detected"] = live.get("sleeping_detected", False) if live else False
                    status_data["last_heartbeat"] = hb.isoformat() if (live and live.get("last_heartbeat")) else None
                    
                    if status_data["status"] == "online":
                        online_count += 1
                    elif status_data["status"] == "idle":
                        idle_count += 1
                    
                    # Count alerts
                    if status_data["mobile_detected"] or status_data["sleeping_detected"] or status_data["camera_state"] in ["covered", "off"]:
                        alert_count += 1
        
        total_productivity += status_data["productivity_score"]
        live_statuses.append(status_data)
    
    total_emp = len(employees)
    offline_count = total_emp - online_count - idle_count - lunch_count
    avg_productivity = total_productivity / total_emp if total_emp > 0 else 0
    
    return {
        "status": "success",
        "dashboard": {
            "total_employees": total_emp,
            "online": online_count,
            "offline": max(0, offline_count),
            "idle": idle_count,
            "on_lunch": lunch_count,
            "alerts": alert_count,
            "avg_productivity": round(avg_productivity, 1),
            "total_working_hours_today": round(total_hours, 2),
        },
        "employees": live_statuses
    }
