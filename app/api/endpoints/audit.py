from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.audit import AuditLogCreate, AuditLogInDB

router = APIRouter()

@router.get("/", response_model=List[AuditLogInDB])
async def list_audit_logs(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    action: Optional[str] = None,
):
    """List audit logs with optional action filter. Reads from both 'audit' and 'audit_logs' collections for compatibility."""
    query = {}
    if action:
        query["action"] = {"$regex": action, "$options": "i"}

    # Read from 'audit' collection (where event_trigger_service writes)
    logs_audit = await db["audit"].find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(length=limit)
    
    # Also read from 'audit_logs' if it has data
    logs_audit_logs = await db["audit_logs"].find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    # Merge and normalize
    all_logs = []
    for log in logs_audit:
        all_logs.append({
            "_id": str(log["_id"]),
            "user_id": log.get("admin_email", "system"),
            "event_type": log.get("action", "unknown"),
            "resource_type": log.get("resource_type", "system"),
            "resource_id": log.get("resource_id"),
            "old_value": log.get("old_value"),
            "new_value": log.get("new_value"),
            "description": log.get("details", ""),
            "ip_address": log.get("ip_address"),
            "user_agent": log.get("user_agent"),
            "created_at": log.get("timestamp", log.get("created_at", get_now())),
        })

    for log in logs_audit_logs:
        all_logs.append({
            "_id": str(log["_id"]),
            "user_id": log.get("user_id", "system"),
            "event_type": log.get("event_type", "unknown"),
            "resource_type": log.get("resource_type", "system"),
            "resource_id": log.get("resource_id"),
            "old_value": log.get("old_value"),
            "new_value": log.get("new_value"),
            "description": log.get("description", ""),
            "ip_address": log.get("ip_address"),
            "user_agent": log.get("user_agent"),
            "created_at": log.get("created_at", get_now()),
        })

    # Sort by created_at descending
    all_logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return all_logs[:limit]


@router.get("/activity-feed")
async def get_activity_feed(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Get activity feed from activity_logs collection."""
    logs = await db["activity_logs"].find({}).sort("timestamp", -1).skip(skip).limit(limit).to_list(length=limit)

    activities = []
    for log in logs:
        activities.append({
            "_id": str(log["_id"]),
            "event_type": log.get("event_type", "unknown"),
            "resource_type": log.get("resource_type", ""),
            "resource_id": log.get("resource_id", ""),
            "action_description": log.get("action_description", ""),
            "performed_by": log.get("performed_by", "system"),
            "timestamp": log.get("timestamp", get_now()),
        })

    return activities
