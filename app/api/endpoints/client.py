from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.schemas.client import ClientCreate, ClientResponse

router = APIRouter()

@router.get("/", response_model=List[ClientResponse])
async def get_clients(db=Depends(get_db)):
    clients = await db["clients"].find({}).to_list(length=1000)
    return clients

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(client_in: ClientCreate, db=Depends(get_db)):
    client_dict = client_in.model_dump()
    client_dict["created_at"] = get_now()
    client_dict["updated_at"] = get_now()
    
    result = await db["clients"].insert_one(client_dict)
    
    created_client = await db["clients"].find_one({"_id": result.inserted_id})
    return created_client
