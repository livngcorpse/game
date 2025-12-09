from src.utils.constants import XP_REWARDS, XP_PENALTIES, STREAK_BONUS
from src.database.connection import db
from src.systems.achievement_system import AchievementSystem
from typing import Any

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
        user = await db.get_user(user_id)
        if not user:
            return
            
        # Track task completions
        if event == "task_completed":
            # Increment task counter in user achievements
            task_count = user.achievements.get("task_counter", 0) + 1
            await self._update_user_achievement(user_id, "task_counter", task_count)
            
            # Check for Task Master achievement
            if task_count >= 10:
                await self.achievement_system.check_and_award(user_id, "tasks_completed_10")

        # Track wins
        if event == "win":
            # Check for First Victory achievement
            if user.xp >= 25:  # Assuming first win gives 25 XP
                await self.achievement_system.check_and_award(user_id, "win_count_1")
            
            # Track win streak for other achievements
            win_streak = user.achievements.get("win_streak", 0) + 1
            await self._update_user_achievement(user_id, "win_streak", win_streak)

        # Track losses
        elif event == "loss":
            # Reset win streak
            await self._update_user_achievement(user_id, "win_streak", 0)

        # Track sheriff kills
        if event == "sheriff_kills_impostor":
            # Check for Sheriff Clutch achievement
            if context.get("game_won"):
                await self.achievement_system.check_and_award(user_id, "sheriff_kill_win")

        # Track engineer saves
        if event == "engineer_saves_ship":
            await self.achievement_system.check_and_award(user_id, "engineer_fix_success")

        # Track detective findings
        if event == "detective_finds_impostor":
            # Track detective streak
            detective_streak = user.achievements.get("detective_streak", 0) + 1
            await self._update_user_achievement(user_id, "detective_streak", detective_streak)
            
            # Check for Detective Streak achievement
            if detective_streak >= 3:
                await self.achievement_system.check_and_award(user_id, "detective_finds_3")

    async def _update_user_achievement(self, user_id: int, key: str, value: Any):
        """Update a specific achievement counter for a user"""
        user = await db.get_user(user_id)
        if not user:
            return
            
        achievements = user.achievements or {}
        achievements[key] = value
        
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET achievements = $1 WHERE id = $2",
                achievements, user_id
            )