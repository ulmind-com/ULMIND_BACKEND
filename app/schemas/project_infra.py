from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from typing import Annotated
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class UserBase(BaseModel):
    id: str
    name: str
    email: str
    profile_photo: Optional[str] = None

class ProjectInfraCreate(BaseModel):
    project_name: str
    email_used: str
    frontend_url: Optional[str] = ""
    backend_url: Optional[str] = ""
    database_url: Optional[str] = ""
    server_location: Optional[str] = ""

class ProjectInfraUpdate(BaseModel):
    project_name: Optional[str] = None
    email_used: Optional[str] = None
    frontend_url: Optional[str] = None
    backend_url: Optional[str] = None
    database_url: Optional[str] = None
    server_location: Optional[str] = None

class ProjectInfraInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    project_name: str
    email_used: str
    frontend_url: str = ""
    backend_url: str = ""
    database_url: str = ""
    server_location: str = ""
    created_by: UserBase
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

class ProjectInfraListResponse(BaseModel):
    items: List[ProjectInfraInDB]
    total: int
