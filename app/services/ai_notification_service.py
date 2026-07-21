import asyncio
import httpx
import json
import time
from typing import Optional
from app.core.config import settings


# ── Deterministic classification ────────────────────────────────
# The AI call is an enhancement, not a dependency. Everything below
# produces a genuinely useful notification on its own, so an expired
# API key or a rate limit degrades the wording — never the feature.

CATEGORY_RULES = [
    (("crm_", "client", "lead", "contact"), "CRM"),
    (("invoice", "payment", "expense", "finance", "salary", "revenue"), "Finance"),
    (("task", "project", "milestone", "sprint"), "Project"),
    (("employee", "team", "hw_", "hardware", "attendance", "session"), "Team"),
    (("security", "login", "auth", "password", "otp", "permission", "role", "delete_request"), "Security"),
]

# Actions that deserve attention when they happen.
HIGH_PRIORITY_HINTS = ("deleted", "removed", "failed", "expired", "overdue", "breach", "rejected")
CRITICAL_HINTS = ("security", "breach", "unauthorized", "fraud")
LOW_PRIORITY_HINTS = ("viewed", "opened", "read", "heartbeat")

# Human labels for the entity part of an event type.
ENTITY_LABELS = {
    "crm_activity": "activity",
    "crm_meeting": "meeting",
    "crm_contract": "contract",
    "crm_document": "document",
    "client": "client",
    "invoice": "invoice",
    "payment": "payment",
    "expense": "expense",
    "task": "task",
    "project": "project",
    "employee": "employee",
}

# Fields worth quoting in the message, in order of preference.
NAME_FIELDS = ("title", "companyName", "name", "invoice_number", "contract_number",
               "content", "description", "employee_id")


def _split_event(event_type: str) -> tuple[str, str]:
    """"crm_contract_created" -> ("crm_contract", "created")"""
    normalised = event_type.replace("-", "_").lower()
    parts = normalised.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in {
        "created", "updated", "deleted", "received", "completed",
        "cancelled", "assigned", "failed", "approved", "rejected",
    }:
        return parts[0], parts[1]
    return normalised, ""


def _categorise(event_type: str) -> str:
    lowered = event_type.lower()
    for needles, category in CATEGORY_RULES:
        if any(n in lowered for n in needles):
            return category
    return "System"


def _prioritise(event_type: str, action: str) -> str:
    lowered = event_type.lower()
    if any(h in lowered for h in CRITICAL_HINTS):
        return "Critical"
    if action in ("deleted", "failed", "rejected") or any(h in lowered for h in HIGH_PRIORITY_HINTS):
        return "High"
    if any(h in lowered for h in LOW_PRIORITY_HINTS):
        return "Low"
    return "Medium"


def _subject(data: dict) -> Optional[str]:
    """Pull a human-recognisable name out of the event payload."""
    if not isinstance(data, dict):
        return None
    for field in NAME_FIELDS:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            return text if len(text) <= 60 else text[:57] + "..."
    return None


ACTION_VERBS = {
    "created": "created",
    "updated": "updated",
    "deleted": "deleted",
    "received": "received",
    "completed": "completed",
    "cancelled": "cancelled",
    "assigned": "assigned",
    "failed": "failed",
    "approved": "approved",
    "rejected": "rejected",
}

ACTION_LABELS = {
    "created": "Review",
    "updated": "View changes",
    "deleted": "Open section",
    "received": "View payment",
    "completed": "View details",
    "cancelled": "View details",
    "assigned": "Open task",
}


def build_fallback(event_type: str, data: dict) -> dict:
    """A real notification built purely from the event — no AI needed."""
    entity_key, action = _split_event(event_type)
    entity = ENTITY_LABELS.get(entity_key, entity_key.replace("_", " ").strip() or "record")
    verb = ACTION_VERBS.get(action, "")
    subject = _subject(data)

    if verb:
        title = f"{entity.capitalize()} {verb}"
    else:
        title = entity.replace("_", " ").capitalize()

    if subject and verb:
        message = f'"{subject}" was {verb}.'
    elif subject:
        # No recognisable action in the event name — don't invent one.
        message = subject if subject.endswith((".", "!", "?")) else f"{subject}."
    elif verb:
        message = f"A {entity} was {verb}."
    else:
        message = f"A {entity} event was recorded."

    return {
        "title": title,
        "message": message,
        "priority": _prioritise(event_type, action),
        "category": _categorise(event_type),
        "recommended_action": ACTION_LABELS.get(action, "View details"),
        "ai_generated": False,
    }


class AINotificationService:
    """Wraps the OpenRouter call with a circuit breaker.

    Without the breaker a dead key made every single event wait for the
    10s HTTP timeout before falling back, which slowed every mutation in
    the app and filled the log with the same error.
    """

    # How long to stop calling the API after a hard failure (auth/quota).
    COOLDOWN_SECONDS = 15 * 60

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self._disabled_until: float = 0.0
        self._last_reason: str = ""

    @property
    def available(self) -> bool:
        if not self.api_key:
            return False
        return time.monotonic() >= self._disabled_until

    def _trip_breaker(self, reason: str, permanent: bool = False):
        self._last_reason = reason
        # A quota/auth problem will not fix itself in seconds — back off.
        self._disabled_until = time.monotonic() + (self.COOLDOWN_SECONDS * (4 if permanent else 1))
        print(f"[ai-notifications] disabled for a while: {reason}")

    async def analyze_event(self, event_type: str, data: dict) -> dict:
        """Return notification fields, AI-enriched when possible."""
        fallback = build_fallback(event_type, data)
        if not self.available:
            return fallback

        prompt = f"""
You are the AI engine for ULMIND, an enterprise web application.
An event just occurred. Analyze it and generate a notification summary.

Event Type: {event_type}
Data: {json.dumps(data, default=str)[:2000]}

Return ONLY a raw JSON object (no markdown formatting, no code blocks) with these exact keys:
{{
  "title": "Short notification title",
  "message": "1-2 sentence detailed summary",
  "priority": "Low",
  "category": "CRM",
  "recommended_action": "e.g., View Client, Follow Up"
}}
Priority must be one of Low, Medium, High, Critical.
Category must be one of CRM, Project, Finance, Team, Security, System.
"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": settings.CORS_ORIGIN,
            "X-Title": "ULMIND Notification Engine",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "google/gemini-2.5-pro",
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(self.base_url, headers=headers, json=payload)

            if response.status_code in (401, 402, 403, 429):
                # No credit / bad key / rate limited — stop hammering it.
                self._trip_breaker(
                    f"HTTP {response.status_code} from OpenRouter",
                    permanent=response.status_code in (401, 402, 403),
                )
                return fallback
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()

            result = json.loads(content)
            # Never let a malformed AI reply produce an empty notification.
            merged = {**fallback, **{k: v for k, v in result.items() if v}}
            if merged.get("priority") not in ("Low", "Medium", "High", "Critical"):
                merged["priority"] = fallback["priority"]
            if merged.get("category") not in ("CRM", "Project", "Finance", "Team", "Security", "System"):
                merged["category"] = fallback["category"]
            merged["ai_generated"] = True
            return merged

        except (httpx.TimeoutException, httpx.RequestError) as e:
            self._trip_breaker(f"network error: {e}")
            return fallback
        except Exception as e:
            print(f"[ai-notifications] unusable response, using fallback: {e}")
            return fallback


ai_notification_service = AINotificationService()
