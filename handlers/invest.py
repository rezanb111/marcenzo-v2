"""Investment pool: deposit unique address, verify & activate, stats."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from loguru import logger

from database.session import async_session
from database.models import User, Investment
from services.loan_service import create_investment, activate_investment
from services.polygon_pay import polygon_pay
from keyboards.inline import (
    invest_kb, invest_confirm_kb, invest_verify_kb, back_main_kb, cancel_kb
)
from locales import t
from utils.media import safe_edit, safe_answer_cb
from config import settings

router = Router(name="invest")


class InvestStates(StatesGroup):
    amount = State()


@router.callback_query(F.data == "menu:invest")
async def menu_invest(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        pool_result = await session.execute(
            select(func.coalesce(func.sum(Investment.amount), 0)).where(Investment.status == "ACTIVE")
        )
        pool = float(pool_result.scalar() or 0)
        await safe_edit(cb, t("invest_title", lang, pool=pool, yours=user.invested_amount, earned=user.earned_interest), reply_markup=invest_kb())


@router.callback_query(F.data == "invest:deposit")
async def invest_deposit(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    await state.set_state(InvestStates.amount)
    await safe_edit(cb, t("invest_amount_prompt", lang, min=settings.MIN_INVEST_AMOUNT), reply_markup=cancel_kb("menu:invest"))


@router.message(InvestStates.amount)
async def invest_amount_entered(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("❌ Invalid number.")
        return
    if amount < settings.MIN_INVEST_AMOUNT:
        await message.answer(f"❌ Minimum {settings.MIN_INVEST_AMOUNT} USDT")
        return
    await state.clear()
    await message.answer(f"Confirm investment of <b>{amount} USDT</b>?", reply_markup=invest_confirm_kb(amount), parse_mode="HTML")


@router.callback_query(F.data.startswith("invest:confirm:"))
async def invest_confirm(cb: CallbackQuery):
    await safe_answer_cb(cb)
    amount = float(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        inv = await create_investment(session, user, amount)
        await safe_edit(cb, t("invest_deposit_info", lang, amount=amount, address=inv.deposit_address), reply_markup=invest_verify_kb(inv.id))


@router.callback_query(F.data.startswith("invest:verify:"))
async def invest_verify(cb: CallbackQuery):
    await safe_answer_cb(cb, "Verifying on-chain…")
    inv_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        result = await session.execute(
            select(Investment).where(Investment.id == inv_id, Investment.user_id == user.id).options(selectinload(Investment.user))
        )
        inv = result.scalar_one_or_none()
        if not inv:
            await safe_edit(cb, "Investment not found.", reply_markup=back_main_kb())
            return
        if inv.status == "ACTIVE":
            await safe_edit(cb, "✅ Already active.", reply_markup=back_main_kb())
            return
        success, msg, received, tx_hash = await polygon_pay.verify_and_sweep_investment(
            inv.deposit_address, inv.deposit_private_key, inv.amount
        )
        if success and tx_hash:
            await activate_investment(session, inv, received, tx_hash)
            await safe_edit(cb, f"{msg}\n\nInvestment activated!\nTX: <code>{tx_hash}</code>", reply_markup=back_main_kb())
        else:
            await safe_edit(cb, f"❌ {msg}\n\nReceived: {received:.6f} / Required: {inv.amount}", reply_markup=invest_verify_kb(inv.id))


@router.callback_query(F.data == "invest:my")
async def invest_my(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        result = await session.execute(select(Investment).where(Investment.user_id == user.id).order_by(Investment.id.desc()))
        invs = result.scalars().all()
        if not invs:
            await safe_edit(cb, "No investments yet.", reply_markup=back_main_kb())
            return
        lines = ["📊 <b>My Investments</b>\n"]
        for i in invs:
            lines.append(f"#{i.id} | {i.amount} USDT | {i.status} | earned {i.earned:.4f}")
        await safe_edit(cb, "\n".join(lines), reply_markup=back_main_kb())
