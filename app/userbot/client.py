from telethon import TelegramClient

from app.config import settings

userbot: TelegramClient | None = None


def get_userbot() -> TelegramClient:
    global userbot
    if userbot is None:
        userbot = TelegramClient(
            settings.session_path,
            settings.tg_api_id,
            settings.tg_api_hash,
        )
    return userbot
