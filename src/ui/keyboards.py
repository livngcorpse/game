from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Any, Dict, List
from src.database.connection import db
from src.database.models import Role

class Keyboards:
    @staticmethod
    def get_join_game_keyboard(game_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Join Game", callback_data=f"join_game_{game_id}")
        ]])

    @staticmethod
    def get_start_game_keyboard(game_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Begin Game", callback_data=f"begin_game_{game_id}")],
            [InlineKeyboardButton("End Game", callback_data=f"end_game_{game_id}")]
        ])

    @staticmethod
    def get_dm_redirect_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("Go to DM", url="https://t.me/your_bot_username")
        ]])

    @staticmethod
    async def get_voting_keyboard(game_id: str) -> InlineKeyboardMarkup:
        players = await db.get_players(game_id)
        alive_players = [p for p in players if p.is_alive]
        
        buttons = []
        for player in alive_players:
            buttons.append([InlineKeyboardButton(
                f"Vote Player {player.user_id}", 
                callback_data=f"vote_{game_id}_{player.user_id}"
            )])
        
        buttons.append([InlineKeyboardButton("Skip Vote", callback_data=f"vote_skip_{game_id}")])
        
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def get_engineer_day_keyboard(game_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Fix Ship", callback_data=f"engineer_fix_{game_id}")],
            [InlineKeyboardButton("Skip", callback_data=f"engineer_skip_{game_id}")]
        ])

    @staticmethod
    def get_help_commands_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("Rules", callback_data="help_rules")],
            [InlineKeyboardButton("Roles", callback_data="help_roles")],
            [InlineKeyboardButton("Commands", callback_data="help_commands")],
            [InlineKeyboardButton("About", callback_data="help_about")]
        ])
        
# Add these methods to src/ui/keyboards.py

@staticmethod
async def get_impostor_night_keyboard(game_id: str, impostor_id: int) -> InlineKeyboardMarkup:
    """Generate kill target keyboard for impostors"""
    players = await db.get_players(game_id)
    alive_players = [p for p in players if p.is_alive and p.user_id != impostor_id]
    
    buttons = []
    for player in alive_players:
        buttons.append([InlineKeyboardButton(
            f"Kill Player {player.user_id}", 
            callback_data=f"impostor_kill_{game_id}_{player.user_id}"
        )])
    
    buttons.append([InlineKeyboardButton("Skip", callback_data=f"impostor_skip_{game_id}")])
    return InlineKeyboardMarkup(buttons)

@staticmethod
async def get_detective_night_keyboard(game_id: str, detective_id: int) -> InlineKeyboardMarkup:
    """Generate investigation keyboard for detectives"""
    # Check if detective can investigate this round
    detectives = await db.get_players_by_role(game_id, Role.DETECTIVE)
    alive_detectives = [d for d in detectives if d.is_alive]
    round_number = await db.get_game_round(game_id)
    
    can_investigate = False
    if len(alive_detectives) == 1:
        can_investigate = round_number % 2 == 0  # Every 2 rounds
    else:
        can_investigate = True  # Every round if 2 detectives
    
    if not can_investigate:
        return None
    
    players = await db.get_players(game_id)
    alive_players = [p for p in players if p.is_alive and p.user_id != detective_id]
    
    buttons = []
    for player in alive_players:
        buttons.append([InlineKeyboardButton(
            f"Investigate Player {player.user_id}", 
            callback_data=f"detective_investigate_{game_id}_{player.user_id}"
        )])
    
    buttons.append([InlineKeyboardButton("Skip", callback_data=f"detective_skip_{game_id}")])
    return InlineKeyboardMarkup(buttons)

@staticmethod
async def get_sheriff_night_keyboard(game_id: str, sheriff_id: int) -> InlineKeyboardMarkup:
    """Generate shoot target keyboard for sheriff"""
    players = await db.get_players(game_id)
    alive_players = [p for p in players if p.is_alive and p.user_id != sheriff_id]
    
    buttons = []
    for player in alive_players:
        buttons.append([InlineKeyboardButton(
            f"Shoot Player {player.user_id}", 
            callback_data=f"sheriff_shoot_{game_id}_{player.user_id}"
        )])
    
    buttons.append([InlineKeyboardButton("Skip", callback_data=f"sheriff_skip_{game_id}")])
    return InlineKeyboardMarkup(buttons)

@staticmethod
def get_task_keyboard(game_id: str, player_id: int, task: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Generate task completion keyboard for crewmates"""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            task['button_text'], 
            callback_data=f"task_complete_{game_id}_{player_id}_{task['task_id']}"
        )
    ]])