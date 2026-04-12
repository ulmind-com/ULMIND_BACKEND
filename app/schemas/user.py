from datetime import datetime
from typing import Optional, List, Annotated
from app.core.datetime_utils import get_now
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class ImageInfo(BaseModel):
    url: str
    public_id: str

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    status: str = "Active"
    profile_photo: Optional[ImageInfo] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    email: Optional[EmailStr] = None

class UserResponse(UserBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = ConfigDict(populate_by_name=True)

# Rebuild models for Pydantic V2
UserBase.model_rebuild()
UserCreate.model_rebuild()
UserUpdate.model_rebuild()
UserResponse.model_rebuild()
