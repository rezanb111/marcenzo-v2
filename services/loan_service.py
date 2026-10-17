"""
Loan business logic: create, approve, interest calculation, level upgrades.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from database.models import User, Loan, Installment, Investment, ProcessedTx
from config import settings
from services.polygon_pay import polygon_pay


LEVEL_TITLES = {
    1: "Bronze",
    2: "Silver",
    3: "Gold",
    4: "Platinum",
    5: "Diamond",
    6: "Master",
}

def level_title(level: int) -> str:
    if level >= 7:
        return "Legend"
    return LEVEL_TITLES.get(level, f"Level {level}")


def calculate_late_fee(base_amount: float, due_date: datetime, now: Optional[datetime] = None) -> float:
    now = now or datetime.utcnow()
    if now <= due_date:
        return 0.0
    days_late = (now - due_date).days
    periods = days_late // settings.INTEREST_PERIOD_DAYS
    if periods <= 0:
        return 0.0
    fee = base_amount * (settings.LATE_INCREASE_PERCENT / 100.0) * periods
    return round(fee, 6)


def payable_amount(installment: Installment, now: Optional[datetime] = None) -> float:
    late = calculate_late_fee(installment.amount, installment.due_date, now)
    return round(installment.amount + late, 6)


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    full_name: Optional[str] = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        changed = False
        if username and user.username != username:
            user.username = username
            changed = True
        if full_name and user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if changed:
            await session.commit()
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        language=settings.DEFAULT_LANGUAGE,
        level=1,
        credit_limit=settings.INITIAL_CREDIT_LIMIT,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    logger.info(f"New user created: {telegram_id}")
    return user


async def has_active_or_pending_loan(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        select(Loan).where(
            and_(Loan.user_id == user_id, Loan.status.in_(["PENDING", "ACTIVE"]))
        )
    )
    return result.scalar_one_or_none() is not None


async def create_loan_request(
    session: AsyncSession,
    user: User,
    amount: float,
    installments_count: int,
    discount_percent: float = 0.0,
    promo_code: str | None = None,
) -> Loan:
    base_interest_pct = settings.LOAN_INTEREST_PERCENT
    effective_pct = max(0.0, base_interest_pct - discount_percent)
    interest_amount = round(amount * (effective_pct / 100.0), 6)
    total_repay = round(amount + interest_amount, 6)
    installment_amount = round(total_repay / installments_count, 6)

    from datetime import date
    today = date.today().isoformat()
    if user.loans_today_date != today:
        user.loans_today = 0
        user.loans_today_date = today
    if user.loans_today >= settings.MAX_LOANS_PER_DAY:
        raise ValueError(f"Daily loan limit reached ({settings.MAX_LOANS_PER_DAY})")

    loan = Loan(
        user_id=user.id,
        amount=amount,
        interest_percent=effective_pct,
        interest_amount=interest_amount,
        total_repay=total_repay,
        currency=settings.DEFAULT_CURRENCY,
        installments_count=installments_count,
        installment_amount=installment_amount,
        status="PENDING",
        promo_code=promo_code,
        discount_percent=discount_percent,
    )
    session.add(loan)
    user.loans_today += 1
    await session.commit()
    await session.refresh(loan)
    return loan


async def approve_loan(session: AsyncSession, loan: Loan, user: User) -> Tuple[bool, str]:
    if not user.polygon_wallet:
        return False, "User has no Polygon wallet bound."
    if not polygon_pay.is_valid_address(user.polygon_wallet):
        return False, "Invalid Polygon wallet address."

    success, tx_hash, msg = await polygon_pay.disburse_usdt(user.polygon_wallet, loan.amount)
    if not success:
        return False, f"Disbursement failed: {msg}"

    session.add(ProcessedTx(tx_hash=tx_hash, purpose="disburse", related_id=loan.id))
    now = datetime.utcnow()
    loan.status = "ACTIVE"
    loan.disburse_tx_hash = tx_hash
    loan.issued_at = now
    loan.due_date = now + timedelta(days=settings.INSTALLMENT_PERIOD_DAYS * loan.installments_count)

    for i in range(1, loan.installments_count + 1):
        due = now + timedelta(days=settings.INSTALLMENT_PERIOD_DAYS * i)
        inst = Installment(
            loan_id=loan.id,
            number=i,
            amount=loan.installment_amount,
            status="PENDING",
            due_date=due,
        )
        session.add(inst)
        await session.flush()
        addr, priv = polygon_pay.generate_installment_deposit(inst.id, user.telegram_id)
        inst.deposit_address = addr
        inst.deposit_private_key = priv

    user.total_borrowed = round(user.total_borrowed + loan.amount, 6)
    await session.commit()
    logger.info(f"Loan #{loan.id} approved & disbursed | tx={tx_hash}")
    return True, tx_hash


async def reject_loan(session: AsyncSession, loan: Loan) -> None:
    loan.status = "REJECTED"
    await session.commit()


async def mark_installment_paid(
    session: AsyncSession,
    installment: Installment,
    paid_amount: float,
    sweep_tx: str,
) -> None:
    installment.status = "PAID"
    installment.paid_amount = paid_amount
    installment.paid_at = datetime.utcnow()
    installment.sweep_tx_hash = sweep_tx
    session.add(ProcessedTx(tx_hash=sweep_tx, purpose="sweep_installment", related_id=installment.id))

    loan = installment.loan
    result = await session.execute(select(Installment).where(Installment.loan_id == loan.id))
    all_inst = result.scalars().all()
    if all(i.status == "PAID" for i in all_inst):
        loan.status = "COMPLETED"
        loan.completed_at = datetime.utcnow()
        user = loan.user
        user.successful_loans += 1
        user.total_repaid = round(user.total_repaid + loan.total_repay, 6)

        if user.successful_loans % settings.SUCCESSFUL_LOANS_FOR_UPGRADE == 0:
            user.level += 1
            new_limit = min(user.credit_limit * settings.CREDIT_MULTIPLIER, settings.MAX_LOAN_AMOUNT)
            user.credit_limit = new_limit
            logger.info(f"User {user.telegram_id} upgraded to level {user.level}, limit={new_limit}")

        await _distribute_interest(session, loan.interest_amount)

    await session.commit()


async def _distribute_interest(session: AsyncSession, interest_pool: float) -> None:
    result = await session.execute(select(Investment).where(Investment.status == "ACTIVE"))
    invs = result.scalars().all()
    if not invs:
        return
    total_stake = sum(i.amount for i in invs)
    if total_stake <= 0:
        return
    for inv in invs:
        share = round(interest_pool * (inv.amount / total_stake), 6)
        inv.earned = round(inv.earned + share, 6)
        user_result = await session.execute(select(User).where(User.id == inv.user_id))
        u = user_result.scalar_one()
        u.earned_interest = round(u.earned_interest + share, 6)
    await session.commit()


async def create_investment(session: AsyncSession, user: User, amount: float) -> Investment:
    inv = Investment(user_id=user.id, amount=amount, status="PENDING")
    session.add(inv)
    await session.flush()
    addr, priv = polygon_pay.generate_investment_deposit(inv.id, user.telegram_id)
    inv.deposit_address = addr
    inv.deposit_private_key = priv
    await session.commit()
    await session.refresh(inv)
    return inv


async def activate_investment(
    session: AsyncSession, inv: Investment, paid_amount: float, tx_hash: str
) -> None:
    inv.status = "ACTIVE"
    inv.deposit_tx_hash = tx_hash
    inv.activated_at = datetime.utcnow()
    session.add(ProcessedTx(tx_hash=tx_hash, purpose="invest", related_id=inv.id))
    user = inv.user
    user.invested_amount = round(user.invested_amount + inv.amount, 6)
    await session.commit()
