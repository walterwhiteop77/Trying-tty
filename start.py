import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

logger = logging.getLogger(__name__)

def register_handlers(application, bot):
    # add bot reference to handlers via closures
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        # send to log channel about new user
        try:
            await bot.send_log(f"👤 New user started: {user.id} ({user.username})")
        except Exception:
            logger.exception("Failed to send start log")
        await update.message.reply_text("""👋 Welcome!
Use the inline bookmark button presented with videos to save them.
Commands:
/mybookmarks - list your bookmarks
/deletebookmark <number> - delete bookmark by its number (use /mybookmarks to see numbers)
""")

    async def toggle_bookmark_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data  # expected "bookmark:<file_id>"
        if ":" not in data:
            await query.message.reply_text("Invalid callback data.")
            return
        _, file_id = data.split(":", 1)
        user_data = bot.get_user_data(user_id) or {"bookmarks": []}
        bookmarks = user_data.get("bookmarks", [])
        if file_id in bookmarks:
            bookmarks.remove(file_id)
            msg = "❌ Bookmark removed."
        else:
            if len(bookmarks) >= 5:
                msg = "⚠️ You can only keep 5 bookmarks."
            else:
                bookmarks.append(file_id)
                msg = "✅ Video bookmarked!"
        user_data["bookmarks"] = bookmarks
        bot.save_user_data(user_id, user_data)
        await query.message.reply_text(msg)

    async def my_bookmarks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data = bot.get_user_data(user_id) or {"bookmarks": []}
        bookmarks = user_data.get("bookmarks", [])
        if not bookmarks:
            await update.message.reply_text("📂 You have no bookmarks yet.")
            return
        # send numbered list with small preview where possible
        text_lines = []
        for idx, file_id in enumerate(bookmarks, start=1):
            text_lines.append(f"{idx}. {file_id}")
        await update.message.reply_text("\n".join(text_lines))

    async def delete_bookmark_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.args:
            await update.message.reply_text("Usage: /deletebookmark <number>")
            return
        try:
            n = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Please provide a valid number.")
            return
        user_data = bot.get_user_data(user_id) or {"bookmarks": []}
        bookmarks = user_data.get("bookmarks", [])
        if n < 1 or n > len(bookmarks):
            await update.message.reply_text("Invalid bookmark number.")
            return
        removed = bookmarks.pop(n-1)
        user_data["bookmarks"] = bookmarks
        bot.save_user_data(user_id, user_data)
        await update.message.reply_text(f"🗑️ Removed bookmark #{n}: {removed}")

    # Register handlers on the application
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("mybookmarks", my_bookmarks))
    application.add_handler(CommandHandler("deletebookmark", delete_bookmark_cmd))
    application.add_handler(CallbackQueryHandler(toggle_bookmark_callback, pattern=r"^bookmark:"))
