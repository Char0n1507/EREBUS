import os
import requests
import logging

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")

    def send_telegram(self, message):
        """
        Sends a message via Telegram Bot API.
        """
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials not set.")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message[:4096] # Telegram limit
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Telegram alert sent.")
                return True
            else:
                logger.error(f"Telegram failed: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram connection failed: {e}")
            return False

    def send_discord(self, message):
        """
        Sends a message via Discord Webhook.
        """
        if not self.discord_webhook:
            logger.warning("Discord webhook not set.")
            return False
            
        payload = {
            "content": message[:2000] # Discord limit per message
        }
        
        try:
            resp = requests.post(self.discord_webhook, json=payload, timeout=10)
            if resp.status_code in [200, 204]:
                logger.info("Discord alert sent.")
                return True
            else:
                logger.error(f"Discord failed: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Discord connection failed: {e}")
            return False

    def send_alert(self, subject, body):
        """
        Broadcasts alert to all configured channels.
        """
        full_msg = f"🔔 **{subject}**\n\n{body}"
        
        # We can run these async if needed, but for now sequential is fine for low volume
        t_status = self.send_telegram(full_msg)
        d_status = self.send_discord(full_msg)
        
        return t_status or d_status
