import asyncio
from datetime import datetime, timedelta
import random
import uuid

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import connect_to_mongo, close_mongo_connection, get_db

def _random_date(days_back=30):
    return datetime.utcnow() - timedelta(days=random.randint(0, days_back), hours=random.randint(0, 23))

async def seed_data():
    connect_to_mongo()
    db = get_db()
    
    # ── CRM DATA (clients) ──
    print("Seeding CRM Data...")
    await db["clients"].delete_many({})
    clients = []
    statuses = ["active", "lead", "inactive"]
    companies = ["Acme Corp", "TechFlow", "Global Industries", "Stark Enterprises", "Wayne Financial"]
    for i in range(15):
        clients.append({
            "name": f"Client {i+1}",
            "email": f"client{i+1}@example.com",
            "phone": f"+9198765432{i%10}0",
            "company": random.choice(companies),
            "status": random.choice(statuses),
            "value": random.randint(10000, 500000),
            "created_at": _random_date(),
            "updated_at": datetime.utcnow()
        })
    await db["clients"].insert_many(clients)

    # ── PROJECTS DATA (projects) ──
    print("Seeding Projects Data...")
    await db["projects"].delete_many({})
    projects = []
    proj_statuses = ["active", "completed", "delayed", "planning"]
    for i in range(10):
        projects.append({
            "name": f"Project {chr(65+i)}",
            "description": "Comprehensive digital transformation.",
            "client_id": str(clients[i%len(clients)]["_id"]) if "_id" in clients[i%len(clients)] else None,
            "status": random.choice(proj_statuses),
            "progress": random.randint(10, 100),
            "budget": random.randint(50000, 1000000),
            "spent": random.randint(10000, 500000),
            "tasks_total": random.randint(5, 50),
            "tasks_completed": random.randint(0, 5),
            "hours_logged": random.randint(10, 200),
            "start_date": _random_date(60),
            "deadline": _random_date(30) + timedelta(days=60),
            "created_at": _random_date(),
            "updated_at": datetime.utcnow()
        })
    await db["projects"].insert_many(projects)

    # ── FINANCE DATA (invoices, payments, expenses) ──
    print("Seeding Finance Data...")
    await db["invoices"].delete_many({})
    await db["payments"].delete_many({})
    await db["expenses"].delete_many({})
    
    invoices = []
    payments = []
    expenses = []
    
    inv_statuses = ["paid", "pending", "overdue"]
    for i in range(20):
        total = random.randint(10000, 250000)
        status = random.choice(inv_statuses)
        invoice_doc = {
            "invoice_number": f"INV-{uuid.uuid4().hex[:6].upper()}",
            "client_id": str(clients[i%len(clients)]["_id"]) if "_id" in clients[i%len(clients)] else None,
            "subtotal": int(total * 0.82),
            "tax": int(total * 0.18),
            "total": total,
            "status": status,
            "due_date": _random_date(10) + timedelta(days=15),
            "created_at": _random_date(40),
            "updated_at": datetime.utcnow()
        }
        invoices.append(invoice_doc)
        
    res = await db["invoices"].insert_many(invoices)
    
    for i, inv_id in enumerate(res.inserted_ids):
        if invoices[i]["status"] == "paid":
            payments.append({
                "invoice_id": str(inv_id),
                "amount": invoices[i]["total"],
                "method": random.choice(["Bank Transfer", "Credit Card", "UPI"]),
                "reference": f"REF-{uuid.uuid4().hex[:8].upper()}",
                "created_at": invoices[i]["created_at"] + timedelta(days=random.randint(1, 10))
            })
    if payments:
        await db["payments"].insert_many(payments)
        
    expense_categories = ["Software", "Marketing", "Travel", "Office", "Salaries"]
    for i in range(15):
        expenses.append({
            "category": random.choice(expense_categories),
            "amount": random.randint(5000, 80000),
            "description": f"Monthly {random.choice(expense_categories)} Expense",
            "date": _random_date(),
            "created_at": _random_date()
        })
    await db["expenses"].insert_many(expenses)
    
    # ── AI NOTIFICATIONS & AUDIT LOGS ──
    # We already seeded these in previous script, let's just make sure there's plenty.
    # We will just add a few more.
    now = datetime.utcnow()
    more_notifs = [
        {
            "user_id": "global",
            "type": "project_completed",
            "title": "Project Delivered Successfully",
            "message": "Project A has been marked as completed and delivered to the client.",
            "priority": "Medium",
            "category": "Project",
            "recommended_action": "Request Client Review",
            "is_read": False,
            "link": "/admin/projects/all",
            "created_at": now - timedelta(hours=1)
        }
    ]
    await db["notifications"].insert_many(more_notifs)

    print("Dummy data seeded successfully for CRM, Projects, and Finance!")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed_data())
