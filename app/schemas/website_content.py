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

class TestimonialMetric(BaseModel):
    label: str = Field(..., description="Metric label e.g. 'Quality'")
    score: str = Field(..., description="Metric score e.g. '5.0'")

class TestimonialBase(BaseModel):
    name: str = Field(..., description="Client Name")
    username: str = Field(..., description="Client sub-heading or designation")
    body: str = Field(..., description="Review content")
    rating: int = Field(default=5, description="Star rating 1-5")
    order: int = Field(default=0, description="Order to display")
    title: Optional[str] = Field(default=None, description="Card headline")
    location: Optional[str] = Field(default=None, description="Location e.g. 'Calgary, Canada'")
    flag: Optional[str] = Field(default=None, description="Country flag emoji")
    metrics: Optional[List[TestimonialMetric]] = Field(default=None, description="Score metrics (Quality, Cost, ...)")
    source: Optional[str] = Field(default=None, description="Review source e.g. 'Google', 'Clutch', 'Trustpilot'")

class TestimonialCreate(TestimonialBase):
    img: Optional[ImageInfo] = None
    companyLogo: Optional[ImageInfo] = None
    sourceLogo: Optional[ImageInfo] = None

class TestimonialUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    body: Optional[str] = None
    rating: Optional[int] = None
    order: Optional[int] = None
    title: Optional[str] = None
    location: Optional[str] = None
    flag: Optional[str] = None
    metrics: Optional[List[TestimonialMetric]] = None
    source: Optional[str] = None
    img: Optional[ImageInfo] = None
    companyLogo: Optional[ImageInfo] = None
    sourceLogo: Optional[ImageInfo] = None

class TestimonialResponse(TestimonialBase):
    id: PyObjectId = Field(alias="_id")
    img: Optional[ImageInfo] = None
    companyLogo: Optional[ImageInfo] = None
    sourceLogo: Optional[ImageInfo] = None
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


# ─── BLOG POSTS ───────────────────────────────────────────────────────────────

class BlogPostBase(BaseModel):
    title: str = Field(..., description="Blog Title")
    slug: str = Field(..., description="URL slug (e.g. 'how-to-integrate-chatgpt-2026')")
    excerpt: str = Field(..., description="Short summary for card view")
    content: str = Field(default="", description="Full markdown/html content")
    category: str = Field(default="Software Engineering", description="Industry/Category e.g. 'AI Integration', 'Custom Software'")
    service: Optional[str] = Field(default=None, description="Related service e.g. 'Web Development', 'Mobile Apps', 'Cloud'")
    tags: List[str] = Field(default_factory=list, description="Tags/Hashtags e.g. ['#AI Integration', '#ChatGPT']")
    author: str = Field(default="ULMIND Team", description="Author Name")
    authorRole: Optional[str] = Field(default="Tech Specialist", description="Author Role / Designation")
    authorAvatar: Optional[str] = Field(default=None, description="Author Avatar URL")
    readTime: str = Field(default="5 min read", description="Estimated read time")
    published: bool = Field(default=True, description="Whether blog is published live")
    featured: bool = Field(default=False, description="Featured post on top")
    order: int = Field(default=0, description="Display sort order")
    views: int = Field(default=0, description="View count")

class BlogPostCreate(BlogPostBase):
    coverImage: Optional[ImageInfo] = None

class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    service: Optional[str] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None
    authorRole: Optional[str] = None
    authorAvatar: Optional[str] = None
    readTime: Optional[str] = None
    published: Optional[bool] = None
    featured: Optional[bool] = None
    order: Optional[int] = None
    views: Optional[int] = None
    coverImage: Optional[ImageInfo] = None

class BlogPostResponse(BlogPostBase):
    id: PyObjectId = Field(alias="_id")
    coverImage: Optional[ImageInfo] = None
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
BlogPostBase.model_rebuild()
BlogPostResponse.model_rebuild()
