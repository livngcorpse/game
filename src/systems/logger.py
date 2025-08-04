import structlog
from telegram import Bot
from src.utils.config import GAME_LOG_CHANNEL_ID, BOT_LOG_CHANNEL_ID

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

class GameLogger:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def log_game_start(self, game_id: str, creator_id: int, group_id: int, mode: str, players_count: int):
        logger.info("Someone just triggered chaos. Let the sus begin 🎭", 
                   game_id=game_id, creator_id=creator_id, group_id=group_id, mode=mode, players=players_count)
        
        if GAME_LOG_CHANNEL_ID:
            await self.bot.send_message(
                GAME_LOG_CHANNEL_ID,
                f"🎮 New {mode} game started\nID: {game_id}\nCreator: {creator_id}\nGroup: {group_id}\nPlayers: {players_count}"
            )

    async def log_game_end(self, game_id: str, winners: str, duration: str, player_names: list):
        logger.info("Game over! Someone's trust issues just got validated 💀", 
                   game_id=game_id, winners=winners, duration=duration, players=player_names)
        
        if GAME_LOG_CHANNEL_ID:
            await self.bot.send_message(
                GAME_LOG_CHANNEL_ID,
                f"🏁 Game ended\nID: {game_id}\nWinners: {winners}\nDuration: {duration}\nPlayers: {', '.join(player_names)}"
            )

    async def log_phase_transition(self, game_id: str, from_phase: str, to_phase: str):
        logger.info("Phase shift! Everyone's paranoia level just increased 📈", 
                   game_id=game_id, from_phase=from_phase, to_phase=to_phase)

    async def log_kill(self, game_id: str, killer_role: str, victim_id: int, method: str):
        logger.info("RIP another innocent soul (or maybe not so innocent) 💀", 
                   game_id=game_id, killer_role=killer_role, victim_id=victim_id, method=method)

    async def log_vote(self, game_id: str, voter_id: int, target_id: int):
        logger.info("Democracy in action! Someone's about to get yeeted 🗳️", 
                   game_id=game_id, voter_id=voter_id, target_id=target_id)

    async def log_task_result(self, game_id: str, success: bool, assigned_players: list):
        status = "Crewmates actually did something useful" if success else "Tasks failed, ship go boom soon 💥"
        logger.info(status, game_id=game_id, success=success, assigned_players=assigned_players)

    async def log_sheriff_action(self, game_id: str, sheriff_id: int, target_id: int, target_role: str, success: bool):
        result = "Sheriff just rage-clicked an innocent. RIP trust issues 💀🔫" if not success else "Sheriff actually hit an impostor! Rare W 🎯"
        logger.info(result, game_id=game_id, sheriff_id=sheriff_id, target_id=target_id, target_role=target_role, success=success)

    async def log_detective_investigation(self, game_id: str, detective_id: int, target_id: int, result: str):
        logger.info("Detective playing 4D chess while everyone else playing checkers 🕵️", 
                   game_id=game_id, detective_id=detective_id, target_id=target_id, result=result)

    async def log_engineer_action(self, game_id: str, engineer_id: int, action: str):
        logger.info("Engineer either saved everyone or just delayed the inevitable 🔧", 
                   game_id=game_id, engineer_id=engineer_id, action=action)

class BotLogger:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def log_user_start(self, user_id: int):
        logger.info("Fresh meat joined the lobby 🥩", user_id=user_id)
        
        if BOT_LOG_CHANNEL_ID:
            await self.bot.send_message(
                BOT_LOG_CHANNEL_ID,
                f"👋 New user started bot: {user_id}"
            )

    async def log_ban(self, user_id: int, duration: str, reason: str):
        logger.info("Someone got the hammer treatment 🔨", user_id=user_id, duration=duration, reason=reason)
        
        if BOT_LOG_CHANNEL_ID:
            await self.bot.send_message(
                BOT_LOG_CHANNEL_ID,
                f"🔨 User banned: {user_id}\nDuration: {duration}\nReason: {reason}"
            )

    async def log_unban(self, user_id: int):
        logger.info("Second chances exist apparently 🙄", user_id=user_id)
        
        if BOT_LOG_CHANNEL_ID:
            await self.bot.send_message(
                BOT_LOG_CHANNEL_ID,
                f"🔓 User unbanned: {user_id}"
            )

    async def log_error(self, error: str, context: dict = None):
        logger.error("Something went horribly wrong 💩", error=error, context=context or {})