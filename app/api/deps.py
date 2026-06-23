from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from bson import ObjectId
from app.core.config import settings
from app.db.database import get_db
from app.schemas.admin import AdminInDB

# Simple HTTPBearer — in Swagger UI, click "Authorize" and paste your token directly.
# Works exactly like Express.js: reads `Authorization: Bearer <token>` from the header.
bearer_scheme = HTTPBearer()


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db=Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        admin_id: str = payload.get("id")
        if admin_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception

    admin_record = await db["admins"].find_one({"_id": ObjectId(admin_id)})
    if admin_record is None:
        raise credentials_exception

    admin = AdminInDB(**admin_record)
    
    if request.method == "DELETE" and admin.role.lower() != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admins can perform deletion directly.")
        
    return admin


async def get_current_active_admin(current_admin: AdminInDB = Depends(get_current_admin)):
    if current_admin.status != "Active":
        raise HTTPException(status_code=400, detail="Inactive admin")
    return current_admin

async def get_current_super_admin(current_admin: AdminInDB = Depends(get_current_active_admin)):
    if current_admin.role.lower() != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin privileges required")
    return current_admin

async def get_current_admin_or_leader(current_admin: AdminInDB = Depends(get_current_active_admin)):
    allowed = ["super_admin", "admin", "team_leader"]
    if current_admin.role.lower() not in allowed:
        raise HTTPException(status_code=403, detail="Admin or Team Leader privileges required")
    return current_admin

async def require_mutation_rights(current_admin: AdminInDB = Depends(get_current_active_admin)):
    if current_admin.role.lower() == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot modify data")
    return current_admin
