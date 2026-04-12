from datetime import datetime
from typing import Optional, Annotated
from app.core.datetime_utils import get_now
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
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = {"populate_by_name": True}
