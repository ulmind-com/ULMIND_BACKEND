from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.schemas.client import ClientCreate, ClientResponse
from app.services.event_trigger_service import fire_event_background

router = APIRouter()

@router.get("/", response_model=List[ClientResponse])
async def get_clients(db=Depends(get_db)):
    clients = await db["clients"].find({}).to_list(length=1000)
    return clients

@router.get("/{id}", response_model=ClientResponse)
async def get_client(id: str, db=Depends(get_db)):
    try:
        obj_id = ObjectId(id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")
    client = await db["clients"].find_one({"_id": obj_id})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(client_in: ClientCreate, db=Depends(get_db)):
    client_dict = client_in.model_dump()
    client_dict["created_at"] = get_now()
    client_dict["updated_at"] = get_now()
    
    result = await db["clients"].insert_one(client_dict)
    
    created_client = await db["clients"].find_one({"_id": result.inserted_id})
    
    # Trigger AI event
    fire_event_background(
        event_type="client_created",
        resource_type="clients",
        resource_id=str(result.inserted_id),
        user_email="system@ulmind.com", # Needs admin email, but we'll use system for now if not available in route deps
        data=client_in.model_dump(),
        db=db
    )
    
    return created_client

@router.put("/{id}/stage", response_model=ClientResponse)
async def update_client_stage(id: str, stage: str, db=Depends(get_db)):
    try:
        obj_id = ObjectId(id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    result = await db["clients"].find_one_and_update(
        {"_id": obj_id},
        {"$set": {"crm_data.stage": stage, "updated_at": get_now()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result

from pydantic import BaseModel
class NoteCreate(BaseModel):
    content: str
    author_id: str

@router.post("/{id}/notes", response_model=ClientResponse)
async def add_client_note(id: str, note_in: NoteCreate, db=Depends(get_db)):
    try:
        obj_id = ObjectId(id)
    except:
        raise HTTPException(status_code=400, detail="Invalid ID")
    
    note_dict = {
        "id": str(ObjectId()),
        "content": note_in.content,
        "author_id": note_in.author_id,
        "created_at": get_now()
    }
    
    result = await db["clients"].find_one_and_update(
        {"_id": obj_id},
        {"$push": {"crm_data.notes": note_dict}, "$set": {"updated_at": get_now()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result
