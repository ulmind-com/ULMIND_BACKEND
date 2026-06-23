from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.core.datetime_utils import get_now
from typing import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

# --- ProjectEnv Models ---
class ProjectEnvBase(BaseModel):
    project_id: str
    key: str
    value: str
    environment: str = "production" # development, staging, production
    description: Optional[str] = None

class ProjectEnvCreate(ProjectEnvBase):
    pass

class ProjectEnvUpdate(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    environment: Optional[str] = None
    description: Optional[str] = None

class ProjectEnvInDB(ProjectEnvBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    
    model_config = {"populate_by_name": True}

# --- ProjectEnvHistory Models ---
class ProjectEnvHistoryBase(BaseModel):
    env_id: str
    project_id: str
    changed_by: str
    action: str  # Create, Update, Import
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime

class ProjectEnvHistoryInDB(ProjectEnvHistoryBase):
    id: PyObjectId = Field(alias="_id")
    
    model_config = {"populate_by_name": True}
