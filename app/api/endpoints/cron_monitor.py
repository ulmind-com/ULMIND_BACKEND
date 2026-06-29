import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_active_admin
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

UPTIMEROBOT_URL = "https://api.uptimerobot.com/v2/getMonitors"

@router.get("/monitors")
async def get_monitors(_admin=Depends(get_current_active_admin)):
    """
    Fetches live monitors from UptimeRobot API using form-urlencoded POST request.
    """
    payload = {
        "api_key": settings.UPTIMEROBOT_API_KEY or "ur3211458-fb7e1b4adaeaecaa74e10a50",
        "format": "json",
        "all_time_uptime_ratio": "1"
    }
    
    headers = {
        "content-type": "application/x-www-form-urlencoded",
        "cache-control": "no-cache"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                UPTIMEROBOT_URL,
                data=payload,
                headers=headers,
                timeout=15.0
            )
            
            if response.status_code != 200:
                logger.error(f"UptimeRobot API returned status {response.status_code}: {response.text}")
                raise HTTPException(status_code=502, detail="Failed to fetch monitors from UptimeRobot")
            
            data = response.json()
            
            if data.get("stat") != "ok":
                error_detail = data.get("error", {}).get("message", "Unknown error from UptimeRobot")
                logger.error(f"UptimeRobot API error: {error_detail}")
                raise HTTPException(status_code=502, detail=f"UptimeRobot API error: {error_detail}")
                
            return {
                "status": "success",
                "monitors": data.get("monitors", [])
            }
            
    except httpx.RequestError as exc:
        logger.error(f"HTTP request to UptimeRobot failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Cannot reach UptimeRobot API: {str(exc)}")
    except Exception as exc:
        logger.error(f"Unexpected error in get_monitors: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching monitors")
