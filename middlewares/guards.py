"""
Production middlewares: rate-limit + blocked-user guard.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from loguru import logger

from database.session import async_session
from database.models import User
from services.security import rate_limit
from config import settings


class ThrottleMiddleware(BaseMiddleware):
    """Limit how fast a single user can hit the bot (anti-spam)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        is_adm = user.id in settings.admin_ids or (
            user.username and user.username.lower() in settings.admin_usernames
        )
        max_hits = 30 if is_adm else 10
        window = 8.0 if is_adm else 10.0
        key = f"tg:{user.id}"
        if not rate_limit(key, max_hits=max_hits, window_sec=window):
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⏳ Slow down a bit…", show_alert=False)
                except Exception:
                    pass
                return None
            if isinstance(event, Message):
                try:
                    await event.answer("⏳ Please wait a few seconds.")
                except Exception:
                    pass
                return None
        return await handler(event, data)


class BlockGuardMiddleware(BaseMiddleware):
    """Block known banned users early."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        if user.id in settings.admin_ids:
            return await handler(event, data)
        if user.username and user.username.lower() in settings.admin_usernames:
            return await handler(event, data)

        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        try:
            async with async_session() as session:
                result = await session.execute(
                    select(User.is_blocked, User.block_reason).where(User.telegram_id == user.id)
                )
                row = result.first()
                if row and row[0]:
                    reason = row[1] or "N/A"
                    if isinstance(event, CallbackQuery):
                        try:
                            await event.answer(f"Blocked: {reason}", show_alert=True)
                        except Exception:
                            pass
                        return None
                    if isinstance(event, Message):
                        try:
                            await event.answer(f"🚫 Account blocked.\nReason: {reason}")
                        except Exception:
                            pass
                        return None
        except Exception as e:
            logger.debug(f"BlockGuard skip: {e}")

        return await handler(event, data)
