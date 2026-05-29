"""
bot_utils.py — Bot Utility Functions (Enterprise)
─────────────────────────────────────────────────
Uses ConnectionManager for database access.
"""

import logging
import requests
import time
from dotenv import load_dotenv
from config import BOT_CONFIG

load_dotenv()

BOT_TOKEN = BOT_CONFIG['token']
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message_to_bot(user_id, message_text):
    """
    Send message to user via Telegram bot API.
    
    Args:
        user_id: Telegram user ID
        message_text: Message text to send
    
    Returns:
        bool: Success or failure
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            url = f"{TELEGRAM_API_URL}/sendMessage"
            data = {
                "chat_id": user_id,
                "text": message_text,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logging.info(f"Message sent to user {user_id}")
                    return True
                else:
                    error_desc = result.get('description', 'Unknown error')
                    logging.error(f"Telegram API error for user {user_id}: {error_desc}")
                    if 'chat not found' in str(error_desc).lower():
                        return False
                    retry_count += 1
                    time.sleep(1)
            else:
                logging.error(f"HTTP {response.status_code} sending to {user_id}")
                retry_count += 1
                time.sleep(1)

        except Exception as e:
            logging.error(f"Error sending message to {user_id}: {e}")
            retry_count += 1
            time.sleep(1)

    return False