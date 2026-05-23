from __future__ import annotations

import logging

from agent.alerts.telegram import escape_markdownv2, send_telegram_message_sync
from agent.settings import get_settings
from schemas.python.alerts import Alert

logger = logging.getLogger(__name__)

def dispatch_alert(alert: Alert) -> None:
    settings = get_settings()
    if settings.telegram.configured:
        token_secret = settings.telegram.bot_token
        token = token_secret.get_secret_value() if token_secret else None
        chat_id = settings.telegram.chat_id
        if token and chat_id:
            try:
                title = escape_markdownv2(alert.title)
                msg = escape_markdownv2(alert.message)
                text = f"*{title}*\n\n{msg}"
                send_telegram_message_sync(token, chat_id, text)
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")
                raise
    else:
        logger.info(f"Alert {alert.title} not sent because Telegram is not configured.")
