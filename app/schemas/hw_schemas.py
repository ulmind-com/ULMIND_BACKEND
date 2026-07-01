"""
Hardware Monitoring System — Pydantic Schemas
==============================================
Enterprise-grade schemas for QR-based hardware login,
real-time camera AI monitoring, work timer, and analytics.
"""

from pydantic import BaseModel, Field, EmailStr, ConfigDict
from pydantic.functional_validators import BeforeValidator
from typing import Optional, List, Annotated
from datetime import datetime
from enum import Enum

PyObjectId = Annotated[str, BeforeValidator(str)]


# ═══════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════

class HWEmployeeStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    SUSPENDED = "Suspended"

class HWSessionStatus(str, Enum):
    ACTIVE = "active"
    LUNCH_BREAK = "lunch_break"
    ENDED = "ended"
    AUTO_ENDED = "auto_ended"
    FORCE_ENDED = "force_ended"

class MonitoringEventType(str, Enum):
    FACE_PRESENT = "face_present"
    FACE_ABSENT = "face_absent"
    MOBILE_DETECTED = "mobile_detected"
    SLEEPING_DETECTED = "sleeping_detected"
    CAMERA_COVERED = "camera_covered"
    CAMERA_UNCOVERED = "camera_uncovered"
    CAMERA_FROZEN = "camera_frozen"
    CAMERA_LOW_LIGHT = "camera_low_light"
    CAMERA_ROTATED = "camera_rotated"
    MULTIPLE_PERSONS = "multiple_persons"
    UNAUTHORIZED_PERSON = "unauthorized_person"
    HEAD_DOWN = "head_down"
    LOOKING_AWAY = "looking_away"
    YAWNING = "yawning"
    INTERNET_DISCONNECTED = "internet_disconnected"
    INTERNET_RECONNECTED = "internet_reconnected"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    LUNCH_START = "lunch_start"
    LUNCH_END = "lunch_end"
    IDLE_DETECTED = "idle_detected"
    ACTIVE_WORKING = "active_working"

class CameraState(str, Enum):
    ON = "on"
    OFF = "off"
    COVERED = "covered"
    FROZEN = "frozen"
    LOW_LIGHT = "low_light"
    PERMISSION_DENIED = "permission_denied"

class AlertSeverityHW(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class EmployeeCreate(BaseModel):
    name: str = Field(..., description="Full name of the employee")
    email: EmailStr = Field(..., description="Employee email address")
    designation: str = Field(..., description="Job title/designation")
    employee_id: str = Field(..., description="Company employee ID, e.g. UL-001")
    phone: Optional[str] = None
    department: Optional[str] = None

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    designation: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None

class EmployeeInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    email: str
    designation: str
    employee_id: str
    phone: Optional[str] = None
    department: Optional[str] = None
    status: str = "Active"
    qr_code_data: Optional[str] = None
    qr_code_image: Optional[str] = None  # base64 encoded QR image
    face_encoding: Optional[str] = None  # stored face template for future face recognition
    total_working_hours: float = 0
    total_sessions: int = 0
    avg_productivity_score: float = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True)

class EmployeeResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    name: str
    email: str
    designation: str
    employee_id: str
    phone: Optional[str] = None
    department: Optional[str] = None
    status: str = "Active"
    qr_code_data: Optional[str] = None
    qr_code_image: Optional[str] = None
    total_working_hours: float = 0
    total_sessions: int = 0
    avg_productivity_score: float = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
#  QR CODE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class QRCodePayload(BaseModel):
    """The data embedded inside the QR code"""
    employee_id: str
    employee_db_id: str
    email: str
    name: str
    company: str = "ulmind"
    generated_at: str  # ISO timestamp

class QRLoginRequest(BaseModel):
    """Request body when scanning QR code"""
    qr_payload: str  # JSON string from QR code
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class QRLoginResponse(BaseModel):
    token: str
    session_id: str
    employee: dict
    session_start: str
    session_schedule: dict
    message: str = "Login successful"


# ═══════════════════════════════════════════════════════════════
#  SESSION SCHEMAS
# ═══════════════════════════════════════════════════════════════

class HWSessionCreate(BaseModel):
    employee_id: str
    employee_db_id: str
    device_info: Optional[str] = None
    ip_address: Optional[str] = None

class HWSessionInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    employee_id: str
    employee_db_id: str
    status: str = "active"
    login_time: datetime
    logout_time: Optional[datetime] = None
    
    # Session segments (morning + afternoon)
    morning_start: Optional[datetime] = None
    morning_end: Optional[datetime] = None
    afternoon_start: Optional[datetime] = None
    afternoon_end: Optional[datetime] = None
    lunch_start: Optional[datetime] = None
    lunch_end: Optional[datetime] = None
    
    # Duration tracking
    total_active_seconds: float = 0
    total_idle_seconds: float = 0
    total_break_seconds: float = 0
    total_absent_seconds: float = 0
    
    # Camera monitoring summary
    face_present_seconds: float = 0
    mobile_detected_count: int = 0
    mobile_detected_seconds: float = 0
    sleeping_detected_count: int = 0
    sleeping_detected_seconds: float = 0
    camera_covered_seconds: float = 0
    looking_away_seconds: float = 0
    
    # Device info
    device_info: Optional[str] = None
    ip_address: Optional[str] = None
    
    created_at: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
#  MONITORING EVENT SCHEMAS
# ═══════════════════════════════════════════════════════════════

class MonitoringEventCreate(BaseModel):
    session_id: str
    employee_id: str
    event_type: str  # MonitoringEventType value
    confidence: float = 0.0  # AI detection confidence
    details: Optional[dict] = None  # Additional detection data
    frame_snapshot: Optional[str] = None  # Optional base64 frame for evidence

class MonitoringEventInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    session_id: str
    employee_id: str
    event_type: str
    confidence: float = 0.0
    details: Optional[dict] = None
    severity: str = "info"
    timestamp: datetime

    model_config = ConfigDict(populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
#  CAMERA STATUS SCHEMAS
# ═══════════════════════════════════════════════════════════════

class CameraStatusUpdate(BaseModel):
    session_id: str
    employee_id: str
    camera_state: str  # CameraState value
    details: Optional[str] = None

class CameraStatusResponse(BaseModel):
    employee_id: str
    camera_state: str
    last_updated: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════
#  HEARTBEAT SCHEMAS
# ═══════════════════════════════════════════════════════════════

class MonitorHeartbeat(BaseModel):
    session_id: str
    employee_id: str
    camera_state: str = "on"
    face_detected: bool = False
    is_active: bool = True
    detection_summary: Optional[dict] = None  # Current detection state


# ═══════════════════════════════════════════════════════════════
#  PRODUCTIVITY & ANALYTICS SCHEMAS
# ═══════════════════════════════════════════════════════════════

class ProductivityScoreHW(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    date: str  # YYYY-MM-DD
    
    # Time-based scores (0-100)
    attendance_score: float = 0
    presence_score: float = 0  # How long face was detected
    focus_score: float = 0  # Time not looking away
    activity_score: float = 0  # Active vs idle
    
    # Penalty scores
    mobile_penalty: float = 0
    sleeping_penalty: float = 0
    absence_penalty: float = 0
    camera_tampering_penalty: float = 0
    
    # Final scores
    overall_productivity_score: float = 0  # 0-100
    
    # Time breakdown
    total_hours: float = 0
    active_hours: float = 0
    idle_hours: float = 0
    absent_hours: float = 0
    mobile_hours: float = 0
    sleeping_hours: float = 0
    
    # Counts
    mobile_detections: int = 0
    sleep_detections: int = 0
    absence_events: int = 0

class SalaryRecommendation(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    month: str  # YYYY-MM
    
    # Input metrics
    total_working_days: int = 0
    days_present: int = 0
    avg_productivity_score: float = 0
    total_mobile_hours: float = 0
    total_sleeping_hours: float = 0
    total_absence_hours: float = 0
    overtime_hours: float = 0
    
    # AI recommendation
    base_salary_percent: float = 100  # 100% = full salary
    deduction_percent: float = 0
    bonus_percent: float = 0
    final_salary_percent: float = 100
    
    # AI reasoning
    ai_analysis: str = ""
    recommendations: List[str] = []

class DailyReport(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    date: str
    
    # Timeline events
    events: List[dict] = []
    
    # Summary
    productivity_score: float = 0
    total_working_hours: float = 0
    total_active_hours: float = 0
    total_idle_hours: float = 0
    
    # AI analysis
    ai_summary: str = ""
    ai_recommendations: List[str] = []


# ═══════════════════════════════════════════════════════════════
#  TEAM DASHBOARD / LIVE STATUS
# ═══════════════════════════════════════════════════════════════

class EmployeeLiveStatusHW(BaseModel):
    employee_id: str
    employee_db_id: str
    name: str
    email: str
    designation: str
    status: str = "offline"  # online, idle, absent, offline, lunch, alert
    session_id: Optional[str] = None
    camera_state: str = "off"
    face_detected: bool = False
    current_event: Optional[str] = None  # Latest detection event
    login_time: Optional[datetime] = None
    session_duration_seconds: float = 0
    active_seconds: float = 0
    idle_seconds: float = 0
    mobile_detected: bool = False
    sleeping_detected: bool = False
    last_heartbeat: Optional[datetime] = None
    productivity_score: float = 0

class TeamDashboardHW(BaseModel):
    total_employees: int = 0
    online: int = 0
    offline: int = 0
    idle: int = 0
    on_lunch: int = 0
    alerts: int = 0
    avg_productivity: float = 0
    total_working_hours_today: float = 0
    employees: List[EmployeeLiveStatusHW] = []


# ═══════════════════════════════════════════════════════════════
#  LEADERBOARD
# ═══════════════════════════════════════════════════════════════

class LeaderboardEntry(BaseModel):
    rank: int
    employee_id: str
    employee_name: str
    designation: str
    productivity_score: float = 0
    active_hours: float = 0
    mobile_penalty: float = 0
    attendance_score: float = 0


# Rebuild all models
EmployeeCreate.model_rebuild()
EmployeeUpdate.model_rebuild()
EmployeeInDB.model_rebuild()
EmployeeResponse.model_rebuild()
QRCodePayload.model_rebuild()
QRLoginRequest.model_rebuild()
QRLoginResponse.model_rebuild()
HWSessionCreate.model_rebuild()
HWSessionInDB.model_rebuild()
MonitoringEventCreate.model_rebuild()
MonitoringEventInDB.model_rebuild()
CameraStatusUpdate.model_rebuild()
CameraStatusResponse.model_rebuild()
MonitorHeartbeat.model_rebuild()
ProductivityScoreHW.model_rebuild()
SalaryRecommendation.model_rebuild()
DailyReport.model_rebuild()
EmployeeLiveStatusHW.model_rebuild()
TeamDashboardHW.model_rebuild()
LeaderboardEntry.model_rebuild()
