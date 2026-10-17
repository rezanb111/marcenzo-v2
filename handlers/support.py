"""
Support tickets.
"""
from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from loguru import logger

from database.session import async_session
from database.models import User, SupportTicket
from keyboards.inline import support_kb, back_main_kb, cancel_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb
from config import settings

router = Router(name="support")


class SupportStates(StatesGroup):
    message = State()


@router.callback_query(F.data == "menu:support")
async def menu_support(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.clear()
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        user = result.scalar_one()
        lang = user.language or "en"
    await safe_edit(cb, t("support_title", lang), reply_markup=support_kb())


@router.callback_query(F.data == "support:new")
async def support_new(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == cb.from_user.id)
        )
        user = result.scalar_one()
        lang = user.language or "en"
    await state.set_state(SupportStates.message)
    await safe_edit(
        cb,
        t("support_new_prompt", lang),
        reply_markup=cancel_kb("menu:support"),
    )


@router.message(SupportStates.message)
async def support_message(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("❌ Message too short.")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one()
        lang = user.language or "en"
        ticket = SupportTicket(
            user_id=user.id,
            subject=f"Ticket from @{user.username or user.telegram_id}",
            message=text,
            status="OPEN",
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        await state.clear()
        await message.answer(
            t("support_sent", lang, id=ticket.id),
            reply_markup=back_main_kb(),
            parse_mode="HTML",
        )

        for aid in settings.admin_ids:
            try:
                await bot.send_message(
                    aid,
                    f"🎫 New Support Ticket #{ticket.id}\n"
                    f"From: @{user.username or user.telegram_id} ({user.telegram_id})\n\n"
                    f"{text}\n\n"
                    f"Reply via Admin Panel → Tickets",
                )
            except Exception as e:
                logger.warning(f"Notify admin ticket: {e}")
