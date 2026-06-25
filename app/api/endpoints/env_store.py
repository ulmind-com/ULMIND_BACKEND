from fastapi import APIRouter, Depends, HTTPException
from typing import List
from bson import ObjectId
import logging

from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.core.datetime_utils import get_now
from app.core.encryption import encrypt_value, decrypt_value
from app.schemas.env_store import (
    EnvStoreCreate, EnvStoreUpdate, EnvStoreInDB, EnvStoreListItem
)

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "env_store"


def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def _count_vars(content: str) -> int:
    """Count non-empty, non-comment lines that look like KEY=VALUE."""
    count = 0
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            count += 1
    return count


def _make_preview(content: str, max_lines: int = 3) -> str:
    """Return the first few KEY= entries as a preview snippet."""
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            lines.append(key)
            if len(lines) >= max_lines:
                break
    return ", ".join(lines)


# ─── LIST ALL ────────────────────────────────────────────────────
@router.get("", response_model=List[EnvStoreListItem])
async def list_env_stores(
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """List all saved .env entries (lightweight, no full content)."""
    docs = await db[COLLECTION].find().sort("updated_at", -1).to_list(500)

    items = []
    for doc in docs:
        raw = decrypt_value(doc.get("env_content", ""))
        doc["env_content"] = raw
        doc["var_count"] = _count_vars(raw)
        doc["preview"] = _make_preview(raw)
        items.append(doc)

    return items


# ─── GET SINGLE ──────────────────────────────────────────────────
@router.get("/{entry_id}", response_model=EnvStoreInDB)
async def get_env_store(
    entry_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Get a single .env entry with full decrypted content."""
    obj_id = _parse_id(entry_id)
    doc = await db[COLLECTION].find_one({"_id": obj_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Entry not found")

    raw = decrypt_value(doc.get("env_content", ""))
    doc["env_content"] = raw
    doc["var_count"] = _count_vars(raw)
    return doc


# ─── CREATE ──────────────────────────────────────────────────────
@router.post("", response_model=EnvStoreInDB)
async def create_env_store(
    payload: EnvStoreCreate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Create a new .env entry (encrypted at rest)."""
    # Check duplicate project name
    existing = await db[COLLECTION].find_one({"project_name": payload.project_name})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"An entry for '{payload.project_name}' already exists."
        )

    now = get_now()
    doc = {
        "project_name": payload.project_name,
        "env_content": encrypt_value(payload.env_content),
        "created_at": now,
        "updated_at": now,
    }

    result = await db[COLLECTION].insert_one(doc)
    created = await db[COLLECTION].find_one({"_id": result.inserted_id})

    # Return decrypted for immediate UI display
    created["env_content"] = payload.env_content
    created["var_count"] = _count_vars(payload.env_content)
    return created


# ─── UPDATE ──────────────────────────────────────────────────────
@router.put("/{entry_id}", response_model=EnvStoreInDB)
async def update_env_store(
    entry_id: str,
    payload: EnvStoreUpdate,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Update an existing .env entry."""
    obj_id = _parse_id(entry_id)
    existing = await db[COLLECTION].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # If project name is changing, check for duplicates
    if "project_name" in update_data and update_data["project_name"] != existing["project_name"]:
        dup = await db[COLLECTION].find_one({"project_name": update_data["project_name"]})
        if dup:
            raise HTTPException(
                status_code=400,
                detail=f"An entry for '{update_data['project_name']}' already exists."
            )

    raw_content = None
    if "env_content" in update_data:
        raw_content = update_data["env_content"]
        update_data["env_content"] = encrypt_value(raw_content)

    update_data["updated_at"] = get_now()

    updated = await db[COLLECTION].find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True,
    )

    # Decrypt for response
    if raw_content is not None:
        updated["env_content"] = raw_content
    else:
        updated["env_content"] = decrypt_value(updated["env_content"])

    updated["var_count"] = _count_vars(updated["env_content"])
    return updated


# ─── DELETE ──────────────────────────────────────────────────────
@router.delete("/{entry_id}")
async def delete_env_store(
    entry_id: str,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """Delete an .env entry permanently."""
    obj_id = _parse_id(entry_id)
    result = await db[COLLECTION].delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Deleted successfully"}
