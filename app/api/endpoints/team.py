from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.core.datetime_utils import get_now
from bson import ObjectId

from app.db.database import get_db
from app.schemas.admin import AdminResponse, AdminUpdate, PublicAdminResponse
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


def _is_super_admin(admin) -> bool:
    """Roles are stored inconsistently (both "super_admin" and "SUPER_ADMIN"
    exist in the collection), so every comparison must be case-insensitive."""
    return (getattr(admin, "role", "") or "").lower() == "super_admin"


def _same_role(a: Optional[str], b: Optional[str]) -> bool:
    return (a or "").lower() == (b or "").lower()


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/public", response_model=List[PublicAdminResponse])
async def list_public_team(db=Depends(get_db)):
    """
    Publicly list active team members with non-sensitive details.
    Does not require authentication.
    """
    team = await db["admins"].find({"status": "Active"}).to_list(length=100)
    return team


# ══════════════════════════════════════════════════════════════════════════════
#  TEAM MANAGEMENT (Admin Only)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/")
async def list_team_members(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """List all team members (Admins/Editors)."""
    team = await db["admins"].find({}).to_list(length=1000)
    # Normalize for frontend
    result = []
    for member in team:
        member["_id"] = str(member["_id"])
        # Ensure required fields have defaults
        member.setdefault("role", "admin")
        member.setdefault("status", "Active")
        member.setdefault("must_change_password", False)
        member.setdefault("specialization", [])
        member.setdefault("employee_id", None)
        member.setdefault("position", None)
        result.append(member)
    return result


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
    current_admin=Depends(get_current_active_admin)
):
    """Add a new staff member (Admin/Editor) to the system."""
    existing = await db["admins"].find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")

    # Closes the obvious way around the update rule: without this a non-super
    # admin could simply create a brand new super_admin account.
    if _same_role(data.role, "super_admin") and not _is_super_admin(current_admin):
        raise HTTPException(
            status_code=403,
            detail="Only a super admin can grant the super admin role",
        )

    hashed_password = get_password_hash(data.initial_password)
    now = get_now()
    
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
    current_admin=Depends(get_current_active_admin)
):
    """Update a team member. Everyone with admin access may edit names,
    positions and status; only a super admin may change the access role.

    This is enforced here and not just hidden in the UI — without it any
    signed-in user could promote themselves to super_admin with one request.
    """
    update_data = member_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    target = await db["admins"].find_one({"_id": _parse_id(id)})
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")

    if "role" in update_data:
        if _same_role(update_data["role"], target.get("role")):
            # Unchanged role — drop it so a normal edit isn't blocked just
            # because the form echoed the existing value back.
            update_data.pop("role")
        elif not _is_super_admin(current_admin):
            raise HTTPException(
                status_code=403,
                detail="Only a super admin can change a member's access role",
            )

    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    update_data["updated_at"] = get_now()

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
