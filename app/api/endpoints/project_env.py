from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from bson import ObjectId
import logging

from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.core.datetime_utils import get_now
from app.schemas.project_env import (
    ProjectEnvCreate, ProjectEnvUpdate, ProjectEnvInDB, ProjectEnvHistoryInDB
)
from app.core.encryption import encrypt_value, decrypt_value

router = APIRouter()
logger = logging.getLogger(__name__)

ENV_COLLECTION = "project_envs"
HISTORY_COLLECTION = "project_env_history"

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

def check_super_admin(admin: dict):
    if admin.get("role") != "Super Admin":
        raise HTTPException(status_code=403, detail="Super Admin privileges required to modify environment variables.")

@router.get("/{project_id}/env", response_model=List[ProjectEnvInDB])
async def list_env_vars(
    project_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """List all environment variables for a project (decrypted for viewing)."""
    envs = await db[ENV_COLLECTION].find({"project_id": project_id}).to_list(1000)
    
    # Decrypt values
    for env in envs:
        env["value"] = decrypt_value(env.get("value", ""))
    
    return envs

@router.post("/{project_id}/env", response_model=ProjectEnvInDB)
async def add_env_var(
    project_id: str,
    env_in: ProjectEnvCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Add a new environment variable (Super Admin only)."""
    check_super_admin(_admin)
    
    now = get_now()
    doc = env_in.model_dump()
    doc["project_id"] = project_id
    
    # Check for duplicate key in the same environment
    existing = await db[ENV_COLLECTION].find_one({"project_id": project_id, "key": doc["key"], "environment": doc["environment"]})
    if existing:
        raise HTTPException(status_code=400, detail=f"Key {doc['key']} already exists in {doc['environment']} environment.")
    
    # Encrypt value
    raw_value = doc["value"]
    doc["value"] = encrypt_value(raw_value)
    doc["created_at"] = now
    doc["updated_at"] = now
    
    result = await db[ENV_COLLECTION].insert_one(doc)
    created = await db[ENV_COLLECTION].find_one({"_id": result.inserted_id})
    
    # Audit log
    history_doc = {
        "env_id": str(result.inserted_id),
        "project_id": project_id,
        "changed_by": _admin.get("email", "admin"),
        "action": "Create",
        "previous_value": None,
        "new_value": encrypt_value(raw_value), # Always store encrypted in history too!
        "timestamp": now
    }
    await db[HISTORY_COLLECTION].insert_one(history_doc)
    
    # Return with decrypted value so UI sees it
    created["value"] = raw_value
    return created

@router.put("/{project_id}/env/{env_id}", response_model=ProjectEnvInDB)
async def update_env_var(
    project_id: str,
    env_id: str,
    env_in: ProjectEnvUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update environment variable (Super Admin only). Logs history."""
    check_super_admin(_admin)
    
    obj_id = _parse_id(env_id)
    existing = await db[ENV_COLLECTION].find_one({"_id": obj_id, "project_id": project_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Environment variable not found")
        
    update_data = env_in.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
        
    now = get_now()
    
    previous_value_encrypted = existing.get("value")
    new_value_encrypted = previous_value_encrypted
    
    if "value" in update_data:
        raw_value = update_data["value"]
        new_value_encrypted = encrypt_value(raw_value)
        update_data["value"] = new_value_encrypted
        
    update_data["updated_at"] = now
    
    updated = await db[ENV_COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True
    )
    
    # Audit log
    history_doc = {
        "env_id": env_id,
        "project_id": project_id,
        "changed_by": _admin.get("email", "admin"),
        "action": "Update",
        "previous_value": previous_value_encrypted,
        "new_value": new_value_encrypted,
        "timestamp": now
    }
    await db[HISTORY_COLLECTION].insert_one(history_doc)
    
    updated["value"] = decrypt_value(updated["value"])
    return updated

@router.get("/{project_id}/env/{env_id}/history", response_model=List[ProjectEnvHistoryInDB])
async def get_env_history(
    project_id: str,
    env_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """View the audit trail of a specific environment variable."""
    history = await db[HISTORY_COLLECTION].find({"env_id": env_id}).sort("timestamp", -1).to_list(100)
    
    # Decrypt values for viewing
    for h in history:
        if h.get("previous_value"):
            h["previous_value"] = decrypt_value(h["previous_value"])
        if h.get("new_value"):
            h["new_value"] = decrypt_value(h["new_value"])
            
    return history

@router.delete("/{project_id}/env/{env_id}")
async def delete_env_var(
    project_id: str,
    env_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Security Requirement: .env records must NEVER be deletable from the UI."""
    raise HTTPException(status_code=403, detail="Security Policy: Environment variables cannot be deleted to preserve the audit trail.")

@router.post("/{project_id}/env/import")
async def import_env_file(
    project_id: str,
    content: str = Body(..., embed=True),
    environment: str = Body("production", embed=True),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Import a .env string and securely parse it."""
    check_super_admin(_admin)
    
    lines = content.split("\n")
    imported_count = 0
    now = get_now()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
            
        parts = line.split("=", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip().strip("\"'")
            
            existing = await db[ENV_COLLECTION].find_one({"project_id": project_id, "key": key, "environment": environment})
            
            if existing:
                # Update existing
                prev_enc = existing.get("value")
                new_enc = encrypt_value(val)
                if prev_enc != new_enc:
                    await db[ENV_COLLECTION].update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"value": new_enc, "updated_at": now}}
                    )
                    # Log History
                    await db[HISTORY_COLLECTION].insert_one({
                        "env_id": str(existing["_id"]),
                        "project_id": project_id,
                        "changed_by": _admin.get("email", "admin"),
                        "action": "Import (Update)",
                        "previous_value": prev_enc,
                        "new_value": new_enc,
                        "timestamp": now
                    })
                    imported_count += 1
            else:
                # Create new
                new_enc = encrypt_value(val)
                doc = {
                    "project_id": project_id,
                    "key": key,
                    "value": new_enc,
                    "environment": environment,
                    "description": "Imported from file",
                    "created_at": now,
                    "updated_at": now
                }
                res = await db[ENV_COLLECTION].insert_one(doc)
                await db[HISTORY_COLLECTION].insert_one({
                    "env_id": str(res.inserted_id),
                    "project_id": project_id,
                    "changed_by": _admin.get("email", "admin"),
                    "action": "Import (Create)",
                    "previous_value": None,
                    "new_value": new_enc,
                    "timestamp": now
                })
                imported_count += 1

    return {"message": f"Successfully imported {imported_count} variables.", "count": imported_count}
