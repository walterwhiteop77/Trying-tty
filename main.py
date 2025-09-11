#!/usr/bin/env python3
"""
Telegram Video Bot with MongoDB
A comprehensive bot for video management with categories, bookmarks, premium features, and broadcast.
"""

import os
import asyncio
import logging
# Reduce httpx logging to prevent token exposure
logging.getLogger("httpx").setLevel(logging.WARNING)
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaVideo
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes)
from telegram.constants import ParseMode
from dotenv import load_dotenv
import json
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import random
import requests
import hashlib
import secrets
from urllib.parse import urlencode

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoBot:

    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.channel_ids = {
            1: os.getenv('CATEGORY_1_CHANNEL'),
            2: os.getenv('CATEGORY_2_CHANNEL'),
            3: os.getenv('CATEGORY_3_CHANNEL'),
            4: os.getenv('CATEGORY_4_CHANNEL')
        }
        self.log_channel_id = os.getenv('LOG_CHANNEL_ID')
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        self.admin_ids = set(map(
            int, admin_ids_str.split(','))) if admin_ids_str else set()

        # Auto-delete toggle (can be controlled via environment variable)
        self.auto_delete_enabled = os.getenv('AUTO_DELETE_VIDEOS',
                                             'true').lower() == 'true'
        self.auto_delete_minutes = int(os.getenv('AUTO_DELETE_MINUTES', '10'))

        # URL Shortener and verification settings
        self.url_shortener_api = os.getenv('URL_SHORTENER_API_KEY')
        self.force_subscribe_channel = os.getenv('FORCE_SUBSCRIBE_CHANNEL')

        # Bot settings (stored in database)
        self.bot_settings = {}
        self.verification_tokens = {}

        # MongoDB connection
        self.mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        self.db_name = os.getenv('DB_NAME', 'telegram_video_bot')
        self.client = None
        self.db = None

    def init_database(self):
        """Initialize MongoDB connection and collections"""
        try:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]

            # Test connection
            self.client.admin.command('ping')

            # Create collections with indexes
            if self.db is not None:
                self.db.users.create_index("user_id", unique=True)
                self.db.videos.create_index("file_id", unique=True)
                self.db.videos.create_index("category")
                self.db.bookmarks.create_index([("user_id", 1),
                                                ("video_id", 1)],
                                               unique=True)
                self.db.bot_settings.create_index("setting_name", unique=True)
                self.db.verification_tokens.create_index("token", unique=True)
                self.db.verification_tokens.create_index(
                    "created_at",
                    expireAfterSeconds=3600)  # Expire after 1 hour
                # Add unique index for video likes to prevent duplicates
                self.db.video_likes.create_index(
                    [("user_id", 1), ("video_id", 1)], unique=True)

            # Initialize complete

            logger.info("✅ MongoDB connected successfully")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            return False

    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Get user data from MongoDB"""
        try:
            if self.db is not None:
                user = self.db.users.find_one({"user_id": user_id})
                return user
            return None
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return None

    def save_user_data(self, user_id: int, user_data: Dict):
        """Save user data to MongoDB"""
        try:
            if self.db is not None:
                user_data['user_id'] = user_id
                self.db.users.update_one({"user_id": user_id},
                                         {"$set": user_data},
                                         upsert=True)
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving user data: {e}")
            return False

    def add_video_to_db(self, file_id: str, file_name: str, category: int,
                        file_size: int):
        """Add video to MongoDB"""
        try:
            if self.db is not None:
                video_data = {
                    "file_id": file_id,
                    "file_name": file_name,
                    "category": category,
                    "file_size": file_size,
                    "added_date": datetime.now()
                }
                self.db.videos.insert_one(video_data)
                return True
            return False
        except DuplicateKeyError:
            return False  # Video already exists
        except Exception as e:
            logger.error(f"Error adding video: {e}")
            return False

    def get_bot_setting(self, setting_name: str, default_value=None):
        """Get a bot setting from database"""
        try:
            if self.db is None:
                return default_value
            setting = self.db.bot_settings.find_one({"setting_name": setting_name})
            if setting:
                return setting.get("setting_value", default_value)
            return default_value
        except Exception as e:
            logger.error(f"Error getting bot setting {setting_name}: {e}")
            return default_value

    def get_video_like_percentage(self, video_id: str) -> int:
        """Calculate like percentage for a video"""
        try:
            if self.db is None:
                return 77  # Default percentage
                
            total_likes = self.db.video_likes.count_documents({"video_id": video_id, "liked": True})
            total_dislikes = self.db.video_likes.count_documents({"video_id": video_id, "liked": False})
            total_votes = total_likes + total_dislikes
            
            if total_votes == 0:
                return 77  # Default percentage when no votes
            
            return int((total_likes / total_votes) * 100)
        except Exception as e:
            logger.error(f"Error calculating like percentage: {e}")
            return 77

    def get_videos_by_category(self, category: int) -> List[Dict]:
        """Get all videos from a specific category"""
        try:
            if self.db is not None:
                videos = list(
                    self.db.videos.find({
                        "category": category
                    }).sort("added_date", 1))
                return videos
            return []
        except Exception as e:
            logger.error(f"Error getting videos: {e}")
            return []

    def get_mixed_videos(self) -> List[Dict]:
        """Get random videos from all categories"""
        try:
            if self.db is not None:
                videos = list(
                    self.db.videos.aggregate([{
                        "$sample": {
                            "size": 100
                        }
                    }]))
                return videos
            return []
        except Exception as e:
            logger.error(f"Error getting mixed videos: {e}")
            return []

    def create_main_keyboard(self) -> InlineKeyboardMarkup:
        """Create main menu keyboard"""
        keyboard = [[
            InlineKeyboardButton("🎥 Get Video", callback_data="get_video")
        ], [InlineKeyboardButton("📊 My Status", callback_data="status")]]
        return InlineKeyboardMarkup(keyboard)

    def create_video_keyboard(
            self,
            user_id: int,
            is_premium: bool = False) -> InlineKeyboardMarkup:
        """Create video control keyboard matching screenshot design"""
        keyboard = [
            # Row 1: Like, Dislike, Download
            [
                InlineKeyboardButton("👍 Like", callback_data="like_video"),
                InlineKeyboardButton("👎 Dislike", callback_data="dislike_video"),
                InlineKeyboardButton("⬇️ Download", callback_data="download_video") if is_premium else InlineKeyboardButton("🔒 Download", callback_data="premium_required")
            ],
            # Row 2: Previous, Next  
            [
                InlineKeyboardButton("⏮️ Previous", callback_data="prev_video"),
                InlineKeyboardButton("Next ▶️", callback_data="next_video")
            ],
            # Row 3: Change Category, Bookmark
            [
                InlineKeyboardButton("🔄 Change Category", callback_data="change_category"),
                InlineKeyboardButton("🔖 Bookmark", callback_data="bookmark_video")
            ],
            # Row 4: For Dark Content
            [
                InlineKeyboardButton("💥 For D@rk C00ntent", callback_data="dark_content")
            ]
        ]

        return InlineKeyboardMarkup(keyboard)

    def create_category_keyboard(self) -> InlineKeyboardMarkup:
        """Create category selection keyboard"""
        keyboard = [[
            InlineKeyboardButton("Category 1", callback_data="cat_1"),
            InlineKeyboardButton("Category 2", callback_data="cat_2")
        ],
                    [
                        InlineKeyboardButton("Category 3",
                                             callback_data="cat_3"),
                        InlineKeyboardButton("Category 4",
                                             callback_data="cat_4")
                    ],
                    [InlineKeyboardButton("🎲 Mix", callback_data="cat_mix")],
                    [
                        InlineKeyboardButton("🔙 Back",
                                             callback_data="get_video")
                    ]]
        return InlineKeyboardMarkup(keyboard)

    async def start_command(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        if not user:
            return

        user_id = user.id

        # Initialize user data
        user_data = self.get_user_data(user_id)
        if not user_data:
            user_data = {
                'user_id': user_id,
                'username': user.username,
                'first_name': user.first_name,
                'join_date': datetime.now(),
                'is_premium': False,
                'premium_expires': None,
                'current_category': 1,
                'current_video_index': 0,
                'watched_videos': 0
            }
            self.save_user_data(user_id, user_data)

            # Log new member
            if self.log_channel_id:
                try:
                    await context.bot.send_message(
                        chat_id=self.log_channel_id,
                        text=f"🆕 New member joined:\n"
                        f"👤 Name: {user.first_name}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📝 Username: @{user.username or 'None'}\n"
                        f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                except Exception as e:
                    logger.error(f"Error logging new member: {e}")

        welcome_text = f"🎬 Welcome to Video Bot, {user.first_name}!\n\n" \
                      f"Choose an option below to get started:"

        if update.message:
            await update.message.reply_text(
                welcome_text, reply_markup=self.create_main_keyboard())

    async def status_callback(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """Handle status button callback"""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            await query.edit_message_text(
                "❌ User data not found. Please use /start command.")
            return

        # Check premium status
        is_premium = user_data.get('is_premium', False)
        premium_expires = user_data.get('premium_expires')

        if is_premium and premium_expires:
            if isinstance(premium_expires, str):
                expires_date = datetime.fromisoformat(premium_expires)
            else:
                expires_date = premium_expires

            if expires_date < datetime.now():
                is_premium = False
                user_data['is_premium'] = False
                self.save_user_data(user_id, user_data)

        status_text = f"🌟 My Status\n\n" \
                     f"🎬 Watched Videos: {user_data.get('watched_videos', 0)}\n" \
                     f"📂 Current Category: {user_data.get('current_category', 1)}\n" \
                     f"🔑 Access Status: {'✅ Premium' if is_premium else '🔓 Free'}\n"

        if is_premium and premium_expires:
            if isinstance(premium_expires, str):
                expires_date = datetime.fromisoformat(premium_expires)
            else:
                expires_date = premium_expires
            status_text += f"⏳ Access Expires: {expires_date.strftime('%Y-%m-%d %H:%M')}\n"
        else:
            status_text += f"⏳ Access Expires: No active premium\n"

        status_text += f"📥 Downloads: {'✅ Available' if is_premium else '❌ Premium only'}\n" \
                      f"🔗 Link Access: ✅ Available"

        keyboard = [[
            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
        ]]

        await query.edit_message_text(
            status_text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def get_video_callback(self, update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
        """Handle get video button callback"""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            await query.edit_message_text(
                "❌ User data not found. Please use /start command.")
            return

        # Get videos for current category
        category = user_data.get('current_category', 1)
        if category == 0:  # Mix mode
            videos = self.get_mixed_videos()
        else:
            videos = self.get_videos_by_category(category)

        if not videos:
            await query.edit_message_text(
                f"📭 No videos available in category {category}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]))
            return

        # Get current video
        video_index = user_data.get('current_video_index', 0)
        if video_index >= len(videos):
            video_index = 0
            user_data['current_video_index'] = 0
            self.save_user_data(user_id, user_data)

        current_video = videos[video_index]

        # Check premium status
        is_premium = user_data.get('is_premium', False)
        premium_expires = user_data.get('premium_expires')

        if is_premium and premium_expires:
            if isinstance(premium_expires, str):
                expires_date = datetime.fromisoformat(premium_expires)
            else:
                expires_date = premium_expires
            if expires_date < datetime.now():
                is_premium = False

        # Get video stats for caption
        video_id = str(current_video.get('_id', ''))[-5:]  # Last 5 digits as Video ID
        like_percentage = self.get_video_like_percentage(str(current_video.get('_id', '')))
        
        caption = f"Video ID: {video_id}\n{like_percentage}% users liked this"

        try:
            if query.message and hasattr(query.message, 'chat_id'):
                # Validate video file_id before sending
                file_id = current_video.get('file_id', '')
                if not file_id or len(file_id) < 20:
                    logger.warning(f"Invalid file_id for video: {current_video.get('_id')}")
                    # Skip to next video
                    user_data['current_video_index'] = (video_index + 1) % len(videos)
                    self.save_user_data(user_id, user_data)
                    await query.edit_message_text(
                        "⚠️ Skipping invalid video... Loading next one.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Again", callback_data="get_video")
                        ]]))
                    return

                # Check forwarding protection setting
                protect_content = self.get_bot_setting('forward_protection_enabled', False)
                
                video_message = await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=file_id,
                    caption=caption,
                    reply_markup=self.create_video_keyboard(
                        user_id, is_premium),
                    protect_content=protect_content)
                await query.delete_message()

                # Schedule auto-deletion if enabled
                if self.auto_delete_enabled:

                    async def delete_video_message():
                        await asyncio.sleep(self.auto_delete_minutes * 60)
                        try:
                            await context.bot.delete_message(
                                chat_id=video_message.chat_id,
                                message_id=video_message.message_id)
                        except Exception as e:
                            logger.error(f"Error deleting video message: {e}")

                    asyncio.create_task(delete_video_message())
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            # Try to skip to next video automatically
            if "wrong padding" in str(e).lower() or "remote file identifier" in str(e).lower():
                try:
                    user_data['current_video_index'] = (video_index + 1) % len(videos)
                    self.save_user_data(user_id, user_data)
                    await query.edit_message_text(
                        "⚠️ Video error detected. Auto-skipping to next video...",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Next", callback_data="get_video"),
                            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                        ]]))
                except:
                    await query.edit_message_text(
                        "❌ Error loading video. Please try again.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔄 Try Again", callback_data="get_video"),
                            InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                        ]]))
            else:
                await query.edit_message_text(
                    "❌ Error loading video. Please try again.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔄 Try Again", callback_data="get_video"),
                        InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                    ]]))

    async def navigate_video(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE,
                             direction: str):
        """Handle video navigation (next/previous)"""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            return

        # Get videos for current category
        category = user_data.get('current_category', 1)
        if category == 0:  # Mix mode
            videos = self.get_mixed_videos()
        else:
            videos = self.get_videos_by_category(category)

        if not videos:
            return

        # Update video index
        current_index = user_data.get('current_video_index', 0)
        if direction == "next":
            current_index = (current_index + 1) % len(videos)
            # Update watched videos count
            user_data['watched_videos'] = user_data.get('watched_videos',
                                                        0) + 1
        else:  # previous
            current_index = (current_index - 1) % len(videos)

        user_data['current_video_index'] = current_index
        self.save_user_data(user_id, user_data)

        current_video = videos[current_index]

        # Check premium status
        is_premium = user_data.get('is_premium', False)
        premium_expires = user_data.get('premium_expires')

        if is_premium and premium_expires:
            if isinstance(premium_expires, str):
                expires_date = datetime.fromisoformat(premium_expires)
            else:
                expires_date = premium_expires
            if expires_date < datetime.now():
                is_premium = False

        # Get video stats for caption
        video_id = str(current_video.get('_id', ''))[-5:]  # Last 5 digits as Video ID
        like_percentage = self.get_video_like_percentage(str(current_video.get('_id', '')))
        
        caption = f"Video ID: {video_id}\n{like_percentage}% users liked this"

        try:
            if query.message and hasattr(query.message, 'chat_id'):
                # Validate video file_id before sending
                file_id = current_video.get('file_id', '')
                if not file_id or len(file_id) < 20:
                    logger.warning(f"Invalid file_id for video: {current_video.get('_id')}")
                    # Skip to next valid video
                    for _ in range(len(videos)):
                        current_index = (current_index + 1) % len(videos)
                        next_video = videos[current_index]
                        next_file_id = next_video.get('file_id', '')
                        if next_file_id and len(next_file_id) >= 20:
                            current_video = next_video
                            user_data['current_video_index'] = current_index
                            self.save_user_data(user_id, user_data)
                            file_id = next_file_id
                            # Update caption for new video
                            video_id = str(current_video.get('_id', ''))[-5:]
                            like_percentage = self.get_video_like_percentage(str(current_video.get('_id', '')))
                            caption = f"Video ID: {video_id}\n{like_percentage}% users liked this"
                            break
                    else:
                        # No valid videos found
                        await query.edit_message_text(
                            "❌ No valid videos available in this category.",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                            ]]))
                        return

                # Edit the existing video message instead of creating new one
                await context.bot.edit_message_media(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    media=InputMediaVideo(
                        media=file_id,
                        caption=caption
                    ),
                    reply_markup=self.create_video_keyboard(user_id, is_premium)
                )
        except Exception as e:
            logger.error(f"Error sending video: {e}")

    async def change_category_callback(self, update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
        """Handle change category button"""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        # Send new message instead of editing video message
        if query.message:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="📂 Choose a category:",
                reply_markup=self.create_category_keyboard())
            # Delete the video message
            try:
                await query.delete_message()
            except Exception:
                pass

    async def category_selection_callback(self, update: Update,
                                          context: ContextTypes.DEFAULT_TYPE):
        """Handle category selection"""
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            return

        # Extract category from callback data
        callback_data = query.data
        if callback_data == "cat_mix":
            category = 0  # Mix mode
        else:
            try:
                category = int(callback_data.split('_')[1])
            except (IndexError, ValueError):
                category = 1

        # Update user category
        user_data['current_category'] = category
        user_data['current_video_index'] = 0  # Reset to first video
        self.save_user_data(user_id, user_data)

        # Delete the category selection message first
        try:
            await query.delete_message()
        except Exception:
            pass

        # Get videos for selected category
        if category == 0:  # Mix mode
            videos = self.get_mixed_videos()
        else:
            videos = self.get_videos_by_category(category)

        if not videos:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📭 No videos available in category {category}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]))
            return

        # Send first video
        current_video = videos[0]

        # Check premium status
        is_premium = user_data.get('is_premium', False)
        premium_expires = user_data.get('premium_expires')

        if is_premium and premium_expires:
            if isinstance(premium_expires, str):
                expires_date = datetime.fromisoformat(premium_expires)
            else:
                expires_date = premium_expires
            if expires_date < datetime.now():
                is_premium = False

        # Get video stats for caption
        video_id = str(current_video.get('_id', ''))[-5:]  # Last 5 digits as Video ID
        like_percentage = self.get_video_like_percentage(str(current_video.get('_id', '')))
        
        caption = f"Video ID: {video_id}\n{like_percentage}% users liked this"

        try:
            # Check forwarding protection setting
            protect_content = self.get_bot_setting('forward_protection_enabled', False)
            
            video_message = await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=current_video['file_id'],
                caption=caption,
                reply_markup=self.create_video_keyboard(user_id, is_premium),
                protect_content=protect_content)

            # Schedule auto-deletion if enabled
            if self.auto_delete_enabled:

                async def delete_category_video_message():
                    await asyncio.sleep(self.auto_delete_minutes * 60)
                    try:
                        await context.bot.delete_message(
                            chat_id=video_message.chat_id,
                            message_id=video_message.message_id)
                    except Exception as e:
                        logger.error(
                            f"Error deleting category video message: {e}")

                asyncio.create_task(delete_category_video_message())

        except Exception as e:
            logger.error(f"Error sending video: {e}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="❌ Error loading video. Please try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="main_menu")
                ]]))

    async def bookmark_video_callback(self, update: Update,
                                      context: ContextTypes.DEFAULT_TYPE):
        """Handle bookmark video button"""
        query = update.callback_query
        if not query:
            return

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            await query.answer("❌ User data not found.")
            return

        # Get current video
        category = user_data.get('current_category', 1)
        if category == 0:  # Mix mode
            videos = self.get_mixed_videos()
        else:
            videos = self.get_videos_by_category(category)

        if not videos:
            await query.answer("❌ No videos available.")
            return

        video_index = user_data.get('current_video_index', 0)
        if video_index >= len(videos):
            await query.answer("❌ Invalid video index.")
            return

        current_video = videos[video_index]

        # Check if user already has 5 bookmarks
        bookmark_count = 0
        if self.db is not None:
            bookmark_count = self.db.bookmarks.count_documents(
                {"user_id": user_id})

        if bookmark_count >= 5:
            await query.answer("❌ You can only bookmark 5 videos at a time.")
            return

        # Check if video is already bookmarked
        existing = None
        if self.db is not None:
            existing = self.db.bookmarks.find_one({
                "user_id":
                user_id,
                "video_id":
                str(current_video['_id'])
            })

        if existing:
            await query.answer("📖 Video already bookmarked.")
            return

        # Add bookmark
        try:
            if self.db is not None:
                self.db.bookmarks.insert_one({
                    "user_id":
                    user_id,
                    "video_id":
                    str(current_video['_id']),
                    "file_id":
                    current_video['file_id'],
                    "file_name":
                    current_video.get('file_name', 'Unknown'),
                    "category":
                    current_video.get('category'),
                    "created_at":
                    datetime.now()
                })
                await query.answer("✅ Video bookmarked successfully!")
            else:
                await query.answer("❌ Database not available.")
        except Exception as e:
            logger.error(f"Error bookmarking video: {e}")
            await query.answer("❌ Error bookmarking video.")

    async def main_menu_callback(self, update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
        """Handle main menu button"""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        # Send new message instead of editing video message
        if query.message:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="🎬 Choose an option:",
                reply_markup=self.create_main_keyboard())
            # Delete the video message
            try:
                await query.delete_message()
            except Exception:
                pass

    async def like_video_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle like video button"""
        query = update.callback_query
        if not query:
            return

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            await query.answer("❌ User data not found.")
            return

        # Get current video
        category = user_data.get('current_category', 1)
        if category == 0:  # Mix mode
            videos = self.get_mixed_videos()
        else:
            videos = self.get_videos_by_category(category)

        if not videos:
            await query.answer("❌ No videos available.")
            return

        video_index = user_data.get('current_video_index', 0)
        if video_index >= len(videos):
            await query.answer("❌ Invalid video index.")
            return

        current_video = videos[video_index]
        video_id = str(current_video.get('_id', ''))

        # Save like to database with consistent video_id format
        if self.db is not None:
            self.db.video_likes.update_one(
                {"user_id": user_id, "video_id": video_id},
                {"$set": {"user_id": user_id, "video_id": video_id, "liked": True, "updated_at": datetime.now()}},
                upsert=True
            )
            
            # Refresh the caption with updated like percentage
            updated_percentage = self.get_video_like_percentage(video_id)
            video_id_display = video_id[-5:]  # Last 5 digits for display
            updated_caption = f"Video ID: {video_id_display}\n{updated_percentage}% users liked this"
            
            # Check premium status for keyboard
            user_data = self.get_user_data(user_id)
            is_premium = user_data.get('is_premium', False)
            premium_expires = user_data.get('premium_expires')
            if is_premium and premium_expires:
                if isinstance(premium_expires, str):
                    expires_date = datetime.fromisoformat(premium_expires)
                else:
                    expires_date = premium_expires
                if expires_date < datetime.now():
                    is_premium = False
            
            # Update the message with new percentage
            try:
                await context.bot.edit_message_caption(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    caption=updated_caption,
                    reply_markup=self.create_video_keyboard(user_id, is_premium)
                )
            except Exception as e:
                logger.error(f"Error updating caption after like: {e}")

        await query.answer("👍 Liked!")

    async def dislike_video_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle dislike video button"""
        query = update.callback_query
        if not query:
            return

        user_id = query.from_user.id
        user_data = self.get_user_data(user_id)

        if not user_data:
            await query.answer("❌ User data not found.")
            return

        # Get current video
        category = user_data.get('current_category', 1)
        if category == 0:  # Mix mode
            videos = self.get_mixed_videos()
        else:
            videos = self.get_videos_by_category(category)

        if not videos:
            await query.answer("❌ No videos available.")
            return

        video_index = user_data.get('current_video_index', 0)
        if video_index >= len(videos):
            await query.answer("❌ Invalid video index.")
            return

        current_video = videos[video_index]
        video_id = str(current_video.get('_id', ''))

        # Save dislike to database with consistent video_id format
        if self.db is not None:
            self.db.video_likes.update_one(
                {"user_id": user_id, "video_id": video_id},
                {"$set": {"user_id": user_id, "video_id": video_id, "liked": False, "updated_at": datetime.now()}},
                upsert=True
            )
            
            # Refresh the caption with updated like percentage
            updated_percentage = self.get_video_like_percentage(video_id)
            video_id_display = video_id[-5:]  # Last 5 digits for display
            updated_caption = f"Video ID: {video_id_display}\n{updated_percentage}% users liked this"
            
            # Check premium status for keyboard
            user_data = self.get_user_data(user_id)
            is_premium = user_data.get('is_premium', False)
            premium_expires = user_data.get('premium_expires')
            if is_premium and premium_expires:
                if isinstance(premium_expires, str):
                    expires_date = datetime.fromisoformat(premium_expires)
                else:
                    expires_date = premium_expires
                if expires_date < datetime.now():
                    is_premium = False
            
            # Update the message with new percentage
            try:
                await context.bot.edit_message_caption(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    caption=updated_caption,
                    reply_markup=self.create_video_keyboard(user_id, is_premium)
                )
            except Exception as e:
                logger.error(f"Error updating caption after dislike: {e}")

        await query.answer("👎 Disliked!")

    async def premium_required_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle premium required button for download"""
        query = update.callback_query
        if not query:
            return

        await query.answer("🔒 Premium subscription required for downloads!", show_alert=True)

    async def dark_content_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle dark content button"""
        query = update.callback_query
        if not query:
            return

        await query.answer("💥 Dark content feature coming soon!", show_alert=True)

    async def mybookmarks_command(self, update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
        """Handle /mybookmarks command"""
        if not update.effective_user:
            return

        user_id = update.effective_user.id

        bookmarks = []
        if self.db is not None:
            bookmarks = list(
                self.db.bookmarks.find({
                    "user_id": user_id
                }).sort("created_at", -1))

        if not bookmarks:
            if update.message:
                await update.message.reply_text("📭 You have no bookmarks.")
            return

        # Send bookmarked videos
        for bookmark in bookmarks:
            file_name = bookmark.get('file_name', 'Unknown').replace(
                '_', ' ').replace('*', '').replace('[', '').replace(']', '')
            caption = f"🔖 {file_name}\n" \
                     f"📂 Category: {bookmark.get('category', 'Unknown')}\n" \
                     f"📅 Bookmarked: {bookmark.get('created_at', datetime.now()).strftime('%Y-%m-%d %H:%M')}"
            try:
                if update.effective_chat:
                    # Check forwarding protection setting
                    protect_content = self.get_bot_setting('forward_protection_enabled', False)
                    
                    video_message = await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=bookmark['file_id'],
                        caption=caption,
                        protect_content=protect_content)

                    # Schedule auto-deletion if enabled
                    if self.auto_delete_enabled:

                        async def delete_bookmark_video():
                            await asyncio.sleep(self.auto_delete_minutes * 60)
                            try:
                                await context.bot.delete_message(
                                    chat_id=video_message.chat_id,
                                    message_id=video_message.message_id)
                            except Exception as e:
                                logger.error(
                                    f"Error deleting bookmark video: {e}")

                        asyncio.create_task(delete_bookmark_video())
            except Exception as e:
                logger.error(f"Error sending bookmarked video: {e}")

        # Schedule deletion notification if auto-delete is enabled
        if self.auto_delete_enabled:

            async def delete_bookmarks_notification():
                await asyncio.sleep(self.auto_delete_minutes * 60)
                try:
                    if update.effective_chat:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=
                            "🗑️ Bookmark messages have been automatically deleted."
                        )
                except Exception as e:
                    logger.error(
                        f"Error in bookmark deletion notification: {e}")

            asyncio.create_task(delete_bookmarks_notification())

    # Admin Commands
    async def set_premium_command(self, update: Update,
                                  context: ContextTypes.DEFAULT_TYPE):
        """Handle /setpremium command (Admin only)"""
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            if update.message:
                await update.message.reply_text(
                    "❌ You don't have permission to use this command.")
            return

        args = context.args or []
        if len(args) < 2:
            if update.message:
                await update.message.reply_text(
                    "Usage: /setpremium <user_id> <days>\n"
                    "Example: /setpremium 123456789 30")
            return

        try:
            target_user_id = int(args[0])
            days = int(args[1])

            # Set premium expiry
            expires_date = datetime.now() + timedelta(days=days)

            user_data = self.get_user_data(target_user_id)
            if not user_data:
                if update.message:
                    await update.message.reply_text("❌ User not found.")
                return

            user_data['is_premium'] = True
            user_data['premium_expires'] = expires_date
            self.save_user_data(target_user_id, user_data)

            if update.message:
                await update.message.reply_text(
                    f"✅ Premium set for user {target_user_id} for {days} days.\n"
                    f"Expires: {expires_date.strftime('%Y-%m-%d %H:%M:%S')}")

        except (ValueError, IndexError):
            if update.message:
                await update.message.reply_text(
                    "❌ Invalid arguments. Use: /setpremium <user_id> <days>")

    async def remove_premium_command(self, update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
        """Handle /removepremium command (Admin only)"""
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            if update.message:
                await update.message.reply_text(
                    "❌ You don't have permission to use this command.")
            return

        args = context.args or []
        if len(args) < 1:
            if update.message:
                await update.message.reply_text(
                    "Usage: /removepremium <user_id>")
            return

        try:
            target_user_id = int(args[0])

            user_data = self.get_user_data(target_user_id)
            if not user_data:
                if update.message:
                    await update.message.reply_text("❌ User not found.")
                return

            user_data['is_premium'] = False
            user_data['premium_expires'] = None
            self.save_user_data(target_user_id, user_data)

            if update.message:
                await update.message.reply_text(
                    f"✅ Premium removed from user {target_user_id}")

        except (ValueError, IndexError):
            if update.message:
                await update.message.reply_text("❌ Invalid user ID.")

    async def stats_command(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (Admin only)"""
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            if update.message:
                await update.message.reply_text(
                    "❌ You don't have permission to use this command.")
            return

        try:
            if self.db is None:
                if update.message:
                    await update.message.reply_text("❌ Database not available."
                                                    )
                return

            # Get total users
            total_users = self.db.users.count_documents({})

            # Get premium users
            premium_users = self.db.users.count_documents({"is_premium": True})

            # Get total videos by category
            video_stats = {}
            for cat in range(1, 5):
                video_stats[cat] = self.db.videos.count_documents(
                    {"category": cat})

            stats_text = f"📊 **Bot Statistics**\n\n" \
                        f"👥 Total Users: {total_users}\n" \
                        f"💎 Premium Users: {premium_users}\n\n" \
                        f"🎬 **Videos by Category:**\n"

            for cat, count in video_stats.items():
                stats_text += f"📂 Category {cat}: {count} videos\n"

            if update.message:
                await update.message.reply_text(stats_text,
                                                parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            if update.message:
                await update.message.reply_text("❌ Error getting statistics.")

    async def broadcast_command(self, update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command (Admin only)"""
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            if update.message:
                await update.message.reply_text(
                    "❌ You don't have permission to use this command.")
            return

        # Get message to broadcast
        if not context.args:
            if update.message:
                await update.message.reply_text(
                    "Usage: /broadcast <message>\n"
                    "Example: /broadcast Hello everyone! New videos are available."
                )
            return

        message_to_broadcast = ' '.join(context.args)

        # Get all users
        try:
            if self.db is None:
                if update.message:
                    await update.message.reply_text("❌ Database not available."
                                                    )
                return

            users = list(self.db.users.find({}, {"user_id": 1}))
            total_users = len(users)
            successful_sends = 0
            failed_sends = 0

            if update.message:
                await update.message.reply_text(
                    f"📢 Starting broadcast to {total_users} users...")

            # Send broadcast message to all users
            for user in users:
                try:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=
                        f"📢 **Broadcast Message**\n\n{message_to_broadcast}",
                        parse_mode=ParseMode.MARKDOWN)
                    successful_sends += 1

                    # Add small delay to avoid rate limiting
                    await asyncio.sleep(0.1)

                except Exception as e:
                    failed_sends += 1
                    logger.error(
                        f"Failed to send broadcast to {user['user_id']}: {e}")

            # Send completion report
            if update.message:
                await update.message.reply_text(
                    f"✅ Broadcast completed!\n\n"
                    f"📊 **Results:**\n"
                    f"✅ Successful: {successful_sends}\n"
                    f"❌ Failed: {failed_sends}\n"
                    f"📈 Total: {total_users}")

        except Exception as e:
            logger.error(f"Error during broadcast: {e}")
            if update.message:
                await update.message.reply_text("❌ Error during broadcast.")

    async def toggle_forward_protection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /toggleforward command (Admin only)"""
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            if update.message:
                await update.message.reply_text("❌ You don't have permission to use this command.")
            return

        # Get current setting
        current_setting = self.get_bot_setting('forward_protection_enabled', False)
        new_setting = not current_setting
        
        # Update setting
        if self.db is not None:
            self.db.bot_settings.update_one(
                {"setting_name": "forward_protection_enabled"},
                {"$set": {"setting_value": new_setting, "updated_at": datetime.now()}},
                upsert=True
            )

        status = "🔒 ENABLED" if new_setting else "🔓 DISABLED"
        if update.message:
            await update.message.reply_text(
                f"✅ Forwarding Protection: {status}\n\n"
                f"{'Videos can no longer be forwarded by users.' if new_setting else 'Videos can now be forwarded by users.'}"
            )

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command (Admin only)"""
        if not update.effective_user or update.effective_user.id not in self.admin_ids:
            if update.message:
                await update.message.reply_text("❌ You don't have permission to use this command.")
            return

        # Get all bot settings
        forward_protection = self.get_bot_setting('forward_protection_enabled', False)
        auto_delete = self.get_bot_setting('auto_delete_enabled', True)
        auto_delete_mins = self.get_bot_setting('auto_delete_minutes', 10)
        
        settings_text = f"⚙️ **Bot Settings**\n\n" \
                       f"🔒 Forward Protection: {'✅ Enabled' if forward_protection else '❌ Disabled'}\n" \
                       f"🗑️ Auto Delete: {'✅ Enabled' if auto_delete else '❌ Disabled'}\n" \
                       f"⏰ Auto Delete Time: {auto_delete_mins} minutes\n\n" \
                       f"**Admin Commands:**\n" \
                       f"• `/toggleforward` - Toggle forwarding protection\n" \
                       f"• `/setpremium <user_id> <days>` - Set premium\n" \
                       f"• `/removepremium <user_id>` - Remove premium\n" \
                       f"• `/stats` - View statistics\n" \
                       f"• `/broadcast <message>` - Send broadcast"

        if update.message:
            await update.message.reply_text(settings_text, parse_mode='Markdown')

    async def handle_channel_video(self, update: Update,
                                   context: ContextTypes.DEFAULT_TYPE):
        """Handle new videos from monitored channels"""
        if not update.channel_post or not update.channel_post.video:
            return

        channel_id = str(update.channel_post.chat.id)
        video = update.channel_post.video

        # Determine category based on channel
        category = None
        for cat, ch_id in self.channel_ids.items():
            if ch_id and ch_id == channel_id:
                category = cat
                break

        if category is None:
            return  # Not from a monitored channel

        # Add video to database
        file_id = video.file_id
        file_name = video.file_name or f"Video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        file_size = video.file_size or 0

        added = self.add_video_to_db(file_id, file_name, category, file_size)

        if added and self.log_channel_id:
            try:
                await context.bot.send_message(
                    chat_id=self.log_channel_id,
                    text=f"📹 New video indexed:\n"
                    f"📂 Category: {category}\n"
                    f"📝 Name: {file_name}\n"
                    f"💾 Size: {file_size / 1024 / 1024:.1f} MB\n"
                    f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                logger.error(f"Error logging new video: {e}")

    async def error_handler(self, update: object,
                            context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling update: {context.error}")

    def run(self):
        """Run the bot"""
        if not self.bot_token:
            logger.error("BOT_TOKEN not found in environment variables")
            return

        # Initialize database
        if not self.init_database():
            logger.error("Failed to initialize database")
            return

        # Create application
        application = Application.builder().token(self.bot_token).build()

        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(
            CommandHandler("mybookmarks", self.mybookmarks_command))
        application.add_handler(
            CommandHandler("setpremium", self.set_premium_command))
        application.add_handler(
            CommandHandler("removepremium", self.remove_premium_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(
            CommandHandler("broadcast", self.broadcast_command))
        application.add_handler(
            CommandHandler("toggleforward", self.toggle_forward_protection))
        application.add_handler(CommandHandler("settings", self.settings_command))

        # Callback handlers
        application.add_handler(
            CallbackQueryHandler(self.status_callback, pattern="^status$"))
        application.add_handler(
            CallbackQueryHandler(self.get_video_callback,
                                 pattern="^get_video$"))
        application.add_handler(
            CallbackQueryHandler(
                lambda u, c: self.navigate_video(u, c, "next"),
                pattern="^next_video$"))
        application.add_handler(
            CallbackQueryHandler(
                lambda u, c: self.navigate_video(u, c, "prev"),
                pattern="^prev_video$"))
        application.add_handler(
            CallbackQueryHandler(self.change_category_callback,
                                 pattern="^change_category$"))
        application.add_handler(
            CallbackQueryHandler(self.category_selection_callback,
                                 pattern="^cat_"))
        application.add_handler(
            CallbackQueryHandler(self.bookmark_video_callback,
                                 pattern="^bookmark_video$"))
        application.add_handler(
            CallbackQueryHandler(self.main_menu_callback,
                                 pattern="^main_menu$"))
        
        # New handlers for like/dislike and other features
        application.add_handler(
            CallbackQueryHandler(self.like_video_callback,
                                 pattern="^like_video$"))
        application.add_handler(
            CallbackQueryHandler(self.dislike_video_callback,
                                 pattern="^dislike_video$"))
        application.add_handler(
            CallbackQueryHandler(self.premium_required_callback,
                                 pattern="^premium_required$"))
        application.add_handler(
            CallbackQueryHandler(self.dark_content_callback,
                                 pattern="^dark_content$"))

        # Channel video handler
        application.add_handler(
            MessageHandler(filters.VIDEO & filters.ChatType.CHANNEL,
                           self.handle_channel_video))

        # Error handler
        application.add_error_handler(self.error_handler)

        # Run the bot with restart logging
        try:
            application.run_polling(drop_pending_updates=True)
        finally:
            # Log restart in log channel if available
            if self.log_channel_id:
                try:
                    asyncio.run(
                        application.bot.send_message(
                            chat_id=self.log_channel_id,
                            text=
                            f"🤖 Bot restarted successfully!\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        ))
                except Exception as e:
                    logger.error(f"Error sending restart log: {e}")


if __name__ == "__main__":
    bot = VideoBot()
    bot.run()
