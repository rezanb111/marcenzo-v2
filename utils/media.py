"""
Safe message editing helpers for aiogram 3.
Always answer callbacks; fallback delete+answer when edit fails.
"""
from __future__ import annotations

from typing import Optional, Union
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from loguru import logger


async def safe_edit(
    target: Union[Message, CallbackQuery],
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> Message:
    if isinstance(target, CallbackQuery):
        try:
            await target.answer()
        except Exception:
            pass
        msg = target.message
    else:
        msg = target

    try:
        return await msg.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
    except TelegramBadRequest as e:
        err = str(e).lower()
        if "message is not modified" in err:
            return msg
        try:
            await msg.delete()
        except Exception:
            pass
        return await msg.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
    except Exception as e:
        logger.warning(f"safe_edit fallback: {e}")
        try:
            await msg.delete()
        except Exception:
            pass
        return await msg.answer(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )


async def safe_answer_cb(cb: CallbackQuery, text: str = "", show_alert: bool = False):
    try:
        await cb.answer(text, show_alert=show_alert)
    except Exception:
        pass
