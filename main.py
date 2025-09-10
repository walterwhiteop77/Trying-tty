import logging
import os

from telegram.ext import Application

from start import register_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class VideoBot:
    def __init__(self, token, log_channel_id=None):
        self.bot_token = token
        self.log_channel_id = log_channel_id

    async def send_log(self, message: str):
        if self.log_channel_id:
            try:
                from telegram import Bot
                bot = Bot(token=self.bot_token)
                await bot.send_message(chat_id=self.log_channel_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send log message: {e}")

    def run(self):
        application = Application.builder().token(self.bot_token).build()
        register_handlers(application, self)

        async def on_startup(app):
            await self.send_log("✅ Bot has started successfully (Webhook mode).")

        application.post_init = on_startup

        port = int(os.environ.get("PORT", 10000))
        external_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not external_url:
            raise RuntimeError("Missing RENDER_EXTERNAL_URL environment variable")

        # Direct call, no asyncio.run()
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=self.bot_token,
            webhook_url=f"{external_url}/{self.bot_token}",
        )


if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    log_channel = os.getenv("LOG_CHANNEL_ID")

    if not token:
        raise RuntimeError("BOT_TOKEN is required")

    bot = VideoBot(token, log_channel)
    bot.run()
