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

    # Email (Resend HTTP API)
    RESEND_API_KEY: str = ""               # For @ulmind.com
    RESEND_API_KEY_ULMIND_IN: str = ""     # For @ulmind.in
    MAIL_ADDRESS: str = ""                 # Sender for ulmind.com
    MAIL_ADDRESS_ULMIND_IN: str = ""       # Sender for ulmind.in
    ZOHO_SMTP_PASS: str = ""
    MAIL_FROM_NAME: str = "ULMiND Team"
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"               # Silently skip unknown env vars (e.g. old MAIL_PASSWORD)

settings = Settings()

# Hot reload trigger 2
