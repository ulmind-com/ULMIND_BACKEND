from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin, require_mutation_rights
from app.core.datetime_utils import get_now
from app.services.event_trigger_service import fire_event_background
from app.schemas.crm_enterprise import (
    CRMActivityCreate, CRMActivityInDB,
    CRMMeetingCreate, CRMMeetingInDB,
    CRMContractCreate, CRMContractInDB,
    CRMDocumentCreate, CRMDocumentInDB
)

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# ── DASHBOARD STATS ──
@router.get("/dashboard")
async def get_crm_dashboard_stats(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    pipeline = [
        {"$group": {"_id": "$crm_data.stage", "count": {"$sum": 1}, "value": {"$sum": "$revenue"}}}
    ]
    stage_stats = await db["clients"].aggregate(pipeline).to_list(None)
    
    total_leads = await db["clients"].count_documents({"crm_data.stage": "Lead"})
    active_clients = await db["clients"].count_documents({"status": "Active"})
    total_revenue = await db["clients"].aggregate([{"$group": {"_id": None, "total": {"$sum": "$revenue"}}}]).to_list(None)
    revenue = total_revenue[0]["total"] if total_revenue else 0
    
    return {
        "total_leads": total_leads,
        "active_clients": active_clients,
        "revenue": revenue,
        "pipeline_stats": stage_stats
    }

# ── ACTIVITIES ──
@router.get("/activities", response_model=List[CRMActivityInDB])
async def list_activities(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"client_id": client_id} if client_id else {}
    activities = await db["crm_activities"].find(query).sort("created_at", -1).to_list(length=1000)
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

# ── MEETINGS ──
@router.get("/meetings", response_model=List[CRMMeetingInDB])
async def list_meetings(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"client_id": client_id} if client_id else {}
    meetings = await db["crm_meetings"].find(query).sort("date", 1).to_list(length=1000)
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

# ── CONTRACTS ──
@router.get("/contracts", response_model=List[CRMContractInDB])
async def list_contracts(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"client_id": client_id} if client_id else {}
    contracts = await db["crm_contracts"].find(query).sort("created_at", -1).to_list(length=1000)
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

# ── DOCUMENTS ──
@router.get("/documents", response_model=List[CRMDocumentInDB])
async def list_documents(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"client_id": client_id} if client_id else {}
    documents = await db["crm_documents"].find(query).sort("created_at", -1).to_list(length=1000)
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
