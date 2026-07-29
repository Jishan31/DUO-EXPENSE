import os
from dotenv import load_dotenv

load_dotenv()  # reads a .env file in the project root, if present

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # In production, set SECRET_KEY as an environment variable instead of hardcoding it.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-this-in-production")

    # Locally, this defaults to a SQLite file — zero setup needed. On Render
    # (or any host that provides a DATABASE_URL), it uses that instead, which
    # is required there since Render's filesystem doesn't persist a SQLite
    # file across deploys/restarts. Render's Postgres URLs start with
    # "postgres://", but SQLAlchemy 1.4+ requires "postgresql://" — the
    # replace() below is not optional, connections fail without it.
    _database_url = os.environ.get("DATABASE_URL", "")
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url or ("sqlite:///" + os.path.join(BASE_DIR, "instance", "expense_tracker.db"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB upload limit (receipts)
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

    # Session / cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 14  # 14 days

    # AI Assistant — set GEMINI_API_KEY in your environment (or a .env file)
    # to enable it. Free tier, no credit card required: aistudio.google.com/apikey
    # ASSISTANT_MODEL is optional — if unset, the app auto-detects a working
    # Flash model for your key (Gemini model names change over time).
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    ASSISTANT_MODEL = os.environ.get("ASSISTANT_MODEL", "")
