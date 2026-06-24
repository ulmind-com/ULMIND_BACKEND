from datetime import datetime
from typing import Optional, Annotated
from app.core.datetime_utils import get_now
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator
from app.schemas.crm import ClientCRMData

PyObjectId = Annotated[str, BeforeValidator(str)]

class ClientBase(BaseModel):
    companyName: str
    contactName: Optional[str] = None
    contactEmail: str
    phone: Optional[str] = None
    industry: Optional[str] = None
    assigned_manager: Optional[str] = None
    revenue: float = 0.0
    lifetime_value: float = 0.0
    address: Optional[str] = None
    social_links: dict = Field(default_factory=dict)
    status: str = "Active"
    crm_data: Optional[ClientCRMData] = Field(default_factory=ClientCRMData)

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    companyName: Optional[str] = None
    contactName: Optional[str] = None
    contactEmail: Optional[str] = None
    status: Optional[str] = None

class ClientResponse(ClientBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = {"populate_by_name": True}
