from fastapi import APIRouter, Depends, Request, HTTPException, Query
from datetime import datetime, timedelta
from app.core.datetime_utils import get_now
from typing import Optional
import logging

from app.db.database import get_db
from app.schemas.page_analytics import PageViewCreate, AnalyticsReport
from app.api.deps import get_current_active_admin

router = APIRouter()
logger = logging.getLogger(__name__)

COLLECTION = "page_analytics"


# ── Helper: resolve time period filter ──────────────────────────────────────

def _get_since(period: str) -> Optional[datetime]:
    """Returns the lower-bound datetime for the given period string."""
    now = get_now()
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    return None  # "all" → no lower bound


# ── POST /api/v1/analytics/pageview ─────────────────────────────────────────

@router.post("/pageview", status_code=200)
async def record_pageview(
    request: Request,
    payload: PageViewCreate,
    db=Depends(get_db)
):
    """
    Public endpoint. Called by the frontend on every page navigation.
    Can be called twice per visit:
      1. On page load  (time_spent = 0)
      2. On page unload (time_spent = actual seconds) — upserts the record.
    """
    # Extract real client IP
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )

    now = get_now()
    doc_timestamp = payload.timestamp or now

    # Upsert strategy: if a record already exists for this (session_id + page),
    # update the time_spent (on unload the frontend sends the final duration).
    # Otherwise, insert a fresh record.
    try:
        result = await db[COLLECTION].update_one(
            {
                "session_id": payload.session_id,
                "page": payload.page,
            },
            {
                "$setOnInsert": {
                    "page": payload.page,
                    "session_id": payload.session_id,
                    "referrer": payload.referrer,
                    "username": payload.username,
                    "ip": client_ip,
                    "timestamp": doc_timestamp,
                    "created_at": now,
                },
                "$set": {
                    "time_spent": payload.time_spent,
                    "updated_at": now,
                },
            },
            upsert=True,
        )
        logger.info(
            f"Page view recorded: page={payload.page} session={payload.session_id} "
            f"time_spent={payload.time_spent}s matched={result.matched_count}"
        )
    except Exception as e:
        logger.error(f"Page analytics insert error: {e}")
        raise HTTPException(status_code=500, detail="Failed to record page view")

    return {"status": "success", "message": "Page view recorded"}


# ── GET /api/v1/analytics/report ────────────────────────────────────────────

@router.get("/report", response_model=AnalyticsReport)
async def get_analytics_report(
    period: str = Query(default="7d", enum=["7d", "30d", "all"]),
    limit: int = Query(default=10, ge=1, le=50, description="Max pages to return per ranking"),
    db=Depends(get_db),
    _admin=Depends(get_current_active_admin),
):
    """
    Admin-protected endpoint. Returns aggregated page analytics:
    - Top pages by visit count
    - Top pages by total & average time spent
    Filterable by time period: 7d, 30d, or all.
    """
    since = _get_since(period)
    match_stage: dict = {}
    if since:
        match_stage = {"$match": {"timestamp": {"$gte": since}}}

    pipeline_prefix = [match_stage] if match_stage else []

    # ── 1. Total pageviews in period ──────────────────────────────────────
    count_pipeline = pipeline_prefix + [{"$count": "total"}]
    count_cursor = db[COLLECTION].aggregate(count_pipeline)
    count_result = await count_cursor.to_list(length=1)
    total_pageviews = count_result[0]["total"] if count_result else 0

    # ── 2. Top pages by visit count ───────────────────────────────────────
    visits_pipeline = pipeline_prefix + [
        {
            "$group": {
                "_id": "$page",
                "visits": {"$sum": 1},
                "unique_sessions": {"$addToSet": "$session_id"},
            }
        },
        {
            "$project": {
                "page": "$_id",
                "visits": 1,
                "unique_sessions": {"$size": "$unique_sessions"},
                "_id": 0,
            }
        },
        {"$sort": {"visits": -1}},
        {"$limit": limit},
    ]
    visits_cursor = db[COLLECTION].aggregate(visits_pipeline)
    top_pages_by_visits = await visits_cursor.to_list(length=limit)

    # ── 3. Top pages by time spent ────────────────────────────────────────
    time_pipeline = pipeline_prefix + [
        # Only count records where user actually spent time (> 0)
        {"$match": {"time_spent": {"$gt": 0}}},
        {
            "$group": {
                "_id": "$page",
                "total_time_seconds": {"$sum": "$time_spent"},
                "avg_time_seconds": {"$avg": "$time_spent"},
            }
        },
        {
            "$project": {
                "page": "$_id",
                "total_time_seconds": {"$round": ["$total_time_seconds", 2]},
                "avg_time_seconds": {"$round": ["$avg_time_seconds", 2]},
                "_id": 0,
            }
        },
        {"$sort": {"total_time_seconds": -1}},
        {"$limit": limit},
    ]
    time_cursor = db[COLLECTION].aggregate(time_pipeline)
    top_pages_by_time = await time_cursor.to_list(length=limit)

    return AnalyticsReport(
        period=period,
        total_pageviews=total_pageviews,
        top_pages_by_visits=top_pages_by_visits,
        top_pages_by_time_spent=top_pages_by_time,
    )
