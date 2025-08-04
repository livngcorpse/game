from typing import Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.roles.base_role import BaseRole
from src.database.connection import db
from src.database.models import Role

class Sheriff(BaseRole):
    def __init__(self, user_id: int, game_id: str):
        super().__init__(user_id, game_id)

    async def get_night_action_keyboard(self) -> InlineKeyboardMarkup:
        player = await db.get_player(self.game_id, self.user_id)
        
        if player.sheriff_shots_used == 0:
            players = await db.get_players(self.game_id)
            alive_players = [p for p in players if p.is_alive and p.user_id != self.user_id]
            
            buttons = []
            for player in alive_players:
                buttons.append([InlineKeyboardButton(
                    f"Shoot Player {player.user_id}", 
                    callback_data=f"sheriff_shoot_{self.game_id}_{player.user_id}"
                )])
            
            buttons.append([InlineKeyboardButton("Save shot", callback_data=f"sheriff_skip_{self.game_id}")])
            
            return InlineKeyboardMarkup(buttons)
        else:
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("Shot already used", callback_data="no_action")
            ]])

    async def process_night_action(self, action_data: str) -> Dict[str, Any]:
        parts = action_data.split("_")
        if len(parts) < 3:
            return {"action": "invalid"}

        action = parts[1]
        game_id = parts[2]
        
        if action == "shoot" and len(parts) >= 4:
            target_id = int(parts[3])
            return await self._process_shoot(target_id)
        elif action == "skip":
            return {"action": "skip_shot"}
        
        return {"action": "invalid"}

    async def _process_shoot(self, target_id: int) -> Dict[str, Any]:
        target_player = await db.get_player(self.game_id, target_id)
        
        if target_player.role == Role.IMPOSTOR:
            await db.kill_player(self.game_id, target_id)
            await db.update_player_field(self.game_id, self.user_id, "sheriff_shots_used", 1)
            
            return {
                "action": "successful_shot",
                "target": target_id,
                "target_role": target_player.role.value,
                "sheriff_gains_shot": True
            }
        else:
            await db.kill_player(self.game_id, target_id)
            await db.kill_player(self.game_id, self.user_id)
            await db.update_player_field(self.game_id, self.user_id, "sheriff_shots_used", 1)
            
            return {
                "action": "friendly_fire",
                "target": target_id,
                "target_role": target_player.role.value,
                "sheriff_dies": True
            }

    def get_role_description(self) -> str:
        return "🔫 Sheriff\nYou can shoot one player per game. Choose wisely - wrong shots are deadly!"