from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from bson import ObjectId
from app.core.config import settings
from app.db.database import get_db
from app.schemas.admin import AdminInDB

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_admin(token: str = Depends(oauth2_scheme), db=Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        admin_id: str = payload.get("id")
        if admin_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    admin_record = await db["admins"].find_one({"_id": ObjectId(admin_id)})
    if admin_record is None:
        raise credentials_exception
    
    return AdminInDB(**admin_record)

async def get_current_active_admin(current_admin: AdminInDB = Depends(get_current_admin)):
    if current_admin.status != "Active":
        raise HTTPException(status_code=400, detail="Inactive admin")
    return current_admin
