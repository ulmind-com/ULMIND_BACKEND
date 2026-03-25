from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class CredentialBase(BaseModel):
    project_id: str
    name: str
    encrypted_value: str
    iv: str

class CredentialCreate(CredentialBase):
    pass

class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    encrypted_value: Optional[str] = None
    iv: Optional[str] = None

class CredentialResponse(CredentialBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
