from telegram import Update
from telegram.ext import ContextTypes
from src.bot.bot_instance import bot_instance
from src.utils.config import BOT_OWNER_ID

async def xban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("❌ Owner only command!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /xban <user_id> <duration> [reason]")
        return
    
    try:
        user_id = int(context.args[0])
        duration = context.args[1]
        reason = " ".join(context.args[2:]) if len(context.args) > 2 else "No reason provided"
        
        await bot_instance.ban_system.ban_user(user_id, duration, reason)
        await update.message.reply_text(f"✅ User {user_id} banned for {duration}")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def xunban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("❌ Owner only command!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /xunban <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        await bot_instance.ban_system.unban_user(user_id)
        await update.message.reply_text(f"✅ User {user_id} unbanned")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def setxp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_OWNER_ID:
        await update.message.reply_text("❌ Owner only command!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setxp <user_id> <amount>")
        return
    
    try:
        user_id = int(context.args[0])
        xp_amount = int(context.args[1])
        
        await bot_instance.db.set_user_xp(user_id, xp_amount)
        await update.message.reply_text(f"✅ Set user {user_id} XP to {xp_amount}")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or XP amount!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")