import asyncio
import datetime
from typing import Dict, Any, List
from telegram import Bot
from src.game.game_state import GameState
from src.game.task_engine import TaskEngine
from src.game.win_conditions import WinConditions
from src.database.models import GamePhase, Role
from src.database.connection import db
from src.systems.logger import GameLogger
from src.systems.xp_system import XPSystem
from src.utils.constants import LOBBY_TIMEOUT, NIGHT_PHASE_DURATION, DISCUSSION_DURATION, VOTING_DURATION

class PhaseManager:
    def __init__(self, bot: Bot, game_state: GameState, task_engine: TaskEngine, 
                 game_logger: GameLogger, xp_system: XPSystem):
        self.bot = bot
        self.game_state = game_state
        self.task_engine = task_engine
        self.game_logger = game_logger
        self.xp_system = xp_system
        self.phase_timers: Dict[str, asyncio.Task] = {}
        self.night_actions: Dict[str, Dict[int, Dict[str, Any]]] = {}

    async def start_lobby_timer(self, game_id: str, group_id: int):
        timer = asyncio.create_task(self._lobby_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer

    async def _lobby_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(LOBBY_TIMEOUT)
        
        players = self.game_state.get_lobby_players(game_id)
        if len(players) >= 4:
            await self.start_game_from_lobby(game_id, group_id)
        else:
            await self.cancel_game(game_id, group_id)

    async def start_game_from_lobby(self, game_id: str, group_id: int):
        if await self.game_state.start_game(game_id):
            await self.game_logger.log_game_start(
                game_id, 
                (await self.game_state.get_game_by_group(group_id)).creator_id,
                group_id, 
                (await self.game_state.get_game_by_group(group_id)).mode.value,
                len(await db.get_players(game_id))
            )
            
            await self.start_night_phase(game_id, group_id)

    async def cancel_game(self, game_id: str, group_id: int):
        await self.game_state.end_game(game_id)
        
        if game_id in self.phase_timers:
            self.phase_timers[game_id].cancel()
            del self.phase_timers[game_id]

    async def start_night_phase(self, game_id: str, group_id: int):
        await self.game_state.transition_phase(game_id, GamePhase.NIGHT)
        await self.game_logger.log_phase_transition(game_id, "lobby", "night")
        
        self.night_actions[game_id] = {}
        assigned_task_players = await self.task_engine.assign_tasks(game_id)
        
        await self.game_logger.log_task_result(game_id, False, assigned_task_players)
        
        timer = asyncio.create_task(self._night_phase_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer

    async def _night_phase_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(NIGHT_PHASE_DURATION)
        await self.resolve_night_actions(game_id, group_id)

    async def resolve_night_actions(self, game_id: str, group_id: int):
        night_summary = await self._process_all_night_actions(game_id)
        
        win_condition = await WinConditions.check_win_condition(game_id)
        ship_exploded = await WinConditions.check_ship_explosion(game_id)
        
        if ship_exploded:
            await self.end_game_explosion(game_id, group_id)
            return
        
        if win_condition:
            await self.end_game_victory(game_id, group_id, win_condition)
            return
        
        await self.start_day_phase(game_id, group_id, night_summary)

    async def _process_all_night_actions(self, game_id: str) -> Dict[str, Any]:
        players = await db.get_players(game_id)
        deaths = []
        task_success = await self.task_engine.check_task_completion(game_id)
        
        if not task_success:
            await db.increment_failed_rounds(game_id)
        
        impostor_actions = [action for action in self.night_actions.get(game_id, {}).values() 
                           if action.get("role") == "impostor"]
        
        for action in impostor_actions:
            if action.get("action") in ["solo_kill", "group_kill"] and action.get("target"):
                target_id = action["target"]
                await db.kill_player(game_id, target_id)
                target_player = await db.get_player(game_id, target_id)
                deaths.append({
                    "user_id": target_id,
                    "cause": "impostor_kill",
                    "role": target_player.role.value
                })
        
        sheriff_actions = [action for action in self.night_actions.get(game_id, {}).values() 
                          if action.get("role") == "sheriff"]
        
        for action in sheriff_actions:
            if action.get("action") in ["successful_shot", "friendly_fire"]:
                target_id = action["target"]
                target_player = await db.get_player(game_id, target_id)
                deaths.append({
                    "user_id": target_id,
                    "cause": "sheriff_kill",
                    "role": target_player.role.value
                })
                
                if action["action"] == "friendly_fire":
                    sheriff_id = action.get("sheriff_id")
                    sheriff_player = await db.get_player(game_id, sheriff_id)
                    deaths.append({
                        "user_id": sheriff_id,
                        "cause": "sheriff_suicide",
                        "role": sheriff_player.role.value
                    })
        
        return {
            "deaths": deaths,
            "task_success": task_success,
            "round_number": self.game_state.get_round_number(game_id)
        }

    async def start_day_phase(self, game_id: str, group_id: int, night_summary: Dict[str, Any]):
        await self.game_state.transition_phase(game_id, GamePhase.DISCUSSION)
        await self.game_logger.log_phase_transition(game_id, "night", "discussion")
        
        timer = asyncio.create_task(self._discussion_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer

    async def _discussion_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(DISCUSSION_DURATION)
        await self.start_voting_phase(game_id, group_id)

    async def start_voting_phase(self, game_id: str, group_id: int):
        await self.game_state.transition_phase(game_id, GamePhase.VOTING)
        await self.game_logger.log_phase_transition(game_id, "discussion", "voting")
        
        timer = asyncio.create_task(self._voting_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer

    async def _voting_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(VOTING_DURATION)
        await self.resolve_voting(game_id, group_id)

    async def resolve_voting(self, game_id: str, group_id: int):
        vote_result = await self.game_state.resolve_votes(game_id)
        
        if vote_result["ejected"]:
            ejected_player = await db.get_player(game_id, vote_result["ejected"])
            await self.game_logger.log_vote(game_id, 0, vote_result["ejected"])
        
        win_condition = await WinConditions.check_win_condition(game_id)
        if win_condition:
            await self.end_game_victory(game_id, group_id, win_condition)
            return
        
        await self.start_night_phase(game_id, group_id)

    async def end_game_victory(self, game_id: str, group_id: int, win_condition: str):
        winners = await WinConditions.get_winners(game_id, win_condition)
        players = await db.get_players(game_id)
        
        for player in players:
            if player.user_id in winners:
                await self.xp_system.award_xp(player.user_id, "win")
            else:
                await self.xp_system.award_xp(player.user_id, "loss")
        
        await self.game_state.end_game(game_id)
        
        game = await db.get_game_by_group(group_id)
        duration = str(datetime.now() - game.start_time) if game else "Unknown"
        player_names = [str(p.user_id) for p in players]
        
        await self.game_logger.log_game_end(game_id, win_condition, duration, player_names)
        
        if game_id in self.phase_timers:
            self.phase_timers[game_id].cancel()
            del self.phase_timers[game_id]

    async def end_game_explosion(self, game_id: str, group_id: int):
        players = await db.get_players(game_id)
        
        for player in players:
            await self.xp_system.deduct_xp(player.user_id, "ship_explodes")
        
        await self.game_state.end_game(game_id)
        
        duration = "Ship Exploded"
        player_names = [str(p.user_id) for p in players]
        
        await self.game_logger.log_game_end(game_id, "explosion", duration, player_names)
        
        if game_id in self.phase_timers:
            self.phase_timers[game_id].cancel()
            del self.phase_timers[game_id]

    async def record_night_action(self, game_id: str, user_id: int, role: str, action_data: Dict[str, Any]):
        if game_id not in self.night_actions:
            self.night_actions[game_id] = {}
        
        self.night_actions[game_id][user_id] = {
            "role": role,
            "sheriff_id": user_id if role == "sheriff" else None,
            **action_data
        }

    def cleanup_game_timers(self, game_id: str):
        if game_id in self.phase_timers:
            self.phase_timers[game_id].cancel()
            del self.phase_timers[game_id]
        
        if game_id in self.night_actions:
            del self.night_actions[game_id]