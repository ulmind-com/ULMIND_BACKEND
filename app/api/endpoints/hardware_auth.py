"""
Hardware Auth — Employee CRUD + QR-based Login
================================================
Endpoints for managing employees, generating QR codes,
and hardware-style QR scan authentication.
"""

import json
import base64
import io
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from bson import ObjectId
from app.db.database import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.core.datetime_utils import get_now
from app.api.deps import get_current_admin

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def _generate_qr_payload(employee: dict) -> str:
    """Generate the JSON payload to embed in the QR code."""
    payload = {
        "employee_id": employee["employee_id"],
        "employee_db_id": str(employee["_id"]),
        "email": employee["email"],
        "name": employee["name"],
        "company": "ulmind",
        "generated_at": get_now().isoformat(),
        "token": str(uuid.uuid4())[:8]  # Short unique token for verification
    }
    return json.dumps(payload)


def _generate_qr_image_base64(data: str) -> str:
    """Generate a QR code image and return as base64 string."""
    try:
        import qrcode
        from qrcode.image.styledpil import StyledPilImage
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except ImportError:
        # Fallback: just store the payload without image
        return ""


def _get_duty_schedule() -> dict:
    """Return the daily duty schedule configuration."""
    return {
        "morning_start": "10:00",
        "morning_end": "13:00",
        "lunch_start": "13:00",
        "lunch_end": "14:00",
        "afternoon_start": "14:00",
        "afternoon_end": "19:00",
        "total_duty_hours": 8,
        "timezone": "Asia/Kolkata"
    }


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/employees", status_code=201)
async def create_employee(
    employee_data: dict,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Create a new employee with auto-generated QR code."""
    # Validate required fields
    required = ["name", "email", "designation", "employee_id"]
    for field in required:
        if field not in employee_data or not employee_data[field]:
            raise HTTPException(status_code=400, detail=f"'{field}' is required")
    
    # Check for duplicate employee_id or email
    existing = await db["hw_employees"].find_one({
        "$or": [
            {"employee_id": employee_data["employee_id"]},
            {"email": employee_data["email"]}
        ]
    })
    if existing:
        raise HTTPException(status_code=409, detail="Employee with this ID or email already exists")
    
    now = get_now()
    doc = {
        "name": employee_data["name"],
        "email": employee_data["email"],
        "designation": employee_data["designation"],
        "employee_id": employee_data["employee_id"],
        "phone": employee_data.get("phone"),
        "department": employee_data.get("department"),
        "status": "Active",
        "total_working_hours": 0,
        "total_sessions": 0,
        "avg_productivity_score": 0,
        "created_at": now,
        "updated_at": now,
    }
    
    result = await db["hw_employees"].insert_one(doc)
    doc["_id"] = result.inserted_id
    
    # Generate QR code
    qr_payload = _generate_qr_payload(doc)
    qr_image = _generate_qr_image_base64(qr_payload)
    
    await db["hw_employees"].update_one(
        {"_id": result.inserted_id},
        {"$set": {"qr_code_data": qr_payload, "qr_code_image": qr_image}}
    )
    
    doc["qr_code_data"] = qr_payload
    doc["qr_code_image"] = qr_image
    doc["_id"] = str(doc["_id"])
    
    return {"status": "success", "employee": doc}


@router.get("/employees")
async def list_employees(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """List all employees."""
    employees = await db["hw_employees"].find().to_list(100)
    for emp in employees:
        emp["_id"] = str(emp["_id"])
    return {"status": "success", "employees": employees, "total": len(employees)}


@router.get("/employees/{employee_id}")
async def get_employee(
    employee_id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Get employee details by ID."""
    try:
        emp = await db["hw_employees"].find_one({"_id": ObjectId(employee_id)})
    except Exception:
        emp = await db["hw_employees"].find_one({"employee_id": employee_id})
    
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    emp["_id"] = str(emp["_id"])
    return {"status": "success", "employee": emp}


@router.put("/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    update_data: dict,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Update employee details."""
    # Remove protected fields
    update_data.pop("_id", None)
    update_data.pop("qr_code_data", None)
    update_data.pop("qr_code_image", None)
    update_data.pop("created_at", None)
    update_data["updated_at"] = get_now()
    
    result = await db["hw_employees"].find_one_and_update(
        {"_id": ObjectId(employee_id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    result["_id"] = str(result["_id"])
    return {"status": "success", "employee": result}


@router.delete("/employees/{employee_id}")
async def delete_employee(
    employee_id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Delete an employee."""
    result = await db["hw_employees"].delete_one({"_id": ObjectId(employee_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"status": "success", "message": "Employee deleted"}


@router.post("/employees/{employee_id}/regenerate-qr")
async def regenerate_qr(
    employee_id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Regenerate QR code for an employee."""
    emp = await db["hw_employees"].find_one({"_id": ObjectId(employee_id)})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    qr_payload = _generate_qr_payload(emp)
    qr_image = _generate_qr_image_base64(qr_payload)
    
    await db["hw_employees"].update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {"qr_code_data": qr_payload, "qr_code_image": qr_image, "updated_at": get_now()}}
    )
    
    return {
        "status": "success",
        "qr_code_data": qr_payload,
        "qr_code_image": qr_image
    }


# ═══════════════════════════════════════════════════════════════
#  QR CODE LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════

@router.post("/auth/qr-login")
async def qr_login(
    request: Request,
    login_data: dict,
    db=Depends(get_db)
):
    """
    Hardware-style QR code login.
    The laptop camera scans the QR code, this endpoint verifies it
    and creates a monitoring session.
    """
    qr_payload_str = login_data.get("qr_payload", "")
    
    try:
        qr_data = json.loads(qr_payload_str)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid QR code data")
    
    # Verify required fields
    employee_db_id = qr_data.get("employee_db_id")
    employee_id = qr_data.get("employee_id")
    
    if not employee_db_id or not employee_id:
        raise HTTPException(status_code=400, detail="Invalid QR code: missing employee data")
    
    # Find employee
    try:
        employee = await db["hw_employees"].find_one({"_id": ObjectId(employee_db_id)})
    except Exception:
        employee = None
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found. Invalid QR code.")
    
    if employee.get("status") != "Active":
        raise HTTPException(status_code=403, detail="Employee account is not active")
    
    # Verify employee_id matches
    if employee["employee_id"] != employee_id:
        raise HTTPException(status_code=403, detail="QR code data mismatch")
    
    # Check for existing active session
    existing_session = await db["hw_sessions"].find_one({
        "employee_db_id": str(employee["_id"]),
        "status": {"$in": ["active", "lunch_break"]}
    })
    
    now = get_now()
    schedule = _get_duty_schedule()
    
    if existing_session:
        # If returning from lunch break, update session
        if existing_session.get("status") == "lunch_break":
            await db["hw_sessions"].update_one(
                {"_id": existing_session["_id"]},
                {"$set": {
                    "status": "active",
                    "lunch_end": now,
                    "afternoon_start": now,
                }}
            )
            
            token = create_access_token(data={
                "id": str(employee["_id"]),
                "email": employee["email"],
                "role": "hw_employee",
                "session_id": str(existing_session["_id"]),
                "type": "hw_session"
            })
            
            employee["_id"] = str(employee["_id"])
            return {
                "status": "success",
                "token": token,
                "session_id": str(existing_session["_id"]),
                "employee": employee,
                "session_start": existing_session["login_time"].isoformat(),
                "session_type": "afternoon",
                "session_schedule": schedule,
                "message": "Welcome back from lunch! Afternoon session started."
            }
        else:
            # Already has active session
            token = create_access_token(data={
                "id": str(employee["_id"]),
                "email": employee["email"],
                "role": "hw_employee",
                "session_id": str(existing_session["_id"]),
                "type": "hw_session"
            })
            
            employee["_id"] = str(employee["_id"])
            return {
                "status": "success",
                "token": token,
                "session_id": str(existing_session["_id"]),
                "employee": employee,
                "session_start": existing_session["login_time"].isoformat(),
                "session_type": "existing",
                "session_schedule": schedule,
                "message": "Session already active."
            }
    
    # Create new session
    session_doc = {
        "employee_id": employee["employee_id"],
        "employee_db_id": str(employee["_id"]),
        "employee_name": employee["name"],
        "status": "active",
        "login_time": now,
        "morning_start": now,
        "morning_end": None,
        "lunch_start": None,
        "lunch_end": None,
        "afternoon_start": None,
        "afternoon_end": None,
        "logout_time": None,
        "total_active_seconds": 0,
        "total_idle_seconds": 0,
        "total_break_seconds": 0,
        "total_absent_seconds": 0,
        "face_present_seconds": 0,
        "mobile_detected_count": 0,
        "mobile_detected_seconds": 0,
        "sleeping_detected_count": 0,
        "sleeping_detected_seconds": 0,
        "camera_covered_seconds": 0,
        "looking_away_seconds": 0,
        "device_info": login_data.get("device_info"),
        "ip_address": login_data.get("ip_address"),
        "user_agent": login_data.get("user_agent"),
        "created_at": now,
    }
    
    session_result = await db["hw_sessions"].insert_one(session_doc)
    session_id = str(session_result.inserted_id)
    
    # Log session start event
    await db["hw_monitoring_events"].insert_one({
        "session_id": session_id,
        "employee_id": employee["employee_id"],
        "employee_db_id": str(employee["_id"]),
        "event_type": "session_start",
        "confidence": 1.0,
        "severity": "info",
        "details": {"device_info": login_data.get("device_info")},
        "timestamp": now,
    })
    
    # Update employee session count
    await db["hw_employees"].update_one(
        {"_id": employee["_id"]},
        {"$inc": {"total_sessions": 1}, "$set": {"updated_at": now}}
    )
    
    # Generate JWT token for the session
    token = create_access_token(data={
        "id": str(employee["_id"]),
        "email": employee["email"],
        "role": "hw_employee",
        "session_id": session_id,
        "type": "hw_session"
    })
    
    employee["_id"] = str(employee["_id"])
    
    return {
        "status": "success",
        "token": token,
        "session_id": session_id,
        "employee": employee,
        "session_start": now.isoformat(),
        "session_type": "morning",
        "session_schedule": schedule,
        "message": "QR Login successful! Morning session started."
    }


@router.post("/auth/qr-logout")
async def qr_logout(
    logout_data: dict,
    db=Depends(get_db)
):
    """End a hardware monitoring session."""
    session_id = logout_data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session = await db["hw_sessions"].find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    now = get_now()
    login_time = session["login_time"]
    if login_time.tzinfo is None:
        login_time = login_time.replace(tzinfo=timezone.utc)
    
    total_seconds = (now - login_time).total_seconds()
    
    update = {
        "status": "ended",
        "logout_time": now,
        "total_active_seconds": total_seconds,
    }
    
    # Set the correct end time based on current session segment
    if session.get("afternoon_start"):
        update["afternoon_end"] = now
    elif session.get("morning_start"):
        update["morning_end"] = now
    
    await db["hw_sessions"].update_one(
        {"_id": ObjectId(session_id)},
        {"$set": update}
    )
    
    # Log session end event
    await db["hw_monitoring_events"].insert_one({
        "session_id": session_id,
        "employee_id": session["employee_id"],
        "employee_db_id": session["employee_db_id"],
        "event_type": "session_end",
        "confidence": 1.0,
        "severity": "info",
        "details": {"total_seconds": total_seconds},
        "timestamp": now,
    })
    
    return {
        "status": "success",
        "message": "Session ended",
        "total_seconds": total_seconds,
        "total_hours": round(total_seconds / 3600, 2)
    }


@router.post("/auth/lunch-break")
async def start_lunch_break(
    data: dict,
    db=Depends(get_db)
):
    """Transition session to lunch break status."""
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    
    session = await db["hw_sessions"].find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    now = get_now()
    
    await db["hw_sessions"].update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {
            "status": "lunch_break",
            "morning_end": now,
            "lunch_start": now,
        }}
    )
    
    # Log lunch event
    await db["hw_monitoring_events"].insert_one({
        "session_id": session_id,
        "employee_id": session["employee_id"],
        "employee_db_id": session["employee_db_id"],
        "event_type": "lunch_start",
        "confidence": 1.0,
        "severity": "info",
        "timestamp": now,
    })
    
    return {"status": "success", "message": "Lunch break started"}


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    db=Depends(get_db)
):
    """Get session details."""
    session = await db["hw_sessions"].find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session["_id"] = str(session["_id"])
    return {"status": "success", "session": session}


@router.get("/schedule")
async def get_schedule():
    """Get the duty schedule configuration."""
    return {"status": "success", "schedule": _get_duty_schedule()}
