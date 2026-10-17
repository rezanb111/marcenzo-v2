"""
/start, captcha, terms, language, wallet binding, main menu entry.
"""
from __future__ import annotations

from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from loguru import logger

from database.session import async_session
from database.models import User
from services.loan_service import get_or_create_user, level_title
from services.security import generate_math_captcha, verify_password
from keyboards.inline import main_menu_kb, language_kb, terms_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb
from config import settings

router = Router(name="start")


class OnboardStates(StatesGroup):
    captcha = State()
    terms = State()
    password_unlock = State()
    language = State()
    wallet = State()


def is_admin(user: User | None, username: str | None, telegram_id: int) -> bool:
    if user and user.username and user.username.lower() in settings.admin_usernames:
        return True
    if username and username.lower().lstrip("@") in settings.admin_usernames:
        return True
    if telegram_id in settings.admin_ids:
        return True
    return False


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    from services.tasks import is_maintenance_mode
    if await is_maintenance_mode():
        uname = (message.from_user.username or "").lower()
        if uname not in settings.admin_usernames and message.from_user.id not in settings.admin_ids:
            await message.answer("🛠 ربات موقتاً در حالت تعمیر است. لطفاً بعداً مراجعه کنید.")
            return

    async with async_session() as session:
        user = await get_or_create_user(
            session, message.from_user.id, message.from_user.username, message.from_user.full_name
        )
        if user.is_blocked:
            await message.answer(t("blocked", user.language, reason=user.block_reason or "N/A"), parse_mode="HTML")
            return

        args = (message.text or "").split(maxsplit=1)
        if len(args) > 1 and args[1].startswith("ref_"):
            ref_code = args[1][4:].strip()
            from handlers.referral import apply_referral_on_start, ensure_referral_code
            await apply_referral_on_start(session, user, ref_code)
        from handlers.referral import ensure_referral_code
        await ensure_referral_code(session, user)

        if user.captcha_locked:
            user.captcha_locked = False
            user.captcha_fails = 0
            await session.commit()

        lang = user.language or "en"

        if user.password_hash and user.terms_accepted_at:
            await state.set_state(OnboardStates.password_unlock)
            await state.update_data(user_id=user.id)
            await message.answer(t("password_unlock", lang), parse_mode="HTML")
            return

        if user.terms_accepted_at:
            admin = is_admin(user, message.from_user.username, message.from_user.id)
            await message.answer(t("main_menu", lang), reply_markup=main_menu_kb(admin), parse_mode="HTML")
            return

        q, ans = generate_math_captcha()
        await state.set_state(OnboardStates.captcha)
        await state.update_data(captcha_answer=str(ans), user_id=user.id, fails=0)
        await message.answer(t("welcome", lang) + "\n\n" + t("captcha_prompt", lang, question=q), parse_mode="HTML")


@router.message(OnboardStates.captcha)
async def process_captcha(message: Message, state: FSMContext):
    data = await state.get_data()
    expected = str(data.get("captcha_answer", ""))
    fails = int(data.get("fails", 0))
    user_id = data.get("user_id")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()
        lang = user.language or "en"
        if message.text and message.text.strip() == expected:
            user.captcha_fails = 0
            await session.commit()
            await state.set_state(OnboardStates.terms)
            await message.answer(t("terms_title", lang) + "\n\n" + t("terms_body", lang), reply_markup=terms_kb(), parse_mode="HTML")
            return
        fails += 1
        user.captcha_fails = fails
        if fails >= 5:
            user.captcha_locked = True
            await session.commit()
            await state.clear()
            await message.answer(t("captcha_locked", lang), parse_mode="HTML")
            return
        await session.commit()
        await state.update_data(fails=fails)
        q, ans = generate_math_captcha()
        await state.update_data(captcha_answer=str(ans))
        await message.answer(t("captcha_fail", lang, left=5 - fails) + "\n\n" + t("captcha_prompt", lang, question=q), parse_mode="HTML")


@router.callback_query(F.data == "terms:agree")
async def terms_agree(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    data = await state.get_data()
    user_id = data.get("user_id")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
            user = result.scalar_one()
        user.terms_accepted_at = datetime.utcnow()
        await session.commit()
        lang = user.language or "en"
    await state.set_state(OnboardStates.language)
    await safe_edit(cb, t("choose_lang", lang), reply_markup=language_kb())


@router.callback_query(F.data == "terms:decline")
async def terms_decline(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    await state.clear()
    await safe_edit(cb, t("terms_declined", lang))


@router.callback_query(F.data.startswith("lang:"))
async def set_language(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    lang_code = cb.data.split(":")[1]
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        user.language = lang_code
        await session.commit()
        lang = lang_code
        if not user.polygon_wallet:
            await state.set_state(OnboardStates.wallet)
            await safe_edit(cb, t("bind_wallet_prompt", lang))
            return
        admin = is_admin(user, cb.from_user.username, cb.from_user.id)
        await state.clear()
        await safe_edit(cb, t("main_menu", lang), reply_markup=main_menu_kb(admin))


@router.message(OnboardStates.wallet)
async def bind_wallet(message: Message, state: FSMContext):
    addr = (message.text or "").strip()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        from services.polygon_pay import polygon_pay
        if not polygon_pay.is_valid_address(addr):
            await message.answer(t("wallet_invalid", lang), parse_mode="HTML")
            return
        user.polygon_wallet = polygon_pay.to_checksum(addr)
        await session.commit()
        admin = is_admin(user, message.from_user.username, message.from_user.id)
        await state.clear()
        await message.answer(t("wallet_bound", lang, wallet=user.polygon_wallet), parse_mode="HTML")
        await message.answer(t("main_menu", lang), reply_markup=main_menu_kb(admin), parse_mode="HTML")


@router.message(OnboardStates.password_unlock)
async def password_unlock(message: Message, state: FSMContext):
    pwd = (message.text or "").strip()
    data = await state.get_data()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == data["user_id"]))
        user = result.scalar_one()
        lang = user.language or "en"
        if verify_password(pwd, user.password_salt, user.password_hash):
            admin = is_admin(user, message.from_user.username, message.from_user.id)
            await state.clear()
            await message.answer(t("main_menu", lang), reply_markup=main_menu_kb(admin), parse_mode="HTML")
        else:
            await message.answer(t("password_wrong", lang), parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def menu_main(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        if user.is_blocked:
            await safe_edit(cb, t("blocked", user.language, reason=user.block_reason or "N/A"))
            return
        admin = is_admin(user, cb.from_user.username, cb.from_user.id)
        await safe_edit(cb, t("main_menu", user.language), reply_markup=main_menu_kb(admin))
