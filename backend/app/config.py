import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = ""

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        root_db = self.base_dir / "oneeye.db"
        return f"sqlite+aiosqlite:///{root_db}"

    # Computer Vision
    DEMO_MODE: bool = False
    VIDEO_SOURCE: str = "./videos/demo/factory_safety.mp4"
    DEFAULT_CAMERA_ID: str = "CAM_01"
    MODEL_DEVICE: str = "mps"
    YOLO_MODEL_PATH: str = "yolov8n.pt"
    YOLO_CONFIDENCE: float = 0.25
    INFERENCE_FPS: int = 15

    # Evidence and Storage
    EVIDENCE_DIR: str = ""
    MAX_EVIDENCE_AGE_DAYS: int = 30

    def get_evidence_dir(self) -> Path:
        if self.EVIDENCE_DIR:
            return Path(self.EVIDENCE_DIR).resolve()
        return (self.base_dir / "evidence").resolve()

    # AI Reasoning
    ENABLE_QWEN: bool = False
    QWEN_API_KEY: str = ""
    QWEN_MODEL_NAME: str = "qwen-vl-plus"

    # Alert Channels
    ENABLE_TTS: bool = False
    SARVAM_API_KEY: str = ""
    ENABLE_WHATSAPP: bool = False
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_PHONE: str = ""
    ENABLE_TELEGRAM: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    ENABLE_RELAY: bool = False
    RELAY_TYPE: str = "mock"

    # Risk Engine (0-100)
    RISK_THRESHOLD_ADVISORY: int = 30
    RISK_THRESHOLD_HIGH: int = 60
    RISK_THRESHOLD_CRITICAL: int = 80
    EXPOSURE_ESCALATION_SECONDS: float = 5.0

    @property
    def base_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent


settings = Settings()
