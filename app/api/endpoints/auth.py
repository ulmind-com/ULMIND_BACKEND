from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from app.db.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.schemas.admin import AdminResponse, AdminInDB
from app.api.deps import get_current_admin
from app.core.cloudinary import upload_image, delete_image, PROFILE_FOLDER

router = APIRouter()

class LoginJSON(BaseModel):
    email: str
    password: str

@router.post("/login")
async def login(login_data: LoginJSON, db=Depends(get_db)):
    admin = await db["admins"].find_one({"email": login_data.email})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(login_data.password, admin["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"id": str(admin["_id"]), "email": admin["email"], "role": admin["role"]})
    
    return {
        "token": token,
        "must_change_password": admin.get("must_change_password", True),
        "email": admin["email"]
    }

class ChangePasswordReq(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
async def change_password(
    data: ChangePasswordReq, 
    current_admin=Depends(get_current_admin),
    db=Depends(get_db)
):
    admin = await db["admins"].find_one({"_id": ObjectId(current_admin.id)})
    if not verify_password(data.current_password, admin["password"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        
    new_hashed_password = get_password_hash(data.new_password)
    
    await db["admins"].update_one(
        {"_id": ObjectId(current_admin.id)},
        {"$set": {"password": new_hashed_password, "must_change_password": False}}
    )
    
    return {"message": "Password changed successfully"}

@router.get("/me", response_model=AdminResponse)
async def get_me(current_admin=Depends(get_current_admin)):
    return current_admin

@router.patch("/me/profile-photo", response_model=AdminResponse)
async def update_my_profile_photo(
    file: UploadFile = File(...),
    current_admin=Depends(get_current_admin),
    db=Depends(get_db)
):
    """Upload or update the logged-in admin's profile photo."""
    # 1. Delete old photo if exists
    if current_admin.profile_photo and current_admin.profile_photo.public_id:
        await delete_image(current_admin.profile_photo.public_id)
        
    # 2. Upload new photo
    file_bytes = await file.read()
    image_info = await upload_image(file_bytes, file.filename, folder=PROFILE_FOLDER)
    
    # 3. Update DB
    result = await db["admins"].find_one_and_update(
        {"_id": ObjectId(current_admin.id)},
        {"$set": {
            "profile_photo": image_info,
            "updated_at": datetime.now(timezone.utc)
        }},
        return_document=True
    )
    return result

@router.delete("/me/profile-photo", response_model=AdminResponse)
async def delete_my_profile_photo(
    current_admin=Depends(get_current_admin),
    db=Depends(get_db)
):
    """Remove the logged-in admin's profile photo."""
    if not current_admin.profile_photo:
        raise HTTPException(status_code=400, detail="No profile photo to delete")
        
    await delete_image(current_admin.profile_photo.public_id)
    
    result = await db["admins"].find_one_and_update(
        {"_id": ObjectId(current_admin.id)},
        {
            "$set": {"updated_at": datetime.now(timezone.utc)},
            "$unset": {"profile_photo": ""}
        },
        return_document=True
    )
    return result
