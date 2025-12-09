import asyncio
import datetime
from typing import Dict, Any, List, Optional
from telegram import Bot
from src.game.game_state import GameState
from src.game.task_engine import TaskEngine
from src.game.win_conditions import WinConditions
from src.database.models import GamePhase, Role
from src.database.connection import db
from src.systems.logger import GameLogger
from src.systems.xp_system import XPSystem
from src.ui.messages import Messages
from src.ui.keyboards import Keyboards
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
        self.impostor_votes: Dict[str, Dict[int, Optional[int]]] = {}
        self.detective_votes: Dict[str, Dict[int, Optional[int]]] = {}
        self.engineer_timeouts: Dict[str, asyncio.Task] = {}

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
        try:
            if await self.game_state.start_game(game_id):
                await self.game_logger.log_game_start(
                    game_id, 
                    (await self.game_state.get_game_by_group(group_id)).creator_id,
                    group_id, 
                    (await self.game_state.get_game_by_group(group_id)).mode.value,
                    len(await db.get_players(game_id))
                )
                
                # Send role assignments via DM
                await self._send_role_assignments(game_id)
                
                # Wait 5 seconds then start night phase
                await asyncio.sleep(5)
                await self.start_night_phase(game_id, group_id)
        except Exception as e:
            # Log the error and cancel the game
            await self.game_logger.log_error(f"Error starting game: {e}", {"game_id": game_id, "group_id": group_id})
            # Try to notify the group
            try:
                await self.bot.send_message(group_id, "❌ Error starting game. Please try again.")
            except:
                pass
            # Clean up the game state
            try:
                await self.game_state.end_game(game_id)
                # Clean up timers
                await self.cleanup_game_timers(game_id)
            except:
                pass

    async def cancel_game(self, game_id: str, group_id: int):
        # Notify lobby players
        lobby_players = self.game_state.get_lobby_players(game_id)
        for player_id in lobby_players:
            try:
                await self.bot.send_message(player_id, "❌ Game cancelled - not enough players joined.")
            except:
                pass
        
        # Send group message
        try:
            await self.bot.send_message(group_id, "❌ Game cancelled - need at least 4 players.")
        except Exception as e:
            await self.game_logger.log_error(f"Can't send cancellation message to group {group_id}", {"error": str(e)})
        
        await self.game_state.end_game(game_id)
        
        # Clean up timers
        if game_id in self.phase_timers:
            self.phase_timers[game_id].cancel()
            del self.phase_timers[game_id]

    async def start_night_phase(self, game_id: str, group_id: int):
        await self.game_state.transition_phase(game_id, GamePhase.NIGHT)
        await self.game_logger.log_phase_transition(game_id, "lobby", "night")
        
        # Clear previous night actions
        self.night_actions[game_id] = {}
        self.impostor_votes[game_id] = {}
        self.detective_votes[game_id] = {}
        
        # Assign tasks to crewmates
        assigned_task_players = await self.task_engine.assign_tasks(game_id)
        
        # Send night phase message to group
        try:
            await self.bot.send_message(
                group_id, 
                "🌙 The lights go out... Everyone close your eyes and pretend to sleep.\nRoles, prepare your sneaky business!",
                reply_markup=Keyboards.get_dm_redirect_keyboard()
            )
        except Exception as e:
            await self.game_logger.log_error(f"Can't send night phase message to group {group_id}", {"error": str(e)})
        
        # Send role-specific action prompts via DM
        await self._send_night_action_prompts(game_id)
        
        await self.game_logger.log_task_result(game_id, False, assigned_task_players)
        
        timer = asyncio.create_task(self._night_phase_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer

    async def _night_phase_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(NIGHT_PHASE_DURATION)
        await self.resolve_night_actions(game_id, group_id)

    async def resolve_night_actions(self, game_id: str, group_id: int):
        """Enhanced night action resolution with proper order"""
        try:
            # Process actions in correct order
            night_summary = await self._resolve_actions_in_order(game_id)
            
            # Check win conditions
            win_condition = await WinConditions.check_win_condition(game_id)
            ship_exploded = await WinConditions.check_ship_explosion(game_id)
            
            if ship_exploded:
                await self.end_game_explosion(game_id, group_id)
                return
            
            if win_condition:
                await self.end_game_victory(game_id, group_id, win_condition)
                return
            
            await self.start_day_phase(game_id, group_id, night_summary)
        except Exception as e:
            # Log the error and end the game gracefully
            await self.game_logger.log_error(f"Error resolving night actions: {e}", {"game_id": game_id, "group_id": group_id})
            # Try to end the game gracefully
            try:
                await self.game_state.end_game(game_id)
                # Clean up timers
                await self.cleanup_game_timers(game_id)
            except Exception as end_game_error:
                await self.game_logger.log_error(f"Error ending game after night action failure: {end_game_error}", {"game_id": game_id})

    async def _resolve_actions_in_order(self, game_id: str) -> Dict[str, Any]:
        """Process night actions in correct order"""
        results = {
            "deaths": [],
            "investigations": [],
            "task_success": False,
            "round_number": self.game_state.get_round_number(game_id)
        }
        
        # Apply AFK penalties for players who didn't perform night actions
        await self._apply_afk_penalties(game_id)
        
        # 1. Process sheriff shots first (can prevent impostor kills)
        sheriff_results = await self._process_sheriff_actions(game_id)
        results["deaths"].extend(sheriff_results.get("deaths", []))
        
        # 2. Process impostor kills (unless impostor was shot)
        impostor_results = await self._process_impostor_actions(game_id)
        results["deaths"].extend(impostor_results.get("deaths", []))
        
        # 3. Process detective investigations
        detective_results = await self._process_detective_actions(game_id)
        results["investigations"] = detective_results.get("findings", [])
        
        # 4. Check task completion
        task_results = await self._process_task_completions(game_id)
        results["task_success"] = task_results.get("success", False)
        
        return results

    async def _apply_afk_penalties(self, game_id: str):
        """Apply XP penalties to players who were AFK during night phase"""
        # Get all alive players
        players = await db.get_alive_players(game_id)
        
        # Check each player's actions
        for player in players:
            # Check if player had a required night action but didn't perform it
            action_performed = False
            
            # Check if player was assigned a task
            if player.role == Role.CREWMATE and self.task_engine.get_player_task(game_id, player.user_id):
                if player.completed_task:
                    action_performed = True
            
            # Check if player is impostor
            elif player.role == Role.IMPOSTOR:
                if self.night_actions.get(game_id, {}).get(player.user_id):
                    action_performed = True
            
            # Check if player is detective
            elif player.role == Role.DETECTIVE:
                round_number = self.game_state.get_round_number(game_id)
                can_investigate = False
                if await db.get_players_by_role(game_id, Role.DETECTIVE) == 1:
                    can_investigate = round_number % 2 == 0
                else:
                    can_investigate = True
                
                if can_investigate and self.night_actions.get(game_id, {}).get(player.user_id):
                    action_performed = True
            
            # Check if player is sheriff
            elif player.role == Role.SHERIFF:
                if self.night_actions.get(game_id, {}).get(player.user_id):
                    action_performed = True
            
            # Apply AFK penalty if no action was performed when required
            if not action_performed and (
                player.role == Role.CREWMATE and self.task_engine.get_player_task(game_id, player.user_id) or
                player.role == Role.IMPOSTOR or
                player.role == Role.DETECTIVE and (
                    await db.get_players_by_role(game_id, Role.DETECTIVE) == 1 and 
                    self.game_state.get_round_number(game_id) % 2 == 0 or
                    await db.get_players_by_role(game_id, Role.DETECTIVE) > 1
                ) or
                player.role == Role.SHERIFF
            ):
                await self.xp_system.deduct_xp(player.user_id, "afk")

    async def _process_impostor_actions(self, game_id: str) -> Dict[str, Any]:
        """Process impostor kills - voting or solo"""
        deaths = []
        impostors = await db.get_players_by_role(game_id, Role.IMPOSTOR)
        alive_impostors = [imp for imp in impostors if imp.is_alive]
        
        if not alive_impostors:
            return {"deaths": deaths}
        
        if len(alive_impostors) == 1:
            # Solo impostor - direct kill
            impostor_id = alive_impostors[0].user_id
            action = self.night_actions.get(game_id, {}).get(impostor_id)
            
            if action and action.get("action") == "kill" and action.get("target"):
                target_id = action["target"]
                # Check if target is still alive (sheriff might have killed them)
                target = await db.get_player(game_id, target_id)
                if target and target.is_alive:
                    await db.kill_player(game_id, target_id)
                    deaths.append({
                        "user_id": target_id,
                        "cause": "impostor_kill",
                        "role": target.role.value
                    })
                    await self.xp_system.award_xp(impostor_id, "impostor_kill")
        else:
            # Multiple impostors - voting system
            votes = self.impostor_votes.get(game_id, {})
            if votes:
                vote_counts = {}
                for target in votes.values():
                    if target is not None:
                        vote_counts[target] = vote_counts.get(target, 0) + 1
                
                if vote_counts:
                    max_votes = max(vote_counts.values())
                    winners = [target for target, count in vote_counts.items() if count == max_votes]
                    
                    if len(winners) == 1:  # No tie
                        target_id = winners[0]
                        target = await db.get_player(game_id, target_id)
                        if target and target.is_alive:
                            await db.kill_player(game_id, target_id)
                            deaths.append({
                                "user_id": target_id,
                                "cause": "impostor_kill",
                                "role": target.role.value
                            })
                            # Award XP to all voting impostors
                            for imp_id in votes.keys():
                                await self.xp_system.award_xp(imp_id, "impostor_kill")
        
        return {"deaths": deaths}

    async def _process_detective_actions(self, game_id: str) -> Dict[str, Any]:
        """Process detective investigations"""
        findings = []
        detectives = await db.get_players_by_role(game_id, Role.DETECTIVE)
        alive_detectives = [det for det in detectives if det.is_alive]
        
        if not alive_detectives:
            return {"findings": findings}
        
        round_number = self.game_state.get_round_number(game_id)
        
        # Check if detectives can investigate this round
        can_investigate = False
        if len(alive_detectives) == 1:
            can_investigate = round_number % 2 == 0  # Every 2 rounds
        else:
            can_investigate = True  # Every round if 2 detectives
        
        if not can_investigate:
            return {"findings": findings}
        
        if len(alive_detectives) == 1:
            # Solo detective
            detective_id = alive_detectives[0].user_id
            action = self.night_actions.get(game_id, {}).get(detective_id)
            
            if action and action.get("action") == "investigate" and action.get("target"):
                target_id = action["target"]
                target = await db.get_player(game_id, target_id)
                if target and target.is_alive:
                    result = "Impostor" if target.role == Role.IMPOSTOR else "Not Impostor"
                    findings.append({
                        "detective_id": detective_id,
                        "target_id": target_id,
                        "result": result
                    })
                    await self.xp_system.award_xp(detective_id, "detective_investigation")
                    await self.game_logger.log_detective_investigation(game_id, detective_id, target_id, result)
                    
                    # Update detective's last investigation round
                    round_number = self.game_state.get_round_number(game_id)
                    await db.update_player_field(game_id, detective_id, "detective_last_investigation", round_number)
        else:
            # Multiple detectives - must coordinate
            votes = self.detective_votes.get(game_id, {})
            if len(votes) >= 2:  # Both must vote
                targets = list(votes.values())
                if len(set(targets)) == 1 and targets[0] is not None:  # Same target
                    target_id = targets[0]
                    target = await db.get_player(game_id, target_id)
                    if target and target.is_alive:
                        result = "Impostor" if target.role == Role.IMPOSTOR else "Not Impostor"
                        for det_id in votes.keys():
                            findings.append({
                                "detective_id": det_id,
                                "target_id": target_id,
                                "result": result
                            })
                            await self.xp_system.award_xp(det_id, "detective_investigation")
                            
                            # Update detective's last investigation round
                            round_number = self.game_state.get_round_number(game_id)
                            await db.update_player_field(game_id, det_id, "detective_last_investigation", round_number)
                        await self.game_logger.log_detective_investigation(game_id, 0, target_id, result)
        
        return {"findings": findings}

    async def _process_sheriff_actions(self, game_id: str) -> Dict[str, Any]:
        """Process sheriff shots with friendly fire logic"""
        deaths = []
        sheriffs = await db.get_players_by_role(game_id, Role.SHERIFF)
        
        for sheriff in sheriffs:
            if not sheriff.is_alive:
                continue
                
            action = self.night_actions.get(game_id, {}).get(sheriff.user_id)
            if not action or action.get("action") != "shoot" or not action.get("target"):
                continue
            
            # Check if sheriff already used their shot
            if await db.get_player_field(game_id, sheriff.user_id, "sheriff_used_shot"):
                continue
            
            target_id = action["target"]
            target = await db.get_player(game_id, target_id)
            
            if not target or not target.is_alive:
                continue
            
            # Mark sheriff as having used shot
            await db.update_player_field(game_id, sheriff.user_id, "sheriff_used_shot", True)
            
            if target.role == Role.IMPOSTOR:
                # Successful shot - impostor dies, sheriff gets another shot
                await db.kill_player(game_id, target_id)
                await db.update_player_field(game_id, sheriff.user_id, "sheriff_used_shot", False)  # Reset shot
                deaths.append({
                    "user_id": target_id,
                    "cause": "sheriff_kill",
                    "role": target.role.value,
                    "sheriff_success": True
                })
                await self.xp_system.award_xp(sheriff.user_id, "sheriff_kills_impostor")
                await self.game_logger.log_sheriff_action(game_id, sheriff.user_id, target_id, target.role.value, True)
            else:
                # Friendly fire - both die
                await db.kill_player(game_id, target_id)
                await db.kill_player(game_id, sheriff.user_id)
                deaths.extend([
                    {
                        "user_id": target_id,
                        "cause": "sheriff_friendly_fire",
                        "role": target.role.value,
                        "sheriff_success": False
                    },
                    {
                        "user_id": sheriff.user_id,
                        "cause": "sheriff_suicide",
                        "role": sheriff.role.value,
                        "sheriff_success": False
                    }
                ])
                await self.xp_system.deduct_xp(sheriff.user_id, "sheriff_friendly_fire")
                await self.game_logger.log_sheriff_action(game_id, sheriff.user_id, target_id, target.role.value, False)
        
        return {"deaths": deaths}

    async def _process_task_completions(self, game_id: str) -> Dict[str, Any]:
        """Check if assigned tasks were completed"""
        task_success = await self.task_engine.check_task_completion(game_id)
        
        if not task_success:
            await db.increment_failed_rounds(game_id)
        
        return {"success": task_success}

    async def start_day_phase(self, game_id: str, group_id: int, night_summary: Dict[str, Any]):
        """Enhanced day phase with full summary and engineer prompts"""
        await self.game_state.transition_phase(game_id, GamePhase.DISCUSSION)
        await self.game_logger.log_phase_transition(game_id, "night", "discussion")
        
        # Get alive players for day summary
        alive_players = await db.get_alive_players(game_id)
        alive_player_ids = [p.user_id for p in alive_players]
        
        # Create day phase message with night summary
        day_message = Messages.get_day_phase_message(alive_player_ids, night_summary)
        
        try:
            await self.bot.send_message(group_id, day_message)
        except Exception as e:
            await self.game_logger.log_error(f"Can't send day phase message to group {group_id}", {"error": str(e)})
        
        # Check for ship explosion condition
        game = await db.get_game_by_id(game_id)
        if game and game.failed_task_rounds >= 3:
            await self.end_game_explosion(game_id, group_id)
            return
        
        # Check if engineer needs to fix the ship
        if not night_summary["task_success"] and game:
            engineer_prompted = await self._prompt_engineer_if_needed(game_id)
            if engineer_prompted:
                # Start 30-second timer for engineer decision
                timeout_task = asyncio.create_task(self._engineer_timeout(game_id, group_id))
                self.engineer_timeouts[game_id] = timeout_task
                return
        
        # Continue to normal discussion phase
        await self._continue_to_discussion(game_id, group_id)

    async def _engineer_timeout(self, game_id: str, group_id: int):
        """Handle timeout for engineer decision (30 seconds)"""
        await asyncio.sleep(30)  # Engineer gets 30 seconds to decide
        # After timeout, proceed to normal discussion phase
        await self._continue_to_discussion(game_id, group_id)
    
    async def _continue_to_discussion(self, game_id: str, group_id: int):
        """Continue to normal discussion phase after engineer decision or if no engineer"""
        try:
            await self.bot.send_message(
                group_id, 
                "🗣️ Discussion time! Point fingers, throw accusations, and blame everyone except yourself.\nYou have 90 seconds of pure chaos."
            )
        except Exception as e:
            await self.game_logger.log_error(f"Can't send discussion message to group {group_id}", {"error": str(e)})
        
        # Start discussion timer
        timer = asyncio.create_task(self._discussion_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer
    
    async def _discussion_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(DISCUSSION_DURATION)
        await self.start_voting_phase(game_id, group_id)

    async def start_voting_phase(self, game_id: str, group_id: int):
        await self.game_state.transition_phase(game_id, GamePhase.VOTING)
        await self.game_logger.log_phase_transition(game_id, "discussion", "voting")
        
        # Reset player votes
        await db.reset_votes(game_id)
        
        try:
            await self.bot.send_message(
                group_id, 
                "🗳️ Voting phase has begun! Choose wisely... or just point at someone random.\n30 seconds to make your decision."
            )
        except Exception as e:
            await self.game_logger.log_error(f"Can't send voting message to group {group_id}", {"error": str(e)})
        
        # Send voting keyboards to all alive players
        alive_players = await db.get_alive_players(game_id)
        for player in alive_players:
            try:
                keyboard = await Keyboards.get_voting_keyboard(game_id, player.user_id)
                await self.bot.send_message(
                    player.user_id,
                    "🗳️ Time to vote! Who's the most sus player?\nChoose carefully - your reputation depends on this.",
                    reply_markup=keyboard
                )
            except Exception as e:
                await self.game_logger.log_error(f"Can't send voting prompt to {player.user_id}", {"error": str(e)})
        
        # Start voting timer
        timer = asyncio.create_task(self._voting_timeout(game_id, group_id))
        self.phase_timers[game_id] = timer

    async def _voting_timeout(self, game_id: str, group_id: int):
        await asyncio.sleep(VOTING_DURATION)
        await self.resolve_voting(game_id, group_id)

    async def resolve_voting(self, game_id: str, group_id: int):
        """Enhanced voting resolution with proper win condition checking"""
        try:
            # Apply AFK penalties for players who didn't vote
            await self._apply_voting_afk_penalties(game_id)
            
            vote_result = await self.game_state.resolve_votes(game_id)
            
            # Send voting results to group
            if vote_result["ejected"]:
                ejected_player = vote_result["ejected"]
                player = await db.get_player(game_id, ejected_player)
                if player:
                    result_message = Messages.get_voting_result_message(ejected_player, player.role.value)
                    try:
                        await self.bot.send_message(group_id, result_message)
                    except Exception as e:
                        await self.game_logger.log_error(f"Can't send voting result to group {group_id}", {"error": str(e)})
                    
                    # Award XP to correct voters
                    voters = await db.get_voters_for_target(game_id, ejected_player)
                    for voter_id in voters:
                        await self.xp_system.award_xp(voter_id, "correct_vote")
            else:
                no_ejection_message = Messages.get_voting_result_message(None, "")
                try:
                    await self.bot.send_message(group_id, no_ejection_message)
                except Exception as e:
                    await self.game_logger.log_error(f"Can't send no ejection message to group {group_id}", {"error": str(e)})
            
            # Show vote breakdown
            if vote_result["votes"]:
                vote_breakdown = Messages.get_vote_breakdown_message(vote_result["votes"])
                try:
                    await self.bot.send_message(group_id, vote_breakdown)
                except Exception as e:
                    await self.game_logger.log_error(f"Can't send vote breakdown to group {group_id}", {"error": str(e)})
            
            win_condition = await WinConditions.check_win_condition(game_id)
            if win_condition:
                await self.end_game_victory(game_id, group_id, win_condition)
                return
            
            await self.start_night_phase(game_id, group_id)
        except Exception as e:
            # Log the error and end the game gracefully
            await self.game_logger.log_error(f"Error resolving voting: {e}", {"game_id": game_id, "group_id": group_id})
            # Try to end the game gracefully
            try:
                await self.game_state.end_game(game_id)
                # Clean up timers
                await self.cleanup_game_timers(game_id)
            except Exception as end_game_error:
                await self.game_logger.log_error(f"Error ending game after voting failure: {end_game_error}", {"game_id": game_id})

    async def _apply_voting_afk_penalties(self, game_id: str):
        """Apply XP penalties to players who were AFK during voting phase"""
        # Get all alive players
        players = await db.get_alive_players(game_id)
        
        # Check each player's voting status
        for player in players:
            # Check if player has voted
            if not player.voted:
                # Apply AFK penalty
                await self.xp_system.deduct_xp(player.user_id, "afk")

    async def _send_role_assignments(self, game_id: str):
        """Send role assignments via DM with team reveals"""
        players = await db.get_players(game_id)
        
        # Group players by role for team reveals
        impostors = [p for p in players if p.role == Role.IMPOSTOR]
        detectives = [p for p in players if p.role == Role.DETECTIVE]
        
        # Send individual role assignments
        for player in players:
            try:
                role_message = Messages.get_role_assignment_message(
                    player.role.value.title(),
                    Messages.get_role_description(player.role)
                )
                await self.bot.send_message(player.user_id, role_message)
            except Exception as e:
                await self.game_logger.log_error(f"Can't send role to {player.user_id}", {"error": str(e)})
        
        # Send team reveal messages
        # Impostors know each other if there are 2 or more
        if len(impostors) >= 2:
            impostor_ids = [str(p.user_id) for p in impostors]
            team_message = f"👥 You know each other! Other impostors: {', '.join(impostor_ids)}"
            for impostor in impostors:
                try:
                    await self.bot.send_message(impostor.user_id, team_message)
                except Exception as e:
                    await self.game_logger.log_error(f"Can't send impostor team reveal to {impostor.user_id}", {"error": str(e)})
        
        # Detectives know each other if there are 2
        if len(detectives) >= 2:
            detective_ids = [str(p.user_id) for p in detectives]
            team_message = f"👥 You know each other! Other detectives: {', '.join(detective_ids)}"
            for detective in detectives:
                try:
                    await self.bot.send_message(detective.user_id, team_message)
                except Exception as e:
                    await self.game_logger.log_error(f"Can't send detective team reveal to {detective.user_id}", {"error": str(e)})

    async def _send_night_action_prompts(self, game_id: str):
        """Send role-specific action prompts via DM"""
        game = await db.get_game_by_id(game_id)
        if not game:
            return
            
        players = await db.get_alive_players(game_id)
        
        for player in players:
            try:
                if player.role == Role.IMPOSTOR:
                    # Handle impostor actions
                    impostors = await db.get_players_by_role(game_id, Role.IMPOSTOR)
                    alive_impostors = [imp for imp in impostors if imp.is_alive]
                    
                    if len(alive_impostors) == 1:
                        # Solo impostor - direct kill action
                        keyboard = await Keyboards.get_impostor_night_keyboard(game_id, player.user_id)
                        await self.bot.send_message(
                            player.user_id,
                            "🔪 You're the lone wolf tonight. Choose your victim wisely...",
                            reply_markup=keyboard
                        )
                    else:
                        # Multiple impostors - voting system
                        keyboard = await Keyboards.get_impostor_night_keyboard(game_id, player.user_id)
                        await self.bot.send_message(
                            player.user_id,
                            "🔪 Collaborate with your fellow impostors. Vote on tonight's victim:",
                            reply_markup=keyboard
                        )
                        
                elif player.role == Role.DETECTIVE:
                    # Handle detective actions
                    keyboard = await Keyboards.get_detective_night_keyboard(game_id, player.user_id)
                    await self.bot.send_message(
                        player.user_id,
                        "🕵️ Time to investigate! Choose a player to scrutinize:",
                        reply_markup=keyboard
                    )
                elif player.role == Role.SHERIFF:
                    # Handle sheriff actions
                    if not await db.get_player_field(game_id, player.user_id, "sheriff_used_shot"):
                        keyboard = await Keyboards.get_sheriff_night_keyboard(game_id, player.user_id)
                        await self.bot.send_message(
                            player.user_id,
                            "🔫 Choose your target carefully, Sheriff. One wrong move and it's game over:",
                            reply_markup=keyboard
                        )
                elif player.role == Role.CREWMATE:
                    # Check if assigned a task
                    task = await self.task_engine.get_player_task(game_id, player.user_id)
                    if task:
                        keyboard = Keyboards.get_task_keyboard(game_id, player.user_id, task)
                        await self.bot.send_message(
                            player.user_id,
                            f"🔧 Your mission, should you choose to accept it:\n{task['description']}",
                            reply_markup=keyboard
                        )
            except Exception as e:
                await self.game_logger.log_error(f"Can't send night action to {player.user_id}", {"error": str(e)})

    async def _send_detective_results(self, game_id: str, findings: List[Dict]):
        """Send investigation results to detectives privately"""
        for finding in findings:
            try:
                message = Messages.get_detective_result_message(
                    finding["target_id"],
                    finding["result"]
                )
                await self.bot.send_message(finding["detective_id"], message)
            except Exception as e:
                await self.game_logger.log_error(f"Can't send detective result to {finding['detective_id']}", {"error": str(e)})

    async def _prompt_engineer_if_needed(self, game_id: str) -> bool:
        """Send engineer the fix/skip choice if tasks failed"""
        engineers = await db.get_players_by_role(game_id, Role.ENGINEER)
        
        for engineer in engineers:
            if not engineer.is_alive:
                continue
                
            # Check if engineer already used ability
            if await db.get_player_field(game_id, engineer.user_id, "engineer_used_ability"):
                continue
            
            try:
                keyboard = Keyboards.get_engineer_day_keyboard(game_id)
                await self.bot.send_message(
                    engineer.user_id,
                    "⚙️ Tasks failed! Fix the ship? (You have 30 seconds to decide)",
                    reply_markup=keyboard
                )
                return True  # Engineer was prompted
            except Exception as e:
                await self.game_logger.log_error(f"Can't send engineer prompt to {engineer.user_id}", {"error": str(e)})
        
        return False  # No engineer was prompted

    # Action processing methods for callbacks
    async def process_impostor_action(self, game_id: str, user_id: int, action_type: str, target_id: Optional[int]) -> Dict[str, Any]:
        """Process impostor action from callback"""
        if action_type == "kill" and target_id:
            impostors = await db.get_players_by_role(game_id, Role.IMPOSTOR)
            alive_impostors = [imp for imp in impostors if imp.is_alive]
            
            if len(alive_impostors) == 1:
                # Solo impostor - direct action
                self.night_actions[game_id][user_id] = {"action": "kill", "target": target_id}
                return {"message": f"You chose to kill Player {target_id}"}
            else:
                # Group voting
                self.impostor_votes[game_id][user_id] = target_id
                return {"message": f"You voted to kill Player {target_id}"}
        
        return {"message": "Invalid action"}

    async def process_detective_action(self, game_id: str, user_id: int, action_type: str, target_id: Optional[int]) -> Dict[str, Any]:
        """Process detective action from callback"""
        if action_type == "investigate" and target_id:
            detectives = await db.get_players_by_role(game_id, Role.DETECTIVE)
            alive_detectives = [det for det in detectives if det.is_alive]
            
            if len(alive_detectives) == 1:
                self.night_actions[game_id][user_id] = {"action": "investigate", "target": target_id}
                return {"message": f"You chose to investigate Player {target_id}"}
            else:
                self.detective_votes[game_id][user_id] = target_id
                return {"message": f"You voted to investigate Player {target_id}"}
        
        return {"message": "Invalid action"}

    async def process_sheriff_action(self, game_id: str, user_id: int, action_type: str, target_id: Optional[int]) -> Dict[str, Any]:
        """Process sheriff action from callback"""
        if action_type == "shoot" and target_id:
            self.night_actions[game_id][user_id] = {"action": "shoot", "target": target_id}
            return {"message": f"You chose to shoot Player {target_id}"}
        
        return {"message": "Invalid action"}

    async def end_game_victory(self, game_id: str, group_id: int, win_condition: str):
        winners = await WinConditions.get_winners(game_id, win_condition)
        players = await db.get_players(game_id)
        
        # Award XP
        for player in players:
            if player.user_id in winners:
                await self.xp_system.award_xp(player.user_id, "win")
            else:
                await self.xp_system.award_xp(player.user_id, "loss")
        
        # Send victory message
        if win_condition == "crewmates":
            victory_message = "🎉 The forces of good have prevailed! Somehow the crewmates managed to not kill each other.\n\nWinners: " + ", ".join([f"Player {winner}" for winner in winners])
        elif win_condition == "impostors":
            victory_message = "🔪 Chaos wins again! The impostors have successfully sabotaged the mission.\n\nWinners: " + ", ".join([f"Player {winner}" for winner in winners])
        
        try:
            await self.bot.send_message(group_id, victory_message)
        except Exception as e:
            await self.game_logger.log_error(f"Can't send victory message to group {group_id}", {"error": str(e)})
        
        await self.game_state.end_game(game_id)
        
        game = await db.get_game_by_group(group_id)
        duration = str(datetime.datetime.now() - game.start_time) if game else "Unknown"
        player_names = [str(p.user_id) for p in players]
        
        await self.game_logger.log_game_end(game_id, win_condition, duration, player_names)
        
        # Clean up timers
        await self.cleanup_game_timers(game_id)

    async def end_game_explosion(self, game_id: str, group_id: int):
        players = await db.get_players(game_id)
        
        # Deduct XP for ship explosion
        for player in players:
            await self.xp_system.deduct_xp(player.user_id, "ship_explodes")
        
        explosion_message = "💥 Well, that's what happens when you don't do your tasks! The ship has exploded and everyone loses.\n\nBetter luck next time, or maybe just do your job?"
        try:
            await self.bot.send_message(group_id, explosion_message)
        except Exception as e:
            await self.game_logger.log_error(f"Can't send explosion message to group {group_id}", {"error": str(e)})
        
        await self.game_state.end_game(game_id)
        
        duration = "Ship Exploded"
        player_names = [str(p.user_id) for p in players]
        
        await self.game_logger.log_game_end(game_id, "explosion", duration, player_names)
        
        # Clean up timers
        await self.cleanup_game_timers(game_id)

    async def record_night_action(self, game_id: str, user_id: int, role: str, action_data: Dict[str, Any]):
        """Record night action (legacy method for compatibility)"""
        if game_id not in self.night_actions:
            self.night_actions[game_id] = {}
        
        self.night_actions[game_id][user_id] = {
            "role": role,
            **action_data
        }

    async def relay_team_message(self, game_id: str, sender_id: int, message: str, role: Role):
        """Relay messages between team members (impostors/detectives)"""
        # Get all players with the same role
        players = await db.get_players_by_role(game_id, role)
        teammates = [p for p in players if p.is_alive and p.user_id != sender_id]
        
        # Relay message to teammates
        for teammate in teammates:
            try:
                await self.bot.send_message(
                    teammate.user_id, 
                    f"👥 Team message from Player {sender_id}:\n{message}"
                )
            except Exception as e:
                await self.game_logger.log_error(f"Can't relay team message to {teammate.user_id}", {"error": str(e)})
    
    async def cleanup_game_timers(self, game_id: str):
        """Enhanced cleanup with better error handling"""
        if game_id in self.phase_timers:
            timer = self.phase_timers[game_id]
            if not timer.done():
                timer.cancel()
                try:
                    await timer
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
            del self.phase_timers[game_id]
        
        # Clear game-specific data
        if game_id in self.night_actions:
            del self.night_actions[game_id]
        if game_id in self.impostor_votes:
            del self.impostor_votes[game_id]
        if game_id in self.detective_votes:
            del self.detective_votes[game_id]
            
        # Also clean up any engineer timeouts
        if game_id in self.engineer_timeouts:
            timeout_task = self.engineer_timeouts[game_id]
            if not timeout_task.done():
                timeout_task.cancel()
                try:
                    await timeout_task
                except asyncio.CancelledError:
                    pass
            del self.engineer_timeouts[game_id]
