import asyncio
import os
import json
import urllib.request
from datetime import datetime, timedelta
from pymongo import MongoClient

# Base URLs and setup
BASE_URL = "http://localhost:8000/api/v1"
client = MongoClient("mongodb+srv://samiran:samiran2004@cluster2004.eowyegm.mongodb.net/ulmind")
db = client.get_default_database()

def get_token():
    req = urllib.request.Request(f"{BASE_URL}/auth/login", data=json.dumps({"username": "arnab.senapati@ulmind.com", "password": "ulmind@123"}).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["token"]

def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    print("--- 1. Creating Realistic Project ---")
    proj_data = {
        "name": "SmartInvest CRM Dashboard v2",
        "client_name": "SmartInvest Solutions",
        "client_email": "contact@smartinvest.com",
        "client_phone": "+1-800-555-0199",
        "status": "Active",
        "cost": 150000,
        "currency": "INR",
        "payment_status": "Pending",
        "start_date": datetime.now().isoformat(),
        "end_date": (datetime.now() + timedelta(days=60)).isoformat(),
        "notes": "End-to-End Enterprise Validation Project"
    }
    
    req = urllib.request.Request(f"{BASE_URL}/projects/", data=json.dumps(proj_data).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            project = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("Failed to create project:", e)
        return
        
    project_id = project["_id"]
    print(f"✅ Project Created: {project['name']} (ID: {project_id})")
    
    print("\n--- 2. Assigning Task to Arnab ---")
    # Get Arnab's ID
    arnab = db.admins.find_one({"email": "arnab.senapati@ulmind.com"})
    if not arnab:
        print("Arnab not found in database.")
        return
        
    task_data = {
        "title": "Frontend Dashboard Development",
        "description": "Develop the primary dashboard UI for SmartInvest. Needs robust charting, data tables, and dark mode support.",
        "project_id": project_id,
        "assigned_to": str(arnab["_id"]),
        "status": "In Progress",
        "priority": "Urgent",
        "due_date": (datetime.now() + timedelta(days=7)).isoformat()
    }
    
    req = urllib.request.Request(f"{BASE_URL}/tasks/", data=json.dumps(task_data).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            task = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("Failed to create task:", e)
        return
        
    task_id = task["_id"]
    print(f"✅ Task Assigned: {task['title']} (ID: {task_id})")
    
    print("\n--- 3. Triggering Premium Email Notification ---")
    req = urllib.request.Request(f"{BASE_URL}/tasks/{task_id}/notify", method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"✅ Email notification endpoint succeeded: {json.loads(resp.read().decode('utf-8'))}")
    except Exception as e:
        print(f"❌ Email notification failed: {e}")
        
    print("\n--- 4. Validating Automatic Integrations in Database ---")
    # Wait a moment for background events to fire
    import time
    time.sleep(2)
    
    audit = db.audit.find_one({"details": {"$regex": task_id}})
    print(f"Audit Log Created: {'✅ Yes' if audit else '❌ No'}")
    
    activity = db.activity_logs.find_one({"resource_id": task_id})
    print(f"Activity Feed Created: {'✅ Yes' if activity else '❌ No'}")
    
    notif = db.notifications.find_one({"link": f"/admin/tasks/{task_id}"})
    print(f"AI Notification Created: {'✅ Yes' if notif else '❌ No'}")
    
    emp_timeline = db.employee_timeline.find_one({"resource_id": task_id})
    print(f"Employee Timeline Created: {'✅ Yes' if emp_timeline else '❌ No'}")
    
    proj_timeline = db.project_timeline.find_one({"resource_id": task_id})
    print(f"Project Timeline Created: {'✅ Yes' if proj_timeline else '❌ No'}")
    
    work_log = db.work_logs.find_one({"task_id": task_id})
    print(f"Work Log Created: {'✅ Yes' if work_log else '❌ No'}")
    
    print("\n--- End-to-End Workflow Validation Complete ---")

if __name__ == "__main__":
    main()
