from datetime import datetime
from typing import Optional, Annotated, List
from app.core.datetime_utils import get_now
from pydantic import BaseModel, Field, ConfigDict
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]

class ImageInfo(BaseModel):
    url: str
    public_id: str

# ─── WEBSITE STATS ─────────────────────────────────────────────────────────────

class WebsiteStatBase(BaseModel):
    value: str = Field(..., description="The stat value (e.g., '7+')")
    label: str = Field(..., description="The stat label (e.g., 'Projects Completed')")
    order: int = Field(default=0, description="Order to display")

class WebsiteStatCreate(WebsiteStatBase):
    pass

class WebsiteStatUpdate(BaseModel):
    value: Optional[str] = None
    label: Optional[str] = None
    order: Optional[int] = None

class WebsiteStatResponse(WebsiteStatBase):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)
    model_config = ConfigDict(populate_by_name=True)

# ─── TESTIMONIALS (REVIEWS) ────────────────────────────────────────────────────

class TestimonialBase(BaseModel):
    name: str = Field(..., description="Client Name")
    username: str = Field(..., description="Client sub-heading or designation")
    body: str = Field(..., description="Review content")
    rating: int = Field(default=5, description="Star rating 1-5")
    order: int = Field(default=0, description="Order to display")

class TestimonialCreate(TestimonialBase):
    img: Optional[ImageInfo] = None

class TestimonialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    body: Optional[str] = None
    rating: Optional[int] = None
    order: Optional[int] = None

class TestimonialResponse(TestimonialBase):
    id: PyObjectId = Field(alias="_id")
    img: Optional[ImageInfo] = None
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)
    model_config = ConfigDict(populate_by_name=True)

# ─── PORTFOLIO PROJECTS ────────────────────────────────────────────────────────

class PortfolioProjectBase(BaseModel):
    title: str = Field(..., description="Project Title")
    description: str = Field(..., description="Project Description")
    type: str = Field(..., description="'web' or 'app'")
    category: str = Field(..., description="Project Category")
    timeline: str = Field(..., description="Project Timeline")
    teamSize: str = Field(..., description="Team Size")
    demoUrl: Optional[str] = None
    githubUrl: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    order: int = Field(default=0, description="Order to display")

class PortfolioProjectCreate(PortfolioProjectBase):
    image: Optional[ImageInfo] = None

class PortfolioProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    timeline: Optional[str] = None
    teamSize: Optional[str] = None
    demoUrl: Optional[str] = None
    githubUrl: Optional[str] = None
    languages: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    order: Optional[int] = None

class PortfolioProjectResponse(PortfolioProjectBase):
    id: PyObjectId = Field(alias="_id")
    image: Optional[ImageInfo] = None
    created_at: datetime = Field(alias="createdAt", default_factory=get_now)
    updated_at: datetime = Field(alias="updatedAt", default_factory=get_now)
    model_config = ConfigDict(populate_by_name=True)

# ─── FESTIVE BANNER (singleton hero decoration config) ─────────────────────────

class FestiveBannerBase(BaseModel):
    enabled: bool = Field(default=False, description="Master on/off switch")
    text: str = Field(default="Celebrating 80th Independence Day", description="Badge text shown in the hero")
    color1: str = Field(default="#FF9933", description="Left glow colour (hex)")
    color2: str = Field(default="#138808", description="Right glow colour (hex)")
    intensity: float = Field(default=0.48, ge=0.0, le=1.0, description="Glow strength 0-1 (light mode)")
    showChakra: bool = Field(default=True, description="Show the spinning Ashoka Chakra accent")
    startAt: Optional[datetime] = Field(default=None, description="Show from this moment (UTC). Null = no lower bound")
    endAt: Optional[datetime] = Field(default=None, description="Hide after this moment (UTC). Null = no upper bound")

class FestiveBannerUpdate(BaseModel):
    enabled: Optional[bool] = None
    text: Optional[str] = None
    color1: Optional[str] = None
    color2: Optional[str] = None
    intensity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    showChakra: Optional[bool] = None
    startAt: Optional[datetime] = None
    endAt: Optional[datetime] = None

class FestiveBannerResponse(FestiveBannerBase):
    # `active` is computed server-side: enabled AND now within [startAt, endAt].
    active: bool = Field(default=False, description="Whether the banner should render right now")
    model_config = ConfigDict(populate_by_name=True)


# Rebuild models
WebsiteStatBase.model_rebuild()
WebsiteStatResponse.model_rebuild()
TestimonialBase.model_rebuild()
TestimonialResponse.model_rebuild()
PortfolioProjectBase.model_rebuild()
PortfolioProjectResponse.model_rebuild()
