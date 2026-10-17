# ربات وام مارچنزو (MARCENZO) v2

پروتکل وام پریمیوم روی شبکه پالیگان (USDT)

ربات: @See30bot | پشتیبانی: @marcenzo

## نصب یک‌خطی

```bash
cd /root && git clone https://github.com/rezanb111/marcenzo-v2.git marcenzo-loan-bot
cd marcenzo-loan-bot
# ویرایش .env با مقادیر واقعی
cp .env.SERVER_TEMPLATE .env && nano .env
chmod +x deploy.sh && ./deploy.sh
journalctl -u loan-bot -f
```

## امکانات v2
- گزارش هر ۳ ساعت به ادمین‌ها
- یادآوری اقساط
- سیستم دعوت + کد تخفیف
- حالت تعمیرات + پیام همگانی
- پرداخت USDT پالیگان با آدرس یکتا
