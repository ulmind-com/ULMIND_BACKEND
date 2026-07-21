from pydantic import BaseModel, Field, model_validator
from pydantic.functional_validators import BeforeValidator
from typing import List, Optional, Annotated
from datetime import datetime

# Mongo returns ObjectId for `_id`; coerce to str so responses validate once
# real documents exist (same pattern as app/schemas/client.py).
PyObjectId = Annotated[str, BeforeValidator(str)]

class InvoiceItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float

class InvoiceCreate(BaseModel):
    client_id: str
    project_id: Optional[str] = None
    items: List[InvoiceItem]
    subtotal: float
    tax: float
    total: float
    due_date: datetime
    status: str = "pending" # "pending", "paid", "overdue", "cancelled"

class InvoiceInDB(InvoiceCreate):
    id: PyObjectId = Field(alias="_id")
    invoice_number: str = ""
    # Most historical invoices were stored as a total only, with no line items.
    items: List[InvoiceItem] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy(cls, data):
        if not isinstance(data, dict):
            return data
        doc = dict(data)  # never mutate the Mongo document itself
        doc.setdefault("items", [])
        if not doc.get("updated_at") and doc.get("created_at"):
            doc["updated_at"] = doc["created_at"]
        return doc

class PaymentCreate(BaseModel):
    invoice_id: str
    client_id: Optional[str] = None
    amount: float
    payment_method: str # "bank_transfer", "credit_card", "stripe", "cash"
    reference_number: Optional[str] = None
    payment_date: Optional[datetime] = None

class PaymentInDB(PaymentCreate):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy(cls, data):
        """Historical payments used `method`/`reference` and carried no
        client_id or payment_date. Read them without rewriting anything."""
        if not isinstance(data, dict):
            return data
        doc = dict(data)
        if not doc.get("payment_method"):
            doc["payment_method"] = doc.get("method") or "unknown"
        if not doc.get("reference_number"):
            doc["reference_number"] = doc.get("reference")
        if not doc.get("payment_date"):
            doc["payment_date"] = doc.get("created_at")
        return doc

class ExpenseCreate(BaseModel):
    category: str # "software", "marketing", "office", "salary", "other"
    amount: float
    description: str
    date: datetime
    receipt_url: Optional[str] = None
    project_id: Optional[str] = None  # Link expense to a project for budget tracking

class ExpenseInDB(ExpenseCreate):
    id: PyObjectId = Field(alias="_id")
    created_at: datetime
