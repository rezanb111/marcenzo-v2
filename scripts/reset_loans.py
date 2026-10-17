#!/usr/bin/env python3
"""Reset all loans & installments. Reset users level/limit/stats."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, update
from database.session import async_session, init_db, engine
from database.models import Loan, Installment, User, ProcessedTx
from config import settings
from loguru import logger


async def reset():
    await init_db()
    async with async_session() as session:
        await session.execute(delete(Installment))
        await session.execute(delete(Loan))
        await session.execute(
            delete(ProcessedTx).where(
                ProcessedTx.purpose.in_(["disburse", "sweep_installment"])
            )
        )
        await session.execute(
            update(User).values(
                level=1,
                credit_limit=settings.INITIAL_CREDIT_LIMIT,
                successful_loans=0,
                total_borrowed=0.0,
                total_repaid=0.0,
            )
        )
        await session.commit()
        logger.info("All loans wiped. Users reset.")
    await engine.dispose()


if __name__ == "__main__":
    confirm = input("Type YES to wipe all loans and reset user credit stats: ")
    if confirm.strip() == "YES":
        asyncio.run(reset())
        print("Done.")
    else:
        print("Aborted.")
