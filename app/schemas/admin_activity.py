from datetime import datetime
from typing import Optional, Annotated
from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator
from app.core.datetime_utils import get_now

PyObjectId = Annotated[str, BeforeValidator(str)]

class AdminActivityBase(BaseModel):
    admin_id: PyObjectId
    login_time: datetime = Field(default_factory=get_now)
    last_heartbeat: datetime = Field(default_factory=get_now)
    logout_time: Optional[datetime] = None
    is_online: bool = True
    duration_minutes: float = 0.0

class AdminActivityCreate(AdminActivityBase):
    pass

class AdminActivityInDB(AdminActivityBase):
    id: PyObjectId = Field(alias="_id")

    model_config = ConfigDict(populate_by_name=True)

class AdminActivityResponse(AdminActivityBase):
    id: PyObjectId = Field(alias="_id")

    model_config = ConfigDict(populate_by_name=True)

# For nested response
class AdminActivityDetailedResponse(AdminActivityResponse):
    admin_name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_role: Optional[str] = None
    admin_photo: Optional[str] = None

AdminActivityBase.model_rebuild()
AdminActivityCreate.model_rebuild()
AdminActivityInDB.model_rebuild()
AdminActivityResponse.model_rebuild()
AdminActivityDetailedResponse.model_rebuild()
