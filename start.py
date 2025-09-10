from telegram import Update
from telegram.ext import ContextTypes
from main import VideoBot

bot = VideoBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Log new user in log channel
    await bot.send_log(f"👤 New user started the bot: {user.id} - {user.full_name}")

    # Your existing welcome/start logic
    await update.message.reply_text(
        "👋 Welcome to the bot! Use the menu below to browse videos."
    )
