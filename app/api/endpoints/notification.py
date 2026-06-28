from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.notification import NotificationCreate, NotificationInDB

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

@router.get("/", response_model=List[NotificationInDB])
async def list_notifications(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    notifications = await db["notifications"].find({}).sort("created_at", -1).to_list(length=100)
    for n in notifications:
        n["_id"] = str(n["_id"])
    return notifications

@router.post("/", response_model=NotificationInDB, status_code=201)
async def create_notification(notif_in: NotificationCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    doc = notif_in.model_dump()
    doc.update({"created_at": now})
    result = await db["notifications"].insert_one(doc)
    created = await db["notifications"].find_one({"_id": result.inserted_id})
    return created

@router.put("/{id}/read", response_model=NotificationInDB)
async def mark_as_read(id: str, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    result = await db["notifications"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": {"is_read": True}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result

@router.put("/read-all", response_model=dict)
async def mark_all_as_read(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    await db["notifications"].update_many(
        {"is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"status": "success", "message": "All notifications marked as read"}
