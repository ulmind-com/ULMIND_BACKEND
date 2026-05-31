from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from pydantic import BaseModel, Field
from app.core.datetime_utils import get_now
from typing import Optional
from bson import ObjectId
from app.db.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.schemas.admin import AdminResponse, AdminInDB, AdminUpdate
from app.schemas.otp import ForgotPasswordRequest, VerifyOTPRequest, ResetPasswordRequest
from app.api.deps import get_current_admin
from app.core.cloudinary import upload_image, delete_image, PROFILE_FOLDER
from app.services import otp_service

router = APIRouter()


class LoginJSON(BaseModel):
    username: str = Field(..., description="Email address or Admin ID")
    password: str

@router.post("/login")
async def login(login_data: LoginJSON, db=Depends(get_db)):
    # 1. Determine if username is an Email or an ID
    query = {}
    try:
        # Check if it's a valid MongoDB ObjectId
        obj_id = ObjectId(login_data.username)
        query = {"$or": [{"email": login_data.username}, {"_id": obj_id}]}
    except Exception:
        # Not a valid ObjectId, search by email only
        query = {"email": login_data.username}
        
    admin = await db["admins"].find_one(query)
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(login_data.password, admin["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"id": str(admin["_id"]), "email": admin["email"], "role": admin["role"]})
    
    return {
        "token": token,
        "must_change_password": admin.get("must_change_password", True),
        "email": admin["email"],
        "id": str(admin["_id"])
    }

@router.patch("/me", response_model=AdminResponse)
async def update_my_profile(
    data: AdminUpdate,
    current_admin=Depends(get_current_admin),
    db=Depends(get_db)
):
    """Allows the logged-in admin to update their own professional bio and details."""
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided")
        
    update_data["updated_at"] = get_now()
    
    result = await db["admins"].find_one_and_update(
        {"_id": ObjectId(current_admin.id)},
        {"$set": update_data},
        return_document=True
    )
    return result

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
            "updated_at": get_now()
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
            "$set": {"updated_at": get_now()},
            "$unset": {"profile_photo": ""}
        },
        return_document=True
    )
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD — OTP FLOW
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db=Depends(get_db),
):
    """
    Step 1 — Request a 6-digit OTP to be sent to the given email.
    Rate limited: 5 requests/hour per email, 10 requests/hour per IP.
    Returns 404 if the user does not exist.
    """
    return await otp_service.request_otp(db, email=body.email, request=request)


@router.post("/verify-reset-otp")
async def verify_reset_otp(
    body: VerifyOTPRequest,
    db=Depends(get_db),
):
    """
    Step 2 — Verify the OTP entered by the user.
    On success, returns a 15-minute JWT reset_token.
    The OTP is single-use and locked after 10 failed attempts.
    """
    return await otp_service.verify_otp(db, email=body.email, otp=body.otp)


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db=Depends(get_db),
):
    """
    Step 3 — Set a new password using the reset_token from step 2.
    Validates password policy (min 8 chars, uppercase, lowercase, digit, special char).
    """
    return await otp_service.reset_password(
        db, reset_token=body.reset_token, new_password=body.new_password
    )

