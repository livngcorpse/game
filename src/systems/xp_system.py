from src.utils.constants import XP_REWARDS, XP_PENALTIES, STREAK_BONUS
from src.database.connection import db
from src.systems.achievement_system import AchievementSystem

class XPSystem:
    def __init__(self, achievement_system: AchievementSystem):
        self.achievement_system = achievement_system

    async def award_xp(self, user_id: int, event: str, context: dict = None):
        base_xp = XP_REWARDS.get(event, 0)
        if base_xp <= 0:
            return

        user = await db.get_user(user_id)
        if not user:
            return

        streak_multiplier = 1 + (user.streak * STREAK_BONUS / 100) if event == "win" else 1
        final_xp = int(base_xp * streak_multiplier)

        await db.update_user_xp(user_id, final_xp)

        if event == "win":
            await db.update_user_streak(user_id, user.streak + 1)
        elif event == "loss":
            await db.update_user_streak(user_id, 0)

        await self._check_achievements(user_id, event, context or {})

    async def deduct_xp(self, user_id: int, event: str):
        penalty = XP_PENALTIES.get(event, 0)
        if penalty > 0:
            await db.update_user_xp(user_id, -penalty)

    async def _check_achievements(self, user_id: int, event: str, context: dict):
        if event == "win":
            user = await db.get_user(user_id)
            if user and user.xp >= 25:
                await self.achievement_system.check_and_award(user_id, "win_count_1")

        if event == "task_completed":
            await self.achievement_system.check_and_award(user_id, "tasks_completed_10")

        if event == "sheriff_kills_impostor" and context.get("game_won"):
            await self.achievement_system.check_and_award(user_id, "sheriff_kill_win")

        if event == "engineer_saves_ship":
            await self.achievement_system.check_and_award(user_id, "engineer_fix_success")

        if event == "detective_finds_impostor":
            await self.achievement_system.check_and_award(user_id, "detective_finds_3")