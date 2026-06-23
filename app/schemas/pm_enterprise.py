from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.core.datetime_utils import get_now

# ── PM Tasks ──
class PMTaskBase(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    status: str = "Backlog"  # Backlog, Pending, In Progress, Review, Testing, Completed, Archived
    priority: str = "Medium"  # Low, Medium, High, Critical
    assignee_id: Optional[str] = None
    reporter_id: Optional[str] = None
    due_date: Optional[datetime] = None
    estimated_hours: float = 0
    actual_hours: float = 0
    labels: List[str] = []
    subtasks: List[str] = []
    dependencies: List[str] = []
    checklist: List[dict] = []  # [{"text": "...", "done": false}]
    attachments: List[str] = []
    order: int = 0

class PMTaskCreate(PMTaskBase):
    pass

class PMTaskInDB(PMTaskBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# ── PM Milestones ──
class PMMilestoneBase(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: str = "Pending"  # Pending, In Progress, Completed, Delayed
    completion_pct: float = 0

class PMMilestoneCreate(PMMilestoneBase):
    pass

class PMMilestoneInDB(PMMilestoneBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# ── PM Time Logs ──
class PMTimeLogBase(BaseModel):
    project_id: str
    task_id: Optional[str] = None
    employee_id: str
    hours: float
    notes: Optional[str] = None
    log_date: datetime

class PMTimeLogCreate(PMTimeLogBase):
    pass

class PMTimeLogInDB(PMTimeLogBase):
    id: str = Field(alias="_id")
    created_at: datetime

# ── PM Files ──
class PMFileBase(BaseModel):
    project_id: str
    title: str
    folder: str = "Deliverables"  # Requirements, Designs, Development, Testing, Contracts, Deliverables
    file_url: str
    size_bytes: int = 0
    uploaded_by: Optional[str] = None

class PMFileCreate(PMFileBase):
    pass

class PMFileInDB(PMFileBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# ── PM Feedback ──
class PMFeedbackBase(BaseModel):
    project_id: str
    client_id: Optional[str] = None
    content: str
    rating: Optional[int] = None  # 1-5
    status: str = "Open"  # Open, Acknowledged, Resolved

class PMFeedbackCreate(PMFeedbackBase):
    pass

class PMFeedbackInDB(PMFeedbackBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# ── PM Expenses (Budget Tracking) ──
class PMExpenseBase(BaseModel):
    project_id: str
    category: str = "Development"  # Development, Design, Marketing, Operations, Miscellaneous
    amount: float
    description: str
    date: datetime

class PMExpenseCreate(PMExpenseBase):
    pass

class PMExpenseInDB(PMExpenseBase):
    id: str = Field(alias="_id")
    created_at: datetime
