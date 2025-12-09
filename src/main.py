import asyncio
import logging
import sys
from src.bot.bot_instance import bot_instance
from src.bot.dispatcher import setup_handlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    try:
        await bot_instance.initialize()
        logger.info("Bot initialized successfully")
        
        setup_handlers(bot_instance.application)
        logger.info("Handlers registered")
        
        await bot_instance.application.initialize()
        await bot_instance.application.start()
        await bot_instance.application.updater.start_polling()
        
        logger.info("Bot started successfully")
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Unexpected error during bot operation: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Fatal error during bot startup: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Shutting down bot")
        try:
            await bot_instance.application.updater.stop()
        except Exception as e:
            logger.error(f"Error stopping updater: {e}")
        try:
            await bot_instance.application.stop()
        except Exception as e:
            logger.error(f"Error stopping application: {e}")
        try:
            await bot_instance.application.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down application: {e}")
        try:
            await bot_instance.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down bot instance: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)