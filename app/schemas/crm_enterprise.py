from pydantic import BaseModel, Field, model_validator
from pydantic.functional_validators import BeforeValidator
from typing import List, Optional, Annotated, Any
from datetime import datetime

# Mongo hands us an ObjectId for `_id`; coerce it to a string the same way
# app/schemas/client.py does. Without this every list/create response blows up
# with a ResponseValidationError as soon as a single document exists.
PyObjectId = Annotated[str, BeforeValidator(str)]


def _blank_to_none(v: Any) -> Any:
    """HTML date/select inputs submit "" for an untouched field. Treat that as
    'not provided' instead of letting pydantic reject it."""
    if v == "":
        return None
    return v


OptionalDate = Annotated[Optional[datetime], BeforeValidator(_blank_to_none)]
OptionalStr = Annotated[Optional[str], BeforeValidator(_blank_to_none)]


def _first(doc: dict, *keys, default=None):
    """Return the first key present and non-empty, else default."""
    for k in keys:
        v = doc.get(k)
        if v not in (None, ""):
            return v
    return default


def _legacy_read(mapping: dict):
    """Build a `before` validator that lets a response model read documents
    written by earlier versions of this app, which used different field names.

    This is READ-ONLY normalisation: the stored document is never rewritten, so
    existing CRM records keep their original shape in Mongo and simply become
    displayable again. `mapping` is {canonical_field: (alias, alias, ...)}.
    """
    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data):
        if not isinstance(data, dict):
            return data
        doc = dict(data)  # never mutate the caller's Mongo document
        for canonical, aliases in mapping.items():
            if doc.get(canonical) in (None, ""):
                found = _first(doc, *aliases)
                if found is not None:
                    doc[canonical] = found
        # Records created before `updated_at` existed fall back to created_at.
        if not doc.get("updated_at") and doc.get("created_at"):
            doc["updated_at"] = doc["created_at"]
        return doc
    return _normalise

# Activities (Contact History, Calls, Emails)
class CRMActivityBase(BaseModel):
    # Optional so an activity can be logged before it is attached to a client.
    client_id: OptionalStr = None
    type: str # "call", "email", "whatsapp", "meeting", "note"
    content: str
    author_id: str
    attachments: List[str] = []

class CRMActivityCreate(CRMActivityBase):
    pass

class CRMActivityUpdate(BaseModel):
    client_id: OptionalStr = None
    type: Optional[str] = None
    content: Optional[str] = None
    attachments: Optional[List[str]] = None

class CRMActivityInDB(CRMActivityBase):
    id: PyObjectId = Field(alias="_id")
    # Legacy rows store the text under `description` and the person under
    # `performed_by`; both are surfaced so nothing is lost in the response.
    author_id: str = ""
    content: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

    _legacy = _legacy_read({
        "content": ("description", "note", "body"),
        "author_id": ("performed_by", "author", "created_by"),
    })

# Meetings
class CRMMeetingBase(BaseModel):
    client_id: OptionalStr = None
    title: str
    date: datetime
    # Was required, but no UI ever collected it — every "Schedule Meeting"
    # request failed validation. Optional with a blank default.
    agenda: str = ""
    attendees: List[str] = []
    follow_up_tasks: List[str] = []
    integration: OptionalStr = None # "Google Meet", "Zoom", "Teams"
    meeting_link: OptionalStr = None
    status: str = "scheduled" # "scheduled", "completed", "cancelled"

class CRMMeetingCreate(CRMMeetingBase):
    pass

class CRMMeetingUpdate(BaseModel):
    client_id: OptionalStr = None
    title: Optional[str] = None
    date: OptionalDate = None
    agenda: Optional[str] = None
    attendees: Optional[List[str]] = None
    follow_up_tasks: Optional[List[str]] = None
    integration: OptionalStr = None
    meeting_link: OptionalStr = None
    status: Optional[str] = None

class CRMMeetingInDB(CRMMeetingBase):
    id: PyObjectId = Field(alias="_id")
    # Extra columns older meeting rows carry — kept so the UI can show them.
    notes: OptionalStr = None
    duration: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

    _legacy = _legacy_read({"agenda": ("notes", "summary")})

# Contracts
class CRMContractBase(BaseModel):
    client_id: OptionalStr = None
    contract_number: str
    title: str
    value: float = 0.0
    start_date: datetime
    end_date: OptionalDate = None
    status: str = "pending" # "active", "expired", "pending"
    file_url: OptionalStr = None

class CRMContractCreate(CRMContractBase):
    pass

class CRMContractUpdate(BaseModel):
    client_id: OptionalStr = None
    contract_number: Optional[str] = None
    title: Optional[str] = None
    value: Optional[float] = None
    start_date: OptionalDate = None
    end_date: OptionalDate = None
    status: Optional[str] = None
    file_url: OptionalStr = None

class CRMContractInDB(CRMContractBase):
    id: PyObjectId = Field(alias="_id")
    # Older contracts were saved without a contract number.
    contract_number: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

    _legacy = _legacy_read({"contract_number": ("number", "reference")})

# Documents
class CRMDocumentBase(BaseModel):
    client_id: OptionalStr = None
    title: str
    folder: str = "Other Files" # "Contracts", "Invoices", "Proposals", "Presentations", "Legal Documents"
    file_url: str
    size_bytes: int = 0

class CRMDocumentCreate(CRMDocumentBase):
    pass

class CRMDocumentUpdate(BaseModel):
    client_id: OptionalStr = None
    title: Optional[str] = None
    folder: Optional[str] = None
    file_url: Optional[str] = None
    size_bytes: Optional[int] = None

class CRMDocumentInDB(CRMDocumentBase):
    id: PyObjectId = Field(alias="_id")
    # Older documents predate this field, so it must tolerate being absent.
    uploaded_by: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

    _legacy = _legacy_read({
        "file_url": ("url", "link"),
        "uploaded_by": ("author", "created_by"),
    })
