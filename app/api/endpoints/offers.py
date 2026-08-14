from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging

from app.db.database import get_db
from app.core.datetime_utils import get_now
from app.schemas.offer import OfferCreate, OfferUpdate, OfferResponse, ImageInfo
from app.api.deps import get_current_active_admin
from app.core.cloudinary import upload_image, delete_image, OFFERS_FOLDER

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "offers"

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid offer ID format")

# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/active", response_model=List[OfferResponse])
async def list_active_offers(db=Depends(get_db)):
    """
    Returns currently valid offers.
    Criteria:
    1. is_active is True
    2. Current IST time is between start_time and end_time (if defined)
    """
    now = get_now()
    # MongoDB query logic:
    # (start_time is null OR now >= start_time) AND (end_time is null OR now <= end_time)
    query = {
        "is_active": True,
        "$and": [
            {"$or": [{"start_time": None}, {"start_time": {"$lte": now}}]},
            {"$or": [{"end_time": None}, {"end_time": {"$gte": now}}]}
        ]
    }
    offers = await db[COLLECTION].find(query).sort("created_at", -1).to_list(length=100)
    return offers

@router.get("/{id}", response_model=OfferResponse)
async def get_offer(id: str, db=Depends(get_db)):
    """Get a single offer by ID."""
    offer = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[OfferResponse])
async def list_all_offers(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """List all offers (Admin Only - includes inactive and expired)."""
    offers = await db[COLLECTION].find({}).sort("created_at", -1).to_list(length=500)
    return offers

@router.post("/", response_model=OfferResponse, status_code=201)
async def create_offer(
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    start_time: Optional[datetime] = Form(None),
    end_time: Optional[datetime] = Form(None),
    is_active: bool = Form(default=True),
    color1: Optional[str] = Form(None),
    color2: Optional[str] = Form(None),
    text_color: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Create a new offer with optional image."""
    image_info = None
    if image:
        file_bytes = await image.read()
        image_info = await upload_image(file_bytes, image.filename, folder=OFFERS_FOLDER)
        
    now = get_now()
    doc = {
        "title": title,
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "is_active": is_active,
        "color1": color1,
        "color2": color2,
        "text_color": text_color,
        "image": image_info,
        "created_at": now,
        "updated_at": now
    }
    
    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/{id}", response_model=OfferResponse)
async def update_offer(
    id: str,
    offer_in: OfferUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Update textual/scheduling fields of an offer."""
    update_data = offer_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = get_now()
    
    result = await db[COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Offer not found")
    return result

@router.patch("/{id}/image", response_model=OfferResponse)
async def update_offer_image(
    id: str,
    image: UploadFile = File(...),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Upload or replace the offer image."""
    obj_id = _parse_id(id)
    existing = await db[COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Offer not found")
        
    # Delete old image if exists
    if existing.get("image") and existing["image"].get("public_id"):
        await delete_image(existing["image"]["public_id"])
        
    # Upload new image
    file_bytes = await image.read()
    image_info = await upload_image(file_bytes, image.filename, folder=OFFERS_FOLDER)
    
    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {"$set": {"image": image_info, "updated_at": get_now()}},
        return_document=True
    )
    return result

@router.delete("/{id}")
async def delete_offer(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Delete an offer and its associated image from Cloudinary."""
    obj_id = _parse_id(id)
    existing = await db[COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Offer not found")
        
    # Clean up Cloudinary
    if existing.get("image") and existing["image"].get("public_id"):
        await delete_image(existing["image"]["public_id"])
        
    await db[COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success", "message": "Offer deleted successfully"}
