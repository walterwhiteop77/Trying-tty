# Overview

This is a comprehensive Telegram Video Bot built with Python that provides video management capabilities across multiple categories. The bot features user bookmarks (max 5, auto-delete after 10 minutes), premium user management with admin controls, broadcast functionality, and automatic video indexing from monitored channels. It uses MongoDB for data persistence and integrates with 4 category channels plus 1 logging channel. The system includes user status tracking, category-based video navigation (including a mix mode), and comprehensive admin commands for user management and statistics.

## Key Features Implemented

### User Features
- **Main Interface**: Get Video and Status buttons
- **Video Navigation**: Next/Previous with category support (1-4 plus Mix mode)
- **Bookmarking**: Up to 5 videos per user with auto-deletion after 10 minutes
- **Premium Features**: Download access for premium users only
- **Status Tracking**: Watch count, current category, premium status, and expiry dates

### Admin Features  
- **Premium Management**: `/setpremium <user_id> <days>` and `/removepremium <user_id>`
- **User Statistics**: `/stats` command showing total users, premium users, and video counts by category
- **Broadcast System**: `/broadcast <message>` to send messages to all users
- **Automatic Logging**: New member joins and bot restarts logged to dedicated channel

### Channel Integration
- **Auto-indexing**: Monitors 4 category channels for new video content
- **Real-time Updates**: Videos automatically added to database when posted to monitored channels
- **Logging Channel**: Dedicated channel for administrative notifications

### Database Features
- **MongoDB Integration**: Full user data, video metadata, and bookmark storage
- **Premium Tracking**: Expiry dates and status management
- **Video Categorization**: Organized storage by category with search capabilities

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Python Telegram Bot Library**: Uses `python-telegram-bot==22.3` as the core framework for Telegram API interactions
- **Async Architecture**: Built with asyncio support for handling concurrent operations and improved performance
- **Handler-based Design**: Implements CommandHandler, CallbackQueryHandler, and MessageHandler for different types of user interactions

## Data Storage
- **MongoDB Integration**: Uses PyMongo for database operations with configurable connection URI
- **Document-based Storage**: Leverages MongoDB's flexible schema for storing user data, video metadata, bookmarks, and administrative information
- **Database Configuration**: Supports custom database names and connection strings through environment variables

## Channel Management
- **Multi-channel Architecture**: Supports 4 different category channels for content distribution
- **Channel Mapping**: Maintains a dictionary mapping category IDs to channel identifiers
- **Logging Channel**: Dedicated channel for administrative logging and monitoring

## Authentication & Authorization
- **Admin-based System**: Uses environment variable-defined admin IDs for privileged operations
- **Role-based Access**: Distinguishes between regular users and administrators
- **Set-based Admin Storage**: Efficient admin ID checking using Python sets

## Configuration Management
- **Environment Variables**: All sensitive configuration managed through .env files
- **Validation System**: Startup script validates required environment variables before bot initialization
- **Modular Configuration**: Separate configuration for bot tokens, channels, database, and admin access

## Application Structure
- **Main Bot Class**: Centralized VideoBot class containing all bot logic and database connections
- **Startup Validation**: Dedicated start.py script for environment validation and bot initialization
- **Logging Integration**: Comprehensive logging setup with configurable levels and formatting

# External Dependencies

## Telegram Integration
- **Telegram Bot API**: Primary interface for bot functionality through python-telegram-bot library
- **Multiple Telegram Channels**: Integration with 4 category channels plus 1 logging channel
- **Inline Keyboards**: Support for interactive button-based user interfaces

## Database Services
- **MongoDB**: Primary data storage using PyMongo driver
- **Configurable Connection**: Supports both local and cloud MongoDB instances via connection URI

## Python Libraries
- **AsyncIO Libraries**: 
  - `aiofiles==24.1.0` for asynchronous file operations
  - `asyncio-throttle==1.0.2` for rate limiting and throttling
- **Configuration Management**: `python-dotenv==1.1.1` for environment variable management
- **Database Driver**: `pymongo==4.14.1` for MongoDB connectivity

## Environment Requirements
- **BOT_TOKEN**: Telegram bot authentication token
- **Channel IDs**: 4 category channels and 1 logging channel
- **Admin Configuration**: Comma-separated list of admin user IDs
- **Database URI**: MongoDB connection string (defaults to localhost)
- **Database Name**: Configurable database name (defaults to 'telegram_video_bot')