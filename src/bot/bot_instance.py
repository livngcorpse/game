from telegram.ext import Application
from src.utils.config import BOT_TOKEN
from src.database.connection import db
from src.game.game_state import GameState
from src.game.phase_manager import PhaseManager
from src.game.task_engine import TaskEngine
from src.game.role_factory import RoleFactory
from src.systems.logger import GameLogger, BotLogger
from src.systems.xp_system import XPSystem
from src.systems.achievement_system import AchievementSystem
from src.systems.ban_system import BanSystem

class BotInstance:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.bot = self.application.bot
        
        self.task_engine = TaskEngine()
        self.role_factory = RoleFactory(self.task_engine)
        self.game_state = GameState(self.role_factory, self.task_engine)
        
        self.game_logger = GameLogger(self.bot)
        self.bot_logger = BotLogger(self.bot)
        
        self.achievement_system = AchievementSystem(self.bot)
        self.xp_system = XPSystem(self.achievement_system)
        self.ban_system = BanSystem(self.bot_logger)
        
        self.phase_manager = PhaseManager(
            self.bot, 
            self.game_state, 
            self.task_engine, 
            self.game_logger, 
            self.xp_system
        )

    async def initialize(self):
        await db.connect()

    async def shutdown(self):
        await db.disconnect()

bot_instance = BotInstance()