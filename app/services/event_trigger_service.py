import asyncio
from app.db.database import get_db
from app.api.websockets import manager
from app.services.ai_notification_service import ai_notification_service
from app.core.datetime_utils import get_now
import uuid

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
        "details": f"{user_email} triggered {event_type} on {resource_type}",
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
    
    # 2. Create Notification
    notif_doc = {
        "user_id": "global", # Or specific admin user ID
        "type": event_type,
        "title": ai_result.get("title", f"New {event_type}"),
        "message": ai_result.get("message", "System event occurred."),
        "priority": ai_result.get("priority", "Info"),
        "category": ai_result.get("category", "System"),
        "recommended_action": ai_result.get("recommended_action"),
        "is_read": False,
        "link": f"/admin/{resource_type}/{resource_id}",
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
