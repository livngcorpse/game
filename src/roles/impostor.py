from typing import Dict, Any, List
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from src.roles.base_role import BaseRole
from src.database.connection import db
from src.database.models import Role

class Impostor(BaseRole):
    def __init__(self, user_id: int, game_id: str):
        super().__init__(user_id, game_id)
        self.votes: Dict[str, Dict[int, int]] = {}

    async def get_night_action_keyboard(self) -> InlineKeyboardMarkup:
        players = await db.get_players(self.game_id)
        alive_non_impostors = [p for p in players if p.is_alive and p.role != Role.IMPOSTOR]
        
        buttons = []
        for player in alive_non_impostors:
            buttons.append([InlineKeyboardButton(
                f"Kill Player {player.user_id}", 
                callback_data=f"impostor_kill_{self.game_id}_{player.user_id}"
            )])
        
        buttons.append([InlineKeyboardButton("Skip", callback_data=f"impostor_skip_{self.game_id}")])
        
        return InlineKeyboardMarkup(buttons)

    async def process_night_action(self, action_data: str) -> Dict[str, Any]:
        parts = action_data.split("_")
        if len(parts) < 3:
            return {"action": "invalid"}

        action = parts[1]
        game_id = parts[2]
        
        if action == "kill" and len(parts) >= 4:
            target_id = int(parts[3])
            return await self._process_kill_vote(target_id)
        elif action == "skip":
            return await self._process_kill_vote(None)
        
        return {"action": "invalid"}

    async def _process_kill_vote(self, target_id: int) -> Dict[str, Any]:
        if self.game_id not in self.votes:
            self.votes[self.game_id] = {}
        
        self.votes[self.game_id][self.user_id] = target_id
        
        players = await db.get_players(self.game_id)
        alive_impostors = [p for p in players if p.is_alive and p.role == Role.IMPOSTOR]
        
        if len(alive_impostors) == 1:
            return {"action": "solo_kill", "target": target_id}
        
        if len(self.votes[self.game_id]) == len(alive_impostors):
            return await self._resolve_group_kill()
        
        return {"action": "vote_recorded", "target": target_id}

    async def _resolve_group_kill(self) -> Dict[str, Any]:
        votes = self.votes[self.game_id]
        vote_counts = {}
        
        for target in votes.values():
            if target is not None:
                vote_counts[target] = vote_counts.get(target, 0) + 1
        
        if not vote_counts:
            return {"action": "no_kill"}
        
        max_votes = max(vote_counts.values())
        winners = [target for target, count in vote_counts.items() if count == max_votes]
        
        if len(winners) > 1:
            return {"action": "tie_no_kill"}
        
        return {"action": "group_kill", "target": winners[0]}

    def get_role_description(self) -> str:
        return "🔪 Impostor\nSabotage the ship and eliminate crewmates. Don't get caught!"

    def clear_votes(self):
        if self.game_id in self.votes:
            self.votes[self.game_id].clear()