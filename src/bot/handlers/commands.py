from telegram import Update
from telegram.ext import ContextTypes
from src.bot.bot_instance import bot_instance
from src.database.models import GameMode, GamePhase
from src.utils.config import RANKED_GC_IDS
from src.ui.messages import Messages
from src.ui.keyboards import Keyboards

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    await bot_instance.bot_logger.log_user_start(user_id)
    await bot_instance.db.create_user(user_id)
    
    await update.message.reply_text(
        "🎮 Welcome to Among Us Bot!\n\nUse /help for more information.",
        reply_markup=Keyboards.get_help_commands_keyboard()
    )

async def startgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ Games can only be started in groups!")
        return
    
    group_id = update.effective_chat.id
    creator_id = update.effective_user.id
    
    if await bot_instance.ban_system.is_user_banned(creator_id):
        await update.message.reply_text(Messages.get_banned_message("check your ban status"))
        return
    
    existing_game = await bot_instance.game_state.get_game_by_group(group_id)
    if existing_game:
        await update.message.reply_text("⚠️ A game is already active in this group!")
        return
    
    mode_arg = context.args[0].lower() if context.args else None
    
    if group_id in RANKED_GC_IDS:
        mode = GameMode.UNRANKED if mode_arg == "unranked" else GameMode.RANKED
    else:
        if mode_arg == "ranked":
            await update.message.reply_text("❌ Ranked games are not allowed in this group!")
            return
        mode = GameMode.UNRANKED
    
    game = await bot_instance.game_state.create_game(group_id, creator_id, mode)
    
    await update.message.reply_text(
        Messages.get_lobby_message([], mode, creator_id),
        reply_markup=Keyboards.get_join_game_keyboard(game.id)
    )
    
    await bot_instance.phase_manager.start_lobby_timer(game.id, group_id)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ Use the join button in the group!")
        return
    
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    game = await bot_instance.game_state.get_game_by_group(group_id)
    if not game or game.phase != GamePhase.LOBBY:
        await update.message.reply_text(Messages.get_game_not_found_message())
        return
    
    if await bot_instance.ban_system.is_user_banned(user_id) and game.mode == GameMode.RANKED:
        await update.message.reply_text(Messages.get_banned_message("check your ban status"))
        return
    
    if await bot_instance.game_state.join_game(game.id, user_id):
        try:
            await bot_instance.bot.send_message(user_id, "✅ You joined the game! Wait for it to start.")
        except:
            await update.message.reply_text(Messages.get_dm_redirect_message())
            return
        
        players = bot_instance.game_state.get_lobby_players(game.id)
        await update.message.edit_text(
            Messages.get_lobby_message(players, game.mode, game.creator_id),
            reply_markup=Keyboards.get_join_game_keyboard(game.id)
        )
    else:
        await update.message.reply_text("⚠️ Could not join game (already joined or game full)!")

async def begin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    game = await bot_instance.game_state.get_game_by_group(group_id)
    if not game or game.phase != GamePhase.LOBBY:
        await update.message.reply_text(Messages.get_game_not_found_message())
        return
    
    if user_id != game.creator_id:
        await update.message.reply_text("❌ Only the game creator can force start!")
        return
    
    players = bot_instance.game_state.get_lobby_players(game.id)
    if len(players) < 4:
        await update.message.reply_text("❌ Need at least 4 players to start!")
        return
    
    await bot_instance.phase_manager.start_game_from_lobby(game.id, group_id)
    await update.message.reply_text(Messages.get_game_started_message())

async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    game = await bot_instance.game_state.get_game_by_group(group_id)
    if not game:
        await update.message.reply_text(Messages.get_game_not_found_message())
        return
    
    chat_member = await bot_instance.bot.get_chat_member(group_id, user_id)
    is_admin = chat_member.status in ['administrator', 'creator']
    is_creator = user_id == game.creator_id
    
    if not (is_admin or is_creator):
        await update.message.reply_text("❌ Only admins or game creator can end the game!")
        return
    
    await bot_instance.phase_manager.cleanup_game_timers(game.id)
    await bot_instance.game_state.end_game(game.id)
    await update.message.reply_text("🛑 Game ended by admin/creator.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            "📱 Help is available in DM only!",
            reply_markup=Keyboards.get_dm_redirect_keyboard()
        )
        return
    
    await update.message.reply_text(
        Messages.get_help_message(),
        reply_markup=Keyboards.get_help_commands_keyboard()
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _dm_only_command(update, "ℹ️ Game info available in DM!", "Game Information:\n\nAmong Us bot with roles, tasks, and XP system.")

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is responsive.")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _dm_only_command(update, "📋 About info available in DM!", "🤖 Among Us Telegram Bot\n\nDeveloped for group gameplay with full role system.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _dm_only_command(update, "🐛 Bug reporting available in DM!", "🐛 Bug Report\n\nPlease describe the issue you encountered.")

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _dm_only_command(update, "💭 Feedback available in DM!", "💭 Feedback\n\nShare your suggestions for improvement!")

async def roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _dm_only_command(update, "🎭 Roles info available in DM!", "🎭 Available Roles:\n\n🔧 Crewmate\n🔪 Impostor\n🕵️ Detective\n🔫 Sheriff\n⚙️ Engineer")

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _dm_only_command(update, "📜 Rules available in DM!", "📜 Game Rules:\n\n• Complete tasks or find impostors\n• Vote out suspicious players\n• Special roles have unique abilities")

async def _dm_only_command(update: Update, group_message: str, dm_message: str):
    if update.effective_chat.type != 'private':
        await update.message.reply_text(
            group_message,
            reply_markup=Keyboards.get_dm_redirect_keyboard()
        )
        return
    
    await update.message.reply_text(dm_message)