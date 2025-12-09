import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Handle BOT_OWNER_ID with proper error handling
try:
    BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 0))
except (ValueError, TypeError):
    BOT_OWNER_ID = 0

# Handle RANKED_GC_IDS with proper error handling
try:
    RANKED_GC_IDS = [int(id.strip()) for id in os.getenv("RANKED_GC_IDS", "").split(",") if id.strip()]
except (ValueError, TypeError):
    RANKED_GC_IDS = []

# Handle channel IDs with proper error handling
try:
    GAME_LOG_CHANNEL_ID = int(os.getenv("GAME_LOG_CHANNEL_ID", 0))
except (ValueError, TypeError):
    GAME_LOG_CHANNEL_ID = 0

try:
    BOT_LOG_CHANNEL_ID = int(os.getenv("BOT_LOG_CHANNEL_ID", 0))
except (ValueError, TypeError):
    BOT_LOG_CHANNEL_ID = 0