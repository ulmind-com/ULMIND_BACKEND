from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from typing import Optional, Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class NotificationCreate(BaseModel):
    user_id: str
    type: str # "client_new", "project_alert", "payment_received", "deadline", "system"
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool = False
    priority: str = "Info" # Info, Warning, Critical, Low, Medium, High
    category: str = "System" # CRM, Project, Finance, Team, Security, System
    recommended_action: Optional[str] = None

class NotificationInDB(NotificationCreate):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    
    model_config = {"populate_by_name": True}
