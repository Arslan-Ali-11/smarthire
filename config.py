import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Always normalize SQLite path with forward slashes for Windows compatibility
    db_env = os.environ.get("DATABASE_URL")
    if db_env and not db_env.startswith("sqlite:///instance/"):
        if db_env.startswith("postgres://"):
            db_env = db_env.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = db_env
    else:
        db_path = os.path.join(BASE_DIR, "instance", "smarthire.db").replace("\\", "/")
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # File uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload
    ALLOWED_EXTENSIONS = {"pdf", "docx"}

    # AI API keys (set via .env or environment)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

    # Email (Gmail SMTP / Custom SMTP)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ("true", "1")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "").replace(" ", "").strip()
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", f"SmartHire <{MAIL_USERNAME}>" if MAIL_USERNAME else "SmartHire <noreply@smarthire.local>")
    MAIL_SUPPRESS_SEND = os.environ.get("MAIL_SUPPRESS_SEND", "False").lower() in ("true", "1")
