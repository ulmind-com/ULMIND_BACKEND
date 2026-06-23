import httpx
import json
from app.core.config import settings

class AINotificationService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
    async def analyze_event(self, event_type: str, data: dict) -> dict:
        """
        Analyzes an event and returns AI-enhanced insights for a notification.
        Returns a dictionary with:
        - title
        - message
        - priority (Low, Medium, High, Critical)
        - category (CRM, Project, Finance, Team, Security, System)
        - recommended_action
        """
        prompt = f"""
You are the AI engine for ULMIND, an enterprise web application.
An event just occurred. Analyze it and generate a notification summary.

Event Type: {event_type}
Data: {json.dumps(data, default=str)}

Return ONLY a raw JSON object (no markdown formatting, no code blocks) with these exact keys:
{{
  "title": "Short notification title",
  "message": "1-2 sentence detailed summary",
  "priority": "Low", // Can be Low, Medium, High, or Critical
  "category": "CRM", // Can be CRM, Project, Finance, Team, Security, or System
  "recommended_action": "e.g., View Client, Follow Up"
}}
"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": settings.CORS_ORIGIN, # Assuming CORS_ORIGIN is the frontend URL
            "X-Title": "ULMIND Notification Engine",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/gemini-2.5-pro", # OpenRouter supports google/gemini-pro
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                
                resp_data = response.json()
                content = resp_data['choices'][0]['message']['content'].strip()
                
                # Strip markdown blocks if any exist
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                    
                result = json.loads(content)
                return result
        except Exception as e:
            # Fallback in case of AI failure
            print(f"AI Notification Error: {e}")
            return {
                "title": f"New {event_type.replace('_', ' ').title()}",
                "message": "System event occurred.",
                "priority": "Medium",
                "category": "System",
                "recommended_action": "View Details"
            }

ai_notification_service = AINotificationService()
