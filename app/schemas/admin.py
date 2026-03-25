from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

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
    id: str = Field(alias="_id")
    must_change_password: bool = True
    created_at: datetime
    updated_at: datetime

class AdminResponse(AdminBase):
    id: str = Field(alias="_id")
    must_change_password: bool
