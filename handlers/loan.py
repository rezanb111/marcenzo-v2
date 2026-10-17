"""
Loan request flow: amount → installments → confirm → PENDING.
"""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from loguru import logger

from database.session import async_session
from database.models import User, Loan
from services.loan_service import (
    get_or_create_user, has_active_or_pending_loan, create_loan_request, level_title
)
from keyboards.inline import (
    loan_amount_kb, installments_kb, confirm_loan_kb, main_menu_kb, cancel_kb, back_main_kb
)
from locales import t
from utils.media import safe_edit, safe_answer_cb
from config import settings
from handlers.start import is_admin

router = Router(name="loan")


class LoanStates(StatesGroup):
    custom_amount = State()


@router.callback_query(F.data == "menu:loan")
async def menu_loan(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.clear()
    async with async_session() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username, cb.from_user.full_name
        )
        lang = user.language or "en"
        if user.is_blocked:
            await safe_edit(cb, t("blocked", lang, reason=user.block_reason or "N/A"))
            return
        if not user.polygon_wallet:
            await safe_edit(cb, t("no_wallet", lang), reply_markup=back_main_kb())
            return
        if await has_active_or_pending_loan(session, user.id):
            await safe_edit(cb, t("loan_already_active", lang), reply_markup=back_main_kb())
            return
        await safe_edit(
            cb,
            t("loan_select_amount", lang, limit=user.credit_limit, level=user.level, title=level_title(user.level)),
            reply_markup=loan_amount_kb(user.credit_limit),
        )


@router.callback_query(F.data.startswith("loan:amt:"))
async def loan_amount_selected(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    amount = float(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        if amount > user.credit_limit + 1e-9:
            await safe_answer_cb(cb, "Above your credit limit", show_alert=True)
            return
        if amount < settings.MIN_LOAN_AMOUNT:
            await safe_answer_cb(cb, f"Min {settings.MIN_LOAN_AMOUNT}", show_alert=True)
            return
    interest = round(amount * (settings.LOAN_INTEREST_PERCENT / 100), 6)
    total = round(amount + interest, 6)
    await safe_edit(cb, t("loan_select_inst", lang, amount=amount, total=total), reply_markup=installments_kb(amount))


@router.callback_query(F.data == "loan:custom")
async def loan_custom(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    await state.set_state(LoanStates.custom_amount)
    await safe_edit(cb, t("loan_custom_prompt", lang, min=settings.MIN_LOAN_AMOUNT, max=user.credit_limit), reply_markup=cancel_kb("menu:loan"))


@router.message(LoanStates.custom_amount)
async def process_custom_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("❌ Invalid number. Try again.")
        return
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        if amount < settings.MIN_LOAN_AMOUNT or amount > user.credit_limit:
            await message.answer(f"❌ Amount must be between {settings.MIN_LOAN_AMOUNT} and {user.credit_limit} USDT")
            return
    interest = round(amount * (settings.LOAN_INTEREST_PERCENT / 100), 6)
    total = round(amount + interest, 6)
    await state.clear()
    await message.answer(t("loan_select_inst", lang, amount=amount, total=total), reply_markup=installments_kb(amount), parse_mode="HTML")


@router.callback_query(F.data.startswith("loan:inst:"))
async def loan_inst_selected(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    parts = cb.data.split(":")
    amount = float(parts[2])
    inst = int(parts[3])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    interest = round(amount * (settings.LOAN_INTEREST_PERCENT / 100), 6)
    total = round(amount + interest, 6)
    inst_amt = round(total / inst, 6)
    await safe_edit(cb, t("loan_confirm", lang, amount=amount, interest=interest, total=total, inst=inst, inst_amt=inst_amt, days=settings.INSTALLMENT_PERIOD_DAYS), reply_markup=confirm_loan_kb(amount, inst))


@router.callback_query(F.data.startswith("loan:confirm:"))
async def loan_confirm(cb: CallbackQuery, state: FSMContext, bot):
    await safe_answer_cb(cb)
    parts = cb.data.split(":")
    amount = float(parts[2])
    inst = int(parts[3])
    async with async_session() as session:
        user = await get_or_create_user(session, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
        lang = user.language or "en"
        if await has_active_or_pending_loan(session, user.id):
            await safe_edit(cb, t("loan_already_active", lang), reply_markup=back_main_kb())
            return
        if not user.polygon_wallet:
            await safe_edit(cb, t("no_wallet", lang), reply_markup=back_main_kb())
            return
        if amount > user.credit_limit + 1e-9:
            await safe_answer_cb(cb, "Above limit", show_alert=True)
            return
        try:
            loan = await create_loan_request(session, user, amount, inst)
        except ValueError as e:
            await safe_edit(cb, f"❌ {e}", reply_markup=back_main_kb())
            return
        await safe_edit(cb, t("loan_submitted", lang, id=loan.id), reply_markup=back_main_kb())
        for aid in settings.admin_ids:
            try:
                await bot.send_message(aid, f"🆕 New loan request #{loan.id}\nUser: @{user.username or user.telegram_id}\nAmount: {amount} USDT\nInstallments: {inst}\nUse Admin Panel → Pending Loans", parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Notify admin {aid}: {e}")
