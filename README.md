# TeleBotIndex - Deploy-ready (Webhook)

This repo has been patched to run in webhook mode on Render (or any PaaS).

Important env vars to set in Render:
- BOT_TOKEN
- LOG_CHANNEL_ID (optional)
- RENDER_EXTERNAL_URL (Render provides this automatically)

Before deploying on Render, clear build cache and redeploy so new requirements are installed.

