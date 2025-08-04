import random
from typing import List, Dict
from src.game.task_pool import TASK_POOL
from src.utils.constants import TASK_DISTRIBUTION
from src.database.connection import db
from src.database.models import Role

class TaskEngine:
    def __init__(self):
        self.active_tasks: Dict[str, Dict[int, dict]] = {}

    def get_task_count_for_players(self, player_count: int) -> int:
        for (min_players, max_players), count in TASK_DISTRIBUTION.items():
            if min_players <= player_count <= max_players:
                return count
        return 1

    async def assign_tasks(self, game_id: str) -> List[int]:
        players = await db.get_players(game_id)
        crewmates = [p for p in players if p.role == Role.CREWMATE and p.is_alive]
        
        task_count = self.get_task_count_for_players(len(players))
        assigned_players = random.sample(crewmates, min(task_count, len(crewmates)))
        
        self.active_tasks[game_id] = {}
        
        for player in assigned_players:
            task = random.choice(TASK_POOL)
            self.active_tasks[game_id][player.user_id] = task
            
        return [p.user_id for p in assigned_players]

    def get_player_task(self, game_id: str, user_id: int) -> dict:
        return self.active_tasks.get(game_id, {}).get(user_id)

    async def complete_task(self, game_id: str, user_id: int) -> bool:
        if game_id in self.active_tasks and user_id in self.active_tasks[game_id]:
            await db.update_player_field(game_id, user_id, "completed_task", True)
            return True
        return False

    async def check_task_completion(self, game_id: str) -> bool:
        if game_id not in self.active_tasks:
            return True
            
        assigned_players = list(self.active_tasks[game_id].keys())
        
        for user_id in assigned_players:
            player = await db.get_player(game_id, user_id)
            if not player or not player.completed_task:
                return False
        
        return True

    def clear_game_tasks(self, game_id: str):
        if game_id in self.active_tasks:
            del self.active_tasks[game_id]