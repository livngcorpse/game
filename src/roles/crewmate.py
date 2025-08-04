from typing import Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.roles.base_role import BaseRole
from src.game.task_engine import TaskEngine

class Crewmate(BaseRole):
    def __init__(self, user_id: int, game_id: str, task_engine: TaskEngine):
        super().__init__(user_id, game_id)
        self.task_engine = task_engine

    async def get_night_action_keyboard(self) -> InlineKeyboardMarkup:
        task = self.task_engine.get_player_task(self.game_id, self.user_id)
        
        if task:
            return InlineKeyboardMarkup([[
                InlineKeyboardButton(task["button_text"], callback_data=f"task_complete_{self.game_id}_{self.user_id}")
            ]])
        else:
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("No task assigned", callback_data="no_action")
            ]])

    async def process_night_action(self, action_data: str) -> Dict[str, Any]:
        if action_data.startswith("task_complete"):
            success = await self.task_engine.complete_task(self.game_id, self.user_id)
            return {"action": "task_complete", "success": success}
        return {"action": "none"}

    def get_role_description(self) -> str:
        return "🔧 Crewmate\nComplete tasks to keep the ship running. Vote out the impostors!"