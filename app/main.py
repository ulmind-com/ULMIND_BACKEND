from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection
from app.api.endpoints import auth, client, project, team, stats, track

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_to_mongo()
    yield
    close_mongo_connection()

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(client.router, prefix=f"{settings.API_V1_STR}/clients", tags=["clients"])
app.include_router(project.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(team.router, prefix=f"{settings.API_V1_STR}/team", tags=["team", "admin"])
app.include_router(stats.router, prefix=f"{settings.API_V1_STR}/stats", tags=["stats"])
app.include_router(track.router, prefix=f"{settings.API_V1_STR}/track", tags=["track"])

@app.get("/health")
async def health_check():
    return {"status": "success", "message": "Server is healthy"}

# We will include routers later
