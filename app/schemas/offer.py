from datetime import datetime
from typing import Optional, Annotated
from app.core.datetime_utils import get_now
from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class ImageInfo(BaseModel):
    url: str
    public_id: str

class OfferBase(BaseModel):
    title: Optional[str] = Field(None, description="Title of the offer")
    description: Optional[str] = Field(None, description="Full description of the offer")
    start_time: Optional[datetime] = Field(None, description="Scheduled start time (IST)")
    end_time: Optional[datetime] = Field(None, description="Scheduled end time (IST)")
    is_active: bool = Field(default=True, description="Manual toggle for visibility")
    color1: Optional[str] = Field(None, description="Gradient start color")
    color2: Optional[str] = Field(None, description="Gradient end color")
    text_color: Optional[str] = Field(None, description="Text color")

class OfferCreate(OfferBase):
    image: Optional[ImageInfo] = None

class OfferUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_active: Optional[bool] = None
    color1: Optional[str] = None
    color2: Optional[str] = None
    text_color: Optional[str] = None

class OfferResponse(OfferBase):
    id: PyObjectId = Field(alias="_id")
    image: Optional[ImageInfo] = None
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)

    model_config = ConfigDict(populate_by_name=True)

# Rebuild models for Pydantic V2
OfferBase.model_rebuild()
OfferCreate.model_rebuild()
OfferUpdate.model_rebuild()
OfferResponse.model_rebuild()
