"""
Background tasks:
- Periodic admin report every 3 hours
- Installment due reminders
- Treasury low-balance check
- Maintenance mode helper
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from sqlalchemy import select, func, and_
from loguru import logger

from database.session import async_session
from database.models import (
    User, Loan, Installment, Investment, SupportTicket, SystemSetting, AdminReportLog
)
from services.polygon_pay import polygon_pay
from services.loan_service import payable_amount
from config import settings


REPORT_INTERVAL_SEC = 3 * 60 * 60  # 3 hours
REMINDER_INTERVAL_SEC = 6 * 60 * 60
TREASURY_CHECK_INTERVAL_SEC = 30 * 60
LOW_TREASURY_THRESHOLD = 20.0


async def get_setting(session, key: str, default: str = "") -> str:
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else default


async def set_setting(session, key: str, value: str) -> None:
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(SystemSetting(key=key, value=value))
    await session.commit()


async def is_maintenance_mode() -> bool:
    async with async_session() as session:
        val = await get_setting(session, "maintenance_mode", "0")
        return val == "1"


async def set_maintenance_mode(enabled: bool) -> None:
    async with async_session() as session:
        await set_setting(session, "maintenance_mode", "1" if enabled else "0")
    logger.info(f"Maintenance mode set to {enabled}")


async def build_admin_report() -> str:
    async with async_session() as session:
        users = (await session.execute(select(func.count(User.id)))).scalar() or 0
        blocked = (await session.execute(
            select(func.count(User.id)).where(User.is_blocked == True)
        )).scalar() or 0
        pending = (await session.execute(
            select(func.count(Loan.id)).where(Loan.status == "PENDING")
        )).scalar() or 0
        active = (await session.execute(
            select(func.count(Loan.id)).where(Loan.status == "ACTIVE")
        )).scalar() or 0
        completed = (await session.execute(
            select(func.count(Loan.id)).where(Loan.status == "COMPLETED")
        )).scalar() or 0
        volume = float((await session.execute(
            select(func.coalesce(func.sum(Loan.amount), 0)).where(
                Loan.status.in_(["ACTIVE", "COMPLETED"])
            )
        )).scalar() or 0)
        repaid = float((await session.execute(
            select(func.coalesce(func.sum(User.total_repaid), 0))
        )).scalar() or 0)
        pool = float((await session.execute(
            select(func.coalesce(func.sum(Investment.amount), 0)).where(
                Investment.status == "ACTIVE"
            )
        )).scalar() or 0)
        open_tickets = (await session.execute(
            select(func.count(SupportTicket.id)).where(SupportTicket.status == "OPEN")
        )).scalar() or 0
        now = datetime.utcnow()
        overdue = (await session.execute(
            select(func.count(Installment.id)).where(
                and_(Installment.status == "PENDING", Installment.due_date < now)
            )
        )).scalar() or 0
        since = now - timedelta(hours=3)
        new_users = (await session.execute(
            select(func.count(User.id)).where(User.created_at >= since)
        )).scalar() or 0
        try:
            treasury_usdt = await polygon_pay.get_usdt_balance(settings.TREASURY_ADDRESS)
        except Exception as e:
            treasury_usdt = -1.0
            logger.warning(f"Treasury balance fetch failed: {e}")
        text = (
            "📊 <b>MARCENZO — گزارش دوره‌ای (هر ۳ ساعت)</b>\n"
            f"🕐 {now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            f"👥 کاربران: <b>{users}</b> (مسدود: {blocked}) | جدید ۳س: <b>{new_users}</b>\n"
            f"⏳ وام در انتظار: <b>{pending}</b>\n"
            f"🟢 وام فعال: <b>{active}</b>\n"
            f"✅ تکمیل‌شده: <b>{completed}</b>\n"
            f"💰 حجم پرداخت‌شده: <b>{volume:.2f} USDT</b>\n"
            f"💸 کل بازپرداخت‌شده: <b>{repaid:.2f} USDT</b>\n"
            f"📈 استخر سرمایه‌گذاری: <b>{pool:.2f} USDT</b>\n"
            f"⚠️ اقساط سررسید گذشته: <b>{overdue}</b>\n"
            f"🎫 تیکت باز: <b>{open_tickets}</b>\n"
            f"🏦 موجودی خزانه: <b>{treasury_usdt if treasury_usdt >= 0 else 'N/A'} USDT</b>\n"
        )
        if treasury_usdt >= 0 and treasury_usdt < LOW_TREASURY_THRESHOLD:
            text += f"\n🚨 <b>هشدار: موجودی خزانه کم است! (زیر {LOW_TREASURY_THRESHOLD} USDT)</b>"
        return text


async def send_admin_report(bot: Bot) -> None:
    text = await build_admin_report()
    sent = 0
    targets = list(settings.admin_ids)
    if not targets:
        async with async_session() as session:
            for uname in settings.admin_usernames:
                result = await session.execute(select(User).where(User.username == uname))
                u = result.scalar_one_or_none()
                if u:
                    targets.append(u.telegram_id)
    for tid in set(targets):
        try:
            await bot.send_message(tid, text, parse_mode="HTML")
            sent += 1
        except Exception as e:
            logger.warning(f"Admin report to {tid} failed: {e}")
    async with async_session() as session:
        session.add(AdminReportLog(summary=text[:500], recipients=sent))
        await session.commit()
    logger.info(f"Admin report sent to {sent} recipient(s)")


async def send_installment_reminders(bot: Bot) -> None:
    now = datetime.utcnow()
    soon = now + timedelta(days=1)
    async with async_session() as session:
        result = await session.execute(
            select(Installment).where(
                and_(Installment.status == "PENDING", Installment.due_date <= soon)
            ).limit(100)
        )
        installments = result.scalars().all()
        for inst in installments:
            if inst.last_reminded_at and (now - inst.last_reminded_at).total_seconds() < 20 * 3600:
                continue
            from sqlalchemy.orm import selectinload
            r2 = await session.execute(
                select(Loan).where(Loan.id == inst.loan_id).options(selectinload(Loan.user))
            )
            loan = r2.scalar_one_or_none()
            if not loan or not loan.user:
                continue
            user = loan.user
            if not user.notify_reminders or user.is_blocked:
                continue
            pay = payable_amount(inst, now)
            overdue = now > inst.due_date
            if overdue:
                msg = (
                    f"⚠️ <b>یادآوری قسط معوق</b>\n\n"
                    f"وام #{loan.id} — قسط #{inst.number}\n"
                    f"مبلغ قابل پرداخت: <b>{pay:.4f} USDT</b>\n"
                    f"سررسید: {inst.due_date.strftime('%Y-%m-%d')}\n\n"
                    f"از منوی «وام‌های من» پرداخت کنید."
                )
            else:
                msg = (
                    f"🔔 <b>یادآوری سررسید قسط</b>\n\n"
                    f"وام #{loan.id} — قسط #{inst.number}\n"
                    f"مبلغ: <b>{pay:.4f} USDT</b>\n"
                    f"سررسید: {inst.due_date.strftime('%Y-%m-%d')}\n\n"
                    f"لطفاً به موقع پرداخت کنید."
                )
            try:
                await bot.send_message(user.telegram_id, msg, parse_mode="HTML")
                inst.last_reminded_at = now
            except Exception as e:
                logger.debug(f"Reminder to {user.telegram_id}: {e}")
        await session.commit()
    logger.info("Installment reminders pass done")


async def check_treasury_low(bot: Bot) -> None:
    try:
        bal = await polygon_pay.get_usdt_balance(settings.TREASURY_ADDRESS)
    except Exception:
        return
    if bal < LOW_TREASURY_THRESHOLD:
        msg = (
            f"🚨 <b>هشدار خزانه</b>\n\n"
            f"موجودی USDT خزانه: <b>{bal:.2f}</b>\n"
            f"آستانه هشدار: {LOW_TREASURY_THRESHOLD}\n"
            f"لطفاً موجودی را شارژ کنید."
        )
        for tid in settings.admin_ids:
            try:
                await bot.send_message(tid, msg, parse_mode="HTML")
            except Exception:
                pass


async def periodic_admin_report_loop(bot: Bot):
    await asyncio.sleep(60)
    while True:
        try:
            await send_admin_report(bot)
        except Exception as e:
            logger.exception(f"Admin report error: {e}")
        await asyncio.sleep(REPORT_INTERVAL_SEC)


async def periodic_reminder_loop(bot: Bot):
    await asyncio.sleep(120)
    while True:
        try:
            await send_installment_reminders(bot)
        except Exception as e:
            logger.exception(f"Reminder loop error: {e}")
        await asyncio.sleep(REMINDER_INTERVAL_SEC)


async def periodic_treasury_loop(bot: Bot):
    await asyncio.sleep(180)
    while True:
        try:
            await check_treasury_low(bot)
        except Exception as e:
            logger.exception(f"Treasury check error: {e}")
        await asyncio.sleep(TREASURY_CHECK_INTERVAL_SEC)


def start_background_tasks(bot: Bot) -> list:
    tasks = [
        asyncio.create_task(periodic_admin_report_loop(bot), name="admin_report"),
        asyncio.create_task(periodic_reminder_loop(bot), name="reminders"),
        asyncio.create_task(periodic_treasury_loop(bot), name="treasury"),
    ]
    logger.info("Background tasks started (report 3h, reminders 6h, treasury 30m)")
    return tasks
