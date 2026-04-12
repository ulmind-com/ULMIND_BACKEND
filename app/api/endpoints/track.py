from fastapi import APIRouter, Depends, Request, HTTPException
from typing import List
from app.db.database import get_db
from app.schemas.tracking import TrackingCreate, TrackingResponse
from app.api.deps import get_current_active_admin
import httpx
from app.core.datetime_utils import get_now
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=List[TrackingResponse])
async def get_tracking_data(
    limit: int = 100,
    skip: int = 0,
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin)
):
    """
    List all tracking telemetry data (Admin Only).
    Ordered by newest first.
    """
    cursor = db["exhaustive_tracking"].find({}).sort("created_at", -1).skip(skip).limit(limit)
    data = await cursor.to_list(length=limit)
    return data

# In-memory cache for GeoIP to avoid hitting rate limits for same IPs
# Format: {ip: {geo_data}}
GEO_IP_CACHE = {}
MAX_CACHE_SIZE = 1000

async def get_geo_info(ip: str):
    if not ip or ip in ("127.0.0.1", "::1", "localhost", "unknown"):
        return None
        
    # 1. Check Cache
    if ip in GEO_IP_CACHE:
        return GEO_IP_CACHE[ip]
        
    try:
        async with httpx.AsyncClient() as client:
            # Using a free IP geolocation API (ip-api.com)
            # Higher timeout (5.0s) and explicitly handling HTTP 429 (Rate Limit)
            response = await client.get(f"http://ip-api.com/json/{ip}", timeout=5.0)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    geo_info = {
                        "country": data.get("country"),
                        "region": data.get("regionName"),
                        "city": data.get("city"),
                        "timezone": data.get("timezone"),
                        "ll": [data.get("lat"), data.get("lon")]
                    }
                    
                    # Store in cache (with simple overflow protection)
                    if len(GEO_IP_CACHE) < MAX_CACHE_SIZE:
                        GEO_IP_CACHE[ip] = geo_info
                    return geo_info
                else:
                    logger.info(f"GeoIP Lookup: IP {ip} not found or reserved. Message: {data.get('message')}")
            elif response.status_code == 429:
                logger.info(f"GeoIP Rate Limit: Hit 45 req/min limit on ip-api.com")
            else:
                logger.debug(f"GeoIP API Error: {response.status_code} for {ip}")
                
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.info(f"GeoIP Timeout/Connection issue for {ip}: {type(e).__name__}")
    except Exception as e:
        # Unexpected errors logged as info to keep logs clean
        logger.info(f"GeoIP unexpected failure for {ip}: {e}")
        
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
        
    tracking_dict["timestamp"] = tracking_dict.get("timestamp", get_now())
    tracking_dict["created_at"] = get_now()
    tracking_dict["updated_at"] = get_now()
    
    try:
        await db["exhaustive_tracking"].insert_one(tracking_dict)
    except Exception as e:
        logger.error(f"Tracking error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
        
    return {"status": "success", "message": "Tracking data synchronized"}
