"""
Manager Tracking & Workforce Intelligence — Pydantic Schemas
=============================================================
Enterprise-grade schemas for live monitoring, task tracking,
time tracking, productivity intelligence, and smart alerts.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════
#  ENUMS
# ═══════════════════════════════════════════════════════════════

class EmployeeStatus(str, Enum):
    ONLINE = "Online"
    OFFLINE = "Offline"
    IDLE = "Idle"
    BREAK = "On Break"
    LEAVE = "On Leave"
    OVERTIME = "Overtime"

class TaskStage(str, Enum):
    PENDING = "Pending"
    ASSIGNED = "Assigned"
    ACCEPTED = "Accepted"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    APPROVED = "Approved"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"

class TaskPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"
    CRITICAL = "Critical"

class ReviewStatus(str, Enum):
    NOT_SUBMITTED = "Not Submitted"
    PENDING_REVIEW = "Pending Review"
    CHANGES_REQUESTED = "Changes Requested"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class AlertType(str, Enum):
    IDLE_TOO_LONG = "Employee Idle Too Long"
    INACTIVE = "Employee Inactive"
    DEADLINE_RISK = "Deadline Risk"
    TASK_DELAY = "Task Delay"
    OVERLOADED = "Employee Overloaded"
    UNDERUTILIZED = "Employee Underutilized"
    MISSED_CHECKIN = "Missed Check-In"
    MISSED_DEADLINE = "Missed Deadline"
    LOW_PRODUCTIVITY = "Low Productivity"
    HIGH_WORKLOAD = "High Workload"

class AlertSeverity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"

class PerformanceLevel(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    AVERAGE = "Average"
    NEEDS_ATTENTION = "Needs Attention"
    CRITICAL = "Critical"

class TimerAction(str, Enum):
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


# ═══════════════════════════════════════════════════════════════
#  ENTERPRISE TASK SCHEMAS
# ═══════════════════════════════════════════════════════════════

class TaskCommentCreate(BaseModel):
    content: str
    mentions: List[str] = []
    attachments: List[str] = []

class TaskCommentInDB(BaseModel):
    id: str
    author_id: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    content: str
    mentions: List[str] = []
    attachments: List[str] = []
    created_at: datetime

class SubtaskCreate(BaseModel):
    title: str
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "Medium"

class SubtaskInDB(BaseModel):
    id: str
    title: str
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "Medium"
    status: str = "Pending"
    completed_at: Optional[datetime] = None
    created_at: datetime

class EnterpriseTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_by_name: Optional[str] = None
    priority: str = "Medium"
    stage: str = "Pending"
    review_status: str = "Not Submitted"
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimated_hours: float = 0
    dependencies: List[str] = []  # task IDs this depends on
    tags: List[str] = []

class EnterpriseTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    priority: Optional[str] = None
    stage: Optional[str] = None
    review_status: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    completion_percent: Optional[int] = None
    dependencies: Optional[List[str]] = None
    tags: Optional[List[str]] = None

class EnterpriseTaskInDB(BaseModel):
    id: str = Field(alias="_id")
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_by_name: Optional[str] = None
    priority: str = "Medium"
    stage: str = "Pending"
    review_status: str = "Not Submitted"
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    estimated_hours: float = 0
    actual_hours: float = 0
    completion_percent: int = 0
    dependencies: List[str] = []
    subtasks: List[SubtaskInDB] = []
    comments: List[TaskCommentInDB] = []
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════
#  TIME TRACKING SCHEMAS
# ═══════════════════════════════════════════════════════════════

class TimeEntryAction(BaseModel):
    employee_id: str
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    notes: Optional[str] = None

class TimeEntryInDB(BaseModel):
    id: str = Field(alias="_id")
    employee_id: str
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    action: str  # start, pause, resume, stop
    started_at: datetime
    paused_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    total_seconds: float = 0
    break_seconds: float = 0
    is_active: bool = True
    is_billable: bool = True
    notes: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
#  LIVE MONITORING SCHEMAS
# ═══════════════════════════════════════════════════════════════

class EmployeeLiveStatus(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    email: Optional[str] = None
    designation: Optional[str] = None
    team: Optional[str] = None
    profile_photo: Optional[str] = None
    status: str = "Offline"
    current_project: Optional[str] = None
    current_task: Optional[str] = None
    current_page: Optional[str] = None
    browser: Optional[str] = None
    device: Optional[str] = None
    os: Optional[str] = None
    login_time: Optional[datetime] = None
    session_duration_minutes: float = 0
    last_activity: Optional[datetime] = None
    ip_address: Optional[str] = None
    active_minutes: float = 0
    idle_minutes: float = 0


# ═══════════════════════════════════════════════════════════════
#  PRODUCTIVITY INTELLIGENCE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class ProductivityScore(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    productivity_score: float = 0
    efficiency_score: float = 0
    workload_percent: float = 0
    capacity_percent: float = 0
    task_completion_rate: float = 0
    deadline_accuracy: float = 0
    delay_frequency: float = 0
    avg_completion_hours: float = 0
    response_time_hours: float = 0
    quality_score: float = 0
    performance_level: str = "Average"


# ═══════════════════════════════════════════════════════════════
#  SMART ALERTS SCHEMAS
# ═══════════════════════════════════════════════════════════════

class SmartAlertInDB(BaseModel):
    id: str = Field(alias="_id")
    alert_type: str
    severity: str = "Warning"
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    title: str
    message: str
    is_resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
#  ACTIVITY TIMELINE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class ActivityTimelineEntry(BaseModel):
    id: str = Field(alias="_id")
    employee_id: str
    action: str  # login, logout, task_opened, task_updated, etc.
    description: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    metadata: dict = {}
    timestamp: datetime


# ═══════════════════════════════════════════════════════════════
#  WORKFORCE DASHBOARD SCHEMAS
# ═══════════════════════════════════════════════════════════════

class WorkforceDashboard(BaseModel):
    online_employees: int = 0
    offline_employees: int = 0
    active_employees: int = 0
    idle_employees: int = 0
    on_break: int = 0
    overtime: int = 0
    on_leave: int = 0
    running_tasks: int = 0
    delayed_tasks: int = 0
    blocked_tasks: int = 0
    completed_today: int = 0
    upcoming_deadlines: int = 0
    team_productivity: float = 0
    avg_response_time_hours: float = 0
    avg_completion_time_hours: float = 0
    total_working_hours_today: float = 0
