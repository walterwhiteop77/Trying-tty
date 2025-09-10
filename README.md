# Telegram Video Bot

A comprehensive Telegram bot for video management with categories, bookmarks, premium features, and broadcasting capabilities.

## Features

### For Users
- 🎬 **Video Browsing**: Navigate through videos by category or random mix
- 📊 **Status Tracking**: View watched videos, current category, and premium status  
- 🔖 **Bookmarking**: Save up to 5 videos (auto-delete after 10 minutes)
- 💎 **Premium Features**: Download access for premium users

### For Admins
- 👑 **Premium Management**: Set/remove premium access with expiry dates
- 📈 **Statistics**: View user counts and video statistics by category
- 📢 **Broadcasting**: Send messages to all users
- 🔍 **Channel Monitoring**: Automatic video indexing from 4 category channels

## Setup Instructions

### 1. Get Required API Keys
- **Bot Token**: Create a bot with @BotFather on Telegram
- **Channel IDs**: Get IDs for your 4 video channels and 1 log channel
- **Admin IDs**: Your Telegram user ID for admin commands
- **MongoDB**: Connection string for database storage

### 2. Configure Environment
Set these secrets in your deployment environment:
- `BOT_TOKEN` - Your Telegram bot token
- `CATEGORY_1_CHANNEL` - Channel ID for category 1 videos  
- `CATEGORY_2_CHANNEL` - Channel ID for category 2 videos
- `CATEGORY_3_CHANNEL` - Channel ID for category 3 videos
- `CATEGORY_4_CHANNEL` - Channel ID for category 4 videos
- `LOG_CHANNEL_ID` - Channel ID for logging
- `ADMIN_IDS` - Comma-separated admin user IDs
- `MONGODB_URI` - MongoDB connection string

### 3. Deploy
The bot is configured for deployment on platforms like Render, Koyeb, or any VPS:
- Uses VM deployment target for persistent operation
- Includes proper error handling and logging
- Automatic restart capabilities

## Commands

### User Commands
- `/start` - Initialize the bot and show main menu
- `/mybookmarks` - View your bookmarked videos

### Admin Commands  
- `/setpremium <user_id> <days>` - Grant premium access
- `/removepremium <user_id>` - Remove premium access
- `/stats` - View bot statistics
- `/broadcast <message>` - Send message to all users

## Database Structure

The bot uses MongoDB with these collections:
- **users**: User data, premium status, preferences
- **videos**: Video metadata organized by category
- **bookmarks**: User bookmark relationships

## Channel Setup

1. Create 4 channels for video categories
2. Add your bot as an admin to all channels
3. Create a logging channel for admin notifications
4. Get channel IDs using @userinfobot

## Technical Details

- **Framework**: python-telegram-bot 22.3
- **Database**: MongoDB with PyMongo
- **Deployment**: Configured for VM deployment
- **Architecture**: Async-based for handling concurrent users
- **Error Handling**: Comprehensive logging and error management