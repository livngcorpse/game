from abc import ABC, abstractmethod
from typing import Dict, Any, List
from telegram import InlineKeyboardMarkup

class BaseRole(ABC):
    def __init__(self, user_id: int, game_id: str):
        self.user_id = user_id
        self.game_id = game_id

    @abstractmethod
    async def get_night_action_keyboard(self) -> InlineKeyboardMarkup:
        pass

    @abstractmethod
    async def process_night_action(self, action_data: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_role_description(self) -> str:
        pass

    async def can_perform_action(self, round_number: int) -> bool:
        return True

    async def get_action_result_message(self, result: Dict[str, Any]) -> str:
        return "Action completed."