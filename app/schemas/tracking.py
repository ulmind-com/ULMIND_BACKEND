from datetime import datetime
from typing import Optional, List, Annotated
from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class BatteryInfo(BaseModel):
    level: Optional[float] = None
    charging: Optional[bool] = None

class GeoInfo(BaseModel):
    range: Optional[List[float]] = None
    country: Optional[str] = None
    region: Optional[str] = None
    eu: Optional[str] = None
    timezone: Optional[str] = None
    city: Optional[str] = None
    ll: Optional[List[float]] = None
    metro: Optional[int] = None
    area: Optional[int] = None

class TrackingBase(BaseModel):
    username: str = "Guest"
    email: str = "Unknown"
    consent_status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Hardware & OS
    os: Optional[str] = None
    osVersion: Optional[str] = None
    platform: Optional[str] = None
    deviceMemory: Optional[float] = None
    hardwareConcurrency: Optional[int] = None

    # Browser & Capabilities
    browser: Optional[str] = None
    browserVersion: Optional[str] = None
    userAgent: Optional[str] = None
    cookieEnabled: Optional[bool] = None
    pdfViewerEnabled: Optional[bool] = None
    webdriver: Optional[bool] = None
    doNotTrack: Optional[str] = None

    # Network & Connectivity
    ip: Optional[str] = None
    onlineStatus: Optional[bool] = None
    connectionType: Optional[str] = None

    # Display & Interface
    screenResolution: Optional[str] = None
    colorDepth: Optional[int] = None
    pixelRatio: Optional[float] = None
    maxTouchPoints: Optional[int] = None

    # Localization
    timezone: Optional[str] = None
    language: Optional[str] = None

    battery: Optional[BatteryInfo] = None
    geo: Optional[GeoInfo] = None

class TrackingCreate(TrackingBase):
    pass

class TrackingResponse(TrackingBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)
