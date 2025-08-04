from datetime import datetime, timedelta
from src.database.connection import db
from src.systems.logger import BotLogger

class BanSystem:
    def __init__(self, bot_logger: BotLogger):
        self.bot_logger = bot_logger

    async def ban_user(self, user_id: int, duration: str, reason: str):
        await db.ban_user(user_id, duration, reason)
        await self.bot_logger.log_ban(user_id, duration, reason)

    async def unban_user(self, user_id: int):
        await db.unban_user(user_id)
        await self.bot_logger.log_unban(user_id)

    async def is_user_banned(self, user_id: int) -> bool:
        user = await db.get_user(user_id)
        if not user or not user.is_banned:
            return False

        if user.ban_expiry and user.ban_expiry <= datetime.now():
            await self.unban_user(user_id)
            return False

        return True

    def parse_duration(self, duration: str) -> datetime:
        if duration == "perma":
            return datetime.max

        unit = duration[-1].lower()
        amount = int(duration[:-1])

        if unit == 'h':
            return datetime.now() + timedelta(hours=amount)
        elif unit == 'd':
            return datetime.now() + timedelta(days=amount)
        elif unit == 'm':
            return datetime.now() + timedelta(days=amount * 30)

        raise ValueError("Invalid duration format")