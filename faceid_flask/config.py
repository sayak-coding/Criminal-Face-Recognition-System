import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY        = os.environ.get("SECRET_KEY", "change-me-in-production-!!!!")
    SQLALCHEMY_DATABASE_URI  = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Paths to your existing data files
    FACE_DB_PATH      = str(BASE_DIR / "face_db.pkl")
    TERRORIST_DB_PATH = str(BASE_DIR / "terrorist.db")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB upload limit


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY")   # must be set in environment
