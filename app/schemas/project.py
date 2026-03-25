from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "Planning"
    manager_id: str

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    manager_id: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
