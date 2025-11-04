# config.py
import os

# Telegram / Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_NAME = os.getenv("BOT_NAME", "Inert Downloader Premium")
BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotUsername")  # without @

# Owner/admins
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS", "").split(",") if x.strip().isdigit()]
# fallback single owner
if not OWNER_IDS:
    OWNER_IDS = [int(os.getenv("OWNER_ID", "0"))] if os.getenv("OWNER_ID") else []

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# Storage channel (your provided value)
STORAGE_CHANNEL = os.getenv("STORAGE_CHANNEL", "-1003292407667")

# DB (MongoDB URI optional)
MONGODB_URI = os.getenv("MONGODB_URI", "")  # if empty, will fallback
SQLITE_DB = os.getenv("SQLITE_DB", "bot.sqlite3")
JSON_DB = os.getenv("JSON_DB", "bot.json")

# Download folder & limits
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
MAX_UPLOAD_FILESIZE = int(os.getenv("MAX_UPLOAD_FILESIZE", str(1900 * 1024 * 1024)))  # ~1.9GB
SPLIT_CHUNK_SIZE = int(os.getenv("SPLIT_CHUNK_SIZE", str(1800 * 1024 * 1024)))  # ~1.8GB per chunk

# Free user daily limit (adjustable)
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "2"))

# Default premium days if any (used for add_premium default fallback)
DEFAULT_PREMIUM_DAYS = int(os.getenv("DEFAULT_PREMIUM_DAYS", "30"))

# Premium QR
QR_CODE = os.getenv("QR_CODE", "https://i.ibb.co/hFjZ6CWD/photo-2025-08-10-02-24-51-7536777335068950548.jpg")

# yt-dlp base options
YTDLP_OPTS_BASE = {
    "quiet": True,
    "no_warnings": True,
    "ignoreerrors": False,
}

# ensure downloads dir
import os as _os
_os.makedirs(DOWNLOAD_DIR, exist_ok=True)
