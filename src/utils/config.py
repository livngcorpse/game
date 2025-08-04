import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID", 0))
RANKED_GC_IDS = [int(id.strip()) for id in os.getenv("RANKED_GC_IDS", "").split(",") if id.strip()]
GAME_LOG_CHANNEL_ID = int(os.getenv("GAME_LOG_CHANNEL_ID", 0))
BOT_LOG_CHANNEL_ID = int(os.getenv("BOT_LOG_CHANNEL_ID", 0))