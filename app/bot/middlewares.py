from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.db import repository as repo


class OwnerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is None:
            return

        owner_id = await repo.get_setting("owner_id")
        if owner_id is None:
            # No owner yet — first user becomes owner (via /start)
            return await handler(event, data)

        if str(user_id) != owner_id:
            return  # Silently ignore non-owner

        return await handler(event, data)
