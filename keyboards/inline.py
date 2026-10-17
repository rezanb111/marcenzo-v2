"""
Premium Inline Keyboards for MARCENZO Bot.
Uses style= and icon_custom_emoji_id when supported; graceful fallback.
"""
from __future__ import annotations

from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

EMOJI = {
    "rocket": "6147654280112248427",
    "green": "6084384451154941172",
    "red": "6082387218347857432",
    "check": "5328210112429438491",
    "cross": "5330561452405176521",
    "check3": "6113832658196762761",
    "star": "4990453424710485047",
    "down": "4990226723451699964",
    "heart": "4987775237723522533",
    "lightning": "4990074969372230665",
    "settings": "5929098607192969118",
    "hourglass": "4990168118622946000",
    "link": "6113813004426416777",
    "flag_en": "5913463998522592692",
    "flag_fa": "5866040533008261990",
    "flag_ru": "5913274246867456342",
    "flag_ar": "5911387497799094470",
    "flag_tr": "5910995113881901195",
    "flag_de": "5911096835887337583",
    "flag_fr": "5913605586414473124",
    "flag_zh": "5913371673905598425",
    "flag_gb": "5913443365499703513",
}


def _btn(text: str, callback_data: str = None, url: str = None, style: str = None, emoji_id: str = None) -> InlineKeyboardButton:
    kwargs = {"text": text}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url
    try:
        if style:
            kwargs["style"] = style
        if emoji_id:
            kwargs["icon_custom_emoji_id"] = emoji_id
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        return InlineKeyboardButton(**kwargs)


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("💰 Request Loan", "menu:loan", style="success", emoji_id=EMOJI["rocket"]), _btn("📋 My Loans", "menu:myloans", style="primary", emoji_id=EMOJI["hourglass"]))
    builder.row(_btn("👤 Profile", "menu:profile", emoji_id=EMOJI["star"]), _btn("📈 Invest", "menu:invest", style="success", emoji_id=EMOJI["green"]))
    builder.row(_btn("📖 Guide", "menu:guide", emoji_id=EMOJI["link"]), _btn("🏆 Leaderboard", "menu:leaderboard", emoji_id=EMOJI["star"]))
    builder.row(_btn("🎁 Referral", "menu:referral", emoji_id=EMOJI["heart"]), _btn("🆘 Support", "menu:support", emoji_id=EMOJI["heart"]))
    builder.row(_btn("🌐 Website", url="https://rezanb111.github.io/Marc/", emoji_id=EMOJI["link"]))
    if is_admin:
        builder.row(_btn("⚙️ Admin Panel", "admin:panel", style="danger", emoji_id=EMOJI["settings"]))
    return builder.as_markup()


def language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    langs = [("🇬🇧 English", "lang:en", EMOJI["flag_en"]), ("🇮🇷 فارسی", "lang:fa", EMOJI["flag_fa"]), ("🇷🇺 Русский", "lang:ru", EMOJI["flag_ru"]), ("🇸🇦 العربية", "lang:ar", EMOJI["flag_ar"]), ("🇹🇷 Türkçe", "lang:tr", EMOJI["flag_tr"]), ("🇩🇪 Deutsch", "lang:de", EMOJI["flag_de"]), ("🇫🇷 Français", "lang:fr", EMOJI["flag_fr"]), ("🇨🇳 中文", "lang:zh", EMOJI["flag_zh"]), ("🇪🇸 Español", "lang:es", None), ("🇮🇳 हिन्दी", "lang:hi", None)]
    for text, cb, eid in langs:
        builder.row(_btn(text, cb, emoji_id=eid))
    return builder.as_markup()


def terms_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("✅ I Agree", "terms:agree", style="success", emoji_id=EMOJI["check"]), _btn("❌ Decline", "terms:decline", style="danger", emoji_id=EMOJI["cross"]))
    return builder.as_markup()


def loan_amount_kb(credit_limit: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    amounts = [0.1, 0.5, 1, 2, 3, 5]
    amounts = [a for a in amounts if a <= credit_limit]
    if credit_limit >= 10:
        amounts.extend([10, 20, 50])
    amounts = [a for a in amounts if a <= credit_limit]
    if credit_limit not in amounts and credit_limit >= 0.1:
        amounts.append(round(credit_limit, 2))
    row = []
    for a in amounts:
        row.append(_btn(f"{a} USDT", f"loan:amt:{a}", style="primary"))
        if len(row) == 3:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)
    builder.row(_btn("✏️ Custom Amount", "loan:custom", emoji_id=EMOJI["lightning"]))
    builder.row(_btn("« Back", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def installments_kb(amount: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in [1, 3, 5, 7, 10]:
        builder.row(_btn(f"{n} installment{'s' if n > 1 else ''}", f"loan:inst:{amount}:{n}", style="primary"))
    builder.row(_btn("« Back", "menu:loan", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def confirm_loan_kb(amount: float, inst: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("✅ Confirm Request", f"loan:confirm:{amount}:{inst}", style="success", emoji_id=EMOJI["check"]))
    builder.row(_btn("« Cancel", "menu:main", style="danger", emoji_id=EMOJI["cross"]))
    return builder.as_markup()


def my_loans_kb(loans) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for loan in loans[:20]:
        builder.row(_btn(f"#{loan.id} | {loan.amount} USDT | {loan.status}", f"loan:view:{loan.id}"))
    builder.row(_btn("« Main Menu", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def loan_detail_kb(loan_id: int, has_unpaid: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_unpaid:
        builder.row(_btn("💳 Pay Next Installment", f"repay:select:{loan_id}", style="success", emoji_id=EMOJI["green"]))
    builder.row(_btn("« My Loans", "menu:myloans", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def installment_pay_kb(inst_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🔄 Verify & Sweep Payment", f"repay:verify:{inst_id}", style="success", emoji_id=EMOJI["check3"]))
    builder.row(_btn("« Back", "menu:myloans", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def invest_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("💵 Deposit / Invest", "invest:deposit", style="success", emoji_id=EMOJI["green"]))
    builder.row(_btn("📊 My Investments", "invest:my", emoji_id=EMOJI["star"]))
    builder.row(_btn("« Main Menu", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def invest_confirm_kb(amount: float) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("✅ Confirm", f"invest:confirm:{amount}", style="success", emoji_id=EMOJI["check"]))
    builder.row(_btn("« Cancel", "menu:invest", style="danger", emoji_id=EMOJI["cross"]))
    return builder.as_markup()


def invest_verify_kb(inv_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🔄 Verify Deposit", f"invest:verify:{inv_id}", style="success", emoji_id=EMOJI["check3"]))
    builder.row(_btn("« Back", "menu:invest", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("🔐 Set Password", "profile:password", emoji_id=EMOJI["settings"]))
    builder.row(_btn("💼 Bind Wallet", "profile:wallet", emoji_id=EMOJI["link"]))
    builder.row(_btn("🌐 Language", "profile:lang", emoji_id=EMOJI["flag_en"]))
    builder.row(_btn("« Main Menu", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def support_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("📝 New Ticket", "support:new", style="primary", emoji_id=EMOJI["heart"]))
    builder.row(_btn("📋 My Tickets", "support:list", emoji_id=EMOJI["hourglass"]))
    builder.row(_btn("« Main Menu", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("📥 Pending Loans", "admin:pending", style="primary", emoji_id=EMOJI["hourglass"]), _btn("📊 Stats", "admin:stats", emoji_id=EMOJI["star"]))
    builder.row(_btn("🎫 Tickets", "admin:tickets", emoji_id=EMOJI["heart"]), _btn("🚫 Block User", "admin:block", style="danger", emoji_id=EMOJI["red"]))
    builder.row(_btn("✅ Unblock", "admin:unblock", style="success"), _btn("⚡ Set Limit", "admin:setlimit", emoji_id=EMOJI["lightning"]))
    builder.row(_btn("📢 Broadcast", "admin:broadcast", style="primary"), _btn("🛠 Maintenance", "admin:maintenance", emoji_id=EMOJI["settings"]))
    builder.row(_btn("📈 Force Report", "admin:forcereport", emoji_id=EMOJI["star"]), _btn("🏷 Create Promo", "admin:createpromo"))
    builder.row(_btn("« Main Menu", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def pending_loan_admin_kb(loan_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("✅ Approve", f"admin:approve:{loan_id}", style="success", emoji_id=EMOJI["check"]), _btn("❌ Reject", f"admin:reject:{loan_id}", style="danger", emoji_id=EMOJI["cross"]))
    builder.row(_btn("« Back", "admin:pending", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def back_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("« Main Menu", "menu:main", emoji_id=EMOJI["down"]))
    return builder.as_markup()


def cancel_kb(callback: str = "menu:main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_btn("❌ Cancel", callback, style="danger", emoji_id=EMOJI["cross"]))
    return builder.as_markup()
