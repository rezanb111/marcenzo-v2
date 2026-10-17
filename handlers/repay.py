"""My Loans + Installment repayment with unique deposit address + verify & sweep."""
from __future__ import annotations

from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from loguru import logger

from database.session import async_session
from database.models import User, Loan, Installment
from services.loan_service import payable_amount, mark_installment_paid, level_title
from services.polygon_pay import polygon_pay
from keyboards.inline import my_loans_kb, loan_detail_kb, installment_pay_kb, back_main_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb

router = Router(name="repay")


@router.callback_query(F.data == "menu:myloans")
async def menu_myloans(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        result = await session.execute(
            select(Loan).where(Loan.user_id == user.id).order_by(Loan.id.desc()).options(selectinload(Loan.installments))
        )
        loans = result.scalars().all()
        if not loans:
            await safe_edit(cb, t("my_loans_empty", lang), reply_markup=back_main_kb())
            return
        await safe_edit(cb, t("my_loans_title", lang), reply_markup=my_loans_kb(loans))


@router.callback_query(F.data.startswith("loan:view:"))
async def loan_view(cb: CallbackQuery):
    await safe_answer_cb(cb)
    loan_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        result = await session.execute(
            select(Loan).where(Loan.id == loan_id, Loan.user_id == user.id).options(selectinload(Loan.installments))
        )
        loan = result.scalar_one_or_none()
        if not loan:
            await safe_answer_cb(cb, "Loan not found", show_alert=True)
            return
        lines = [
            f"📋 <b>Loan #{loan.id}</b>", f"Status: <b>{loan.status}</b>",
            f"Principal: {loan.amount} USDT", f"Interest: {loan.interest_amount} USDT ({loan.interest_percent}%)",
            f"Total: {loan.total_repay} USDT", f"Installments: {loan.installments_count}", "",
            "<b>Installments:</b>",
        ]
        if loan.disburse_tx_hash:
            lines.insert(6, f"Disburse TX: <code>{loan.disburse_tx_hash[:18]}…</code>")
        now = datetime.utcnow()
        has_unpaid = False
        for inst in sorted(loan.installments, key=lambda x: x.number):
            pay = payable_amount(inst, now)
            late = pay - inst.amount
            status = inst.status
            if status == "PENDING" and now > inst.due_date:
                status = "LATE"
            if status in ("PENDING", "LATE"):
                has_unpaid = True
            extra = f" (+{late:.4f} late)" if late > 0 else ""
            lines.append(f"  #{inst.number} | {pay:.4f} USDT{extra} | {status} | due {inst.due_date.strftime('%Y-%m-%d')}")
        await safe_edit(cb, "\n".join(lines), reply_markup=loan_detail_kb(loan.id, has_unpaid))


@router.callback_query(F.data.startswith("repay:select:"))
async def repay_select(cb: CallbackQuery):
    await safe_answer_cb(cb)
    loan_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        result = await session.execute(
            select(Loan).where(Loan.id == loan_id, Loan.user_id == user.id).options(selectinload(Loan.installments))
        )
        loan = result.scalar_one_or_none()
        if not loan:
            await safe_answer_cb(cb, "Not found", show_alert=True)
            return
        now = datetime.utcnow()
        unpaid = [i for i in sorted(loan.installments, key=lambda x: x.number) if i.status != "PAID"]
        if not unpaid:
            await safe_edit(cb, "✅ All installments paid!", reply_markup=back_main_kb())
            return
        inst = unpaid[0]
        pay = payable_amount(inst, now)
        late = pay - inst.amount
        if not inst.deposit_address:
            addr, priv = polygon_pay.generate_installment_deposit(inst.id, user.telegram_id)
            inst.deposit_address = addr
            inst.deposit_private_key = priv
            await session.commit()
        text = f"💳 <b>Pay Installment #{inst.number}</b>\n\nBase amount: {inst.amount} USDT\n"
        if late > 0:
            text += f"Late fee: +{late:.4f} USDT\n"
        text += (
            f"<b>Payable now: {pay:.4f} USDT</b>\n"
            f"Due date: {inst.due_date.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"Send exactly the amount (or more) in <b>USDT (Polygon)</b> to:\n"
            f"<code>{inst.deposit_address}</code>\n\n"
            f"Then press the button below to verify & sweep."
        )
        await safe_edit(cb, text, reply_markup=installment_pay_kb(inst.id))


@router.callback_query(F.data.startswith("repay:verify:"))
async def repay_verify(cb: CallbackQuery):
    await safe_answer_cb(cb, "Verifying on-chain…")
    inst_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        result = await session.execute(
            select(Installment).where(Installment.id == inst_id).options(selectinload(Installment.loan).selectinload(Loan.user))
        )
        inst = result.scalar_one_or_none()
        if not inst or inst.loan.user.telegram_id != cb.from_user.id:
            await safe_edit(cb, "Installment not found.", reply_markup=back_main_kb())
            return
        if inst.status == "PAID":
            await safe_edit(cb, "✅ Already paid.", reply_markup=back_main_kb())
            return
        required = payable_amount(inst)
        success, msg, received, tx_hash = await polygon_pay.verify_and_sweep_installment(
            inst.deposit_address, inst.deposit_private_key, required
        )
        if success and tx_hash:
            await mark_installment_paid(session, inst, received, tx_hash)
            await session.refresh(user)
            await safe_edit(cb, f"{msg}\n\nTX: <code>{tx_hash}</code>\n\nLevel: {user.level} ({level_title(user.level)}) | Successful: {user.successful_loans}", reply_markup=back_main_kb())
        else:
            await safe_edit(cb, f"❌ {msg}\n\nReceived: {received:.6f} USDT\nRequired: {required:.6f} USDT", reply_markup=installment_pay_kb(inst.id))
