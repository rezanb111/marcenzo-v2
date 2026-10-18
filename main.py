"""
MARCENZO Loan Bot — Production entry point.
Includes background tasks: 3h admin report, installment reminders, treasury alerts.
Security middlewares: throttle + block guard.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from loguru import logger

from config import settings
from database.session import init_db
from services.tasks import start_background_tasks
from middlewares.guards import ThrottleMiddleware, BlockGuardMiddleware

from handlers import start, loan, repay, invest, profile, guide, support, leaderboard, admin, referral


def setup_logging():
    Path("logs").mkdir(exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="14 days",
        level="DEBUG",
        encoding="utf-8",
    )


async def main():
    setup_logging()
    logger.info("Starting MARCENZO Loan Bot…")

    if not settings.BOT_TOKEN or ":" not in settings.BOT_TOKEN:
        logger.error("BOT_TOKEN missing or invalid")
        sys.exit(1)
    if not settings.POLYGON_PRIVATE_KEY or not settings.TREASURY_ADDRESS:
        logger.error("POLYGON_PRIVATE_KEY / TREASURY_ADDRESS required")
        sys.exit(1)

    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(ThrottleMiddleware())
    dp.callback_query.middleware(ThrottleMiddleware())
    dp.message.middleware(BlockGuardMiddleware())
    dp.callback_query.middleware(BlockGuardMiddleware())

    @dp.errors()
    async def on_error(event: ErrorEvent):
        logger.exception(f"Update error: {event.exception}")
        try:
            upd = event.update
            if upd.callback_query:
                await upd.callback_query.answer("Something went wrong. Try again.", show_alert=False)
            elif upd.message:
                await upd.message.answer("⚠️ Temporary error. Please try again in a moment.")
        except Exception:
            pass
        return True

    dp.include_router(start.router)
    dp.include_router(loan.router)
    dp.include_router(repay.router)
    dp.include_router(invest.router)
    dp.include_router(profile.router)
    dp.include_router(guide.router)
    dp.include_router(support.router)
    dp.include_router(leaderboard.router)
    dp.include_router(admin.router)
    dp.include_router(referral.router)

    bg_tasks = start_background_tasks(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logger.info(f"Bot @{me.username} is online | id={me.id} | background tasks: {len(bg_tasks)}")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for t in bg_tasks:
            t.cancel()
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested")
