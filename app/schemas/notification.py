from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class NotificationCreate(BaseModel):
    user_id: str = "global"
    type: str # "client_new", "project_alert", "payment_received", "deadline", "system"
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool = False
    priority: str = "Medium" # Low, Medium, High, Critical (legacy rows may say "Warning"/"Info")
    category: str = "System" # CRM, Project, Finance, Team, Security, System
    recommended_action: Optional[str] = None

class NotificationInDB(NotificationCreate):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    # Added later — every one of these must stay optional so the notifications
    # already stored (which have none of them) keep validating.
    read_at: Optional[datetime] = None
    ai_generated: bool = False
    actor: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None

    model_config = {"populate_by_name": True}
