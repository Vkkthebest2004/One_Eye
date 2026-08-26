from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Backend commands run from ``backend/`` while deployment runs from the
        # repository root.  Resolve this once so both environments load the
        # same settings file.
        env_file=PROJECT_ROOT / ".env",
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
            relative_sqlite_prefix = "sqlite+aiosqlite:///./"
            if self.DATABASE_URL.startswith(relative_sqlite_prefix):
                db_file = self.DATABASE_URL.removeprefix(relative_sqlite_prefix)
                return f"sqlite+aiosqlite:///{self.base_dir / db_file}"
            return self.DATABASE_URL
        root_db = self.base_dir / "oneeye.db"
        return f"sqlite+aiosqlite:///{root_db}"

    # Computer Vision
    DEMO_MODE: bool = False
    VIDEO_SOURCE: str = "./videos/demo/factory_safety.mp4"
    DEFAULT_CAMERA_ID: str = "CAM_01"
    MODEL_DEVICE: str = "mps"
    # YOLO26 is the current Ultralytics real-time family.  The nano checkpoint
    # keeps edge inference practical and downloads automatically on first use.
    YOLO_MODEL_PATH: str = "yolo26n.pt"
    # A plant must provide a PPE-trained model before claiming model-grade PPE
    # detection.  The base COCO model only supplies person detection.
    PPE_MODEL_PATH: str = ""
    YOLO_CONFIDENCE: float = 0.25
    INFERENCE_FPS: int = 15

    # Evidence and Storage
    EVIDENCE_DIR: str = ""
    MAX_EVIDENCE_AGE_DAYS: int = 30

    def get_evidence_dir(self) -> Path:
        if self.EVIDENCE_DIR:
            return Path(self.EVIDENCE_DIR).resolve()
        return (self.base_dir / "evidence").resolve()

    # AI Reasoning & Perception Engine
    DEFAULT_PERCEPTION_MODE: str = "QWEN_VL" # "QWEN_VL" | "YOLO" | "HYBRID"
    ENABLE_QWEN: bool = True
    QWEN_API_KEY: str = ""
    QWEN_MODEL_NAME: str = "qwen2-vl-7b-instruct"

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
    TRACK_LOSS_RESOLUTION_SECONDS: float = 3.0

    @property
    def base_dir(self) -> Path:
        return PROJECT_ROOT


settings = Settings()
