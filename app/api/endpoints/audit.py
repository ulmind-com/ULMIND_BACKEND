from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
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
    skip: int = Query(0, ge=0)
):
    logs = await db["audit_logs"].find({}).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    return logs
