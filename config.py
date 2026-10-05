"""
TikTok Auto Poster - Configuration Module
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

VIDEOS_DIR = BASE_DIR / "videos"
VIDEOS_DONE_DIR = BASE_DIR / "videos_done"
COOKIES_DIR = BASE_DIR / "cookies"
RESULTS_DIR = BASE_DIR / "results"
SCREENSHOTS_DIR = RESULTS_DIR / "screenshots"
LOGS_DIR = BASE_DIR / "logs"
ACCOUNTS_FILE = BASE_DIR / "accounts.json"
POST_HISTORY_FILE = RESULTS_DIR / "post_history.json"
USED_CAPTIONS_FILE = RESULTS_DIR / "used_captions.json"

# Create directories
for d in [VIDEOS_DIR, VIDEOS_DONE_DIR, COOKIES_DIR, RESULTS_DIR, SCREENSHOTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# TikTok Studio URLs
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
TIKTOK_FALLBACK_URL = "https://www.tiktok.com/creator-center/upload"

# Video settings
SUPPORTED_EXTENSIONS = [".mp4", ".mov", ".webm", ".avi", ".mkv"]

# Post defaults
DEFAULT_VISIBILITY = os.getenv("DEFAULT_VISIBILITY", "Public")  # 'Public', 'Friends', 'Private'
ALLOW_COMMENTS = True
ALLOW_DUET = True
ALLOW_STITCH = True

# Browser Configuration
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome")  # "chrome" (recommended) or "chromium"
VIEWPORT = {"width": 1366, "height": 850}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Scheduling & Delays
DEFAULT_INTERVAL_MINUTES = int(os.getenv("DEFAULT_INTERVAL_MINUTES", "25"))
INTERVAL_MIN_MINUTES = int(os.getenv("INTERVAL_MIN_MINUTES", "20"))
INTERVAL_MAX_MINUTES = int(os.getenv("INTERVAL_MAX_MINUTES", "30"))
INTERVAL_RANGE_MINUTES = (INTERVAL_MIN_MINUTES, INTERVAL_MAX_MINUTES)
DEFAULT_INTERVAL_SECONDS = DEFAULT_INTERVAL_MINUTES * 60
UPLOAD_TIMEOUT = 300  # Timeout for video file upload (seconds)
AFTER_UPLOAD_WAIT = 5  # Stabilization pause after video is parsed
INTER_ACCOUNT_DELAY = (20, 35)  # Natural human pause between accounts in seconds

# Video Queue Settings
MOVE_AFTER_POST = True  # Automatically move completed videos to videos_done/

# Caption Themes & Placeholders
CAPTION_THEME = os.getenv("CAPTION_THEME", "anomaly")
TOKEN_OR_PRODUCT_NAME = os.getenv("TOKEN_OR_PRODUCT_NAME", "$DEMO")
CONTRACT_ADDRESS_OR_LINK = os.getenv("CONTRACT_ADDRESS_OR_LINK", "https://example.com/item")
