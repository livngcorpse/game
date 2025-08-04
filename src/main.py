import asyncio
import logging
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
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info("Shutting down bot")
        await bot_instance.application.updater.stop()
        await bot_instance.application.stop()
        await bot_instance.application.shutdown()
        await bot_instance.shutdown()

if __name__ == "__main__":
    asyncio.run(main())