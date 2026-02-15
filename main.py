"""
Main entry point for the Telegram bot deployment on render.com
"""
import os
import logging
from flask import Flask, request
from bot import TelegramBot
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize configuration and bot
try:
    config = Config()
    bot = TelegramBot(config.BOT_TOKEN)
    logger.info("✅ Bot initialisé avec succès")
except ValueError as e:
    logger.error(f"❌ ERREUR CRITIQUE: {e}")
    logger.error("💡 Configurez BOT_TOKEN dans les Secrets de Replit")
    raise
except Exception as e:
    logger.error(f"❌ Erreur inattendue lors de l'initialisation: {e}")
    raise

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        update = request.get_json()

        # Log type de message reçu avec détails
        if 'message' in update:
            msg = update['message']
            chat_id = msg.get('chat', {}).get('id', 'unknown')
            user_id = msg.get('from', {}).get('id', 'unknown')
            text = msg.get('text', '')[:50]
            logger.info(f"📨 WEBHOOK - Message normal | Chat:{chat_id} | User:{user_id} | Text:{text}...")
        elif 'edited_message' in update:
            msg = update['edited_message']
            chat_id = msg.get('chat', {}).get('id', 'unknown')
            user_id = msg.get('from', {}).get('id', 'unknown')
            text = msg.get('text', '')[:50]
            logger.info(f"✏️ WEBHOOK - Message édité | Chat:{chat_id} | User:{user_id} | Text:{text}...")

        logger.info(f"Webhook received update: {update}")

        if update:
            # Traitement direct pour meilleure réactivité
            bot.handle_update(update)
            logger.info("Update processed successfully")

        return 'OK', 200
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return 'Error', 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for render.com"""
    return {'status': 'healthy', 'service': 'telegram-bot'}, 200

@app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return {'message': 'Telegram Bot is running', 'status': 'active'}, 200

def setup_webhook():
    """Set up webhook on startup"""
    try:
        # Utiliser l'URL configurée dans Config
        webhook_url = config.WEBHOOK_URL
        if webhook_url and webhook_url != "https://.repl.co":
            full_webhook_url = f"{webhook_url}/webhook"
            logger.info(f"🔗 Configuration webhook: {full_webhook_url}")

            # Configure webhook for Render.com with your specific URL
            success = bot.set_webhook(full_webhook_url)
            if success:
                logger.info(f"✅ Webhook configuré avec succès: {full_webhook_url}")
                logger.info(f"🎯 Bot prêt pour prédictions automatiques et vérifications via webhook")
            else:
                logger.error("❌ Échec configuration webhook")
        else:
            logger.warning("⚠️ WEBHOOK_URL non configurée, mode polling recommandé pour le développement")
            logger.info("💡 Pour activer le webhook, configurez la variable WEBHOOK_URL")
    except Exception as e:
        logger.error(f"❌ Erreur configuration webhook: {e}")

if __name__ == '__main__':
    # Set up webhook on startup
    setup_webhook()

    # Get port from environment (render.com provides this)
    port = int(os.getenv('PORT') or 5000)

    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)
