"""
MARCENZO Loan Bot — Production entry point.
Includes background tasks: 3h admin report, installment reminders, treasury alerts.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from loguru import logger

from config import settings
from database.session import init_db
from services.tasks import start_background_tasks

# Handlers
from handlers import start, loan, repay, invest, profile, guide, support, leaderboard, admin
from handlers import referral  # NEW


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

    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
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

    # Background tasks
    bg_tasks = start_background_tasks(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info(f"Bot @{settings.BOT_USERNAME} is online | background tasks: {len(bg_tasks)}")
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
