from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""

    # AI APIs
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # App
    SECRET_KEY: str = "change-me-in-production-32chars!"
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8081"

    # Workers
    LEAFLET_CRON_HOUR: int = 8
    LEAFLET_CRON_DAY: int = 4
    ALERT_CHECK_INTERVAL_MINUTES: int = 60
    PRICE_CLEANUP_INTERVAL_HOURS: int = 6

    # Storage
    RECEIPT_IMAGES_BUCKET: str = "receipt-images"
    MAX_IMAGE_SIZE_MB: int = 10

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
