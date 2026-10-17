"""
Simple i18n for MARCENZO Bot.
DEFAULT = English. FA keys for main strings.
"""
from typing import Dict

TEXTS: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": "🚀 Welcome to <b>MARCENZO Loan Bot</b>!\nSecure micro-loans on Polygon USDT.",
        "captcha_prompt": "Solve: <b>{question}</b>",
        "captcha_fail": "Wrong. Attempts left: {left}",
        "captcha_locked": "Too many fails. Try /start later.",
        "terms_title": "📜 Terms of Service",
        "terms_body": "1. Loans are USDT on Polygon.\n2. Late fees apply after due date.\n3. You must repay on time.\n4. Admin may block abusive accounts.\n5. By continuing you accept these terms.",
        "terms_declined": "You declined the terms. Send /start to try again.",
        "choose_lang": "🌐 Choose your language:",
        "bind_wallet_prompt": "💼 Send your <b>Polygon wallet address</b> (0x...) to receive loans:",
        "wallet_invalid": "❌ Invalid Polygon address. Send a valid 0x... address.",
        "wallet_bound": "✅ Wallet bound:\n<code>{wallet}</code>",
        "main_menu": "🏠 <b>MARCENZO Main Menu</b>\nSelect an option:",
        "loan_select_amount": "💰 Credit limit: <b>{limit} USDT</b>\nLevel: {level} ({title})\nSelect amount:",
        "loan_custom_prompt": "✏️ Enter amount ({min} – {max} USDT):",
        "loan_select_inst": "Amount: <b>{amount} USDT</b>\nTotal repay: <b>{total} USDT</b>\nChoose installments:",
        "loan_confirm": "Confirm loan:\n• Principal: {amount} USDT\n• Interest: {interest} USDT\n• Total: {total} USDT\n• Installments: {inst} × {inst_amt} USDT\n• Period: every {days} days",
        "loan_submitted": "✅ Loan request <b>#{id}</b> submitted.\nWaiting for admin approval.",
        "loan_already_active": "❌ You already have an active/pending loan.",
        "no_wallet": "❌ Bind a Polygon wallet in Profile first.",
        "blocked": "🚫 Account blocked.\nReason: {reason}",
        "my_loans_empty": "📋 No loans yet.",
        "my_loans_title": "📋 <b>My Loans</b>",
        "invest_title": "📈 <b>Investment Pool</b>\nPool total: {pool} USDT\nYour invested: {yours} USDT\nEarned: {earned} USDT",
        "invest_amount_prompt": "Enter amount to invest (min {min} USDT):",
        "invest_deposit_info": "Send <b>{amount} USDT</b> (Polygon) to:\n<code>{address}</code>\nThen press Verify.",
        "profile_title": "👤 <b>Profile</b>\nID: <code>{tid}</code>\n@{username}\nLevel: {level} ({title})\nLimit: {limit} USDT\nSuccessful loans: {success}\nBorrowed: {borrowed} | Repaid: {repaid}\nInvested: {invested} | Earned: {earned}\nWallet: <code>{wallet}</code>",
        "password_set_prompt": "🔐 Enter new password (min 6 chars):",
        "password_confirm": "Confirm password:",
        "password_mismatch": "❌ Passwords do not match. Try again.",
        "password_set_ok": "✅ Password set.",
        "password_unlock": "🔐 Enter your password to unlock:",
        "password_wrong": "❌ Wrong password.",
        "support_title": "🆘 <b>Support</b>",
        "support_new_prompt": "Describe your issue:",
        "support_sent": "✅ Ticket #{id} created. We will reply soon.",
        "referral_title": "🎁 <b>Referral</b>\nYour code: <code>{code}</code>\nLink: {link}\nInvited: {count} | Bonus earned: {bonus} USDT",
        "leaderboard_title": "🏆 <b>Leaderboard</b>\n{rows}",
        "guide_text": "📖 <b>Guide</b>\n1. Bind Polygon wallet\n2. Request loan (within credit limit)\n3. Wait admin approval → USDT sent to your wallet\n4. Repay installments to unique deposit addresses\n5. Level up with successful loans → higher limit",
        "admin_panel": "⚙️ <b>Admin Panel</b>",
    },
    "fa": {
        "welcome": "🚀 به ربات وام <b>مارچنزو</b> خوش آمدید!\nوام خرد روی پالیگان (USDT).",
        "captcha_prompt": "حل کنید: <b>{question}</b>",
        "captcha_fail": "غلط. باقیمانده: {left}",
        "captcha_locked": "تلاش زیاد. بعداً /start بزنید.",
        "terms_title": "📜 قوانین",
        "terms_body": "۱. وام‌ها USDT روی پالیگان هستند.\n۲. پس از سررسید جریمه دیرکرد اعمال می‌شود.\n۳. باید به‌موقع بازپرداخت کنید.\n۴. ادمین می‌تواند حساب‌های سوءاستفاده را مسدود کند.\n۵. با ادامه دادن این قوانین را می‌پذیرید.",
        "terms_declined": "قوانین را نپذیرفتید. /start را بزنید.",
        "choose_lang": "🌐 زبان را انتخاب کنید:",
        "bind_wallet_prompt": "💼 آدرس کیف‌پول <b>پالیگان</b> خود را بفرستید (0x...):",
        "wallet_invalid": "❌ آدرس نامعتبر. یک آدرس 0x... معتبر بفرستید.",
        "wallet_bound": "✅ کیف‌پول ثبت شد:\n<code>{wallet}</code>",
        "main_menu": "🏠 <b>منوی اصلی مارچنزو</b>\nیک گزینه را انتخاب کنید:",
        "loan_select_amount": "💰 سقف اعتبار: <b>{limit} USDT</b>\nسطح: {level} ({title})\nمبلغ را انتخاب کنید:",
        "loan_custom_prompt": "✏️ مبلغ را وارد کنید ({min} – {max} USDT):",
        "loan_select_inst": "مبلغ: <b>{amount} USDT</b>\nبازپرداخت کل: <b>{total} USDT</b>\nتعداد اقساط:",
        "loan_confirm": "تأیید وام:\n• اصل: {amount} USDT\n• سود: {interest} USDT\n• کل: {total} USDT\n• اقساط: {inst} × {inst_amt} USDT\n• دوره: هر {days} روز",
        "loan_submitted": "✅ درخواست وام <b>#{id}</b> ثبت شد.\nمنتظر تأیید ادمین.",
        "loan_already_active": "❌ شما وام فعال/در انتظار دارید.",
        "no_wallet": "❌ ابتدا در پروفایل کیف‌پول پالیگان را ثبت کنید.",
        "blocked": "🚫 حساب مسدود است.\nدلیل: {reason}",
        "my_loans_empty": "📋 هنوز وامی ندارید.",
        "my_loans_title": "📋 <b>وام‌های من</b>",
        "invest_title": "📈 <b>استخر سرمایه‌گذاری</b>\nکل استخر: {pool} USDT\nسرمایه‌گذاری شما: {yours} USDT\nسود: {earned} USDT",
        "invest_amount_prompt": "مبلغ سرمایه‌گذاری (حداقل {min} USDT):",
        "invest_deposit_info": "مقدار <b>{amount} USDT</b> (پالیگان) به این آدرس بفرستید:\n<code>{address}</code>\nسپس Verify را بزنید.",
        "profile_title": "👤 <b>پروفایل</b>\nشناسه: <code>{tid}</code>\n@{username}\nسطح: {level} ({title})\nسقف: {limit} USDT\nوام موفق: {success}\nقرض: {borrowed} | بازپرداخت: {repaid}\nسرمایه: {invested} | سود: {earned}\nکیف: <code>{wallet}</code>",
        "password_set_prompt": "🔐 رمز جدید (حداقل ۶ کاراکتر):",
        "password_confirm": "تأیید رمز:",
        "password_mismatch": "❌ رمزها یکسان نیستند.",
        "password_set_ok": "✅ رمز تنظیم شد.",
        "password_unlock": "🔐 رمز عبور را وارد کنید:",
        "password_wrong": "❌ رمز اشتباه است.",
        "support_title": "🆘 <b>پشتیبانی</b>",
        "support_new_prompt": "مشکل خود را بنویسید:",
        "support_sent": "✅ تیکت #{id} ثبت شد.",
        "referral_title": "🎁 <b>معرفی</b>\nکد شما: <code>{code}</code>\nلینک: {link}\nدعوت‌شده: {count} | پاداش: {bonus} USDT",
        "leaderboard_title": "🏆 <b>جدول برترین‌ها</b>\n{rows}",
        "guide_text": "📖 <b>راهنما</b>\n۱. کیف‌پول پالیگان را ثبت کنید\n۲. درخواست وام (در سقف اعتبار)\n۳. پس از تأیید ادمین، USDT به کیف شما واریز می‌شود\n۴. اقساط را به آدرس‌های یکتا پرداخت کنید\n۵. با وام‌های موفق سطح و سقف بالا می‌رود",
        "admin_panel": "⚙️ <b>پنل ادمین</b>",
    },
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    lang = (lang or "en").lower()[:2]
    bucket = TEXTS.get(lang) or TEXTS["en"]
    text = bucket.get(key) or TEXTS["en"].get(key) or key
    try:
        return text.format(**kwargs) if kwargs else text
    except Exception:
        return text
