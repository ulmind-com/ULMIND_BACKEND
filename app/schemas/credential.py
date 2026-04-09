from datetime import datetime
from typing import Optional, Annotated
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

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
    id: PyObjectId = Field(alias="_id")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
