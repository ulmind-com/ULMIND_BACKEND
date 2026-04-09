from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.db.database import get_db
from app.schemas.user import UserCreate, UserUpdate, UserResponse, ImageInfo
from app.api.deps import get_current_active_admin
from app.core.security import get_password_hash
from app.core.cloudinary import upload_image, delete_image, USER_FOLDER

router = APIRouter()

COLLECTION = "users"

# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")


# ══════════════════════════════════════════════════════════════════════════════
#  USER MANAGEMENT (Admin Only)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[UserResponse])
async def list_public_users(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """List all public users (customers)."""
    users = await db[COLLECTION].find({}).to_list(length=1000)
    return users


@router.post("/", response_model=UserResponse, status_code=201)
async def create_public_user(
    email: str = Form(...),
    full_name: str = Form(...),
    phone: Optional[str] = Form(None),
    password: str = Form(...),
    status: str = Form(default="Active"),
    profile_photo: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Admin endpoint to manually add a new customer."""
    existing = await db[COLLECTION].find_one({"email": email})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")
        
    image_info = None
    if profile_photo:
        file_bytes = await profile_photo.read()
        image_info = await upload_image(file_bytes, profile_photo.filename, folder=USER_FOLDER)
        
    hashed_password = get_password_hash(password)
    now = datetime.now(timezone.utc)
    
    doc = {
        "email": email,
        "full_name": full_name,
        "phone": phone,
        "password": hashed_password,
        "status": status,
        "profile_photo": image_info,
        "created_at": now,
        "updated_at": now
    }
    
    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return created


@router.get("/{id}", response_model=UserResponse)
async def get_public_user(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Get detail for a specific customer."""
    user = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{id}", response_model=UserResponse)
async def update_public_user(
    id: str,
    user_in: UserUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Update a customer's basic details."""
    update_data = user_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db[COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.delete("/{id}")
async def delete_public_user(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Remove a customer and their profile photo from the system."""
    obj_id = _parse_id(id)
    user = await db[COLLECTION].find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.get("profile_photo"):
        await delete_image(user["profile_photo"]["public_id"])
        
    await db[COLLECTION].delete_one({"_id": obj_id})
    return {"status": "success", "message": "User deleted"}
