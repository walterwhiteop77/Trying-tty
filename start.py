#!/usr/bin/env python3
"""
Startup script for the Telegram Video Bot
"""
import os
import sys
from main import VideoBot

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'BOT_TOKEN',
        'CATEGORY_1_CHANNEL',
        'CATEGORY_2_CHANNEL', 
        'CATEGORY_3_CHANNEL',
        'CATEGORY_4_CHANNEL',
        'LOG_CHANNEL_ID',
        'ADMIN_IDS'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or environment.")
        print("See .env.example for the format.")
        sys.exit(1)

def main():
    """Main startup function"""
    print("🤖 Starting Telegram Video Bot...")
    
    # Check environment
    check_environment()
    
    print("✅ Environment variables verified")
    print("🚀 Initializing bot...")
    
    # Create and run bot
    bot = VideoBot()
    bot.run()

if __name__ == "__main__":
    main()