from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 5000
    MONGO_URI: str
    CORS_ORIGIN: str = "*"
    NODE_ENV: str = "development"
    JWT_SECRET: str
    PROJECT_NAME: str = "ulmind-tracking-backend"
    API_V1_STR: str = "/api/v1"

    class Config:
        env_file = ".env"

settings = Settings()
