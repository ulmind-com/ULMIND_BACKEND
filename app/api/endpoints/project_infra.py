from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
import logging

from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.core.datetime_utils import get_now
from app.schemas.project_infra import (
    ProjectInfraCreate, ProjectInfraUpdate, ProjectInfraInDB, ProjectInfraListResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "project_infra"

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@router.get("", response_model=ProjectInfraListResponse)
async def list_project_infra(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin),
):
    """List all project infrastructure details."""
    query = {}
    if search:
        query["project_name"] = {"$regex": search, "$options": "i"}

    total = await db[COLLECTION].count_documents(query)
    cursor = db[COLLECTION].find(query).sort("updated_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)

    return {"items": docs, "total": total}

@router.get("/{item_id}", response_model=ProjectInfraInDB)
async def get_project_infra(
    item_id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin),
):
    """Get a single project infrastructure entry."""
    obj_id = _parse_id(item_id)
    doc = await db[COLLECTION].find_one({"_id": obj_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")
    return doc

@router.post("", response_model=ProjectInfraInDB)
async def create_project_infra(
    payload: ProjectInfraCreate,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin),
):
    """Create a new project infrastructure entry."""
    now = get_now()
    
    user_data = {
        "id": str(current_admin.id),
        "name": getattr(current_admin, "full_name", "Unknown Admin") or "Unknown Admin",
        "email": current_admin.email or "",
        "profile_photo": current_admin.profile_photo.url if getattr(current_admin, "profile_photo", None) and hasattr(current_admin.profile_photo, "url") else (current_admin.profile_photo.get("url") if isinstance(getattr(current_admin, "profile_photo", None), dict) else None)
    }

    doc = payload.model_dump()
    doc.update({
        "created_by": user_data,
        "created_at": now,
        "updated_at": now,
    })

    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return created

@router.put("/{item_id}", response_model=ProjectInfraInDB)
async def update_project_infra(
    item_id: str,
    payload: ProjectInfraUpdate,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin),
):
    """Update a project infrastructure entry."""
    obj_id = _parse_id(item_id)
    existing = await db[COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # update user_data just in case admin updates it, we track who last updated it but we keep it as created_by or maybe rename to updated_by in UI.
    # For now we'll just update the created_by to the person who did the last edit so the UI shows who last touched it, as per requirements "er ke kakhon store koreche ter profile and name".
    user_data = {
        "id": str(current_admin.id),
        "name": getattr(current_admin, "full_name", "Unknown Admin") or "Unknown Admin",
        "email": current_admin.email or "",
        "profile_photo": current_admin.profile_photo.url if getattr(current_admin, "profile_photo", None) and hasattr(current_admin.profile_photo, "url") else (current_admin.profile_photo.get("url") if isinstance(getattr(current_admin, "profile_photo", None), dict) else None)
    }

    update_data["created_by"] = user_data
    update_data["updated_at"] = get_now()

    updated = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True,
    )
    return updated

@router.delete("/{item_id}")
async def delete_project_infra(
    item_id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin),
):
    """Delete a project infrastructure entry."""
    obj_id = _parse_id(item_id)
    result = await db[COLLECTION].delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Deleted successfully"}
