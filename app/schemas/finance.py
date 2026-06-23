from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.schemas.crm import PyObjectId

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
    id: str = Field(alias="_id")
    invoice_number: str
    created_at: datetime
    updated_at: datetime

class PaymentCreate(BaseModel):
    invoice_id: str
    client_id: str
    amount: float
    payment_method: str # "bank_transfer", "credit_card", "stripe", "cash"
    reference_number: Optional[str] = None
    payment_date: datetime

class PaymentInDB(PaymentCreate):
    id: str = Field(alias="_id")
    created_at: datetime

class ExpenseCreate(BaseModel):
    category: str # "software", "marketing", "office", "salary", "other"
    amount: float
    description: str
    date: datetime
    receipt_url: Optional[str] = None

class ExpenseInDB(ExpenseCreate):
    id: str = Field(alias="_id")
    created_at: datetime
