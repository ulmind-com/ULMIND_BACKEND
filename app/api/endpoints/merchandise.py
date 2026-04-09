from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging

from app.db.database import get_db
from app.schemas.merchandise import ProductCreate, ProductUpdate, ProductResponse, ImageInfo
from app.api.deps import get_current_active_admin
from app.core.cloudinary import upload_image, delete_images

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "products"


# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID format")


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[ProductResponse])
async def list_products(db=Depends(get_db)):
    """List all active products (public)."""
    products = await db[COLLECTION].find({"is_active": True}).to_list(length=500)
    return products


@router.get("/{id}", response_model=ProductResponse)
async def get_product(id: str, db=Depends(get_db)):
    """Get a single product by ID (public)."""
    product = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    # ── Text fields via Form (because we also accept files) ──
    name: str = Form(...),
    caption: str = Form(...),
    details: str = Form(...),
    mrp: float = Form(...),
    gst: float = Form(...),
    cgst: float = Form(...),
    is_active: bool = Form(default=True),
    # ── Optional image files ──
    images: Optional[List[UploadFile]] = File(default=None),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """
    Create a new product. Accepts multipart/form-data.
    Upload 1 or more images alongside the product details.
    """
    uploaded_images: List[dict] = []

    if images:
        for img in images:
            if img.filename:  # skip empty slots
                file_bytes = await img.read()
                image_info = await upload_image(file_bytes, img.filename)
                uploaded_images.append(image_info)

    now = datetime.now(timezone.utc)
    doc = {
        "name": name,
        "caption": caption,
        "details": details,
        "mrp": mrp,
        "gst": gst,
        "cgst": cgst,
        "is_active": is_active,
        "images": uploaded_images,
        "created_at": now,
        "updated_at": now,
    }

    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return created


@router.put("/{id}", response_model=ProductResponse)
async def update_product(
    id: str,
    product_in: ProductUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """
    Update product text fields (name, caption, details, mrp, gst, cgst, is_active).
    Send JSON body. Does NOT touch images — use PATCH /{id}/images for that.
    """
    update_data = product_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db[COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result


@router.patch("/{id}/images", response_model=ProductResponse)
async def replace_product_images(
    id: str,
    images: List[UploadFile] = File(...),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """
    Replace ALL images for a product.
    1. Fetches the existing product to get old Cloudinary public_ids.
    2. Deletes all old images from Cloudinary.
    3. Uploads all new images.
    4. Saves the new image list to the DB.
    """
    obj_id = _parse_id(id)
    existing = await db[COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    # Delete old images from Cloudinary
    old_public_ids = [img["public_id"] for img in existing.get("images", []) if img.get("public_id")]
    if old_public_ids:
        logger.info(f"Deleting {len(old_public_ids)} old image(s) from Cloudinary for product {id}")
        await delete_images(old_public_ids)

    # Upload new images
    new_images: List[dict] = []
    for img in images:
        if img.filename:
            file_bytes = await img.read()
            image_info = await upload_image(file_bytes, img.filename)
            new_images.append(image_info)

    updated = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {"$set": {"images": new_images, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )
    return updated


@router.delete("/{id}")
async def delete_product(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """
    Delete a product and all its images from Cloudinary.
    """
    obj_id = _parse_id(id)
    existing = await db[COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")

    # Clean up Cloudinary images first
    public_ids = [img["public_id"] for img in existing.get("images", []) if img.get("public_id")]
    if public_ids:
        logger.info(f"Deleting {len(public_ids)} image(s) from Cloudinary for product {id}")
        await delete_images(public_ids)

    await db[COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success", "message": "Product and its images deleted successfully"}
