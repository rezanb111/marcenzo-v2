"""Referral system + promo codes."""
from __future__ import annotations

import secrets
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from loguru import logger

from database.session import async_session
from database.models import User, PromoCode, ReferralReward
from keyboards.inline import back_main_kb, cancel_kb
from utils.media import safe_edit, safe_answer_cb
from config import settings

router = Router(name="referral")


class PromoStates(StatesGroup):
    enter_code = State()


def _gen_ref_code() -> str:
    return secrets.token_hex(4).upper()


async def ensure_referral_code(session, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    code = _gen_ref_code()
    while True:
        exists = (await session.execute(select(User).where(User.referral_code == code))).scalar_one_or_none()
        if not exists:
            break
        code = _gen_ref_code()
    user.referral_code = code
    await session.commit()
    return code


@router.callback_query(F.data == "menu:referral")
async def menu_referral(cb: CallbackQuery):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        code = await ensure_referral_code(session, user)
        link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{code}"
        text = (
            f"🎁 <b>سیستم دعوت دوستان (Referral)</b>\n\n"
            f"کد دعوت شما: <code>{code}</code>\n"
            f"لینک دعوت:\n<code>{link}</code>\n\n"
            f"تعداد دعوت‌شده‌ها: <b>{user.referral_count}</b>\n"
            f"پاداش کسب‌شده: <b>{user.referral_bonus_earned:.2f} USDT</b>\n\n"
            f"• ثبت‌نام هر دوست: +{settings.REFERRAL_BONUS_SIGNUP} سقف اعتبار\n"
            f"• اولین وام موفق دوست: +{settings.REFERRAL_BONUS_FIRST_LOAN} سقف اعتبار"
        )
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🏷 وارد کردن کد تخفیف", callback_data="promo:enter"))
        builder.row(InlineKeyboardButton(text="« منوی اصلی", callback_data="menu:main"))
        await safe_edit(cb, text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "promo:enter")
async def promo_enter(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.set_state(PromoStates.enter_code)
    await safe_edit(cb, "🏷 کد تخفیف را وارد کنید:", reply_markup=cancel_kb("menu:referral"))


@router.message(PromoStates.enter_code)
async def promo_apply(message: Message, state: FSMContext):
    code = (message.text or "").strip().upper()
    async with async_session() as session:
        result = await session.execute(select(PromoCode).where(PromoCode.code == code, PromoCode.is_active == True))
        promo = result.scalar_one_or_none()
        if not promo:
            await message.answer("❌ کد نامعتبر یا منقضی است.")
            return
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            await message.answer("❌ کد منقضی شده است.")
            return
        if promo.used_count >= promo.max_uses:
            await message.answer("❌ ظرفیت استفاده تمام شده.")
            return
        await state.clear()
        await state.update_data(promo_code=code, promo_discount=promo.discount_percent)
        await message.answer(
            f"✅ کد <b>{code}</b> پذیرفته شد!\nتخفیف سود: <b>{promo.discount_percent}%</b>",
            parse_mode="HTML",
            reply_markup=back_main_kb(),
        )


async def apply_referral_on_start(session, new_user: User, ref_code: str) -> None:
    if not ref_code or new_user.referred_by:
        return
    result = await session.execute(select(User).where(User.referral_code == ref_code.upper()))
    referrer = result.scalar_one_or_none()
    if not referrer or referrer.id == new_user.id:
        return
    new_user.referred_by = referrer.id
    referrer.referral_count += 1
    referrer.credit_limit = round(referrer.credit_limit + settings.REFERRAL_BONUS_SIGNUP, 2)
    referrer.referral_bonus_earned = round(referrer.referral_bonus_earned + settings.REFERRAL_BONUS_SIGNUP, 2)
    session.add(ReferralReward(referrer_id=referrer.id, referred_id=new_user.id, bonus_amount=settings.REFERRAL_BONUS_SIGNUP, reason="signup"))
    await session.commit()
    logger.info(f"Referral: {referrer.telegram_id} ← {new_user.telegram_id}")
