from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

db = Database()

def connect_to_mongo():
    try:
        db.client = AsyncIOMotorClient(settings.MONGO_URI)
        db.db = db.client.get_default_database()
        logger.info("Connected to MongoDB via Motor.")
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        raise e

def close_mongo_connection():
    if db.client:
        db.client.close()
        logger.info("Closed MongoDB connection.")

def get_db():
    return db.db
