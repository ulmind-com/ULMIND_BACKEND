import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_twilio_sms(phone: str, message: str) -> None:
    """
    Send an SMS using Twilio REST API.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_FROM_NUMBER:
        logger.info("Twilio credentials are not configured. Skipping SMS.")
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    
    # Ensure phone has + country code, defaulting to +91 if not present
    formatted_phone = phone if phone.startswith('+') else f"+91{phone}"

    payload = {
        "To": formatted_phone,
        "From": settings.TWILIO_FROM_NUMBER,
        "Body": message
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data=payload,
                timeout=10.0
            )
            if response.status_code in [200, 201]:
                logger.info(f"Twilio SMS sent successfully to {formatted_phone}")
            else:
                logger.error(f"Twilio API Error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Failed to send Twilio SMS to {formatted_phone}: {e}")

async def send_task_sms_and_whatsapp(phone: str, task: dict, project_name: str, assigned_by: str) -> None:
    """
    Trigger Twilio SMS for a newly assigned task with premium formatting.
    """
    if not phone or len(phone) < 10:
        logger.info("No valid phone number provided for task assignee.")
        return
        
    # Strip non-numeric characters for safety (keep + if present)
    clean_phone = "".join(c for c in phone if c.isdigit() or c == '+')

    # Extract task details safely
    task_id = task.get("task_id") or str(task.get("_id", "Unknown"))
    title = task.get("title", "Untitled Task")
    est_hours = task.get("estimated_hours", 0)
    
    # Calculate days to complete based on due date
    due_date_str = "No due date"
    if task.get("due_date"):
        from datetime import datetime
        try:
            # Check if it's already a datetime object or a string
            due = task["due_date"]
            if isinstance(due, str):
                due = datetime.fromisoformat(due.replace('Z', '+00:00'))
            
            # Format nicely
            due_date_str = due.strftime("%d %b %Y")
            
            # Calculate days left
            delta = due.date() - datetime.now().date()
            if delta.days == 0:
                due_date_str += " (Today)"
            elif delta.days == 1:
                due_date_str += " (Tomorrow)"
            elif delta.days > 1:
                due_date_str += f" ({delta.days} days left)"
            elif delta.days < 0:
                due_date_str += f" (Overdue by {abs(delta.days)} days)"
        except Exception:
            due_date_str = str(task["due_date"])

    # Build the premium message
    message = (
        f"ULMiND Task Assigned!\n\n"
        f"ID: {task_id}\n"
        f"Title: {title[:40]}\n"
        f"Project: {project_name[:20]}\n"
        f"Est. Time: {est_hours} Hours\n"
        f"Due: {due_date_str}\n"
        f"By: {assigned_by}\n\n"
        f"View: https://ulmind.com/admin/projects/tasks?search={task_id}"
    )
    
    # Send the SMS
    await send_twilio_sms(clean_phone, message)
