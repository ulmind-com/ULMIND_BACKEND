"""
ULMIND Enterprise Seed Script
==============================
Seeds realistic enterprise data:
- Backfills employee_id for the 6 founders
- Creates 5 projects with PROJ-UL-XXX IDs
- Creates tasks with TASK-UL-XXX IDs linked to projects
- Creates finance data (invoices, payments, expenses)
- Creates a sample task assigned to FOU-UL-002 (Arnab Senapati)

Run: python -m app.scripts.seed_enterprise
"""

import asyncio
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timedelta
from bson import ObjectId
from app.db.database import connect_to_mongo, get_db, close_mongo_connection
from app.core.datetime_utils import get_now
import uuid


# ── Employee Data ──────────────────────────────────────────────────────────────
EMPLOYEES = [
    {"employee_id": "FOU-UL-001", "full_name": "Soumyajit Banerjee", "email": "soumyajit.banerjee@ulmind.com", "position": "Founder & CTO"},
    {"employee_id": "FOU-UL-002", "full_name": "Arnab Senapati", "email": "arnab.senapati@ulmind.com", "position": "Co-Founder, MD & CEO"},
    {"employee_id": "FOU-UL-003", "full_name": "Sagnik Mondal", "email": "sagnik.mondal@ulmind.com", "position": "Co-Founder & COO"},
    {"employee_id": "FOU-UL-004", "full_name": "Samiran Samanta", "email": "samiran.samanta@ulmind.com", "position": "Co-Founder & CTO"},

    {"employee_id": "FOU-UL-006", "full_name": "Swastika Roy", "email": "swastika.roy@ulmind.com", "position": "Co-Founder & CHRO"},
]


async def backfill_employee_ids(db):
    """Backfill employee_id on existing admin records."""
    print("\n🔧 Backfilling employee IDs...")
    for emp in EMPLOYEES:
        result = await db["admins"].find_one({"email": emp["email"]})
        if result:
            if not result.get("employee_id"):
                await db["admins"].update_one(
                    {"_id": result["_id"]},
                    {"$set": {"employee_id": emp["employee_id"], "position": emp["position"]}}
                )
                print(f"  ✅ {emp['employee_id']} → {emp['full_name']} (updated)")
            else:
                print(f"  ⏩ {emp['employee_id']} → {emp['full_name']} (already set)")
        else:
            print(f"  ⚠️  {emp['email']} not found in admins collection (skip)")


async def get_employee_id_by_code(db, employee_code: str) -> str:
    """Get MongoDB _id from employee_id code like FOU-UL-002."""
    admin = await db["admins"].find_one({"employee_id": employee_code})
    if admin:
        return str(admin["_id"])
    return None


async def seed_projects(db):
    """Seed realistic enterprise projects."""
    print("\n📁 Seeding projects...")

    # Get employee _ids
    emp_ids = {}
    for emp in EMPLOYEES:
        _id = await get_employee_id_by_code(db, emp["employee_id"])
        if _id:
            emp_ids[emp["employee_id"]] = _id

    # Check existing projects to avoid duplicates
    existing = await db["projects"].find({"project_id": {"$regex": "^PROJ-UL-"}}).to_list(100)
    existing_ids = {p.get("project_id") for p in existing}

    now = get_now()

    projects_data = [
        {
            "name": "ULMiND Corporate Website",
            "description": "Full redesign and development of the ULMiND corporate website with modern UI/UX, SEO optimization, and performance enhancements.",
            "category": "Web Development",
            "status": "Active",
            "priority": "High",
            "client_name": "ULMiND Internal",
            "client_email": "info@ulmind.com",
            "client_company": "ULMiND",
            "team_members": [emp_ids.get("FOU-UL-001", ""), emp_ids.get("FOU-UL-002", ""), emp_ids.get("FOU-UL-004", "")],
            "project_manager": emp_ids.get("FOU-UL-002", ""),
            "budget": 500000,
            "cost": 320000,
            "progress": 72,
            "completion_percent": 72,
            "start_date": now - timedelta(days=90),
            "end_date": now + timedelta(days=30),
            "tags": ["website", "frontend", "react", "seo"],
            "milestones": [
                {"id": str(uuid.uuid4()), "title": "UI/UX Design Complete", "status": "Completed", "completion_pct": 100, "due_date": now - timedelta(days=60)},
                {"id": str(uuid.uuid4()), "title": "Frontend Development", "status": "In Progress", "completion_pct": 80, "due_date": now - timedelta(days=15)},
                {"id": str(uuid.uuid4()), "title": "Backend API Integration", "status": "In Progress", "completion_pct": 65, "due_date": now + timedelta(days=10)},
                {"id": str(uuid.uuid4()), "title": "Testing & QA", "status": "Pending", "completion_pct": 0, "due_date": now + timedelta(days=25)},
            ],
        },
        {
            "name": "E-Commerce Platform for TechMart",
            "description": "Full-stack e-commerce platform with payment gateway integration, inventory management, and admin dashboard.",
            "category": "Web Development",
            "status": "Active",
            "priority": "Urgent",
            "client_name": "TechMart India",
            "client_email": "procurement@techmart.in",
            "client_company": "TechMart India Pvt. Ltd.",
            "team_members": [emp_ids.get("FOU-UL-001", ""), emp_ids.get("FOU-UL-003", ""), emp_ids.get("FOU-UL-005", "")],
            "project_manager": emp_ids.get("FOU-UL-003", ""),
            "budget": 850000,
            "cost": 620000,
            "progress": 45,
            "completion_percent": 45,
            "start_date": now - timedelta(days=45),
            "end_date": now + timedelta(days=75),
            "tags": ["e-commerce", "react", "node", "payment-gateway"],
            "milestones": [
                {"id": str(uuid.uuid4()), "title": "Requirements & Architecture", "status": "Completed", "completion_pct": 100, "due_date": now - timedelta(days=30)},
                {"id": str(uuid.uuid4()), "title": "Product Catalog & Cart", "status": "In Progress", "completion_pct": 60, "due_date": now + timedelta(days=10)},
                {"id": str(uuid.uuid4()), "title": "Payment Integration", "status": "Pending", "completion_pct": 0, "due_date": now + timedelta(days=40)},
            ],
        },
        {
            "name": "AI Chatbot for HealthPlus",
            "description": "Conversational AI chatbot for healthcare appointment booking, symptom checking, and patient support.",
            "category": "AI/ML",
            "status": "Planning",
            "priority": "Medium",
            "client_name": "HealthPlus Clinics",
            "client_email": "tech@healthplus.co.in",
            "client_company": "HealthPlus Medical Group",
            "team_members": [emp_ids.get("FOU-UL-004", ""), emp_ids.get("FOU-UL-005", "")],
            "project_manager": emp_ids.get("FOU-UL-004", ""),
            "budget": 1200000,
            "cost": 0,
            "progress": 10,
            "completion_percent": 10,
            "start_date": now + timedelta(days=15),
            "end_date": now + timedelta(days=120),
            "tags": ["ai", "chatbot", "healthcare", "nlp"],
            "milestones": [
                {"id": str(uuid.uuid4()), "title": "Data Collection & Training", "status": "Pending", "completion_pct": 0, "due_date": now + timedelta(days=45)},
                {"id": str(uuid.uuid4()), "title": "Model Training & Evaluation", "status": "Pending", "completion_pct": 0, "due_date": now + timedelta(days=75)},
            ],
        },
        {
            "name": "Mobile App - FoodDash Delivery",
            "description": "Cross-platform mobile application for food delivery with real-time tracking, push notifications, and restaurant management.",
            "category": "Mobile App",
            "status": "Completed",
            "priority": "High",
            "client_name": "FoodDash",
            "client_email": "dev@fooddash.com",
            "client_company": "FoodDash Technologies",
            "team_members": [emp_ids.get("FOU-UL-001", ""), emp_ids.get("FOU-UL-002", ""), emp_ids.get("FOU-UL-006", "")],
            "project_manager": emp_ids.get("FOU-UL-001", ""),
            "budget": 750000,
            "cost": 680000,
            "progress": 100,
            "completion_percent": 100,
            "payment_status": "Paid",
            "start_date": now - timedelta(days=180),
            "end_date": now - timedelta(days=30),
            "tags": ["mobile", "react-native", "delivery", "real-time"],
            "milestones": [
                {"id": str(uuid.uuid4()), "title": "App Design", "status": "Completed", "completion_pct": 100, "due_date": now - timedelta(days=150)},
                {"id": str(uuid.uuid4()), "title": "Core Features", "status": "Completed", "completion_pct": 100, "due_date": now - timedelta(days=90)},
                {"id": str(uuid.uuid4()), "title": "Testing & Launch", "status": "Completed", "completion_pct": 100, "due_date": now - timedelta(days=30)},
            ],
        },
        {
            "name": "DevOps Pipeline for CloudServe",
            "description": "CI/CD pipeline setup, Kubernetes deployment, monitoring, and infrastructure automation.",
            "category": "DevOps",
            "status": "On Hold",
            "priority": "Low",
            "client_name": "CloudServe Solutions",
            "client_email": "ops@cloudserve.io",
            "client_company": "CloudServe Solutions Inc.",
            "team_members": [emp_ids.get("FOU-UL-004", ""), emp_ids.get("FOU-UL-005", "")],
            "project_manager": emp_ids.get("FOU-UL-005", ""),
            "budget": 400000,
            "cost": 120000,
            "progress": 30,
            "completion_percent": 30,
            "start_date": now - timedelta(days=60),
            "end_date": now + timedelta(days=60),
            "tags": ["devops", "kubernetes", "ci-cd", "cloud"],
            "milestones": [
                {"id": str(uuid.uuid4()), "title": "Infrastructure Audit", "status": "Completed", "completion_pct": 100, "due_date": now - timedelta(days=45)},
                {"id": str(uuid.uuid4()), "title": "Pipeline Setup", "status": "Pending", "completion_pct": 0, "due_date": now + timedelta(days=15)},
            ],
        },
    ]

    # Seed counter
    existing_counter = await db["counters"].find_one({"_id": "project_id"})
    if not existing_counter:
        await db["counters"].insert_one({"_id": "project_id", "seq": 0})

    created_projects = []
    for proj_data in projects_data:
        # Generate project ID
        counter = await db["counters"].find_one_and_update(
            {"_id": "project_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True
        )
        project_id = f"PROJ-UL-{counter['seq']:03d}"

        if project_id in existing_ids:
            print(f"  ⏩ {project_id} — {proj_data['name']} (already exists)")
            continue

        doc = {
            **proj_data,
            "project_id": project_id,
            "currency": "INR",
            "payment_status": proj_data.get("payment_status", "Pending"),
            "deployments": [],
            "env_vars": [],
            "notes": None,
            "created_at": now,
            "updated_at": now,
        }
        # Filter empty strings from team_members
        doc["team_members"] = [m for m in doc["team_members"] if m]

        result = await db["projects"].insert_one(doc)
        doc["_id"] = result.inserted_id
        created_projects.append(doc)
        print(f"  ✅ {project_id} — {proj_data['name']}")

    return created_projects


async def seed_tasks(db, projects):
    """Seed realistic tasks linked to projects."""
    print("\n📋 Seeding tasks...")

    # Get employee _ids
    emp_ids = {}
    for emp in EMPLOYEES:
        _id = await get_employee_id_by_code(db, emp["employee_id"])
        if _id:
            emp_ids[emp["employee_id"]] = _id

    # Seed counter
    existing_counter = await db["counters"].find_one({"_id": "task_id"})
    if not existing_counter:
        await db["counters"].insert_one({"_id": "task_id", "seq": 0})

    now = get_now()
    tasks_created = 0

    for proj in projects:
        proj_id = str(proj["_id"])
        proj_name = proj["name"]
        client = proj.get("client_name", "Unknown")

        # Generate 3-5 tasks per project
        task_templates = [
            {"title": f"Design System Setup for {proj_name}", "description": "Create and implement the design system including color palette, typography, spacing, and component library.", "priority": "High", "status": "Completed", "estimated_hours": 24, "actual_hours": 20},
            {"title": f"Backend API Development", "description": "Build RESTful APIs for all core features including authentication, data management, and integrations.", "priority": "High", "status": "In Progress", "estimated_hours": 40, "actual_hours": 28},
            {"title": f"Frontend Implementation", "description": "Implement all UI components and pages based on the approved designs using React and TypeScript.", "priority": "Medium", "status": "In Progress", "estimated_hours": 60, "actual_hours": 35},
            {"title": f"Testing & QA", "description": "Comprehensive testing including unit tests, integration tests, and end-to-end testing.", "priority": "Medium", "status": "Pending", "estimated_hours": 20, "actual_hours": 0},
            {"title": f"Deployment & Documentation", "description": "Deploy to production environment and create comprehensive documentation.", "priority": "Low", "status": "Pending", "estimated_hours": 12, "actual_hours": 0},
        ]

        team = proj.get("team_members", [])

        for i, tmpl in enumerate(task_templates[:4]):  # 4 tasks per project
            counter = await db["counters"].find_one_and_update(
                {"_id": "task_id"},
                {"$inc": {"seq": 1}},
                upsert=True,
                return_document=True
            )
            task_id = f"TASK-UL-{counter['seq']:03d}"

            assignee = team[i % len(team)] if team else None
            assignee_name = ""
            if assignee:
                admin = await db["admins"].find_one({"_id": ObjectId(assignee)})
                if admin:
                    assignee_name = admin.get("full_name", "")

            completion = 100 if tmpl["status"] == "Completed" else (50 if tmpl["status"] == "In Progress" else 0)

            doc = {
                "task_id": task_id,
                "project_id": proj_id,
                "project_name": proj_name,
                "client_name": client,
                "title": tmpl["title"],
                "description": tmpl["description"],
                "priority": tmpl["priority"],
                "status": tmpl["status"],
                "assigned_to": assignee,
                "assigned_to_multiple": [assignee] if assignee else [],
                "assigned_to_names": [assignee_name] if assignee_name else [],
                "start_date": now - timedelta(days=30 - i * 7),
                "due_date": now + timedelta(days=i * 14),
                "estimated_hours": tmpl["estimated_hours"],
                "actual_hours": tmpl["actual_hours"],
                "completion_percent": completion,
                "checklist": [
                    {"id": str(uuid.uuid4()), "text": "Requirements analysis", "done": True},
                    {"id": str(uuid.uuid4()), "text": "Implementation", "done": tmpl["status"] in ["Completed", "In Progress"]},
                    {"id": str(uuid.uuid4()), "text": "Code review", "done": tmpl["status"] == "Completed"},
                    {"id": str(uuid.uuid4()), "text": "Testing", "done": tmpl["status"] == "Completed"},
                ],
                "deliverables": [],
                "attachments": [],
                "tags": [],
                "comments": [],
                "created_at": now - timedelta(days=30),
                "updated_at": now,
            }

            await db["tasks"].insert_one(doc)
            tasks_created += 1
            print(f"  ✅ {task_id} — {tmpl['title'][:50]}...")

    # Create the special sample task for FOU-UL-002 (Arnab Senapati)
    arnab_id = emp_ids.get("FOU-UL-002")
    if arnab_id and projects:
        counter = await db["counters"].find_one_and_update(
            {"_id": "task_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True
        )
        task_id = f"TASK-UL-{counter['seq']:03d}"

        sample_task = {
            "task_id": task_id,
            "project_id": str(projects[0]["_id"]),
            "project_name": projects[0]["name"],
            "client_name": projects[0].get("client_name", "ULMiND"),
            "title": "Admin Panel Enterprise Module Integration",
            "description": "Integrate all enterprise modules (CRM, Finance, Projects, Tasks) into a unified workflow with cross-module data synchronization, automated notifications, and real-time updates.",
            "priority": "Urgent",
            "status": "In Progress",
            "assigned_to": arnab_id,
            "assigned_to_multiple": [arnab_id],
            "assigned_to_names": ["Arnab Senapati"],
            "start_date": now,
            "due_date": now + timedelta(days=7),
            "estimated_hours": 40,
            "actual_hours": 8,
            "completion_percent": 20,
            "checklist": [
                {"id": str(uuid.uuid4()), "text": "Project management module upgrade", "done": True},
                {"id": str(uuid.uuid4()), "text": "Task assignment with auto-suggest", "done": False},
                {"id": str(uuid.uuid4()), "text": "Finance linkage", "done": False},
                {"id": str(uuid.uuid4()), "text": "CRM synchronization", "done": False},
                {"id": str(uuid.uuid4()), "text": "Email automation testing", "done": False},
            ],
            "deliverables": [],
            "attachments": [],
            "tags": ["enterprise", "integration", "priority"],
            "comments": [],
            "created_at": now,
            "updated_at": now,
        }
        await db["tasks"].insert_one(sample_task)
        print(f"\n  🎯 SAMPLE TASK: {task_id} — Assigned to FOU-UL-002 (Arnab Senapati)")

    print(f"\n  📊 Total tasks created: {tasks_created + 1}")


async def seed_finance(db, projects):
    """Seed finance data linked to projects."""
    print("\n💰 Seeding finance data...")

    now = get_now()

    for proj in projects[:3]:  # Finance data for first 3 projects
        proj_id = str(proj["_id"])
        proj_name = proj["name"]
        budget = proj.get("budget", 0)

        # Create invoice
        inv_doc = {
            "client_id": proj.get("client_id", ""),
            "project_id": proj_id,
            "items": [
                {"description": f"{proj_name} - Phase 1", "quantity": 1, "unit_price": budget * 0.5, "total": budget * 0.5},
                {"description": f"{proj_name} - Phase 2", "quantity": 1, "unit_price": budget * 0.5, "total": budget * 0.5},
            ],
            "subtotal": budget,
            "tax": budget * 0.18,
            "total": budget * 1.18,
            "due_date": now + timedelta(days=30),
            "status": "paid" if proj.get("payment_status") == "Paid" else "pending",
            "invoice_number": f"INV-{uuid.uuid4().hex[:6].upper()}",
            "created_at": now - timedelta(days=15),
            "updated_at": now,
        }
        await db["invoices"].insert_one(inv_doc)
        print(f"  ✅ Invoice for {proj_name}: ₹{inv_doc['total']:,.0f}")

    print("  📊 Finance data seeded")


async def main():
    print("=" * 60)
    print("  ULMIND Enterprise Seed Script")
    print("=" * 60)

    connect_to_mongo()
    db = get_db()

    # 1. Backfill employee IDs
    await backfill_employee_ids(db)

    # 2. Seed projects
    projects = await seed_projects(db)

    # 3. Seed tasks (only if projects were created)
    if projects:
        await seed_tasks(db, projects)
        await seed_finance(db, projects)
    else:
        print("\n⚠️  No new projects created (already seeded). Skipping tasks & finance.")

    close_mongo_connection()

    print("\n" + "=" * 60)
    print("  ✅ Enterprise seed complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
