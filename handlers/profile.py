"""Profile, password, wallet rebinding, language."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from database.session import async_session
from database.models import User
from services.loan_service import level_title
from services.security import generate_salt, hash_password
from services.polygon_pay import polygon_pay
from keyboards.inline import profile_kb, language_kb, back_main_kb, cancel_kb
from locales import t
from utils.media import safe_edit, safe_answer_cb

router = Router(name="profile")


class ProfileStates(StatesGroup):
    set_password = State()
    confirm_password = State()
    bind_wallet = State()


@router.callback_query(F.data == "menu:profile")
async def menu_profile(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        await safe_edit(cb, t("profile_title", lang, tid=user.telegram_id, username=user.username or "—", level=user.level, title=level_title(user.level), limit=user.credit_limit, success=user.successful_loans, borrowed=user.total_borrowed, repaid=user.total_repaid, invested=user.invested_amount, earned=user.earned_interest, wallet=user.polygon_wallet or "Not bound"), reply_markup=profile_kb())


@router.callback_query(F.data == "profile:password")
async def profile_password(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    await state.set_state(ProfileStates.set_password)
    await safe_edit(cb, t("password_set_prompt", lang), reply_markup=cancel_kb("menu:profile"))


@router.message(ProfileStates.set_password)
async def set_password_1(message: Message, state: FSMContext):
    pwd = (message.text or "").strip()
    if len(pwd) < 6:
        await message.answer("❌ Min 6 characters.")
        return
    await state.update_data(new_pwd=pwd)
    await state.set_state(ProfileStates.confirm_password)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    await message.answer(t("password_confirm", lang))


@router.message(ProfileStates.confirm_password)
async def set_password_2(message: Message, state: FSMContext):
    data = await state.get_data()
    pwd = data.get("new_pwd", "")
    confirm = (message.text or "").strip()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        if pwd != confirm:
            await message.answer(t("password_mismatch", lang))
            await state.set_state(ProfileStates.set_password)
            return
        salt = generate_salt()
        user.password_salt = salt
        user.password_hash = hash_password(pwd, salt)
        await session.commit()
        await state.clear()
        await message.answer(t("password_set_ok", lang), reply_markup=back_main_kb())


@router.callback_query(F.data == "profile:wallet")
async def profile_wallet(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == cb.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
    await state.set_state(ProfileStates.bind_wallet)
    await safe_edit(cb, t("bind_wallet_prompt", lang), reply_markup=cancel_kb("menu:profile"))


@router.message(ProfileStates.bind_wallet)
async def process_bind_wallet(message: Message, state: FSMContext):
    addr = (message.text or "").strip()
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one()
        lang = user.language or "en"
        if not polygon_pay.is_valid_address(addr):
            await message.answer(t("wallet_invalid", lang))
            return
        user.polygon_wallet = polygon_pay.to_checksum(addr)
        await session.commit()
        await state.clear()
        await message.answer(t("wallet_bound", lang, wallet=user.polygon_wallet), parse_mode="HTML", reply_markup=back_main_kb())


@router.callback_query(F.data == "profile:lang")
async def profile_lang(cb: CallbackQuery, state: FSMContext):
    await safe_answer_cb(cb)
    await safe_edit(cb, t("choose_lang", "en"), reply_markup=language_kb())
