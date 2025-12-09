from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
from src.bot.handlers import commands, admin, callbacks
from src.utils.constants import COMMAND_PREFIXES

def setup_handlers(application):
    prefixes = "|".join(f"\\{prefix}" for prefix in COMMAND_PREFIXES)
    
    command_handlers = [
        CommandHandler(["start"], commands.start_command),
        CommandHandler(["startgame"], commands.startgame_command),
        CommandHandler(["join"], commands.join_command),
        CommandHandler(["begin"], commands.begin_command),
        CommandHandler(["end"], commands.end_command),
        CommandHandler(["help"], commands.help_command),
        CommandHandler(["info"], commands.info_command),
        CommandHandler(["ping"], commands.ping_command),
        CommandHandler(["about"], commands.about_command),
        CommandHandler(["report"], commands.report_command),
        CommandHandler(["feedback"], commands.feedback_command),
        CommandHandler(["roles"], commands.roles_command),
        CommandHandler(["rules"], commands.rules_command),
        CommandHandler(["xban"], admin.xban_command),
        CommandHandler(["xunban"], admin.xunban_command),
        CommandHandler(["setxp"], admin.setxp_command),
    ]
    
    callback_handlers = [
        CallbackQueryHandler(callbacks.handle_callback_query),
    ]
    
    for handler in command_handlers:
        application.add_handler(handler)
    
    for handler in callback_handlers:
        application.add_handler(handler)
    
    # Add team chat handler for impostors and detectives
    team_chat_handler = MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        callbacks.team_chat_callback
    )
    application.add_handler(team_chat_handler)
    
    message_handler = MessageHandler(
        filters.Regex(f"^({prefixes})(startgame|join|begin|end|help|info|ping|about|report|feedback|roles|rules)"),
        _handle_prefixed_commands
    )
    application.add_handler(message_handler)

async def _handle_prefixed_commands(update, context):
    text = update.message.text
    
    for prefix in COMMAND_PREFIXES:
        if text.startswith(prefix):
            command = text[1:].split()[0].lower()
            context.args = text.split()[1:] if len(text.split()) > 1 else []
            
            command_map = {
                "start": commands.start_command,
                "startgame": commands.startgame_command,
                "join": commands.join_command,
                "begin": commands.begin_command,
                "end": commands.end_command,
                "help": commands.help_command,
                "info": commands.info_command,
                "ping": commands.ping_command,
                "about": commands.about_command,
                "report": commands.report_command,
                "feedback": commands.feedback_command,
                "roles": commands.roles_command,
                "rules": commands.rules_command,
            }
            
            handler = command_map.get(command)
            if handler:
                await handler(update, context)
            break