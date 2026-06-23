from fastapi import APIRouter, Depends, HTTPException, status
from app.db.database import get_db
from app.api.deps import get_current_admin, get_current_super_admin, AdminInDB
from app.schemas.delete_request import DeleteRequestCreate, DeleteRequestUpdate
from bson import ObjectId
from datetime import datetime
import math

router = APIRouter()
COLLECTION = "delete_requests"

def _parse_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@router.post("/")
async def create_delete_request(
    request_data: DeleteRequestCreate,
    db=Depends(get_db),
    admin: AdminInDB = Depends(get_current_admin)
):
    """Create a new deletion request for the Super Admin to approve."""
    now = datetime.utcnow()
    new_request = {
        "user_id": str(admin.id),
        "user_name": admin.full_name or admin.email,
        "user_email": admin.email,
        "item_type": request_data.item_type,
        "item_description": request_data.item_description,
        "endpoint": request_data.endpoint,
        "status": "pending",
        "created_at": now,
        "updated_at": now
    }
    
    result = await db[COLLECTION].insert_one(new_request)
    return {"status": "success", "id": str(result.inserted_id), "message": "Deletion request submitted successfully."}

@router.get("/")
async def get_delete_requests(
    page: int = 1,
    limit: int = 20,
    status_filter: str = None,
    db=Depends(get_db),
    super_admin: AdminInDB = Depends(get_current_super_admin)
):
    """Get all delete requests (Super Admin only)."""
    skip = (page - 1) * limit
    
    query = {}
    if status_filter:
        query["status"] = status_filter
        
    cursor = db[COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
    requests = await cursor.to_list(length=limit)
    
    total = await db[COLLECTION].count_documents(query)
    
    for req in requests:
        req["_id"] = str(req["_id"])
        
    return {
        "status": "success",
        "data": requests,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": math.ceil(total / limit)
        }
    }

@router.patch("/{id}/status")
async def update_delete_request_status(
    id: str,
    update_data: DeleteRequestUpdate,
    db=Depends(get_db),
    super_admin: AdminInDB = Depends(get_current_super_admin)
):
    """Approve or reject a delete request (Super Admin only)."""
    if update_data.status not in ["approved", "rejected", "pending"]:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    obj_id = _parse_id(id)
    
    result = await db[COLLECTION].update_one(
        {"_id": obj_id},
        {"$set": {"status": update_data.status, "updated_at": datetime.utcnow()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Delete request not found")
        
    return {"status": "success", "message": f"Delete request marked as {update_data.status}"}
