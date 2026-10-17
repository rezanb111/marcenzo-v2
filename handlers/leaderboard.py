"""Leaderboard — Top 10 in 4 categories."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, desc

from database.session import async_session
from database.models import User
from services.loan_service import level_title
from keyboards.inline import back_main_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb

router = Router(name="leaderboard")


@router.callback_query(F.data == "menu:leaderboard")
async def menu_leaderboard(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        me = result.scalar_one()
        lang = me.language or "en"

        r1 = await session.execute(select(User).order_by(desc(User.successful_loans)).limit(10))
        top_success = r1.scalars().all()
        r2 = await session.execute(select(User).order_by(desc(User.total_repaid)).limit(10))
        top_repaid = r2.scalars().all()
        r3 = await session.execute(select(User).order_by(desc(User.level), desc(User.successful_loans)).limit(10))
        top_level = r3.scalars().all()
        r4 = await session.execute(select(User).order_by(desc(User.earned_interest)).limit(10))
        top_earned = r4.scalars().all()

        def fmt(users, key, label):
            lines = [f"<b>{label}</b>"]
            for i, u in enumerate(users, 1):
                uname = f"@{u.username}" if u.username else str(u.telegram_id)
                val = getattr(u, key)
                if key == "level":
                    val = f"{u.level} ({level_title(u.level)})"
                lines.append(f"{i}. {uname} — {val}")
            return "\n".join(lines)

        text = (
            t("leaderboard_title", lang) + "\n\n"
            + fmt(top_success, "successful_loans", "🏅 Successful Loans") + "\n\n"
            + fmt(top_repaid, "total_repaid", "💸 Total Repaid (USDT)") + "\n\n"
            + fmt(top_level, "level", "⭐ Level") + "\n\n"
            + fmt(top_earned, "earned_interest", "📈 Investor Earned (USDT)")
        )
        await safe_edit(cb, text, reply_markup=back_main_kb())
