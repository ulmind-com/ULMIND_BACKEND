from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime, timezone
from bson import ObjectId

from app.db.database import get_db
from app.schemas.admin import AdminResponse, AdminUpdate
from app.api.deps import get_current_active_admin
from app.core.security import get_password_hash
from pydantic import BaseModel, EmailStr

router = APIRouter()

# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid admin ID format")


# ══════════════════════════════════════════════════════════════════════════════
#  TEAM MANAGEMENT (Admin Only)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[AdminResponse])
async def list_team_members(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """List all team members (Admins/Editors)."""
    team = await db["admins"].find({}).to_list(length=1000)
    return team


class CreateTeamMemberReq(BaseModel):
    full_name: str
    email: EmailStr
    role: str = "editor"
    initial_password: str
    position: Optional[str] = None
    experience: Optional[str] = None
    specialization: Optional[List[str]] = None
    linkedin_url: Optional[str] = None
    x_url: Optional[str] = None
    github_url: Optional[str] = None


@router.post("/", response_model=AdminResponse, status_code=201)
async def create_team_member(
    data: CreateTeamMemberReq, 
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Add a new staff member (Admin/Editor) to the system."""
    existing = await db["admins"].find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")
        
    hashed_password = get_password_hash(data.initial_password)
    now = datetime.now(timezone.utc)
    
    new_admin = data.model_dump(exclude={"initial_password"})
    new_admin.update({
        "password": hashed_password,
        "must_change_password": True,
        "status": "Active",
        "created_at": now,
        "updated_at": now
    })
    
    result = await db["admins"].insert_one(new_admin)
    created = await db["admins"].find_one({"_id": result.inserted_id})
    return created


@router.get("/{id}", response_model=AdminResponse)
async def get_team_member(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Get details of a specific team member."""
    member = await db["admins"].find_one({"_id": _parse_id(id)})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.put("/{id}", response_model=AdminResponse)
async def update_team_member(
    id: str,
    member_in: AdminUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """Update a team member's role, status, etc."""
    update_data = member_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
        
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db["admins"].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Member not found")
    return result


@router.delete("/{id}")
async def delete_team_member(
    id: str,
    db=Depends(get_db),
    current_admin=Depends(get_current_active_admin)
):
    """Remove a team member from the system."""
    obj_id = _parse_id(id)
    
    # Prevent self-deletion
    if str(obj_id) == str(current_admin.id):
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
        
    result = await db["admins"].delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
        
    return {"status": "success", "message": "Team member removed"}
