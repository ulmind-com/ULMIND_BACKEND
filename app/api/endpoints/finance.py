from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from app.core.datetime_utils import get_now
from bson import ObjectId
from app.db.database import get_db
from app.api.deps import get_current_active_admin
from app.schemas.finance import InvoiceCreate, InvoiceInDB, PaymentCreate, PaymentInDB, ExpenseCreate, ExpenseInDB
import uuid
from app.services.event_trigger_service import fire_event_background

router = APIRouter()

def _parse_id(id: str) -> ObjectId:
    try:
        return ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# ── INVOICES ──

@router.get("/invoices", response_model=List[InvoiceInDB])
async def list_invoices(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"client_id": client_id} if client_id else {}
    invoices = await db["invoices"].find(query).to_list(length=1000)
    return invoices

@router.post("/invoices", response_model=InvoiceInDB, status_code=201)
async def create_invoice(invoice_in: InvoiceCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    invoice_number = f"INV-{uuid.uuid4().hex[:6].upper()}"
    doc = invoice_in.model_dump()
    doc.update({
        "invoice_number": invoice_number,
        "created_at": now,
        "updated_at": now
    })
    result = await db["invoices"].insert_one(doc)
    created = await db["invoices"].find_one({"_id": result.inserted_id})
    
    # Trigger AI event
    fire_event_background(
        event_type="invoice_created",
        resource_type="invoices",
        resource_id=str(result.inserted_id),
        user_email=_admin.get("email", "admin"),
        data=invoice_in.model_dump(),
        db=db
    )
    
    return created

# ── PAYMENTS ──

@router.get("/payments", response_model=List[PaymentInDB])
async def list_payments(client_id: Optional[str] = None, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    query = {"client_id": client_id} if client_id else {}
    payments = await db["payments"].find(query).to_list(length=1000)
    return payments

@router.post("/payments", response_model=PaymentInDB, status_code=201)
async def create_payment(payment_in: PaymentCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    doc = payment_in.model_dump()
    doc.update({"created_at": now})
    result = await db["payments"].insert_one(doc)
    
    # Update invoice status
    await db["invoices"].update_one(
        {"_id": _parse_id(payment_in.invoice_id)},
        {"$set": {"status": "paid", "updated_at": now}}
    )
    
    created = await db["payments"].find_one({"_id": result.inserted_id})
    
    # Trigger AI event
    fire_event_background(
        event_type="payment_received",
        resource_type="payments",
        resource_id=str(result.inserted_id),
        user_email=_admin.get("email", "admin"),
        data=payment_in.model_dump(),
        db=db
    )
    
    return created

# ── EXPENSES ──

@router.get("/expenses", response_model=List[ExpenseInDB])
async def list_expenses(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    expenses = await db["expenses"].find({}).to_list(length=1000)
    return expenses

@router.post("/expenses", response_model=ExpenseInDB, status_code=201)
async def create_expense(expense_in: ExpenseCreate, db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    now = get_now()
    doc = expense_in.model_dump()
    doc.update({"created_at": now})
    result = await db["expenses"].insert_one(doc)
    created = await db["expenses"].find_one({"_id": result.inserted_id})
    return created

# ── DASHBOARD STATS ──

@router.get("/dashboard")
async def get_finance_dashboard(db=Depends(get_db), _admin=Depends(get_current_active_admin)):
    invoices = await db["invoices"].find({}).to_list(1000)
    payments = await db["payments"].find({}).to_list(1000)
    expenses = await db["expenses"].find({}).to_list(1000)

    total_revenue = sum(inv.get("total", 0) for inv in invoices if inv.get("status") == "paid")
    total_invoiced = sum(inv.get("total", 0) for inv in invoices)
    total_expenses = sum(exp.get("amount", 0) for exp in expenses)
    total_payments = sum(pay.get("amount", 0) for pay in payments)
    outstanding = sum(inv.get("total", 0) for inv in invoices if inv.get("status") in ["pending", "overdue"])
    overdue_count = sum(1 for inv in invoices if inv.get("status") == "overdue")
    paid_count = sum(1 for inv in invoices if inv.get("status") == "paid")
    net_profit = total_revenue - total_expenses
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

    # Expense breakdown by category
    expense_breakdown = {}
    for exp in expenses:
        cat = exp.get("category", "other")
        expense_breakdown[cat] = expense_breakdown.get(cat, 0) + exp.get("amount", 0)

    # Recent transactions (last 10 payments)
    recent_payments = sorted(payments, key=lambda x: x.get("created_at", ""), reverse=True)[:10]

    return {
        "total_revenue": total_revenue,
        "total_invoiced": total_invoiced,
        "total_expenses": total_expenses,
        "total_payments": total_payments,
        "outstanding": outstanding,
        "overdue_count": overdue_count,
        "paid_count": paid_count,
        "net_profit": net_profit,
        "profit_margin": round(profit_margin, 1),
        "expense_breakdown": expense_breakdown,
        "recent_payments": recent_payments,
        "invoice_count": len(invoices),
        "payment_count": len(payments),
        "expense_count": len(expenses),
    }

