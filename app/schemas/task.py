from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TaskComment(BaseModel):
    id: str
    user_id: str
    content: str
    created_at: datetime

class TaskCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    status: str = "Pending" # "Pending", "In Progress", "Review", "Testing", "Completed", "Archived"
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "Medium" # "Low", "Medium", "High", "Urgent"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None

class TaskInDB(TaskCreate):
    id: str = Field(alias="_id")
    comments: List[TaskComment] = []
    created_at: datetime
    updated_at: datetime
