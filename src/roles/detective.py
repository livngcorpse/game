from typing import Dict, Any
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.roles.base_role import BaseRole
from src.database.connection import db
from src.database.models import Role

class Detective(BaseRole):
    def __init__(self, user_id: int, game_id: str, round_number: int):
        super().__init__(user_id, game_id)
        self.round_number = round_number
        self.investigation_votes: Dict[str, Dict[int, int]] = {}

    async def can_perform_action(self, round_number: int) -> bool:
        players = await db.get_players(self.game_id)
        detectives = [p for p in players if p.is_alive and p.role == Role.DETECTIVE]
        
        if len(detectives) == 1:
            player = await db.get_player(self.game_id, self.user_id)
            return round_number - player.detective_last_investigation >= 2
        else:
            return True

    async def get_night_action_keyboard(self) -> InlineKeyboardMarkup:
        if not await self.can_perform_action(self.round_number):
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("Investigation on cooldown", callback_data="no_action")
            ]])

        players = await db.get_players(self.game_id)
        alive_players = [p for p in players if p.is_alive and p.user_id != self.user_id]
        
        buttons = []
        for player in alive_players:
            buttons.append([InlineKeyboardButton(
                f"Investigate Player {player.user_id}", 
                callback_data=f"detective_investigate_{self.game_id}_{player.user_id}"
            )])
        
        buttons.append([InlineKeyboardButton("Skip", callback_data=f"detective_skip_{self.game_id}")])
        
        return InlineKeyboardMarkup(buttons)

    async def process_night_action(self, action_data: str) -> Dict[str, Any]:
        parts = action_data.split("_")
        if len(parts) < 3:
            return {"action": "invalid"}

        action = parts[1]
        game_id = parts[2]
        
        if action == "investigate" and len(parts) >= 4:
            target_id = int(parts[3])
            return await self._process_investigation_vote(target_id)
        elif action == "skip":
            return await self._process_investigation_vote(None)
        
        return {"action": "invalid"}

    async def _process_investigation_vote(self, target_id: int) -> Dict[str, Any]:
        players = await db.get_players(self.game_id)
        alive_detectives = [p for p in players if p.is_alive and p.role == Role.DETECTIVE]
        
        if len(alive_detectives) == 1:
            if target_id is None:
                return {"action": "skip_investigation"}
            
            target_player = await db.get_player(self.game_id, target_id)
            result = "Impostor" if target_player.role == Role.IMPOSTOR else "Not Impostor"
            
            await db.update_player_field(self.game_id, self.user_id, "detective_last_investigation", self.round_number)
            
            return {"action": "investigation_complete", "target": target_id, "result": result}
        
        if self.game_id not in self.investigation_votes:
            self.investigation_votes[self.game_id] = {}
        
        self.investigation_votes[self.game_id][self.user_id] = target_id
        
        if len(self.investigation_votes[self.game_id]) == len(alive_detectives):
            return await self._resolve_group_investigation()
        
        return {"action": "vote_recorded", "target": target_id}

    async def _resolve_group_investigation(self) -> Dict[str, Any]:
        votes = self.investigation_votes[self.game_id]
        
        if None in votes.values():
            return {"action": "investigation_skipped"}
        
        targets = list(votes.values())
        if len(set(targets)) > 1:
            return {"action": "investigation_mismatch"}
        
        target_id = targets[0]
        target_player = await db.get_player(self.game_id, target_id)
        result = "Impostor" if target_player.role == Role.IMPOSTOR else "Not Impostor"
        
        return {"action": "investigation_complete", "target": target_id, "result": result}

    def get_role_description(self) -> str:
        return "🕵️ Detective\nInvestigate players to find impostors. Use your ability wisely!"

    def clear_votes(self):
        if self.game_id in self.investigation_votes:
            self.investigation_votes[self.game_id].clear()