from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.datetime_utils import get_now
from bson import ObjectId
import uuid
import logging

from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectSummaryResponse,
    DeploymentCreate, DeploymentUpdate, DeploymentInDB,
    EnvVarCreate, EnvVarUpdate, EnvVarInDB,
)

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "projects"


# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID format")


# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT CRUD  (all admin-protected)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[ProjectSummaryResponse])
async def list_projects(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """List all projects (summary view — no env_vars / deployments)."""
    projects = await db[COLLECTION].find(
        {},
        # Exclude heavy sub-documents from list view for performance
        {"env_vars": 0, "deployments": 0},
    ).to_list(length=500)
    return projects


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_in: ProjectCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Create a new project with optional initial deployments and env vars."""
    now = get_now()

    # Assign UUIDs to each embedded sub-document
    deployments = [
        {**dep.model_dump(), "id": str(uuid.uuid4())}
        for dep in project_in.deployments
    ]
    env_vars = [
        {**ev.model_dump(), "id": str(uuid.uuid4())}
        for ev in project_in.env_vars
    ]

    doc = {
        **project_in.model_dump(exclude={"deployments", "env_vars"}),
        "deployments": deployments,
        "env_vars": env_vars,
        "created_at": now,
        "updated_at": now,
    }

    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return created


@router.get("/{id}", response_model=ProjectResponse)
async def get_project(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Get full project details including all env vars and deployments."""
    project = await db[COLLECTION].find_one({"_id": _parse_id(id)})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{id}", response_model=ProjectResponse)
async def update_project(
    id: str,
    project_in: ProjectUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update project details (does not touch env_vars or deployments)."""
    update_data = project_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    update_data["updated_at"] = get_now()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": _parse_id(id)},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.delete("/{id}")
async def delete_project(
    id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Permanently delete a project and all its data."""
    result = await db[COLLECTION].delete_one({"_id": _parse_id(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "success", "message": "Project deleted successfully"}


# ══════════════════════════════════════════════════════════════════════════════
#  ENV VARS SUB-RESOURCE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{id}/env", response_model=ProjectResponse)
async def add_env_var(
    id: str,
    env_in: EnvVarCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Add a new environment variable to the project."""
    obj_id = _parse_id(id)
    new_env = {**env_in.model_dump(), "id": str(uuid.uuid4())}

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {
            "$push": {"env_vars": new_env},
            "$set": {"updated_at": get_now()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.put("/{id}/env/{env_id}", response_model=ProjectResponse)
async def update_env_var(
    id: str,
    env_id: str,
    env_in: EnvVarUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update a specific environment variable by its ID."""
    obj_id = _parse_id(id)
    update_data = env_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    # Build positional $set for the matched array element
    set_fields = {f"env_vars.$.{k}": v for k, v in update_data.items()}
    set_fields["updated_at"] = get_now()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id, "env_vars.id": env_id},
        {"$set": set_fields},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project or env variable not found")
    return result


@router.delete("/{id}/env/{env_id}", response_model=ProjectResponse)
async def delete_env_var(
    id: str,
    env_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Remove an environment variable from the project."""
    obj_id = _parse_id(id)

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {
            "$pull": {"env_vars": {"id": env_id}},
            "$set": {"updated_at": get_now()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  DEPLOYMENTS SUB-RESOURCE
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{id}/deployments", response_model=ProjectResponse)
async def add_deployment(
    id: str,
    dep_in: DeploymentCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Add a new deployment entry to the project."""
    obj_id = _parse_id(id)
    new_dep = {**dep_in.model_dump(), "id": str(uuid.uuid4())}

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {
            "$push": {"deployments": new_dep},
            "$set": {"updated_at": get_now()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.put("/{id}/deployments/{dep_id}", response_model=ProjectResponse)
async def update_deployment(
    id: str,
    dep_id: str,
    dep_in: DeploymentUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update a specific deployment entry by its ID."""
    obj_id = _parse_id(id)
    update_data = dep_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    set_fields = {f"deployments.$.{k}": v for k, v in update_data.items()}
    set_fields["updated_at"] = get_now()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id, "deployments.id": dep_id},
        {"$set": set_fields},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project or deployment not found")
    return result


@router.delete("/{id}/deployments/{dep_id}", response_model=ProjectResponse)
async def delete_deployment(
    id: str,
    dep_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Remove a deployment entry from the project."""
    obj_id = _parse_id(id)

    result = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {
            "$pull": {"deployments": {"id": dep_id}},
            "$set": {"updated_at": get_now()},
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result
