from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from bson import ObjectId
from app.db.database import get_db
from app.core.datetime_utils import get_now
from app.api.deps import get_current_admin, get_current_super_admin
from app.schemas.admin_activity import AdminActivityDetailedResponse
from datetime import timedelta

router = APIRouter()

class HeartbeatReq(BaseModel):
    session_id: str

@router.post("/heartbeat")
async def heartbeat(req: HeartbeatReq, current_admin=Depends(get_current_admin), db=Depends(get_db)):
    """Called by frontend every 30s to keep session alive."""
    session = await db["admin_activity"].find_one({"_id": ObjectId(req.session_id), "admin_id": str(current_admin.id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    now = get_now()
    now_naive = now.replace(tzinfo=None)
    duration = (now_naive - session["login_time"]).total_seconds() / 60.0
    await db["admin_activity"].update_one(
        {"_id": ObjectId(req.session_id)},
        {"$set": {"last_heartbeat": now, "is_online": True, "duration_minutes": round(duration, 2)}}
    )
    return {"status": "ok"}

@router.get("/sessions", response_model=List[AdminActivityDetailedResponse])
async def get_all_sessions(current_admin=Depends(get_current_super_admin), db=Depends(get_db)):
    """Fetch all admin sessions. Only accessible by super admins."""
    # First, mark any sessions as offline if last_heartbeat is older than 2 minutes and they are still 'online'
    now = get_now()
    offline_threshold = now - timedelta(minutes=2)
    await db["admin_activity"].update_many(
        {"is_online": True, "last_heartbeat": {"$lt": offline_threshold}},
        [{"$set": {"is_online": False, "logout_time": "$last_heartbeat"}}] 
    )
    
    # Now fetch all sessions
    cursor = db["admin_activity"].find().sort("login_time", -1)
    sessions = await cursor.to_list(length=1000)
    
    # Fetch admin details to enrich the response
    admin_ids = [ObjectId(s["admin_id"]) for s in sessions]
    admins_cursor = db["admins"].find({"_id": {"$in": admin_ids}})
    admins_list = await admins_cursor.to_list(length=1000)
    admin_map = {str(a["_id"]): a for a in admins_list}
    
    enriched_sessions = []
    for s in sessions:
        admin = admin_map.get(s["admin_id"], {})
        s["admin_name"] = admin.get("full_name", "Unknown")
        s["admin_email"] = admin.get("email", "unknown@ulmind.com")
        s["admin_role"] = admin.get("role", "admin")
        
        photo = admin.get("profile_photo")
        s["admin_photo"] = photo.get("url") if photo else None
        
        # Calculate duration up to now if still online
        if s["is_online"]:
            s["duration_minutes"] = round((now.replace(tzinfo=None) - s["login_time"]).total_seconds() / 60.0, 2)
            
        enriched_sessions.append(s)
        
    return enriched_sessions
