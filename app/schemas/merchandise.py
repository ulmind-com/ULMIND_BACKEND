from datetime import datetime
from typing import Optional, List, Annotated
from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator

PyObjectId = Annotated[str, BeforeValidator(str)]


# ── Sub-model stored per image ────────────────────────────────────────────────

class ImageInfo(BaseModel):
    """Stores a Cloudinary image reference — both the public URL and the
    internal public_id which is required to delete the image later."""
    url: str
    public_id: str


# ── Base fields shared across create / response ───────────────────────────────

class ProductBase(BaseModel):
    name: str = Field(..., description="Product name")
    caption: str = Field(..., description="Short tagline / subtitle")
    details: str = Field(..., description="Full product description")
    mrp: float = Field(..., gt=0, description="Maximum Retail Price (₹)")
    gst: float = Field(..., ge=0, description="GST percentage, e.g. 18.0")
    cgst: float = Field(..., ge=0, description="CGST percentage, e.g. 9.0")
    is_active: bool = Field(default=True, description="Visibility toggle")


# ── Create — used internally after images are uploaded ───────────────────────

class ProductCreate(ProductBase):
    images: List[ImageInfo] = Field(default_factory=list)


# ── Update — all fields optional (PATCH semantics via PUT) ───────────────────

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    caption: Optional[str] = None
    details: Optional[str] = None
    mrp: Optional[float] = Field(default=None, gt=0)
    gst: Optional[float] = Field(default=None, ge=0)
    cgst: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


# ── Response — returned to the client ────────────────────────────────────────

class ProductResponse(ProductBase):
    id: PyObjectId = Field(alias="_id")
    images: List[ImageInfo] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = {"populate_by_name": True}
