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

class Contact(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Project(BaseModel):
    id: str
    name: str
    status: str # "Active", "Completed", "On Hold"
    deadline: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Invoice(BaseModel):
    id: str
    invoice_number: str
    amount: float
    status: str # "Paid", "Pending", "Overdue"
    due_date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Document(BaseModel):
    id: str
    title: str
    file_url: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Meeting(BaseModel):
    id: str
    title: str
    scheduled_at: datetime
    status: str # "Scheduled", "Completed", "Cancelled"
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ActivityLog(BaseModel):
    id: str
    action: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ClientPipelineUpdate(BaseModel):
    stage: str # "Lead", "Qualified", "Prospect", "Proposal Sent", "Negotiation", "Won", "Active Client"
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ClientCRMData(BaseModel):
    stage: str = "Lead"
    tags: List[str] = []
    notes: List[Note] = []
    contracts: List[Contract] = []
    contacts: List[Contact] = []
    projects: List[Project] = []
    invoices: List[Invoice] = []
    documents: List[Document] = []
    meetings: List[Meeting] = []
    activity_logs: List[ActivityLog] = []
    last_contacted_at: Optional[datetime] = None
