from fastapi import APIRouter, Depends, Request, HTTPException
from app.db.database import get_db
from app.schemas.tracking import TrackingCreate
import httpx
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_geo_info(ip: str):
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return None
        
    try:
        async with httpx.AsyncClient() as client:
            # Using a free IP geolocation API 
            response = await client.get(f"http://ip-api.com/json/{ip}", timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {
                        "country": data.get("country"),
                        "region": data.get("regionName"),
                        "city": data.get("city"),
                        "timezone": data.get("timezone"),
                        "ll": [data.get("lat"), data.get("lon")]
                    }
    except Exception as e:
        logger.warning(f"GeoIP Error for {ip}: {e}")
    return None

@router.post("/")
async def track_data(request: Request, track_in: TrackingCreate, db=Depends(get_db)):
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
        
    geo_data = await get_geo_info(client_ip)
    
    tracking_dict = track_in.model_dump(exclude_unset=True)
    tracking_dict["ip"] = client_ip
    if geo_data:
        tracking_dict["geo"] = geo_data
        
    tracking_dict["timestamp"] = tracking_dict.get("timestamp", datetime.now(timezone.utc))
    tracking_dict["created_at"] = datetime.now(timezone.utc)
    tracking_dict["updated_at"] = datetime.now(timezone.utc)
    
    try:
        await db["exhaustive_tracking"].insert_one(tracking_dict)
    except Exception as e:
        logger.error(f"Tracking error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
        
    return {"status": "success", "message": "Tracking data synchronized"}
