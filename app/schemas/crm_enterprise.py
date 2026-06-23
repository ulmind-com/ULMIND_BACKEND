from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.schemas.crm import PyObjectId

# Activities (Contact History, Calls, Emails)
class CRMActivityBase(BaseModel):
    client_id: str
    type: str # "call", "email", "whatsapp", "meeting", "note"
    content: str
    author_id: str
    attachments: List[str] = []

class CRMActivityCreate(CRMActivityBase):
    pass

class CRMActivityInDB(CRMActivityBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# Meetings
class CRMMeetingBase(BaseModel):
    client_id: str
    title: str
    date: datetime
    agenda: str
    attendees: List[str] = []
    follow_up_tasks: List[str] = []
    integration: Optional[str] = None # "Google Meet", "Zoom", "Teams"
    meeting_link: Optional[str] = None
    status: str = "scheduled" # "scheduled", "completed", "cancelled"

class CRMMeetingCreate(CRMMeetingBase):
    pass

class CRMMeetingInDB(CRMMeetingBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# Contracts
class CRMContractBase(BaseModel):
    client_id: str
    contract_number: str
    title: str
    value: float
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str = "active" # "active", "expired", "pending"
    file_url: Optional[str] = None

class CRMContractCreate(CRMContractBase):
    pass

class CRMContractInDB(CRMContractBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: datetime

# Documents
class CRMDocumentBase(BaseModel):
    client_id: str
    title: str
    folder: str = "Other Files" # "Contracts", "Invoices", "Proposals", "Presentations", "Legal Documents"
    file_url: str
    size_bytes: int

class CRMDocumentCreate(CRMDocumentBase):
    pass

class CRMDocumentInDB(CRMDocumentBase):
    id: str = Field(alias="_id")
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
