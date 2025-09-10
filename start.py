import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

logger = logging.getLogger(__name__)


def register_handlers(application, bot):
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await bot.send_log(f"👤 New user started: {user.id} ({user.username})")
        await update.message.reply_text("👋 Welcome! Use /mybookmarks to view your saved videos.")

    async def toggle_bookmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        file_id = query.data.split(":", 1)[1]

        user_data = bot.get_user_data(user_id) or {"bookmarks": []}
        msg = ""

        if file_id in user_data["bookmarks"]:
            user_data["bookmarks"].remove(file_id)
            msg = "❌ Bookmark removed."
        else:
            if len(user_data["bookmarks"]) >= 5:
                msg = "⚠️ You can only keep 5 bookmarks."
            else:
                user_data["bookmarks"].append(file_id)
                msg = "✅ Video bookmarked!"

        bot.save_user_data(user_id, user_data)
        await query.message.reply_text(msg)

    async def my_bookmarks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data = bot.get_user_data(user_id) or {"bookmarks": []}

        if not user_data["bookmarks"]:
            await update.message.reply_text("📂 You have no bookmarks yet.")
            return

        for file_id in user_data["bookmarks"]:
            await update.message.reply_video(
                video=file_id,
                caption="📌 Bookmarked video",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Remove", callback_data=f"removebookmark:{file_id}")]
                ])
            )

    async def remove_bookmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        file_id = query.data.split(":", 1)[1]

        user_data = bot.get_user_data(user_id) or {"bookmarks": []}
        if file_id in user_data["bookmarks"]:
            user_data["bookmarks"].remove(file_id)
            bot.save_user_data(user_id, user_data)
            await query.message.reply_text("🗑️ Bookmark deleted.")
        else:
            await query.message.reply_text("⚠️ That video is not in your bookmarks.")

    async def delete_bookmark_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("Usage: /deletebookmark <file_id>")
            return

        file_id = context.args[0]
        user_data = bot.get_user_data(user_id) or {"bookmarks": []}

        if file_id in user_data["bookmarks"]:
            user_data["bookmarks"].remove(file_id)
            bot.save_user_data(user_id, user_data)
            await update.message.reply_text("🗑️ Bookmark deleted.")
        else:
            await update.message.reply_text("⚠️ That file is not in your bookmarks.")

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mybookmarks", my_bookmarks))
    application.add_handler(CommandHandler("deletebookmark", delete_bookmark_cmd))
    application.add_handler(CallbackQueryHandler(toggle_bookmark, pattern=r"^bookmark:"))
    application.add_handler(CallbackQueryHandler(remove_bookmark, pattern=r"^removebookmark:"))
