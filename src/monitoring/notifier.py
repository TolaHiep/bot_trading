import os
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def send_telegram_alert(message: str) -> bool:
    """
    Send a direct Telegram API message asynchronously using aiohttp.
    Uses .env configurations for BOT_TOKEN and CHAT_IDS.
    Designed for critical execution alerts without spanning python-telegram-bot limits.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids_str = os.getenv("TELEGRAM_CHAT_IDS", "")
    
    if not bot_token or not chat_ids_str:
        return False
        
    chat_ids = [cid.strip() for cid in chat_ids_str.split(",") if cid.strip()]
    if not chat_ids:
        return False
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    success = True
    
    try:
        async with aiohttp.ClientSession() as session:
            for chat_id in chat_ids:
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                async with session.post(url, json=payload, timeout=10) as resp:
                    if resp.status != 200:
                        logger.error(f"Telegram alert failed to {chat_id}. Status: {resp.status}")
                        success = False
    except Exception as e:
        logger.error(f"Error sending telegram alert: {e}")
        return False
        
    return success
