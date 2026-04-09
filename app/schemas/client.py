from datetime import datetime
from typing import Optional, Annotated
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class ClientBase(BaseModel):
    companyName: str
    contactEmail: str
    status: str = "Active"

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    companyName: Optional[str] = None
    contactEmail: Optional[str] = None
    status: Optional[str] = None

class ClientResponse(ClientBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
