from pydantic import BaseModel, Field
from typing import List, Optional, Annotated
from datetime import datetime
from app.core.datetime_utils import get_now
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

# ── Attendance ──
class TeamAttendanceBase(BaseModel):
    employee_id: str
    date: datetime
    status: str = "Present"  # Present, Absent, Half Day, Leave, Remote
    check_in: Optional[str] = None   # "09:00"
    check_out: Optional[str] = None  # "18:00"
    notes: Optional[str] = None

class TeamAttendanceCreate(TeamAttendanceBase):
    pass

class TeamAttendanceInDB(TeamAttendanceBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# ── Work Logs ──
class TeamWorkLogBase(BaseModel):
    employee_id: str
    project_id: Optional[str] = None
    task_description: str
    hours: float
    log_date: datetime
    notes: Optional[str] = None

class TeamWorkLogCreate(TeamWorkLogBase):
    pass

class TeamWorkLogInDB(TeamWorkLogBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime

# ── Performance ──
class TeamPerformanceBase(BaseModel):
    employee_id: str
    reviewer_id: Optional[str] = None
    period: str  # e.g. "2024-Q1"
    attendance_score: float = 0       # 0-100
    productivity_score: float = 0     # 0-100
    quality_score: float = 0          # 0-100
    teamwork_score: float = 0         # 0-100
    deadlines_met_score: float = 0    # 0-100
    overall_score: float = 0          # computed avg
    comments: Optional[str] = None
    status: str = "Draft"             # Draft, Submitted, Approved

class TeamPerformanceCreate(TeamPerformanceBase):
    pass

class TeamPerformanceInDB(TeamPerformanceBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# ── Leaves ──
class TeamLeaveBase(BaseModel):
    employee_id: str
    leave_type: str = "Casual"  # Casual, Sick, Earned, Emergency, WFH
    from_date: datetime
    to_date: datetime
    reason: Optional[str] = None
    status: str = "Pending"  # Pending, Approved, Rejected

class TeamLeaveCreate(TeamLeaveBase):
    pass

class TeamLeaveInDB(TeamLeaveBase):
    id: PyObjectId = Field(alias="_id")
    approved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# ── Payroll ──
class TeamPayrollBase(BaseModel):
    employee_id: str
    month: str  # "2024-01"
    basic_salary: float = 0
    bonus: float = 0
    deductions: float = 0
    net_pay: float = 0
    notes: Optional[str] = None
    status: str = "Draft"  # Draft, Processed, Paid

class TeamPayrollCreate(TeamPayrollBase):
    pass

class TeamPayrollInDB(TeamPayrollBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
