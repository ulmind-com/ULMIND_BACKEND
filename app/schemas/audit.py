from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from datetime import datetime

class AuditLogCreate(BaseModel):
    user_id: str
    event_type: str
    resource_type: str # e.g., "client", "project", "user"
    resource_id: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    description: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditLogInDB(AuditLogCreate):
    id: str = Field(alias="_id")
    created_at: datetime
