"""
Hardware Auth — Employee CRUD + QR-based Login + Manual Login
===============================================================
Endpoints for managing employees, generating QR codes,
hardware-style QR scan authentication, and manual email/password login.
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
from app.core.security import create_access_token, verify_password
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
#  FACE VERIFICATION (Anti-cheat)
# ═══════════════════════════════════════════════════════════════
#  Face descriptors are 128-float vectors produced client-side by
#  face-api.js (FaceRecognitionNet). We never send the enrolled
#  reference back to the browser — matching is done server-side so
#  a stolen QR alone can't unlock another person's account.

SENSITIVE_EMPLOYEE_FIELDS = ("face_descriptor", "face_encoding")


def _face_distance(a: list, b: list) -> float:
    """Euclidean distance between two face descriptors. Lower = more similar."""
    if not a or not b or len(a) != len(b):
        return 999.0
    return sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)) ** 0.5


def _valid_descriptor(desc) -> bool:
    """A usable descriptor is a 128-length list of finite numbers."""
    if not isinstance(desc, list) or len(desc) != 128:
        return False
    try:
        return all(isinstance(v, (int, float)) for v in desc)
    except TypeError:
        return False


def _sanitize_employee(emp: dict) -> dict:
    """Strip sensitive biometric fields before returning an employee to a client."""
    if not isinstance(emp, dict):
        return emp
    clean = {k: v for k, v in emp.items() if k not in SENSITIVE_EMPLOYEE_FIELDS}
    # Expose only a boolean flag about enrollment, never the vector itself.
    clean["face_enrolled"] = _valid_descriptor(emp.get("face_descriptor"))
    if "_id" in clean:
        clean["_id"] = str(clean["_id"])
    return clean


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

    # Optional biometric enrollment at creation time.
    incoming_desc = employee_data.get("face_descriptor")
    if incoming_desc is not None:
        if not _valid_descriptor(incoming_desc):
            raise HTTPException(status_code=400, detail="face_descriptor must be a 128-number array")
        doc["face_descriptor"] = incoming_desc
        doc["face_enrolled_at"] = now

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

    return {"status": "success", "employee": _sanitize_employee(doc)}


@router.get("/employees")
async def list_employees(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """List all employees."""
    employees = await db["hw_employees"].find().to_list(100)
    employees = [_sanitize_employee(emp) for emp in employees]
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

    return {"status": "success", "employee": _sanitize_employee(emp)}


@router.put("/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    update_data: dict,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Update employee details."""
    # Remove protected fields (biometrics only via the dedicated enroll endpoint)
    update_data.pop("_id", None)
    update_data.pop("qr_code_data", None)
    update_data.pop("qr_code_image", None)
    update_data.pop("created_at", None)
    update_data.pop("face_descriptor", None)
    update_data.pop("face_encoding", None)
    update_data.pop("face_enrolled_at", None)
    update_data["updated_at"] = get_now()

    result = await db["hw_employees"].find_one_and_update(
        {"_id": ObjectId(employee_id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"status": "success", "employee": _sanitize_employee(result)}


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


@router.post("/employees/{employee_id}/enroll-face")
async def enroll_face(
    employee_id: str,
    payload: dict,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """
    Enroll (or re-enroll) an employee's face for anti-cheat verification.
    Expects `face_descriptor`: a 128-number vector from face-api.js.
    The reference vector is stored server-side and never returned to clients.
    """
    descriptor = payload.get("face_descriptor")
    if not _valid_descriptor(descriptor):
        raise HTTPException(status_code=400, detail="face_descriptor must be a 128-number array")

    try:
        oid = ObjectId(employee_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee id")

    result = await db["hw_employees"].find_one_and_update(
        {"_id": oid},
        {"$set": {
            "face_descriptor": descriptor,
            "face_enrolled_at": get_now(),
            "updated_at": get_now(),
        }},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {"status": "success", "message": "Face enrolled", "employee": _sanitize_employee(result)}


@router.delete("/employees/{employee_id}/face")
async def remove_face(
    employee_id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_admin)
):
    """Remove an employee's enrolled face (disables face verification for them)."""
    result = await db["hw_employees"].update_one(
        {"_id": ObjectId(employee_id)},
        {"$unset": {"face_descriptor": "", "face_enrolled_at": ""}, "$set": {"updated_at": get_now()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"status": "success", "message": "Face enrollment removed"}


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

    # ── Anti-cheat: face verification (QR + Face) ──
    # If this employee has an enrolled face, the live face captured at the
    # kiosk must match — a stolen QR alone will not unlock the account.
    reference = employee.get("face_descriptor")
    live_descriptor = login_data.get("face_descriptor")
    liveness_passed = bool(login_data.get("liveness_passed"))
    face_verified = None

    if _valid_descriptor(reference):
        if settings.HW_REQUIRE_FACE_MATCH:
            if not _valid_descriptor(live_descriptor):
                raise HTTPException(
                    status_code=422,
                    detail="Face required. Look at the camera so we can verify it's really you.",
                )
            if not liveness_passed:
                raise HTTPException(
                    status_code=403,
                    detail="Liveness check failed. Please blink at the camera (photos are not allowed).",
                )
            distance = _face_distance(reference, live_descriptor)
            if distance > settings.HW_FACE_MATCH_THRESHOLD:
                # Record the spoof attempt against the QR owner for the audit trail.
                await db["hw_monitoring_events"].insert_one({
                    "employee_id": employee["employee_id"],
                    "employee_db_id": str(employee["_id"]),
                    "event_type": "face_mismatch_login_blocked",
                    "confidence": 1.0,
                    "severity": "critical",
                    "details": {"distance": round(distance, 4), "threshold": settings.HW_FACE_MATCH_THRESHOLD},
                    "timestamp": get_now(),
                })
                raise HTTPException(
                    status_code=403,
                    detail="Face does not match the badge owner. Login blocked.",
                )
            face_verified = True
        elif _valid_descriptor(live_descriptor):
            # Verification not enforced — record match result for analytics only.
            face_verified = _face_distance(reference, live_descriptor) <= settings.HW_FACE_MATCH_THRESHOLD

    # Check for existing active session
    existing_session = await db["hw_sessions"].find_one({
        "employee_db_id": str(employee["_id"]),
        "status": {"$in": ["active", "lunch_break"]}
    })
    
    now = get_now()
    schedule = _get_duty_schedule()
    
    # ── GENERATE ADMIN TOKEN FOR SEAMLESS DASHBOARD LOGIN ──
    admin_token = None
    admin_user = await db["admins"].find_one({"email": employee["email"]})
    if not admin_user:
        # Fallback to super admin so the demo works seamlessly
        admin_user = await db["admins"].find_one({"role": "super_admin"})
    if admin_user:
        admin_token = create_access_token(data={"id": str(admin_user["_id"])})
    
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
            
            employee = {**_sanitize_employee(employee), "face_verified": face_verified}
            
            # Update live status immediately
            await db["hw_live_status"].update_one(
                {"employee_id": employee["employee_id"]},
                {"$set": {
                    "employee_id": employee["employee_id"],
                    "employee_db_id": str(employee["_id"]),
                    "status": "online",
                    "camera_state": "on",
                    "face_detected": True,
                    "last_heartbeat": now,
                    "is_online": True,
                    "updated_at": now
                }},
                upsert=True
            )
            
            return {
                "status": "success",
                "token": token,
                "admin_token": admin_token,
                "session_id": str(existing_session["_id"]),
                "employee": employee,
                "session_start": existing_session["login_time"].replace(tzinfo=timezone.utc).isoformat() if existing_session["login_time"].tzinfo is None else existing_session["login_time"].isoformat(),
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
            
            employee = {**_sanitize_employee(employee), "face_verified": face_verified}
            
            # Update live status immediately
            await db["hw_live_status"].update_one(
                {"employee_id": employee["employee_id"]},
                {"$set": {
                    "employee_id": employee["employee_id"],
                    "employee_db_id": str(employee["_id"]),
                    "status": "online",
                    "camera_state": "on",
                    "face_detected": True,
                    "last_heartbeat": now,
                    "is_online": True,
                    "updated_at": now
                }},
                upsert=True
            )
            
            return {
                "status": "success",
                "token": token,
                "admin_token": admin_token,
                "session_id": str(existing_session["_id"]),
                "employee": employee,
                "session_start": existing_session["login_time"].replace(tzinfo=timezone.utc).isoformat() if existing_session["login_time"].tzinfo is None else existing_session["login_time"].isoformat(),
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
        "face_verified": face_verified,
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
        "details": {"device_info": login_data.get("device_info"), "face_verified": face_verified},
        "timestamp": now,
    })
    
    # Update live status immediately
    await db["hw_live_status"].update_one(
        {"employee_id": employee["employee_id"]},
        {"$set": {
            "employee_id": employee["employee_id"],
            "employee_db_id": str(employee["_id"]),
            "status": "online",
            "camera_state": "on",
            "face_detected": True,
            "last_heartbeat": now,
            "is_online": True,
            "updated_at": now
        }},
        upsert=True
    )
    
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
    
    employee = {**_sanitize_employee(employee), "face_verified": face_verified}

    return {
        "status": "success",
        "token": token,
        "admin_token": admin_token,
        "session_id": session_id,
        "employee": employee,
        "session_start": now.isoformat(),
        "session_type": "morning",
        "face_verified": face_verified,
        "session_schedule": schedule,
        "message": "QR Login successful! Morning session started."
    }


@router.post("/auth/manual-login")
async def manual_login(
    request: Request,
    login_data: dict,
    db=Depends(get_db)
):
    """
    Manual email/password login for hardware monitoring.
    Alternative to QR scanning — employees can type their email and
    password (the same credentials as admin panel) to clock in.
    """
    email = (login_data.get("email") or "").strip().lower()
    password = login_data.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    # 1. Verify credentials against the admins collection
    admin_user = await db["admins"].find_one({"email": email})
    if not admin_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, admin_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # 2. Find the matching HW employee by email
    employee = await db["hw_employees"].find_one({"email": email})
    if not employee:
        raise HTTPException(
            status_code=404,
            detail="No hardware employee profile found for this email. Contact your administrator."
        )

    if employee.get("status") != "Active":
        raise HTTPException(status_code=403, detail="Employee account is not active")

    # 3. Create session (same logic as qr-login)
    now = get_now()
    schedule = _get_duty_schedule()

    # Generate admin token for seamless dashboard access
    admin_token = create_access_token(data={"id": str(admin_user["_id"])})

    # Check for existing active session
    existing_session = await db["hw_sessions"].find_one({
        "employee_db_id": str(employee["_id"]),
        "status": {"$in": ["active", "lunch_break"]}
    })

    if existing_session:
        # Returning from lunch break
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

            emp_safe = {**_sanitize_employee(employee), "face_verified": None}

            await db["hw_live_status"].update_one(
                {"employee_id": employee["employee_id"]},
                {"$set": {
                    "employee_id": employee["employee_id"],
                    "employee_db_id": str(employee["_id"]),
                    "status": "online",
                    "camera_state": "on",
                    "face_detected": True,
                    "last_heartbeat": now,
                    "is_online": True,
                    "updated_at": now
                }},
                upsert=True
            )

            return {
                "status": "success",
                "token": token,
                "admin_token": admin_token,
                "session_id": str(existing_session["_id"]),
                "employee": emp_safe,
                "session_start": existing_session["login_time"].replace(tzinfo=timezone.utc).isoformat() if existing_session["login_time"].tzinfo is None else existing_session["login_time"].isoformat(),
                "session_type": "afternoon",
                "session_schedule": schedule,
                "message": "Welcome back from lunch! Afternoon session started."
            }
        else:
            # Already active session
            token = create_access_token(data={
                "id": str(employee["_id"]),
                "email": employee["email"],
                "role": "hw_employee",
                "session_id": str(existing_session["_id"]),
                "type": "hw_session"
            })

            emp_safe = {**_sanitize_employee(employee), "face_verified": None}

            await db["hw_live_status"].update_one(
                {"employee_id": employee["employee_id"]},
                {"$set": {
                    "employee_id": employee["employee_id"],
                    "employee_db_id": str(employee["_id"]),
                    "status": "online",
                    "camera_state": "on",
                    "face_detected": True,
                    "last_heartbeat": now,
                    "is_online": True,
                    "updated_at": now
                }},
                upsert=True
            )

            return {
                "status": "success",
                "token": token,
                "admin_token": admin_token,
                "session_id": str(existing_session["_id"]),
                "employee": emp_safe,
                "session_start": existing_session["login_time"].replace(tzinfo=timezone.utc).isoformat() if existing_session["login_time"].tzinfo is None else existing_session["login_time"].isoformat(),
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
        "face_verified": None,
        "login_method": "manual",
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
        "details": {"login_method": "manual", "device_info": login_data.get("device_info")},
        "timestamp": now,
    })

    # Update live status
    await db["hw_live_status"].update_one(
        {"employee_id": employee["employee_id"]},
        {"$set": {
            "employee_id": employee["employee_id"],
            "employee_db_id": str(employee["_id"]),
            "status": "online",
            "camera_state": "on",
            "face_detected": True,
            "last_heartbeat": now,
            "is_online": True,
            "updated_at": now
        }},
        upsert=True
    )

    # Update employee session count
    await db["hw_employees"].update_one(
        {"_id": employee["_id"]},
        {"$inc": {"total_sessions": 1}, "$set": {"updated_at": now}}
    )

    # Generate JWT token
    token = create_access_token(data={
        "id": str(employee["_id"]),
        "email": employee["email"],
        "role": "hw_employee",
        "session_id": session_id,
        "type": "hw_session"
    })

    emp_safe = {**_sanitize_employee(employee), "face_verified": None}

    return {
        "status": "success",
        "token": token,
        "admin_token": admin_token,
        "session_id": session_id,
        "employee": emp_safe,
        "session_start": now.isoformat(),
        "session_type": "morning",
        "face_verified": None,
        "session_schedule": schedule,
        "message": "Manual login successful! Morning session started."
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

    # Wall-clock duration of the whole session (login → logout). This is
    # NOT the worked time — it includes every pause (face away, sleep,
    # lunch, idle). The AI-tracked active time is accumulated by the
    # heartbeat into `total_active_seconds`, so we must NOT clobber it here.
    session_seconds = (now - login_time).total_seconds()
    active_seconds = session.get("total_active_seconds", 0)

    # Optional flag: 8-hour duty was completed on the client before logout.
    duty_completed = bool(logout_data.get("duty_completed"))

    update = {
        "status": "completed" if duty_completed else "ended",
        "logout_time": now,
        "total_session_seconds": session_seconds,
        "duty_completed": duty_completed,
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

    # Clear live status so the admin board shows the employee as offline.
    await db["hw_live_status"].update_one(
        {"employee_id": session["employee_id"]},
        {"$set": {"status": "offline", "is_online": False, "face_detected": False, "updated_at": now}}
    )

    # Log session end event
    await db["hw_monitoring_events"].insert_one({
        "session_id": session_id,
        "employee_id": session["employee_id"],
        "employee_db_id": session["employee_db_id"],
        "event_type": "session_end",
        "confidence": 1.0,
        "severity": "info",
        "details": {
            "session_seconds": session_seconds,
            "active_seconds": active_seconds,
            "duty_completed": duty_completed,
        },
        "timestamp": now,
    })

    return {
        "status": "success",
        "message": "Session ended",
        "total_active_seconds": active_seconds,
        "total_session_seconds": session_seconds,
        "active_hours": round(active_seconds / 3600, 2),
        "total_hours": round(session_seconds / 3600, 2),
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
    """Get session details, plus today's cumulative active seconds.

    The work timer must survive logout/re-login: a fresh session starts at
    0 active seconds, but the employee should resume where their DAY left
    off. So we sum `total_active_seconds` across every session the employee
    had today (including this one) and return it as `day_active_seconds`.
    """
    session = await db["hw_sessions"].find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now = get_now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    day_sessions = await db["hw_sessions"].find({
        "employee_db_id": session["employee_db_id"],
        "login_time": {"$gte": day_start, "$lt": day_end},
    }).to_list(100)

    day_active_seconds = sum(s.get("total_active_seconds", 0) for s in day_sessions)

    session["_id"] = str(session["_id"])
    return {
        "status": "success",
        "session": session,
        "day_active_seconds": day_active_seconds,
    }


@router.get("/schedule")
async def get_schedule():
    """Get the duty schedule configuration."""
    return {"status": "success", "schedule": _get_duty_schedule()}
