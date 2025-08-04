from src.systems.achievements import ACHIEVEMENTS
from src.database.connection import db
from telegram import Bot

class AchievementSystem:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def check_and_award(self, user_id: int, trigger: str, context: dict = None):
        user = await db.get_user(user_id)
        if not user:
            return

        for achievement_id, achievement in ACHIEVEMENTS.items():
            if achievement["trigger"] == trigger and not user.achievements.get(achievement_id, False):
                await self._award_achievement(user_id, achievement_id, achievement)

    async def _award_achievement(self, user_id: int, achievement_id: str, achievement: dict):
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET achievements = achievements || $1 WHERE id = $2",
                {achievement_id: True}, user_id
            )

        try:
            await self.bot.send_message(
                user_id,
                f"🏆 Achievement Unlocked!\n\n{achievement['name']}\n{achievement['description']}"
            )
        except:
            pass

    async def get_user_achievements(self, user_id: int) -> dict:
        user = await db.get_user(user_id)
        return user.achievements if user else {}