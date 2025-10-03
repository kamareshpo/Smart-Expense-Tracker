import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "expenses.db")
SQLALCHEMY_TRACK_MODIFICATIONS = False
SECRET_KEY = os.environ.get("SECRET_KEY", "replace-this-in-prod")

# Upload folders
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROFILE_UPLOAD = os.path.join(UPLOAD_FOLDER, "profile")
RECEIPT_UPLOAD = os.path.join(UPLOAD_FOLDER, "receipts")
os.makedirs(PROFILE_UPLOAD, exist_ok=True)
os.makedirs(RECEIPT_UPLOAD, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}

# Email config (optional)
SMTP_SERVER = os.environ.get("SMTP_SERVER", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", SMTP_USER)
