import asyncio
from datetime import datetime, timedelta
import random

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import connect_to_mongo, close_mongo_connection, get_db

async def seed_data():
    connect_to_mongo()
    db = get_db()
    
    now = datetime.utcnow()
    
    # ── Seed Notifications ──
    print("Seeding Notifications...")
    notifications = [
        {
            "user_id": "global",
            "type": "client_new",
            "title": "High Value Enterprise Lead",
            "message": "A new enterprise lead from Microsoft just registered on the platform.",
            "priority": "High",
            "category": "CRM",
            "recommended_action": "Review Company Profile",
            "is_read": False,
            "link": "/admin/crm/dashboard",
            "created_at": now - timedelta(minutes=5)
        },
        {
            "user_id": "global",
            "type": "security_alert",
            "title": "Suspicious Login Attempt",
            "message": "Multiple failed login attempts detected from IP 192.168.1.55 within 5 minutes.",
            "priority": "Critical",
            "category": "Security",
            "recommended_action": "Block IP Address",
            "is_read": False,
            "link": "/admin/audit-logs",
            "created_at": now - timedelta(minutes=15)
        },
        {
            "user_id": "global",
            "type": "payment_received",
            "title": "Large Payment Received",
            "message": "Invoice INV-98A21 for $12,500 has been paid by Google LLC.",
            "priority": "Medium",
            "category": "Finance",
            "recommended_action": "Send Thank You Note",
            "is_read": False,
            "link": "/admin/finance/invoices",
            "created_at": now - timedelta(hours=2)
        },
        {
            "user_id": "global",
            "type": "project_deadline",
            "title": "Project Overdue Warning",
            "message": "The 'E-Commerce App' project is 3 days behind schedule.",
            "priority": "Warning",
            "category": "Project",
            "recommended_action": "Reschedule Milestone",
            "is_read": False,
            "link": "/admin/projects/dashboard",
            "created_at": now - timedelta(days=1)
        },
        {
            "user_id": "global",
            "type": "system_update",
            "title": "System Backup Completed",
            "message": "Daily database backup was successful. Size: 2.4GB.",
            "priority": "Low",
            "category": "System",
            "recommended_action": None,
            "is_read": True,
            "link": None,
            "created_at": now - timedelta(days=2)
        }
    ]
    
    await db["notifications"].insert_many(notifications)
    
    # ── Seed Audit Logs ──
    print("Seeding Audit Logs...")
    audit_logs = [
        {
            "user_id": "admin@ulmind.com",
            "event_type": "client_created",
            "resource_type": "clients",
            "resource_id": "60a7f1a3b1f9b31d4c8b4567",
            "description": "admin@ulmind.com created a new client Microsoft.",
            "new_value": {"name": "Microsoft", "email": "contact@microsoft.com"},
            "created_at": now - timedelta(minutes=5)
        },
        {
            "user_id": "system_bot",
            "event_type": "login_failed",
            "resource_type": "auth",
            "resource_id": None,
            "description": "Failed login attempt for user admin@ulmind.com",
            "new_value": {"ip_address": "192.168.1.55"},
            "created_at": now - timedelta(minutes=15)
        },
        {
            "user_id": "finance@ulmind.com",
            "event_type": "payment_marked_paid",
            "resource_type": "invoices",
            "resource_id": "INV-98A21",
            "description": "finance@ulmind.com marked invoice INV-98A21 as Paid.",
            "old_value": {"status": "pending"},
            "new_value": {"status": "paid"},
            "created_at": now - timedelta(hours=2)
        },
        {
            "user_id": "pm@ulmind.com",
            "event_type": "project_status_changed",
            "resource_type": "projects",
            "resource_id": "proj_xyz",
            "description": "pm@ulmind.com changed project status to Delayed.",
            "new_value": {"status": "Delayed"},
            "created_at": now - timedelta(days=1)
        },
        {
            "user_id": "system_bot",
            "event_type": "backup_completed",
            "resource_type": "system",
            "resource_id": "backup_2026_06_21",
            "description": "Automated system backup completed successfully.",
            "new_value": {"size_mb": 2400},
            "created_at": now - timedelta(days=2)
        }
    ]
    
    await db["audit_logs"].insert_many(audit_logs)
    
    print("Dummy data seeded successfully!")
    close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(seed_data())
