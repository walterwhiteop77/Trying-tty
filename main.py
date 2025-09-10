import os
import logging
from telegram.ext import Application
from start import register_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class VideoBot:
    def __init__(self, token: str, data_file: str = "users.json"):
        self.bot_token = token
        self.data_file = data_file
        # Application will be created in run to avoid circular issues
        self.application = Application.builder().token(self.bot_token).build()

    async def send_log(self, message: str):
        log_channel_id = os.getenv("LOG_CHANNEL_ID")
        if log_channel_id:
            try:
                await self.application.bot.send_message(chat_id=log_channel_id, text=message)
            except Exception as e:
                logger.error(f"Failed to send log message: {e}")

    def get_user_data(self, user_id: int):
        # simple JSON-file-backed storage
        import json
        if not os.path.exists(self.data_file):
            return {}
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        return data.get(str(user_id))

    def save_user_data(self, user_id: int, user_data: dict):
        import json
        all_data = {}
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    all_data = json.load(f)
            except Exception:
                all_data = {}
        all_data[str(user_id)] = user_data
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2)

    def run(self):
        # register handlers now that application exists
        register_handlers(self.application, self)

        # post_init to send startup log
        async def _post_init(app):
            await self.send_log("✅ Bot started (webhook mode).")

        self.application.post_init = _post_init

        # Run webhook (Render)
        port = int(os.environ.get("PORT", 10000))
        external_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not external_url:
            raise RuntimeError("Missing RENDER_EXTERNAL_URL environment variable")

        self.application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=self.bot_token,
            webhook_url=f"{external_url}/{self.bot_token}",
        )

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is required")
    bot = VideoBot(token)
    bot.run()
