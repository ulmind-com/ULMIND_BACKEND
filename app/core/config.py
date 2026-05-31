from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 5000
    MONGO_URI: str
    CORS_ORIGIN: str = "*"
    NODE_ENV: str = "development"
    DEBUG: bool = False
    JWT_SECRET: str
    PROJECT_NAME: str = "ulmind-tracking-backend"
    API_V1_STR: str = "/api/v1"

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # Email (SMTP — Gmail)
    MAIL_ADDRESS: str = ""
    MAIL_PASSWORD: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
