from telegram import Update
from telegram.ext import ContextTypes
from src.bot.bot_instance import bot_instance
from src.database.models import GamePhase, GameMode
from src.ui.messages import Messages
from src.ui.keyboards import Keyboards

async def join_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.split("_")[-1]
    user_id = query.from_user.id
    
    game = await bot_instance.game_state.get_game_by_group(query.message.chat.id)
    if not game or game.phase != GamePhase.LOBBY:
        await query.edit_message_text("❌ Game no longer available!")
        return
    
    if await bot_instance.ban_system.is_user_banned(user_id) and game.mode == GameMode.RANKED:
        await query.answer("🚫 You are banned from ranked games!", show_alert=True)
        return
    
    if await bot_instance.game_state.join_game(game_id, user_id):
        try:
            await bot_instance.bot.send_message(user_id, "✅ You joined the game! Wait for it to start.")
        except:
            await query.answer("❌ Please start a conversation with me in DM first!", show_alert=True)
            return
        
        players = bot_instance.game_state.get_lobby_players(game_id)
        await query.edit_message_text(
            Messages.get_lobby_message(players, game.mode, game.creator_id),
            reply_markup=Keyboards.get_join_game_keyboard(game_id)
        )
    else:
        await query.answer("⚠️ Could not join (already joined or game full)!", show_alert=True)

async def begin_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.split("_")[-1]
    user_id = query.from_user.id
    
    game = await bot_instance.game_state.get_game_by_group(query.message.chat.id)
    if not game or game.phase != GamePhase.LOBBY:
        await query.answer("❌ Game no longer available!", show_alert=True)
        return
    
    if user_id != game.creator_id:
        await query.answer("❌ Only game creator can force start!", show_alert=True)
        return
    
    players = bot_instance.game_state.get_lobby_players(game_id)
    if len(players) < 4:
        await query.answer("❌ Need at least 4 players!", show_alert=True)
        return
    
    await bot_instance.phase_manager.start_game_from_lobby(game_id, query.message.chat.id)
    await query.edit_message_text(Messages.get_game_started_message())

async def end_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.split("_")[-1]
    user_id = query.from_user.id
    
    game = await bot_instance.game_state.get_game_by_group(query.message.chat.id)
    if not game:
        await query.answer("❌ No active game!", show_alert=True)
        return
    
    chat_member = await bot_instance.bot.get_chat_member(query.message.chat.id, user_id)
    is_admin = chat_member.status in ['administrator', 'creator']
    is_creator = user_id == game.creator_id
    
    if not (is_admin or is_creator):
        await query.answer("❌ Only admins or creator can end game!", show_alert=True)
        return
    
    await bot_instance.phase_manager.cleanup_game_timers(game_id)
    await bot_instance.game_state.end_game(game_id)
    await query.edit_message_text("🛑 Game ended by admin/creator.")

async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    game_id = parts[1]
    target_id = int(parts[2]) if parts[2] != "skip" else None
    user_id = query.from_user.id
    
    game = await bot_instance.db.get_game_by_group(0)
    if not game or game.phase != GamePhase.VOTING:
        await query.edit_message_text("❌ Voting phase not active!")
        return
    
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive:
        await query.answer("❌ You cannot vote!", show_alert=True)
        return
    
    if player.voted:
        await query.answer("❌ You already voted!", show_alert=True)
        return
    
    await bot_instance.game_state.vote_player(game_id, user_id, target_id)
    
    vote_text = f"Player {target_id}" if target_id else "Skip"
    await query.edit_message_text(f"✅ You voted for: {vote_text}")

async def task_complete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    game_id = parts[2]
    user_id = int(parts[3])
    
    if query.from_user.id != user_id:
        await query.answer("❌ This is not your task!", show_alert=True)
        return
    
    success = await bot_instance.task_engine.complete_task(game_id, user_id)
    if success:
        await bot_instance.xp_system.award_xp(user_id, "task_completed")
        await query.edit_message_text("✅ Task completed!")
    else:
        await query.edit_message_text("❌ Task not assigned to you!")

async def night_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action_data = query.data
    
    parts = action_data.split("_")
    if len(parts) < 3:
        return
    
    role_name = parts[0]
    game_id = parts[2]
    
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive:
        await query.answer("❌ You cannot perform actions!", show_alert=True)
        return
    
    role_instance = bot_instance.role_factory.create_role_instance(
        user_id, game_id, player.role, bot_instance.game_state.get_round_number(game_id)
    )
    
    result = await role_instance.process_night_action(action_data)
    await bot_instance.phase_manager.record_night_action(game_id, user_id, role_name, result)
    
    await query.edit_message_text(f"✅ Action recorded: {result.get('action', 'unknown')}")

async def engineer_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1]
    game_id = parts[2]
    user_id = query.from_user.id
    
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or player.role.value != "engineer":
        await query.answer("❌ You are not the engineer!", show_alert=True)
        return
    
    if action == "fix":
        await bot_instance.db.update_player_field(game_id, user_id, "engineer_used_ability", True)
        await bot_instance.xp_system.award_xp(user_id, "engineer_saves_ship")
        await query.edit_message_text("⚙️ Ship fixed! Crisis averted!")
    else:
        await query.edit_message_text("⚙️ Fix skipped.")

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    help_type = query.data.split("_")[1]
    
    messages = {
        "rules": "📜 Rules:\n• Find and vote out impostors\n• Complete tasks to win\n• Special roles have unique abilities",
        "roles": "🎭 Roles:\n• Crewmate: Complete tasks\n• Impostor: Eliminate crew\n• Detective: Investigate players\n• Sheriff: Eliminate players\n• Engineer: Fix ship",
        "commands": "📋 Commands:\n• /startgame - Create game\n• /join - Join game\n• /help - This help\n• /ping - Test bot",
        "about": "🤖 About:\nAmong Us Telegram Bot\nDeveloped for group gameplay"
    }
    
    await query.edit_message_text(
        messages.get(help_type, "Unknown help topic"),
        reply_markup=Keyboards.get_help_commands_keyboard()
    )