from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin, require_mutation_rights
from app.core.datetime_utils import get_now
from app.services.event_trigger_service import fire_event_background
from app.schemas.crm_enterprise import (
    CRMActivityCreate, CRMActivityUpdate, CRMActivityInDB,
    CRMMeetingCreate, CRMMeetingUpdate, CRMMeetingInDB,
    CRMContractCreate, CRMContractUpdate, CRMContractInDB,
    CRMDocumentCreate, CRMDocumentUpdate, CRMDocumentInDB
)

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def _client_query(client_id: Optional[str]) -> dict:
    """Filter by client, tolerating the two ways an unlinked record was stored
    historically (missing key, or an empty string)."""
    if not client_id:
        return {}
    return {"client_id": client_id}


async def _apply_update(db, collection: str, item_id: str, payload: dict, admin, event_type: str):
    """Shared PATCH-style update: only the keys the caller actually sent are
    written, so a partial edit can never blank out untouched fields."""
    obj_id = _parse_id(item_id)
    changes = {k: v for k, v in payload.items() if v is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")
    changes["updated_at"] = get_now()

    result = await db[collection].find_one_and_update(
        {"_id": obj_id},
        {"$set": changes},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Record not found")

    fire_event_background(
        event_type=event_type,
        resource_type=collection,
        resource_id=item_id,
        user_email=admin.email,
        data=changes,
        db=db
    )
    return result


async def _apply_delete(db, collection: str, item_id: str, admin, event_type: str):
    obj_id = _parse_id(item_id)
    existing = await db[collection].find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Record not found")

    await db[collection].delete_one({"_id": obj_id})
    fire_event_background(
        event_type=event_type,
        resource_type=collection,
        resource_id=item_id,
        user_email=admin.email,
        data={"deleted": True},
        db=db
    )
    return None

# ── DASHBOARD STATS ──
@router.get("/dashboard")
async def get_crm_dashboard_stats(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    # Clients created before crm_data existed have no stage — bucket them as
    # "Lead" so they still appear on the board instead of under a null key.
    pipeline = [
        {"$group": {
            "_id": {"$ifNull": ["$crm_data.stage", "Lead"]},
            "count": {"$sum": 1},
            "value": {"$sum": {"$ifNull": ["$revenue", 0]}}
        }},
        {"$sort": {"count": -1}}
    ]
    stage_stats = await db["clients"].aggregate(pipeline).to_list(None)

    total_clients = await db["clients"].count_documents({})
    total_leads = await db["clients"].count_documents(
        {"$or": [{"crm_data.stage": "Lead"}, {"crm_data.stage": {"$exists": False}}]}
    )
    active_clients = await db["clients"].count_documents({"status": "Active"})
    total_revenue = await db["clients"].aggregate(
        [{"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$revenue", 0]}}}}]
    ).to_list(None)
    revenue = total_revenue[0]["total"] if total_revenue else 0

    won = await db["clients"].count_documents({"crm_data.stage": {"$in": ["Won", "Active Client"]}})
    lost = await db["clients"].count_documents({"crm_data.stage": "Closed Lost"})
    decided = won + lost
    win_rate = round((won / decided) * 100, 1) if decided else 0.0

    # Section counts so the dashboard can link straight into each module.
    counts = {
        "activities": await db["crm_activities"].count_documents({}),
        "meetings": await db["crm_meetings"].count_documents({}),
        "contracts": await db["crm_contracts"].count_documents({}),
        "documents": await db["crm_documents"].count_documents({}),
    }

    contract_value = await db["crm_contracts"].aggregate(
        [{"$match": {"status": {"$ne": "expired"}}},
         {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$value", 0]}}}}]
    ).to_list(None)

    upcoming = await db["crm_meetings"].find(
        {"date": {"$gte": get_now()}, "status": "scheduled"}
    ).sort("date", 1).to_list(length=5)
    for m in upcoming:
        m["_id"] = str(m["_id"])

    return {
        "total_leads": total_leads,
        "total_clients": total_clients,
        "active_clients": active_clients,
        "revenue": revenue,
        "win_rate": win_rate,
        "won_count": won,
        "lost_count": lost,
        "counts": counts,
        "contract_value": contract_value[0]["total"] if contract_value else 0,
        "upcoming_meetings": upcoming,
        "pipeline_stats": stage_stats
    }

# ── ACTIVITIES ──
@router.get("/activities", response_model=List[CRMActivityInDB])
async def list_activities(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    activities = await db["crm_activities"].find(_client_query(client_id)).sort("created_at", -1).to_list(length=1000)
    return activities

@router.post("/activities", response_model=CRMActivityInDB, status_code=201)
async def create_activity(activity_in: CRMActivityCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = activity_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["crm_activities"].insert_one(doc)
    created = await db["crm_activities"].find_one({"_id": result.inserted_id})
    fire_event_background(
        event_type="crm_activity_created",
        resource_type="crm_activities",
        resource_id=str(result.inserted_id),
        user_email=admin.email,
        data=doc,
        db=db
    )
    return created

@router.put("/activities/{item_id}", response_model=CRMActivityInDB)
async def update_activity(item_id: str, payload: CRMActivityUpdate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_update(db, "crm_activities", item_id, payload.model_dump(exclude_unset=True), admin, "crm_activity_updated")

@router.delete("/activities/{item_id}", status_code=204)
async def delete_activity(item_id: str, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_delete(db, "crm_activities", item_id, admin, "crm_activity_deleted")

# ── MEETINGS ──
@router.get("/meetings", response_model=List[CRMMeetingInDB])
async def list_meetings(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    meetings = await db["crm_meetings"].find(_client_query(client_id)).sort("date", -1).to_list(length=1000)
    return meetings

@router.post("/meetings", response_model=CRMMeetingInDB, status_code=201)
async def create_meeting(meeting_in: CRMMeetingCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = meeting_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["crm_meetings"].insert_one(doc)
    created = await db["crm_meetings"].find_one({"_id": result.inserted_id})
    fire_event_background(
        event_type="crm_meeting_created",
        resource_type="crm_meetings",
        resource_id=str(result.inserted_id),
        user_email=admin.email,
        data=doc,
        db=db
    )
    return created

@router.put("/meetings/{item_id}", response_model=CRMMeetingInDB)
async def update_meeting(item_id: str, payload: CRMMeetingUpdate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_update(db, "crm_meetings", item_id, payload.model_dump(exclude_unset=True), admin, "crm_meeting_updated")

@router.delete("/meetings/{item_id}", status_code=204)
async def delete_meeting(item_id: str, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_delete(db, "crm_meetings", item_id, admin, "crm_meeting_deleted")

# ── CONTRACTS ──
@router.get("/contracts", response_model=List[CRMContractInDB])
async def list_contracts(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    contracts = await db["crm_contracts"].find(_client_query(client_id)).sort("created_at", -1).to_list(length=1000)
    return contracts

@router.post("/contracts", response_model=CRMContractInDB, status_code=201)
async def create_contract(contract_in: CRMContractCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = contract_in.model_dump()
    doc.update({"created_at": now, "updated_at": now})
    result = await db["crm_contracts"].insert_one(doc)
    created = await db["crm_contracts"].find_one({"_id": result.inserted_id})
    fire_event_background(
        event_type="crm_contract_created",
        resource_type="crm_contracts",
        resource_id=str(result.inserted_id),
        user_email=admin.email,
        data=doc,
        db=db
    )
    return created

@router.put("/contracts/{item_id}", response_model=CRMContractInDB)
async def update_contract(item_id: str, payload: CRMContractUpdate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_update(db, "crm_contracts", item_id, payload.model_dump(exclude_unset=True), admin, "crm_contract_updated")

@router.delete("/contracts/{item_id}", status_code=204)
async def delete_contract(item_id: str, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_delete(db, "crm_contracts", item_id, admin, "crm_contract_deleted")

# ── DOCUMENTS ──
@router.get("/documents", response_model=List[CRMDocumentInDB])
async def list_documents(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    documents = await db["crm_documents"].find(_client_query(client_id)).sort("created_at", -1).to_list(length=1000)
    return documents

@router.post("/documents", response_model=CRMDocumentInDB, status_code=201)
async def create_document(doc_in: CRMDocumentCreate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    now = get_now()
    doc = doc_in.model_dump()
    doc.update({
        "uploaded_by": admin.email,
        "created_at": now,
        "updated_at": now
    })
    result = await db["crm_documents"].insert_one(doc)
    created = await db["crm_documents"].find_one({"_id": result.inserted_id})
    fire_event_background(
        event_type="crm_document_created",
        resource_type="crm_documents",
        resource_id=str(result.inserted_id),
        user_email=admin.email,
        data=doc,
        db=db
    )
    return created

@router.put("/documents/{item_id}", response_model=CRMDocumentInDB)
async def update_document(item_id: str, payload: CRMDocumentUpdate, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_update(db, "crm_documents", item_id, payload.model_dump(exclude_unset=True), admin, "crm_document_updated")

@router.delete("/documents/{item_id}", status_code=204)
async def delete_document(item_id: str, db=Depends(get_db), admin=Depends(require_mutation_rights)):
    return await _apply_delete(db, "crm_documents", item_id, admin, "crm_document_deleted")
