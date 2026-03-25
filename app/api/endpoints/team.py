from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime, timezone
from app.db.database import get_db
from app.schemas.admin import AdminResponse
from app.core.security import get_password_hash
from pydantic import BaseModel, EmailStr

router = APIRouter()

@router.get("/", response_model=List[AdminResponse])
async def get_team(db=Depends(get_db)):
    team = await db["admins"].find({}).to_list(length=1000)
    return team

class CreateTeamMemberReq(BaseModel):
    email: EmailStr
    role: str = "editor"
    initial_password: str

@router.post("/", response_model=AdminResponse, status_code=201)
async def create_team_member(data: CreateTeamMemberReq, db=Depends(get_db)):
    existing = await db["admins"].find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")
        
    hashed_password = get_password_hash(data.initial_password)
    
    new_admin = {
        "email": data.email,
        "role": data.role,
        "password": hashed_password,
        "must_change_password": True,
        "status": "Active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await db["admins"].insert_one(new_admin)
    created_admin = await db["admins"].find_one({"_id": result.inserted_id})
    
    return created_admin
