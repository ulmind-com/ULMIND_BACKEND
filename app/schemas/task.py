from pydantic import BaseModel, Field
from typing import Optional, List, Annotated
from datetime import datetime
from pydantic.functional_validators import BeforeValidator
import uuid

PyObjectId = Annotated[str, BeforeValidator(str)]


class ChecklistItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    done: bool = False


class DeliverableItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    status: str = "Pending"  # Pending, Submitted, Approved, Rejected
    file_url: Optional[str] = None


class TaskComment(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    content: str
    created_at: datetime


class TaskCreate(BaseModel):
    project_id: str
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str = "Pending"  # Pending, In Progress, Review, Testing, Completed, Blocked, Archived
    assigned_to: Optional[str] = None  # Single assignee (employee _id)
    assigned_to_multiple: List[str] = Field(default_factory=list, description="Multiple assignees (employee _ids)")
    assigned_to_names: List[str] = Field(default_factory=list, description="Names for display")
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    priority: str = "Medium"  # Low, Medium, High, Urgent
    estimated_hours: float = 0
    actual_hours: float = 0
    completion_percent: float = Field(default=0, ge=0, le=100)
    checklist: List[ChecklistItem] = Field(default_factory=list)
    deliverables: List[DeliverableItem] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list, description="File URLs")
    tags: List[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_to_multiple: Optional[List[str]] = None
    assigned_to_names: Optional[List[str]] = None
    due_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    priority: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    completion_percent: Optional[float] = Field(default=None, ge=0, le=100)
    checklist: Optional[List[ChecklistItem]] = None
    deliverables: Optional[List[DeliverableItem]] = None
    attachments: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    project_name: Optional[str] = None
    client_name: Optional[str] = None


class TaskInDB(TaskCreate):
    id: PyObjectId = Field(alias="_id")
    task_id: Optional[str] = None  # Auto-generated TASK-UL-XXX
    comments: List[TaskComment] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}
