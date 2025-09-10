import os
from telegram.ext import Application, CommandHandler

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8443))
APP_NAME = os.getenv("RENDER_EXTERNAL_URL")

async def start(update, context):
    await update.message.reply_text("Bot is running with webhook ✅")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{APP_NAME}/{TOKEN}",
    )

if __name__ == "__main__":
    main()
