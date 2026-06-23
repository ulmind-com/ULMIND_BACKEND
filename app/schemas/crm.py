from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}

class Note(BaseModel):
    id: str
    content: str
    author_id: str
    created_at: datetime

class Contract(BaseModel):
    id: str
    title: str
    file_url: str
    status: str # "active", "expired", "pending"
    created_at: datetime
    expires_at: Optional[datetime] = None

class ClientPipelineUpdate(BaseModel):
    stage: str # "Lead", "Qualified", "Prospect", "Proposal Sent", "Negotiation", "Won", "Active Client"
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ClientCRMData(BaseModel):
    stage: str = "Lead"
    tags: List[str] = []
    notes: List[Note] = []
    contracts: List[Contract] = []
    last_contacted_at: Optional[datetime] = None
