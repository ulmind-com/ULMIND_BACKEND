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
    
    print("Fetching existing team members...")
    team_members = await db["admins"].find({"status": "Active"}).to_list(100)
    if not team_members:
        print("Warning: No active team members found in 'admins'. Will use dummy member IDs.")
        team_members = [{"_id": f"dummy_{i}", "name": f"Employee {i}", "email": f"emp{i}@ulmind.com"} for i in range(6)]
    
    # --- CRM ---
    print("Seeding CRM...")
    await db["clients"].delete_many({})
    await db["crm_activities"].delete_many({})
    await db["crm_meetings"].delete_many({})
    await db["crm_contracts"].delete_many({})
    await db["crm_documents"].delete_many({})

    clients = []
    companies = ["Acme Corp", "TechFlow", "Global Industries", "Stark Enterprises", "Wayne Financial", "Cyberdyne", "Initech", "Umbrella Corp"]
    for i in range(30):
        clients.append({
            "name": f"Client {i+1}",
            "email": f"client{i+1}@example.com",
            "phone": f"+9198765432{i%10}0",
            "company": random.choice(companies),
            "status": random.choice(["Active", "Active", "Lead", "Inactive"]),
            "revenue": random.randint(50000, 2000000),
            "crm_data": {
                "stage": random.choice(["Lead", "Negotiation", "Closed Won", "Active Client"]),
                "source": "Website",
                "assigned_to": str(random.choice(team_members)["_id"])
            },
            "created_at": _random_date(90),
            "updated_at": datetime.utcnow()
        })
    res_clients = await db["clients"].insert_many(clients)
    client_ids = [str(x) for x in res_clients.inserted_ids]

    activities = []
    for _ in range(50):
        activities.append({
            "client_id": random.choice(client_ids),
            "type": random.choice(["Call", "Email", "Note"]),
            "description": "Discussed project requirements and pricing.",
            "performed_by": random.choice(team_members)["full_name"],
            "created_at": _random_date()
        })
    await db["crm_activities"].insert_many(activities)
    
    meetings = []
    for _ in range(20):
        meetings.append({
            "client_id": random.choice(client_ids),
            "title": "Quarterly Review",
            "date": _random_date(10) + timedelta(days=15),
            "duration": 60,
            "attendees": ["Client", random.choice(team_members)["full_name"]],
            "notes": "Discussed upcoming renewals.",
            "created_at": _random_date()
        })
    await db["crm_meetings"].insert_many(meetings)
    
    contracts = []
    for _ in range(15):
        contracts.append({
            "client_id": random.choice(client_ids),
            "title": "Service Agreement",
            "value": random.randint(100000, 500000),
            "status": random.choice(["Active", "Pending", "Expired"]),
            "start_date": _random_date(60),
            "end_date": _random_date() + timedelta(days=365),
            "created_at": _random_date()
        })
    await db["crm_contracts"].insert_many(contracts)

    # --- PROJECTS ---
    print("Seeding Projects & PM...")
    await db["projects"].delete_many({})
    await db["pm_tasks"].delete_many({})
    await db["pm_milestones"].delete_many({})
    await db["pm_time_logs"].delete_many({})
    await db["pm_expenses"].delete_many({})

    projects = []
    for i in range(15):
        projects.append({
            "name": f"Project Alpha {i+1}",
            "description": "Enterprise software development",
            "client_id": random.choice(client_ids),
            "status": random.choice(["Active", "Completed", "On Hold"]),
            "progress": random.randint(10, 100),
            "cost": random.randint(100000, 2000000), # This is budget
            "start_date": _random_date(60),
            "deadline": _random_date() + timedelta(days=60),
            "created_at": _random_date(),
            "updated_at": datetime.utcnow()
        })
    res_projects = await db["projects"].insert_many(projects)
    project_ids = [str(x) for x in res_projects.inserted_ids]

    tasks = []
    for _ in range(150):
        tasks.append({
            "project_id": random.choice(project_ids),
            "title": "Develop feature X",
            "status": random.choice(["To Do", "In Progress", "Review", "Completed"]),
            "assignee_id": str(random.choice(team_members)["_id"]),
            "due_date": _random_date(10) + timedelta(days=5),
            "priority": random.choice(["High", "Medium", "Low"]),
            "order": random.randint(0, 10)
        })
    await db["pm_tasks"].insert_many(tasks)
    
    milestones = []
    for _ in range(45):
        milestones.append({
            "project_id": random.choice(project_ids),
            "title": "Phase 1 Delivery",
            "status": random.choice(["Pending", "Completed"]),
            "due_date": _random_date(10) + timedelta(days=20),
        })
    await db["pm_milestones"].insert_many(milestones)

    time_logs = []
    for _ in range(60):
        time_logs.append({
            "project_id": random.choice(project_ids),
            "user_id": str(random.choice(team_members)["_id"]),
            "hours": random.randint(1, 8),
            "description": "Working on frontend UI",
            "log_date": _random_date(10),
            "created_at": _random_date(10)
        })
    await db["pm_time_logs"].insert_many(time_logs)

    pm_expenses = []
    for _ in range(30):
        pm_expenses.append({
            "project_id": random.choice(project_ids),
            "amount": random.randint(5000, 50000),
            "category": "Software",
            "description": "AWS Hosting",
            "date": _random_date(30),
            "created_at": _random_date(30)
        })
    await db["pm_expenses"].insert_many(pm_expenses)

    # --- FINANCE ---
    print("Seeding Finance...")
    await db["invoices"].delete_many({})
    await db["payments"].delete_many({})
    await db["expenses"].delete_many({})

    invoices = []
    for i in range(40):
        total = random.randint(20000, 500000)
        invoices.append({
            "invoice_number": f"INV-{uuid.uuid4().hex[:6].upper()}",
            "client_id": random.choice(client_ids),
            "subtotal": int(total * 0.82),
            "tax": int(total * 0.18),
            "total": total,
            "status": random.choice(["paid", "pending", "overdue"]),
            "due_date": _random_date() + timedelta(days=15),
            "created_at": _random_date(40),
            "updated_at": datetime.utcnow()
        })
    res_invoices = await db["invoices"].insert_many(invoices)
    
    payments = []
    for i, inv_id in enumerate(res_invoices.inserted_ids):
        if invoices[i]["status"] == "paid":
            payments.append({
                "invoice_id": str(inv_id),
                "amount": invoices[i]["total"],
                "method": "Bank Transfer",
                "reference": f"TXN-{uuid.uuid4().hex[:8].upper()}",
                "created_at": invoices[i]["created_at"] + timedelta(days=3)
            })
    if payments:
        await db["payments"].insert_many(payments)

    expenses = []
    for _ in range(50):
        expenses.append({
            "category": random.choice(["Software", "Marketing", "Travel", "Office", "Salaries"]),
            "amount": random.randint(5000, 150000),
            "description": "Business Expense",
            "date": _random_date(),
            "created_at": _random_date()
        })
    await db["expenses"].insert_many(expenses)

    # --- TEAM (Preserving actual employees, just seeding their data) ---
    print("Seeding Team data...")
    await db["team_attendance"].delete_many({})
    await db["team_work_logs"].delete_many({})
    await db["team_performance"].delete_many({})
    await db["team_leaves"].delete_many({})
    await db["team_payroll"].delete_many({})

    attendance = []
    for tm in team_members:
        # Generate attendance for last 10 days
        for i in range(10):
            attendance.append({
                "user_id": str(tm["_id"]),
                "date": (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "status": random.choice(["Present", "Present", "Present", "Absent", "Half-Day"]),
                "check_in": "09:00",
                "check_out": "18:00"
            })
    await db["team_attendance"].insert_many(attendance)

    work_logs = []
    for tm in team_members:
        for i in range(5):
            work_logs.append({
                "user_id": str(tm["_id"]),
                "log_date": (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "hours": random.randint(4, 8),
                "description": "Completed assigned tasks."
            })
    await db["team_work_logs"].insert_many(work_logs)

    performance = []
    for tm in team_members:
        performance.append({
            "user_id": str(tm["_id"]),
            "score": random.randint(60, 100),
            "review_period": "Q2 2026",
            "feedback": "Great performance.",
            "created_at": _random_date()
        })
    await db["team_performance"].insert_many(performance)

    leaves = []
    for tm in team_members:
        leaves.append({
            "user_id": str(tm["_id"]),
            "from_date": _random_date(10),
            "to_date": _random_date(10) + timedelta(days=2),
            "reason": "Sick leave",
            "status": random.choice(["Approved", "Pending", "Rejected"]),
            "created_at": _random_date()
        })
    await db["team_leaves"].insert_many(leaves)

    payroll = []
    for tm in team_members:
        payroll.append({
            "user_id": str(tm["_id"]),
            "month": "May 2026",
            "basic_salary": random.randint(30000, 80000),
            "bonuses": random.randint(0, 10000),
            "deductions": random.randint(0, 5000),
            "net_pay": random.randint(25000, 85000),
            "status": "Paid",
            "created_at": _random_date()
        })
    await db["team_payroll"].insert_many(payroll)

    print("Comprehensive dummy data generation completed successfully!")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed_data())
