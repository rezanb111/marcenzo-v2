"""Guide / FAQ."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select

from database.session import async_session
from database.models import User
from keyboards.inline import back_main_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb

router = Router(name="guide")


@router.callback_query(F.data == "menu:guide")
async def menu_guide(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        user = result.scalar_one()
        lang = user.language or "en"
    await safe_edit(
        cb,
        t("guide_title", lang) + "\n\n" + t("guide_body", lang),
        reply_markup=back_main_kb(),
    )
