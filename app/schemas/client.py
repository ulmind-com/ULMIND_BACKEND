from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

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
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
