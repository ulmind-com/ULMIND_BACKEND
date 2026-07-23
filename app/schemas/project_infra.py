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

class CustomInfraSection(BaseModel):
    id: Optional[str] = None
    label: str
    url: Optional[str] = ""
    email: Optional[str] = ""
    notes: Optional[str] = ""

class ProjectInfraCreate(BaseModel):
    project_name: str
    email_used: Optional[str] = ""
    frontend_url: Optional[str] = ""
    frontend_email: Optional[str] = ""
    backend_url: Optional[str] = ""
    backend_email: Optional[str] = ""
    database_url: Optional[str] = ""
    database_email: Optional[str] = ""
    server_location: Optional[str] = ""
    server_email: Optional[str] = ""
    custom_sections: Optional[List[CustomInfraSection]] = []

class ProjectInfraUpdate(BaseModel):
    project_name: Optional[str] = None
    email_used: Optional[str] = None
    frontend_url: Optional[str] = None
    frontend_email: Optional[str] = None
    backend_url: Optional[str] = None
    backend_email: Optional[str] = None
    database_url: Optional[str] = None
    database_email: Optional[str] = None
    server_location: Optional[str] = None
    server_email: Optional[str] = None
    custom_sections: Optional[List[CustomInfraSection]] = None

class ProjectInfraInDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    project_name: str
    email_used: str = ""
    frontend_url: str = ""
    frontend_email: str = ""
    backend_url: str = ""
    backend_email: str = ""
    database_url: str = ""
    database_email: str = ""
    server_location: str = ""
    server_email: str = ""
    custom_sections: List[CustomInfraSection] = []
    created_by: UserBase
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

class ProjectInfraListResponse(BaseModel):
    items: List[ProjectInfraInDB]
    total: int
