import random
from typing import List, Dict
from src.database.models import Role, Player
from src.utils.constants import ROLE_DISTRIBUTION
from src.roles.crewmate import Crewmate
from src.roles.impostor import Impostor
from src.roles.detective import Detective
from src.roles.sheriff import Sheriff
from src.roles.engineer import Engineer
from src.roles.base_role import BaseRole
from src.game.task_engine import TaskEngine

class RoleFactory:
    def __init__(self, task_engine: TaskEngine):
        self.task_engine = task_engine

    def distribute_roles(self, player_ids: List[int]) -> Dict[int, Role]:
        player_count = len(player_ids)
        
        for (min_players, max_players), roles in ROLE_DISTRIBUTION.items():
            if min_players <= player_count <= max_players:
                return self._assign_roles(player_ids, roles)
        
        return {player_id: Role.CREWMATE for player_id in player_ids}

    def _assign_roles(self, player_ids: List[int], role_config: Dict[str, int]) -> Dict[int, Role]:
        shuffled_players = player_ids.copy()
        random.shuffle(shuffled_players)
        
        role_assignments = {}
        index = 0
        
        for _ in range(role_config["impostors"]):
            role_assignments[shuffled_players[index]] = Role.IMPOSTOR
            index += 1
        
        for _ in range(role_config["detectives"]):
            role_assignments[shuffled_players[index]] = Role.DETECTIVE
            index += 1
        
        for _ in range(role_config["sheriffs"]):
            role_assignments[shuffled_players[index]] = Role.SHERIFF
            index += 1
        
        for _ in range(role_config["engineers"]):
            role_assignments[shuffled_players[index]] = Role.ENGINEER
            index += 1
        
        for i in range(index, len(shuffled_players)):
            role_assignments[shuffled_players[i]] = Role.CREWMATE
        
        return role_assignments

    def create_role_instance(self, user_id: int, game_id: str, role: Role, round_number: int = 1) -> BaseRole:
        if role == Role.CREWMATE:
            return Crewmate(user_id, game_id, self.task_engine)
        elif role == Role.IMPOSTOR:
            return Impostor(user_id, game_id)
        elif role == Role.DETECTIVE:
            return Detective(user_id, game_id, round_number)
        elif role == Role.SHERIFF:
            return Sheriff(user_id, game_id)
        elif role == Role.ENGINEER:
            return Engineer(user_id, game_id)
        else:
            return Crewmate(user_id, game_id, self.task_engine)