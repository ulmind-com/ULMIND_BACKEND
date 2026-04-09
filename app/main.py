import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection
from app.api.endpoints import auth, client, project, team, stats, track, page_analytics, merchandise, user_management

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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(client.router, prefix=f"{settings.API_V1_STR}/clients", tags=["Clients"])
app.include_router(project.router, prefix=f"{settings.API_V1_STR}/projects", tags=["Projects"])
app.include_router(team.router, prefix=f"{settings.API_V1_STR}/team", tags=["Team"])
app.include_router(stats.router, prefix=f"{settings.API_V1_STR}/stats", tags=["Stats"])
app.include_router(track.router, prefix=f"{settings.API_V1_STR}/track", tags=["Track"])
app.include_router(page_analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])
app.include_router(merchandise.router, prefix=f"{settings.API_V1_STR}/merchandise", tags=["Merchandise"])
app.include_router(user_management.router, prefix=f"{settings.API_V1_STR}/user-management", tags=["User Management"])

@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "success", "message": "Server is healthy"}
