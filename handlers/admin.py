"""
Admin panel: pending loans, approve/reject + disburse, stats, block/unblock,
set limit, broadcast, maintenance, tickets, promo, force 3h report.
"""
from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from loguru import logger

from database.session import async_session
from database.models import User, Loan, SupportTicket
from services.loan_service import approve_loan, reject_loan, level_title
from services.polygon_pay import polygon_pay
from services.tasks import set_maintenance_mode, is_maintenance_mode, send_admin_report
from keyboards.inline import admin_panel_kb, pending_loan_admin_kb, back_main_kb, cancel_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb
from config import settings
from handlers.start import is_admin

router = Router(name="admin")


class AdminStates(StatesGroup):
    block_id = State()
    block_reason = State()
    unblock_id = State()
    setlimit_id = State()
    setlimit_val = State()
    broadcast = State()
    promo_code = State()
    promo_amount = State()


def _admin_only(user: User, username: str | None, tid: int) -> bool:
    return is_admin(user, username, tid)


@router.callback_query(F.data == "admin:panel")
async def admin_panel(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            await safe_answer_cb(cb, "Access denied", show_alert=True)
            return
        await safe_edit(cb, t("admin_panel", user.language or "en"), reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:pending")
async def admin_pending(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
        result = await session.execute(
            select(Loan).where(Loan.status == "PENDING").options(selectinload(Loan.user)).order_by(Loan.id.desc()).limit(20)
        )
        loans = result.scalars().all()
        if not loans:
            await safe_edit(cb, "No pending loans.", reply_markup=admin_panel_kb())
            return
        lines = ["📥 <b>Pending Loans</b>\n"]
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from keyboards.inline import _btn
        builder = InlineKeyboardBuilder()
        for loan in loans:
            u = loan.user
            lines.append(f"#{loan.id} | {loan.amount} USDT | @{u.username or u.telegram_id} | L{u.level}")
            builder.row(_btn(f"#{loan.id} Review", f"admin:review:{loan.id}"))
        builder.row(_btn("« Admin", "admin:panel"))
        await safe_edit(cb, "\n".join(lines), reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("admin:review:"))
async def admin_review(cb: CallbackQuery):
    await safe_answer_cb(cb)
    loan_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
        result = await session.execute(
            select(Loan).where(Loan.id == loan_id).options(selectinload(Loan.user), selectinload(Loan.installments))
        )
        loan = result.scalar_one_or_none()
        if not loan:
            await safe_edit(cb, "Loan not found.", reply_markup=admin_panel_kb())
            return
        u = loan.user
        text = (
            f"📋 Loan <b>#{loan.id}</b>\n"
            f"User: @{u.username or u.telegram_id} (<code>{u.telegram_id}</code>)\n"
            f"Level: {u.level} | Limit: {u.credit_limit}\n"
            f"Amount: <b>{loan.amount} USDT</b>\n"
            f"Interest: {loan.interest_amount} | Total: {loan.total_repay}\n"
            f"Installments: {loan.installments_count}\n"
            f"Wallet: <code>{u.polygon_wallet or 'N/A'}</code>\n"
            f"Status: {loan.status}"
        )
        await safe_edit(cb, text, reply_markup=pending_loan_admin_kb(loan.id))


@router.callback_query(F.data.startswith("admin:approve:"))
async def admin_approve(cb: CallbackQuery, bot: Bot):
    await safe_answer_cb(cb, "Approving & disbursing…")
    loan_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        admin_user = result.scalar_one()
        if not _admin_only(admin_user, cb.from_user.username, cb.from_user.id):
            return
        result = await session.execute(
            select(Loan).where(Loan.id == loan_id).options(selectinload(Loan.user), selectinload(Loan.installments))
        )
        loan = result.scalar_one_or_none()
        if not loan or loan.status != "PENDING":
            await safe_edit(cb, "Loan not pending.", reply_markup=admin_panel_kb())
            return
        try:
            ok, msg = await approve_loan(session, loan, loan.user)
            if ok:
                await safe_edit(cb, f"✅ Approved & disbursed.\nTX: <code>{msg}</code>", reply_markup=admin_panel_kb())
                try:
                    await bot.send_message(
                        loan.user.telegram_id,
                        f"✅ Loan #{loan.id} approved!\n{loan.amount} USDT sent to your wallet.\nTX: <code>{msg}</code>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning(f"Notify user: {e}")
            else:
                await safe_edit(cb, f"❌ Disburse failed: {msg}", reply_markup=pending_loan_admin_kb(loan_id))
        except Exception as e:
            logger.exception("Approve failed")
            await safe_edit(cb, f"❌ Error: {e}", reply_markup=pending_loan_admin_kb(loan_id))


@router.callback_query(F.data.startswith("admin:reject:"))
async def admin_reject(cb: CallbackQuery, bot: Bot):
    await safe_answer_cb(cb)
    loan_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        admin_user = result.scalar_one()
        if not _admin_only(admin_user, cb.from_user.username, cb.from_user.id):
            return
        result = await session.execute(
            select(Loan).where(Loan.id == loan_id).options(selectinload(Loan.user))
        )
        loan = result.scalar_one_or_none()
        if not loan or loan.status != "PENDING":
            await safe_edit(cb, "Not pending.", reply_markup=admin_panel_kb())
            return
        await reject_loan(session, loan)
        await safe_edit(cb, f"❌ Loan #{loan_id} rejected.", reply_markup=admin_panel_kb())
        try:
            await bot.send_message(loan.user.telegram_id, f"❌ Loan #{loan_id} was rejected by admin.")
        except Exception:
            pass


@router.callback_query(F.data == "admin:stats")
async def admin_stats(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
        users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        active = (await session.execute(select(func.count(Loan.id)).where(Loan.status == "ACTIVE"))).scalar() or 0
        pending = (await session.execute(select(func.count(Loan.id)).where(Loan.status == "PENDING"))).scalar() or 0
        completed = (await session.execute(select(func.count(Loan.id)).where(Loan.status == "COMPLETED"))).scalar() or 0
        borrowed = (await session.execute(select(func.coalesce(func.sum(Loan.amount), 0)).where(Loan.status.in_(["ACTIVE", "COMPLETED"])))).scalar() or 0
        try:
            treasury = await polygon_pay.get_usdt_balance(settings.TREASURY_ADDRESS)
        except Exception:
            treasury = -1
        text = (
            f"📊 <b>Stats</b>\n"
            f"Users: {users}\n"
            f"Pending: {pending} | Active: {active} | Completed: {completed}\n"
            f"Total borrowed: {float(borrowed):.2f} USDT\n"
            f"Treasury USDT: {treasury if treasury >= 0 else 'N/A'}"
        )
        await safe_edit(cb, text, reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:block")
async def admin_block_start(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    await state.set_state(AdminStates.block_id)
    await safe_edit(cb, "Send Telegram ID to block:", reply_markup=cancel_kb("admin:panel"))


@router.message(AdminStates.block_id)
async def admin_block_id(message: Message, state: FSMContext):
    try:
        tid = int(message.text.strip())
    except Exception:
        await message.answer("Invalid ID.")
        return
    await state.update_data(block_tid=tid)
    await state.set_state(AdminStates.block_reason)
    await message.answer("Reason:")


@router.message(AdminStates.block_reason)
async def admin_block_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    tid = data["block_tid"]
    reason = (message.text or "Blocked by admin").strip()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tid))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("User not found.")
            await state.clear()
            return
        user.is_blocked = True
        user.block_reason = reason
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Blocked {tid}: {reason}", reply_markup=back_main_kb())


@router.callback_query(F.data == "admin:unblock")
async def admin_unblock_start(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    await state.set_state(AdminStates.unblock_id)
    await safe_edit(cb, "Send Telegram ID to unblock:", reply_markup=cancel_kb("admin:panel"))


@router.message(AdminStates.unblock_id)
async def admin_unblock_id(message: Message, state: FSMContext):
    try:
        tid = int(message.text.strip())
    except Exception:
        await message.answer("Invalid ID.")
        return
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tid))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("User not found.")
            await state.clear()
            return
        user.is_blocked = False
        user.block_reason = None
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Unblocked {tid}", reply_markup=back_main_kb())


@router.callback_query(F.data == "admin:setlimit")
async def admin_setlimit_start(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    await state.set_state(AdminStates.setlimit_id)
    await safe_edit(cb, "Send Telegram ID:", reply_markup=cancel_kb("admin:panel"))


@router.message(AdminStates.setlimit_id)
async def admin_setlimit_id(message: Message, state: FSMContext):
    try:
        tid = int(message.text.strip())
    except Exception:
        await message.answer("Invalid ID.")
        return
    await state.update_data(limit_tid=tid)
    await state.set_state(AdminStates.setlimit_val)
    await message.answer("New credit limit (USDT):")


@router.message(AdminStates.setlimit_val)
async def admin_setlimit_val(message: Message, state: FSMContext):
    try:
        val = float(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Invalid number.")
        return
    data = await state.get_data()
    tid = data["limit_tid"]
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == tid))
        user = result.scalar_one_or_none()
        if not user:
            await message.answer("User not found.")
            await state.clear()
            return
        user.credit_limit = val
        await session.commit()
    await state.clear()
    await message.answer(f"✅ Limit for {tid} = {val} USDT", reply_markup=back_main_kb())


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    await state.set_state(AdminStates.broadcast)
    await safe_edit(cb, "Send broadcast message (HTML ok):", reply_markup=cancel_kb("admin:panel"))


@router.message(AdminStates.broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    text = message.html_text or message.text or ""
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_blocked == False))
        ids = [r[0] for r in result.all()]
    ok = fail = 0
    for tid in ids:
        try:
            await bot.send_message(tid, text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await message.answer(f"Broadcast done. OK={ok} Fail={fail}", reply_markup=back_main_kb())


@router.callback_query(F.data == "admin:maintenance")
async def admin_maintenance(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    current = await is_maintenance_mode()
    await set_maintenance_mode(not current)
    await safe_edit(cb, f"Maintenance mode: <b>{'ON' if not current else 'OFF'}</b>", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:forcereport")
async def admin_force_report(cb: CallbackQuery, bot: Bot):
    await safe_answer_cb(cb, "Sending report…")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    await send_admin_report(bot)
    await safe_edit(cb, "✅ Report sent to admins.", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:tickets")
async def admin_tickets(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
        result = await session.execute(
            select(SupportTicket).where(SupportTicket.status == "OPEN").order_by(SupportTicket.id.desc()).limit(15)
        )
        tickets = result.scalars().all()
        if not tickets:
            await safe_edit(cb, "No open tickets.", reply_markup=admin_panel_kb())
            return
        lines = ["🎫 <b>Open Tickets</b>\n"]
        for tkt in tickets:
            subj = (tkt.subject or "")[:40]
            lines.append(f"#{tkt.id} | {subj} | user_id={tkt.user_id}")
        await safe_edit(cb, "\n".join(lines), reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:createpromo")
async def admin_promo_start(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if not _admin_only(user, cb.from_user.username, cb.from_user.id):
            return
    await state.set_state(AdminStates.promo_code)
    await safe_edit(cb, "Promo code string:", reply_markup=cancel_kb("admin:panel"))


@router.message(AdminStates.promo_code)
async def admin_promo_code(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    if len(code) < 3:
        await message.answer("Min 3 chars.")
        return
    await state.update_data(promo_code=code)
    await state.set_state(AdminStates.promo_amount)
    await message.answer("Bonus amount USDT:")


@router.message(AdminStates.promo_amount)
async def admin_promo_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Invalid number.")
        return
    data = await state.get_data()
    code = data["promo_code"]
    await state.clear()
    try:
        from database.models import PromoCode
        async with async_session() as session:
            promo = PromoCode(code=code, bonus_amount=amount, max_uses=100, used_count=0, is_active=True)
            session.add(promo)
            await session.commit()
        await message.answer(f"✅ Promo {code} = {amount} USDT", reply_markup=back_main_kb())
    except Exception as e:
        logger.warning(f"Promo save: {e}")
        await message.answer(f"Promo noted: {code} = {amount} (optional model)\n{e}", reply_markup=back_main_kb())
