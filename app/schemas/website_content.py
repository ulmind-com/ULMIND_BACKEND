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

# Rebuild models
WebsiteStatBase.model_rebuild()
WebsiteStatResponse.model_rebuild()
TestimonialBase.model_rebuild()
TestimonialResponse.model_rebuild()
PortfolioProjectBase.model_rebuild()
PortfolioProjectResponse.model_rebuild()
