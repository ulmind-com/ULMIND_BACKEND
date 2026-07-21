import asyncio
from app.db.database import get_db
from app.api.websockets import manager
from app.services.ai_notification_service import ai_notification_service
from app.core.datetime_utils import get_now
import uuid

# Where a notification should take you. The old code built
# "/admin/{resource_type}/{id}" which produced dead URLs like
# "/admin/crm_documents/<id>" — no such route exists in the SPA.
# `{id}` is substituted when the route can show a single record.
RESOURCE_ROUTES = {
    "clients": "/admin/crm/clients/{id}",
    "crm_activities": "/admin/crm/activities",
    "crm_meetings": "/admin/crm/meetings",
    "crm_contracts": "/admin/crm/contracts",
    "crm_documents": "/admin/crm/documents",
    "invoices": "/admin/finance/invoices",
    "payments": "/admin/finance/payments",
    "expenses": "/admin/finance/expenses",
    "projects": "/admin/projects/{id}",
    "tasks": "/admin/projects/tasks",
    "employees": "/admin/team",
    "offers": "/admin/offers",
    "delete_requests": "/admin/delete-requests",
}


def build_notification_link(resource_type: str, resource_id: str) -> str:
    """Resolve an in-app route for the event, falling back to the
    notification dashboard rather than a URL that 404s."""
    template = RESOURCE_ROUTES.get(resource_type)
    if not template:
        return "/admin/notifications"
    return template.format(id=resource_id) if "{id}" in template else template

async def trigger_system_event(
    event_type: str, 
    resource_type: str, 
    resource_id: str, 
    user_email: str, 
    data: dict, 
    db
):
    """
    Fire an event asynchronously without blocking the main request.
    This creates an Audit Log and an AI Notification, then broadcasts via WebSockets.
    """
    
    # Run AI Analysis safely
    try:
        ai_result = await ai_notification_service.analyze_event(event_type, data)
    except Exception as e:
        print(f"AI Notification Service Error: {e}")
        ai_result = {}
    
    now = get_now()
    
    # 1. Create Audit Log
    audit_doc = {
        "action": event_type,
        "admin_email": user_email,
        "details": f"{user_email} triggered {event_type} on {resource_type} (ID: {resource_id})",
        "timestamp": now
    }
    await db["audit"].insert_one(audit_doc)

    # Also insert into activity_logs for Activity Feed
    activity_doc = {
        "event_type": event_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action_description": f"New activity: {event_type}",
        "performed_by": user_email,
        "timestamp": now
    }
    await db["activity_logs"].insert_one(activity_doc)

    # 1.5 Create Timeline and Work Log Records if it's a TASK event
    if "TASK" in event_type:
        project_id = data.get("project_id") or data.get("task_in", {}).get("project_id")
        assigned_to = data.get("assigned_to") or data.get("task_in", {}).get("assigned_to")
        
        if assigned_to:
            timeline_doc = {
                "user_id": assigned_to,
                "event_type": event_type,
                "description": f"Task {event_type.split('_')[-1].lower()} in project.",
                "resource_id": resource_id,
                "timestamp": now
            }
            await db["employee_timeline"].insert_one(timeline_doc)
            
            # Create a zero-hour work log just to log the assignment activity
            if event_type == "TASK_CREATED":
                work_log = {
                    "user_id": assigned_to,
                    "project_id": project_id,
                    "task_id": resource_id,
                    "hours": 0.0,
                    "description": "Task initially assigned",
                    "date": now,
                    "timestamp": now
                }
                await db["work_logs"].insert_one(work_log)
                
        if project_id:
            proj_timeline = {
                "project_id": project_id,
                "event_type": event_type,
                "description": f"Task event: {event_type}",
                "resource_id": resource_id,
                "timestamp": now
            }
            await db["project_timeline"].insert_one(proj_timeline)
    
    # 2. Create Notification
    notif_doc = {
        "user_id": "global", # Or specific admin user ID
        "type": event_type,
        "title": ai_result.get("title") or f"New {event_type}",
        "message": ai_result.get("message") or "System event occurred.",
        "priority": ai_result.get("priority") or "Medium",
        "category": ai_result.get("category") or "System",
        "recommended_action": ai_result.get("recommended_action"),
        # Lets the UI mark which alerts were genuinely AI-written.
        "ai_generated": bool(ai_result.get("ai_generated")),
        "actor": user_email,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "is_read": False,
        "link": build_notification_link(resource_type, resource_id),
        "created_at": now
    }
    
    result = await db["notifications"].insert_one(notif_doc)
    notif_doc["_id"] = str(result.inserted_id)
    
    # 3. Broadcast to WebSockets
    await manager.broadcast_to_admins({
        "type": "NEW_NOTIFICATION",
        "notification": notif_doc
    })
    
def fire_event_background(event_type: str, resource_type: str, resource_id: str, user_email: str, data: dict, db):
    """
    Convenience method to fire the event without await.
    Requires an active event loop.
    """
    asyncio.create_task(
        trigger_system_event(event_type, resource_type, resource_id, user_email, data, db)
    )
