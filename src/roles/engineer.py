from typing import Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.roles.base_role import BaseRole
from src.database.connection import db

class Engineer(BaseRole):
    def __init__(self, user_id: int, game_id: str):
        super().__init__(user_id, game_id)

    async def get_night_action_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("No night action", callback_data="no_action")
        ]])

    async def process_night_action(self, action_data: str) -> Dict[str, Any]:
        return {"action": "none"}

    async def get_day_action_keyboard(self) -> InlineKeyboardMarkup:
        player = await db.get_player(self.game_id, self.user_id)
        
        if not player.engineer_used_ability:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("Fix Ship", callback_data=f"engineer_fix_{self.game_id}")],
                [InlineKeyboardButton("Skip", callback_data=f"engineer_skip_{self.game_id}")]
            ])
        else:
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("Ability already used", callback_data="no_action")
            ]])

    async def process_day_action(self, action_data: str) -> Dict[str, Any]:
        parts = action_data.split("_")
        if len(parts) < 3:
            return {"action": "invalid"}

        action = parts[1]
        
        if action == "fix":
            await db.update_player_field(self.game_id, self.user_id, "engineer_used_ability", True)
            return {"action": "fix_ship", "success": True}
        elif action == "skip":
            return {"action": "skip_fix"}
        
        return {"action": "invalid"}

    def get_role_description(self) -> str:
        return "🔧 Engineer\nYou can fix the ship once per game when tasks fail. Save everyone from disaster!"