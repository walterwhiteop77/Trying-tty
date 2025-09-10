# TeleBotIndex - Webhook Deploy

## Render Deployment

1. Create a new Web Service on [Render](https://render.com/).
2. Upload this repo or connect to your GitHub repo.
3. Add Environment Variables:
   - `BOT_TOKEN`: Your Telegram bot token
   - `RENDER_EXTERNAL_URL`: The URL Render assigns (e.g. https://your-app.onrender.com)
   - `PORT`: 10000 (Render default)
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py` (already in Procfile)
6. Deploy 🚀

