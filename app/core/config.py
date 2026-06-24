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

    # AI
    OPENROUTER_API_KEY: str = ""

    # Email (Resend HTTP API — works on Render, HTTPS-based)
    RESEND_API_KEY: str = ""           # Get free key at https://resend.com
    MAIL_ADDRESS: str = ""             # Verified sender email (or leave blank to use resend.dev)
    MAIL_FROM_NAME: str = "ULMiND Team"

    class Config:
        env_file = ".env"
        extra = "ignore"               # Silently skip unknown env vars (e.g. old MAIL_PASSWORD)

settings = Settings()
