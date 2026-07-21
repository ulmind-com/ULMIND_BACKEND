from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
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


# NOTE: the fixed-path routes below (/stats, /read-all, /clear-read) are
# declared before the "/{id}/..." routes so FastAPI can never mistake one
# for an id.

@router.get("/stats")
async def notification_stats(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    """Counts for the dashboard header — cheaper than shipping every row."""
    total = await db["notifications"].count_documents({})
    unread = await db["notifications"].count_documents({"is_read": {"$ne": True}})

    by_priority = await db["notifications"].aggregate([
        {"$group": {"_id": {"$ifNull": ["$priority", "Medium"]}, "count": {"$sum": 1}}}
    ]).to_list(None)
    by_category = await db["notifications"].aggregate([
        {"$group": {"_id": {"$ifNull": ["$category", "System"]}, "count": {"$sum": 1}}}
    ]).to_list(None)

    return {
        "total": total,
        "unread": unread,
        "by_priority": {row["_id"]: row["count"] for row in by_priority},
        "by_category": {row["_id"]: row["count"] for row in by_category},
    }


@router.get("/", response_model=List[NotificationInDB])
async def list_notifications(
    priority: Optional[str] = None,
    category: Optional[str] = None,
    unread_only: bool = False,
    limit: int = Query(200, ge=1, le=500),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    query: dict = {}
    if priority:
        query["priority"] = priority
    if category:
        query["category"] = category
    if unread_only:
        query["is_read"] = {"$ne": True}

    notifications = await db["notifications"].find(query).sort("created_at", -1).to_list(length=limit)
    return notifications


@router.post("/", response_model=NotificationInDB, status_code=201)
async def create_notification(notif_in: NotificationCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    doc = notif_in.model_dump()
    doc.update({"created_at": now})
    result = await db["notifications"].insert_one(doc)
    created = await db["notifications"].find_one({"_id": result.inserted_id})
    return created


@router.put("/read-all", response_model=dict)
async def mark_all_as_read(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    result = await db["notifications"].update_many(
        {"is_read": {"$ne": True}},
        {"$set": {"is_read": True, "read_at": get_now()}}
    )
    return {"status": "success", "updated": result.modified_count}


@router.delete("/clear-read", response_model=dict)
async def clear_read_notifications(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    """Remove notifications that have already been read. Unread alerts are
    deliberately left alone so nothing is lost before it is seen."""
    result = await db["notifications"].delete_many({"is_read": True})
    return {"status": "success", "deleted": result.deleted_count}


@router.put("/{id}/read", response_model=NotificationInDB)
async def mark_as_read(id: str, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    result = await db["notifications"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": {"is_read": True, "read_at": get_now()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.put("/{id}/unread", response_model=NotificationInDB)
async def mark_as_unread(id: str, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    result = await db["notifications"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": {"is_read": False}, "$unset": {"read_at": ""}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


@router.delete("/{id}", status_code=204)
async def delete_notification(id: str, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    result = await db["notifications"].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None
