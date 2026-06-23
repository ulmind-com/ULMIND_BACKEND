import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection
from app.api.endpoints import auth, client, project, team, stats, track, page_analytics, merchandise, user_management, offers, sheets, ai, activity, finance, notification, task, crm_enterprise, pm_enterprise, team_enterprise, audit, project_env, delete_requests
from app.api import websockets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_to_mongo()
    yield
    close_mongo_connection()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Exhaustive Tracking Backend for UlMind",
    version="2.0.0",
    lifespan=lifespan
)

# Rate Limiter setup
from app.core.limiter import limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An internal server error occurred.",
            "detail": str(exc) if settings.DEBUG else "Internal Server Error"
        }
    )

# CORS Middleware - Permissive for tracking and frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Set to False to allow wildcard origins with Bearer tokens
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(client.router, prefix=f"{settings.API_V1_STR}/clients", tags=["Clients"])
app.include_router(project.router, prefix=f"{settings.API_V1_STR}/projects", tags=["Projects"])
app.include_router(project_env.router, prefix=f"{settings.API_V1_STR}/projects", tags=["Project Env"])
app.include_router(team.router, prefix=f"{settings.API_V1_STR}/team", tags=["Team"])
app.include_router(stats.router, prefix=f"{settings.API_V1_STR}/stats", tags=["Stats"])
app.include_router(track.router, prefix=f"{settings.API_V1_STR}/track", tags=["Track"])
app.include_router(page_analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])
app.include_router(merchandise.router, prefix=f"{settings.API_V1_STR}/merchandise", tags=["Merchandise"])
app.include_router(user_management.router, prefix=f"{settings.API_V1_STR}/user-management", tags=["User Management"])
app.include_router(offers.router, prefix=f"{settings.API_V1_STR}/offers", tags=["Offers"])
app.include_router(sheets.router, prefix=f"{settings.API_V1_STR}/sheets", tags=["Sheets"])
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}/ai", tags=["AI"])
app.include_router(activity.router, prefix=f"{settings.API_V1_STR}/activity", tags=["Activity"])
app.include_router(websockets.router, tags=["WebSockets"])
app.include_router(finance.router, prefix=f"{settings.API_V1_STR}/finance", tags=["Finance"])
app.include_router(notification.router, prefix=f"{settings.API_V1_STR}/notifications", tags=["Notifications"])
app.include_router(task.router, prefix=f"{settings.API_V1_STR}/tasks", tags=["Tasks"])
app.include_router(crm_enterprise.router, prefix=f"{settings.API_V1_STR}/crm", tags=["CRM Enterprise"])
app.include_router(pm_enterprise.router, prefix=f"{settings.API_V1_STR}/pm", tags=["Project Management"])
app.include_router(team_enterprise.router, prefix=f"{settings.API_V1_STR}/team-hr", tags=["Team Enterprise"])
app.include_router(audit.router, prefix=f"{settings.API_V1_STR}/audit", tags=["Audit"])
app.include_router(delete_requests.router, prefix=f"{settings.API_V1_STR}/delete-requests", tags=["Delete Requests"])
@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "success", "message": "Server is healthy"}
