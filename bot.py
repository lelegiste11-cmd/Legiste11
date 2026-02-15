
"""
Telegram Bot implementation with advanced features and deployment capabilities
"""
import os
import logging
import requests
import json
from typing import Dict, Any
from handlers import TelegramHandlers
from card_predictor import card_predictor

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.deployment_file_path = "final2025.zip"
        # Initialize advanced handlers
        self.handlers = TelegramHandlers(token)

    def handle_update(self, update: Dict[str, Any]) -> None:
        """Handle incoming Telegram update with advanced features for webhook mode"""
        try:
            # Log avec type de message
            if 'message' in update:
                logger.info(f"🔄 Bot traite message normal via webhook")
            elif 'edited_message' in update:
                logger.info(f"🔄 Bot traite message édité via webhook")
            
            logger.info(f"Received update: {json.dumps(update, indent=2)}")

            # Use the advanced handlers for processing (they handle card predictions too)
            self.handlers.handle_update(update)
            
            # Log succès du traitement
            logger.info(f"✅ Update traité avec succès via webhook")

        except Exception as e:
            logger.error(f"❌ Error handling update via webhook: {e}")

    def _process_card_predictions(self, message: Dict[str, Any]) -> None:
        """Process message for card predictions"""
        try:
            chat_id = message['chat']['id']
            chat_type = message['chat'].get('type', 'private')

            # Only process card predictions in groups/channels
            if chat_type in ['group', 'supergroup', 'channel'] and 'text' in message:
                text = message['text']

                # Check if we should make a prediction
                should_predict, game_number, prediction_data = card_predictor.should_predict(text)

                if should_predict and game_number is not None and prediction_data is not None:
                    prediction = card_predictor.make_prediction(game_number, prediction_data)
                    logger.info(f"Making prediction: {prediction}")

                    # Send prediction to the chat
                    self.send_message(chat_id, prediction)

                # Check if this message verifies a previous prediction
                verification_result = card_predictor.verify_prediction(text)
                if verification_result:
                    logger.info(f"Verification result: {verification_result}")

                    if verification_result['type'] == 'update_message':
                        # For webhook mode, just send the updated status as a new message
                        self.send_message(chat_id, verification_result['new_message'])

        except Exception as e:
            logger.error(f"Error processing card predictions: {e}")

    def handle_start_command(self, chat_id: int) -> None:
        """Handle /start command by sending deployment zip file"""
        try:
            # Send initial message
            self.send_message(
                chat_id, 
                "🚀 Preparing your deployment zip file... Please wait a moment."
            )

            # Check if deployment file exists
            if not os.path.exists(self.deployment_file_path):
                self.send_message(
                    chat_id,
                    "❌ Deployment file not found. Please contact the administrator."
                )
                logger.error(f"Deployment file {self.deployment_file_path} not found")
                return

            # Send the file
            success = self.send_document(chat_id, self.deployment_file_path)

            if success:
                self.send_message(
                    chat_id,
                    "✅ Deployment zip file sent successfully!\n\n"
                    "📋 Instructions:\n"
                    "1. Download the zip file\n"
                    "2. Extract it to your project directory\n"
                    "3. Deploy to render.com\n"
                    "4. Configure your environment variables\n\n"
                    "Need help? Contact support!"
                )
            else:
                self.send_message(
                    chat_id,
                    "❌ Failed to send deployment file. Please try again later."
                )

        except Exception as e:
            logger.error(f"Error handling start command: {e}")
            self.send_message(
                chat_id,
                "❌ An error occurred while processing your request. Please try again."
            )

    def send_message(self, chat_id: int, text: str) -> bool:
        """Send text message to user"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                logger.info(f"Message sent successfully to chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_document(self, chat_id: int, file_path: str) -> bool:
        """Send document file to user"""
        try:
            url = f"{self.base_url}/sendDocument"

            with open(file_path, 'rb') as file:
                files = {
                    'document': (os.path.basename(file_path), file, 'application/zip')
                }
                data = {
                    'chat_id': chat_id,
                    'caption': '📦 Deployment Package for render.com'
                }

                response = requests.post(url, data=data, files=files, timeout=60)
                result = response.json()

                if result.get('ok'):
                    logger.info(f"Document sent successfully to chat {chat_id}")
                    return True
                else:
                    logger.error(f"Failed to send document: {result}")
                    return False

        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending document: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending document: {e}")
            return False

    def set_webhook(self, webhook_url: str) -> bool:
        """Set webhook URL for the bot"""
        try:
            url = f"{self.base_url}/setWebhook"
            data = {
                'url': webhook_url,
                'allowed_updates': ['message', 'edited_message']
            }

            response = requests.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                logger.info(f"Webhook set successfully: {webhook_url}")
                return True
            else:
                logger.error(f"Failed to set webhook: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error setting webhook: {e}")
            return False
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False

    def get_bot_info(self) -> Dict[str, Any]:
        """Get bot information"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=30)
            result = response.json()

            if result.get('ok'):
                return result.get('result', {})
            else:
                logger.error(f"Failed to get bot info: {result}")
                return {}

        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return {}
