import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from src.database.models import Game, Player, GameMode, GamePhase, Role
from src.database.connection import db
from src.game.role_factory import RoleFactory
from src.game.task_engine import TaskEngine

class GameState:
    def __init__(self, role_factory: RoleFactory, task_engine: TaskEngine):
        self.role_factory = role_factory
        self.task_engine = task_engine
        self.active_games: Dict[int, str] = {}
        self.lobby_players: Dict[str, List[int]] = {}
        self.voting_data: Dict[str, Dict[int, Optional[int]]] = {}
        self.round_numbers: Dict[str, int] = {}

    async def create_game(self, group_id: int, creator_id: int, mode: GameMode) -> Game:
        game_id = str(uuid.uuid4())
        
        game = Game(
            id=game_id,
            mode=mode,
            group_id=group_id,
            phase=GamePhase.LOBBY,
            start_time=datetime.now(),
            creator_id=creator_id
        )
        
        await db.create_game(game)
        self.active_games[group_id] = game_id
        self.lobby_players[game_id] = []
        self.round_numbers[game_id] = 1
        
        return game

    async def join_game(self, game_id: str, user_id: int) -> bool:
        if game_id not in self.lobby_players:
            return False
        
        if user_id in self.lobby_players[game_id]:
            return False
        
        if len(self.lobby_players[game_id]) >= 20:
            return False
        
        self.lobby_players[game_id].append(user_id)
        return True

    async def start_game(self, game_id: str) -> bool:
        if game_id not in self.lobby_players:
            return False
        
        players = self.lobby_players[game_id]
        if len(players) < 4:
            return False
        
        role_assignments = self.role_factory.distribute_roles(players)
        
        for user_id, role in role_assignments.items():
            player = Player(game_id=game_id, user_id=user_id, role=role)
            await db.add_player(player)
        
        await db.update_game_phase(game_id, GamePhase.NIGHT)
        
        del self.lobby_players[game_id]
        return True

    async def get_game_by_group(self, group_id: int) -> Optional[Game]:
        return await db.get_game_by_group(group_id)

    async def end_game(self, game_id: str):
        await db.end_game(game_id)
        
        if game_id in self.lobby_players:
            del self.lobby_players[game_id]
        if game_id in self.voting_data:
            del self.voting_data[game_id]
        if game_id in self.round_numbers:
            del self.round_numbers[game_id]
        
        self.task_engine.clear_game_tasks(game_id)
        
        for group_id, g_id in list(self.active_games.items()):
            if g_id == game_id:
                del self.active_games[group_id]
                break

    async def transition_phase(self, game_id: str, new_phase: GamePhase):
        await db.update_game_phase(game_id, new_phase)
        
        if new_phase == GamePhase.NIGHT:
            await db.reset_votes(game_id)
            await db.reset_tasks(game_id)
            self.round_numbers[game_id] = self.round_numbers.get(game_id, 0) + 1
            
            # Persist round number to database
            game = await db.get_game_by_id(game_id)
            if game:
                settings = game.settings or {}
                settings['round_number'] = self.round_numbers[game_id]
                await db.update_game_settings(game_id, settings)

    def get_lobby_players(self, game_id: str) -> List[int]:
        return self.lobby_players.get(game_id, [])

    async def vote_player(self, game_id: str, voter_id: int, target_id: Optional[int]):
        if game_id not in self.voting_data:
            self.voting_data[game_id] = {}
        
        self.voting_data[game_id][voter_id] = target_id
        await db.mark_voted(game_id, voter_id)
        
        # Record vote in database for persistence
        round_number = self.round_numbers.get(game_id, 1)
        await db.record_vote(game_id, voter_id, target_id, round_number)

    async def resolve_votes(self, game_id: str) -> Dict[str, Any]:
        # Use database for vote counting to ensure persistence
        round_number = self.round_numbers.get(game_id, 1)
        vote_counts = await db.get_vote_results(game_id, round_number)
        
        if not vote_counts:
            return {"ejected": None, "votes": vote_counts}
        
        # Convert -1 (skip votes) back to None for processing
        processed_votes = {}
        for target, count in vote_counts.items():
            processed_votes[target if target != -1 else None] = count
        
        if not processed_votes:
            return {"ejected": None, "votes": processed_votes}
        
        max_votes = max(processed_votes.values())
        winners = [target for target, count in processed_votes.items() if count == max_votes]
        
        # If there's a tie or no votes, no one gets ejected
        ejected = None if len(winners) > 1 or (len(winners) == 1 and winners[0] is None) else winners[0]
        
        if ejected:
            await db.kill_player(game_id, ejected)
        
        # Clear in-memory voting data
        self.voting_data[game_id] = {}
        
        return {"ejected": ejected, "votes": processed_votes}

    def get_round_number(self, game_id: str) -> int:
        return self.round_numbers.get(game_id, 1)

    async def reset_failed_rounds(self, game_id: str):
        """Reset failed task rounds for a game"""
        # Update the game settings to reset failed rounds
        game = await db.get_game_by_id(game_id)
        if game:
            settings = game.settings or {}
            settings['failed_task_rounds'] = 0
            await db.update_game_settings(game_id, settings)