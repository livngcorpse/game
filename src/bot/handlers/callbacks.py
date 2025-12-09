from telegram import Update
from telegram.ext import ContextTypes
from src.bot.bot_instance import bot_instance
from src.database.models import GamePhase, GameMode, Role
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
    if parts[1] == "skip":
        game_id = parts[2]
        target_id = None
    else:
        game_id = parts[1]
        target_id = int(parts[2])
    
    user_id = query.from_user.id
    
    # Fix: Get game by game_id, not hardcoded 0
    game = await bot_instance.db.get_game_by_id(game_id)
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
    
    # Announce in group that player voted (anonymously)
    await bot_instance.bot.send_message(
        game.group_id, 
        f"✅ Player {user_id} has voted."
    )
    
    vote_text = f"Player {target_id}" if target_id else "Skip"
    await query.edit_message_text(f"✅ You voted for: {vote_text}")

# NEW: Missing night action callbacks for each role
async def impostor_kill_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle impostor kill actions"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1]  # "kill" or "skip"
    game_id = parts[2]
    target_id = int(parts[3]) if len(parts) > 3 and parts[3] != game_id else None
    user_id = query.from_user.id
    
    # Validate player can act
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive or player.role != Role.IMPOSTOR:
        await query.answer("❌ You cannot perform this action!", show_alert=True)
        return
    
    if action == "skip":
        await query.edit_message_text("🔪 You chose to skip killing.")
        return
    
    # Process the kill action
    result = await bot_instance.phase_manager.process_impostor_action(
        game_id, user_id, "kill", target_id
    )
    
    await query.edit_message_text(f"🔪 {result['message']}")

async def detective_investigate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle detective investigation actions"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1]  # "investigate" or "skip"
    game_id = parts[2]
    target_id = int(parts[3]) if len(parts) > 3 and parts[3] != game_id else None
    user_id = query.from_user.id
    
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive or player.role != Role.DETECTIVE:
        await query.answer("❌ You cannot perform this action!", show_alert=True)
        return
    
    if action == "skip":
        await query.edit_message_text("🕵️ You chose to skip investigating.")
        return
    
    result = await bot_instance.phase_manager.process_detective_action(
        game_id, user_id, "investigate", target_id
    )
    
    await query.edit_message_text(f"🕵️ {result['message']}")

async def sheriff_shoot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle sheriff shoot actions"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1]  # "shoot" or "skip"
    game_id = parts[2]
    target_id = int(parts[3]) if len(parts) > 3 and parts[3] != game_id else None
    user_id = query.from_user.id
    
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive or player.role != Role.SHERIFF:
        await query.answer("❌ You cannot perform this action!", show_alert=True)
        return
    
    # Check if already used shot
    if await bot_instance.db.get_player_field(game_id, user_id, "sheriff_used_shot"):
        await query.answer("❌ You already used your shot!", show_alert=True)
        return
    
    if action == "skip":
        await query.edit_message_text("🔫 You chose not to shoot.")
        return
    
    result = await bot_instance.phase_manager.process_sheriff_action(
        game_id, user_id, "shoot", target_id
    )
    
    await query.edit_message_text(f"🔫 {result['message']}")

async def task_complete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    game_id = parts[2]
    user_id = int(parts[3])
    task_id = parts[4] if len(parts) > 4 else None
    
    if query.from_user.id != user_id:
        await query.answer("❌ This is not your task!", show_alert=True)
        return
    
    # Validate player can complete tasks
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive or player.role != Role.CREWMATE:
        await query.answer("❌ You cannot complete tasks!", show_alert=True)
        return
    
    success = await bot_instance.task_engine.complete_task(game_id, user_id, task_id)
    if success:
        await bot_instance.xp_system.award_xp(user_id, "task_completed")
        await query.edit_message_text("✅ Task completed successfully!")
    else:
        await query.edit_message_text("❌ Task completion failed!")

async def engineer_fix_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle engineer fix/skip actions"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    action = parts[1]  # "fix" or "skip"
    game_id = parts[2]
    user_id = query.from_user.id
    
    player = await bot_instance.db.get_player(game_id, user_id)
    if not player or not player.is_alive or player.role != Role.ENGINEER:
        await query.answer("❌ You are not the engineer!", show_alert=True)
        return
    
    # Check if already used ability
    if await bot_instance.db.get_player_field(game_id, user_id, "engineer_used_ability"):
        await query.answer("❌ You already used your fix ability!", show_alert=True)
        return
    
    if action == "fix":
        # Mark as used and reset failed rounds
        await bot_instance.db.update_player_field(game_id, user_id, "engineer_used_ability", True)
        game = await bot_instance.db.get_game_by_id(game_id)
        if game:
            # Reset failed count by updating game settings
            settings = game.settings or {}
            settings['failed_task_rounds'] = 0
            await bot_instance.db.update_game_settings(game_id, settings)
        await bot_instance.xp_system.award_xp(user_id, "engineer_saves_ship")
        await query.edit_message_text("⚙️ Ship systems fixed! Crisis averted!")
        
        # Log the heroic save
        await bot_instance.game_logger.log_engineer_action(game_id, user_id, True)
    else:
        await query.edit_message_text("⚙️ You chose not to fix the ship.")
        await bot_instance.game_logger.log_engineer_action(game_id, user_id, False)
    
    # Continue to normal discussion phase
    game = await bot_instance.db.get_game_by_id(game_id)
    if game:
        await bot_instance.phase_manager._continue_to_discussion(game_id, game.group_id)

async def engineer_day_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle engineer day actions (deprecated, but kept for backward compatibility)"""
    await engineer_fix_callback(update, context)

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    help_type = query.data.split("_")[1]
    
    messages = {
        "rules": "📜 **Game Rules:**\n\n• Find and vote out all impostors to win\n• Complete tasks when assigned\n• Use your role's special abilities wisely\n• Discussion phase: talk strategy\n• Voting phase: vote out suspicious players",
        
        "roles": "🎭 **Roles Guide:**\n\n🟦 **Crewmate**: Complete tasks, vote out impostors\n🔴 **Impostor**: Kill crewmates, blend in\n🕵️ **Detective**: Find impostors through investigation\n🔫 **Sheriff**: Eliminate players (beware friendly fire!)\n⚙️ **Engineer**: Fix ship when tasks fail",
        
        "commands": "📋 **Commands:**\n\n🎮 **Game Commands:**\n• `/startgame [ranked/unranked]` - Create new game\n• `/join` - Join active game\n• `/begin` - Force start (creator only)\n• `/end` - End game (admin/creator only)\n\n📱 **Utility:**\n• `/help` - Show this help\n• `/ping` - Test bot\n• `/stats` - Your game statistics",
        
        "about": "🤖 **About This Bot:**\n\nAmong Us Telegram Bot v2.0\n\n• Supports 4-20 players\n• Ranked and unranked modes\n• Full role system with special abilities\n• XP and achievement system\n• Developed with ❤️ for group gameplay\n\n🔗 GitHub: [Repository Link]\n👨‍💻 Developer: [Your Name]"
    }
    
    await query.edit_message_text(
        messages.get(help_type, "❌ Unknown help topic"),
        reply_markup=Keyboards.get_help_commands_keyboard(),
        parse_mode='Markdown'
    )

# NEW: Callback router function
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback router - directs callbacks to appropriate handlers"""
    query = update.callback_query
    callback_data = query.data
    
    # Route callbacks based on prefix
    if callback_data.startswith("join_game_"):
        await join_game_callback(update, context)
    elif callback_data.startswith("begin_game_"):
        await begin_game_callback(update, context)
    elif callback_data.startswith("end_game_"):
        await end_game_callback(update, context)
    elif callback_data.startswith("vote_"):
        await vote_callback(update, context)
    elif callback_data.startswith("impostor_"):
        await impostor_kill_callback(update, context)
    elif callback_data.startswith("detective_"):
        await detective_investigate_callback(update, context)
    elif callback_data.startswith("sheriff_"):
        await sheriff_shoot_callback(update, context)
    elif callback_data.startswith("task_complete_"):
        await task_complete_callback(update, context)
    elif callback_data.startswith("engineer_"):
        await engineer_fix_callback(update, context)
    elif callback_data.startswith("help_"):
        await help_callback(update, context)
    else:
        # Handle unknown callbacks gracefully
        await query.answer("❌ Unknown action!", show_alert=True)

async def team_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle team chat messages for impostors and detectives"""
    message = update.message
    user_id = message.from_user.id
    chat_text = message.text
    
    # Get the current game for this user
    game = await bot_instance.game_state.get_game_by_user(user_id)
    if not game:
        return
    
    # Check if user is in the game
    player = await bot_instance.db.get_player(game.id, user_id)
    if not player or not player.is_alive:
        return
    
    # Relay message to teammates based on role
    if player.role == Role.IMPOSTOR:
        await bot_instance.phase_manager.relay_team_message(game.id, user_id, chat_text, Role.IMPOSTOR)
    elif player.role == Role.DETECTIVE:
        await bot_instance.phase_manager.relay_team_message(game.id, user_id, chat_text, Role.DETECTIVE)

# DEPRECATED: Remove this old generic handler
# async def night_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     # This approach was too generic and problematic
#     pass