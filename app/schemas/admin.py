from datetime import datetime
from typing import Optional, List, Annotated
from app.core.datetime_utils import get_now
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class ImageInfo(BaseModel):
    url: str
    public_id: str

class AdminBase(BaseModel):
    full_name: str = Field(..., description="Full name of the admin")
    email: EmailStr
    role: str = "admin"
    status: str = "Active"
    profile_photo: Optional[ImageInfo] = None
    
    # New Bio & Position Fields
    position: Optional[str] = Field(None, description="e.g. CEO, CTO, Developer")
    experience: Optional[str] = Field(None, description="Years or description of experience")
    specialization: List[str] = Field(default_factory=list, description="e.g. ['REST API', 'React', 'DevOps']")
    
    # Social Links
    linkedin_url: Optional[str] = None
    x_url: Optional[str] = None
    github_url: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class AdminCreate(AdminBase):
    password: str

class AdminUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None
    must_change_password: Optional[bool] = None
    
    # Professional fields
    position: Optional[str] = None
    experience: Optional[str] = None
    specialization: Optional[List[str]] = None
    
    # Social links
    linkedin_url: Optional[str] = None
    x_url: Optional[str] = None
    github_url: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

class AdminInDB(AdminBase):
    id: PyObjectId = Field(alias="_id")
    must_change_password: bool = True
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = ConfigDict(populate_by_name=True)

class AdminResponse(AdminBase):
    id: PyObjectId = Field(alias="_id")
    must_change_password: bool
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
