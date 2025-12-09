from typing import Optional, List
from src.database.connection import db
from src.database.models import Role

class WinConditions:
    @staticmethod
    async def check_win_condition(game_id: str) -> Optional[str]:
        players = await db.get_players(game_id)
        alive_players = [p for p in players if p.is_alive]
        
        alive_impostors = [p for p in alive_players if p.role == Role.IMPOSTOR]
        alive_others = [p for p in alive_players if p.role != Role.IMPOSTOR]
        
        if len(alive_impostors) == 0:
            return "crewmates"
        
        if len(alive_impostors) >= len(alive_others):
            return "impostors"
        
        return None

    @staticmethod
    async def check_ship_explosion(game_id: str) -> bool:
        game = await db.get_game_by_id(game_id)
        if game and game.failed_task_rounds >= 2:
            players = await db.get_players(game_id)
            engineer = next((p for p in players if p.role == Role.ENGINEER and p.is_alive), None)
            
            if not engineer or await db.get_player_field(game_id, engineer.user_id, "engineer_used_ability"):
                return True
        
        return False

    @staticmethod
    async def get_winners(game_id: str, win_condition: str) -> List[int]:
        players = await db.get_players(game_id)
        
        if win_condition == "crewmates":
            return [p.user_id for p in players if p.role != Role.IMPOSTOR]
        elif win_condition == "impostors":
            return [p.user_id for p in players if p.role == Role.IMPOSTOR]
        else:
            return []