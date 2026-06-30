from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
from bson import ObjectId
import logging

from app.db.database import get_db
from app.core.datetime_utils import get_now
from app.schemas.website_content import (
    WebsiteStatCreate, WebsiteStatUpdate, WebsiteStatResponse,
    TestimonialCreate, TestimonialUpdate, TestimonialResponse,
    PortfolioProjectCreate, PortfolioProjectUpdate, PortfolioProjectResponse,
    ImageInfo
)
from app.api.deps import get_current_active_admin
from app.core.cloudinary import upload_image, delete_image, GENERAL_FOLDER

router = APIRouter()
logger = logging.getLogger(__name__)

STATS_COLLECTION = "website_stats"
TESTIMONIALS_COLLECTION = "testimonials"
PROJECTS_COLLECTION = "portfolio_projects"

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upload-image", response_model=ImageInfo)
async def upload_content_image(
    image: UploadFile = File(...),
    _admin=Depends(get_current_active_admin)
):
    """Upload an image for CMS content."""
    file_bytes = await image.read()
    image_info = await upload_image(file_bytes, image.filename, folder=GENERAL_FOLDER)
    return image_info


# ══════════════════════════════════════════════════════════════════════════════
#  WEBSITE STATS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/stats", response_model=List[WebsiteStatResponse])
async def list_stats(db=Depends(get_db)):
    """Get all website stats sorted by order."""
    stats = await db[STATS_COLLECTION].find({}).sort("order", 1).to_list(length=100)
    return stats

@router.post("/stats", response_model=WebsiteStatResponse, status_code=201)
async def create_stat(
    stat_in: WebsiteStatCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Create a new website stat."""
    now = get_now()
    doc = stat_in.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[STATS_COLLECTION].insert_one(doc)
    created = await db[STATS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/stats/{id}", response_model=WebsiteStatResponse)
async def update_stat(
    id: str,
    stat_in: WebsiteStatUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Update a website stat."""
    update_data = stat_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[STATS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Stat not found")
    return result

@router.delete("/stats/{id}")
async def delete_stat(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Delete a website stat."""
    result = await db[STATS_COLLECTION].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Stat not found")
    return {"status": "success"}

# ══════════════════════════════════════════════════════════════════════════════
#  TESTIMONIALS (REVIEWS)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/testimonials", response_model=List[TestimonialResponse])
async def list_testimonials(db=Depends(get_db)):
    """Get all testimonials sorted by order."""
    items = await db[TESTIMONIALS_COLLECTION].find({}).sort("order", 1).to_list(length=100)
    return items

@router.post("/testimonials", response_model=TestimonialResponse, status_code=201)
async def create_testimonial(
    item_in: TestimonialCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    now = get_now()
    doc = item_in.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[TESTIMONIALS_COLLECTION].insert_one(doc)
    created = await db[TESTIMONIALS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/testimonials/{id}", response_model=TestimonialResponse)
async def update_testimonial(
    id: str,
    item_in: TestimonialUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    update_data = item_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[TESTIMONIALS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return result

@router.delete("/testimonials/{id}")
async def delete_testimonial(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    obj_id = _parse_id(id)
    existing = await db[TESTIMONIALS_COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Testimonial not found")
        
    if existing.get("img") and existing["img"].get("public_id"):
        await delete_image(existing["img"]["public_id"])
        
    await db[TESTIMONIALS_COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success"}

# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/projects", response_model=List[PortfolioProjectResponse])
async def list_projects(db=Depends(get_db)):
    """Get all portfolio projects sorted by order."""
    items = await db[PROJECTS_COLLECTION].find({}).sort("order", 1).to_list(length=100)
    return items

@router.post("/projects", response_model=PortfolioProjectResponse, status_code=201)
async def create_project(
    item_in: PortfolioProjectCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    now = get_now()
    doc = item_in.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[PROJECTS_COLLECTION].insert_one(doc)
    created = await db[PROJECTS_COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/projects/{id}", response_model=PortfolioProjectResponse)
async def update_project(
    id: str,
    item_in: PortfolioProjectUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    update_data = item_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[PROJECTS_COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@router.delete("/projects/{id}")
async def delete_project(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    obj_id = _parse_id(id)
    existing = await db[PROJECTS_COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")
        
    if existing.get("image") and existing["image"].get("public_id"):
        await delete_image(existing["image"]["public_id"])
        
    await db[PROJECTS_COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success"}
