from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
from src.database.connection import db

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