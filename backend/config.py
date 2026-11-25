import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Application configuration. Secrets must be provided through environment variables."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'smartattend.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-jwt-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads"))
    CORS_ORIGINS = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
    BIOMETRIC_ENCRYPTION_KEY = os.getenv("BIOMETRIC_ENCRYPTION_KEY", "")
    FACE_RECOGNITION_ENABLED = os.getenv("FACE_RECOGNITION_ENABLED", "false").lower() == "true"
    AUTO_APPROVE_MANUAL_ATTENDANCE = os.getenv("AUTO_APPROVE_MANUAL_ATTENDANCE", "false").lower() == "true"
