# MARCENZO Loan Bot v2

Premium Telegram Loan Protocol on Polygon USDT.

Bot: @See30bot | Support: @marcenzo

## New in v2
1. Periodic admin report every 3 hours
2. Installment reminders
3. Treasury low-balance alert
4. Referral system with deep links
5. Promo / discount codes
6. Maintenance mode
7. Admin broadcast
8. Daily loan velocity limit
9. Force report button
10. Early repayment discount setting
11. Notification preferences
12. AdminReportLog history

## Install
```bash
cd /root && unzip marcenzo-loan-bot.zip && cd marcenzo-loan-bot
chmod +x deploy.sh && ./deploy.sh
journalctl -u loan-bot -f
```

Fill `.env` from `.env.SERVER_TEMPLATE` with real secrets on the server only.

Full source is also available as ZIP from the build pipeline.
