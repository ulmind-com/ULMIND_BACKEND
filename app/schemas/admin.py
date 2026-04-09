from datetime import datetime
from typing import Optional, List, Annotated
from pydantic import BaseModel, EmailStr, Field
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class AdminBase(BaseModel):
    email: EmailStr
    role: str = "admin"
    status: str = "Active"

class AdminCreate(AdminBase):
    password: str

class AdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None
    must_change_password: Optional[bool] = None

class AdminInDB(AdminBase):
    id: PyObjectId = Field(alias="_id")
    must_change_password: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class AdminResponse(AdminBase):
    id: PyObjectId = Field(alias="_id")
    must_change_password: bool
