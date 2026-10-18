from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, BigInteger
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    level: Mapped[int] = mapped_column(Integer, default=1)
    credit_limit: Mapped[float] = mapped_column(Float, default=5.0)
    successful_loans: Mapped[int] = mapped_column(Integer, default=0)
    total_borrowed: Mapped[float] = mapped_column(Float, default=0.0)
    total_repaid: Mapped[float] = mapped_column(Float, default=0.0)
    invested_amount: Mapped[float] = mapped_column(Float, default=0.0)
    earned_interest: Mapped[float] = mapped_column(Float, default=0.0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    password_salt: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    polygon_wallet: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    captcha_fails: Mapped[int] = mapped_column(Integer, default=0)
    captcha_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    referral_code: Mapped[Optional[str]] = mapped_column(String(16), unique=True, nullable=True, index=True)
    referred_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    referral_bonus_earned: Mapped[float] = mapped_column(Float, default=0.0)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    notify_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_promos: Mapped[bool] = mapped_column(Boolean, default=True)
    loans_today: Mapped[int] = mapped_column(Integer, default=0)
    loans_today_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    loans: Mapped[List["Loan"]] = relationship("Loan", back_populates="user")
    investments: Mapped[List["Investment"]] = relationship("Investment", back_populates="user")
    tickets: Mapped[List["SupportTicket"]] = relationship("SupportTicket", back_populates="user")


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    interest_percent: Mapped[float] = mapped_column(Float, default=10.0)
    interest_amount: Mapped[float] = mapped_column(Float, nullable=False)
    total_repay: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USDT")
    installments_count: Mapped[int] = mapped_column(Integer, default=1)
    installment_amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    disburse_tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    promo_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    discount_percent: Mapped[float] = mapped_column(Float, default=0.0)
    early_repay_discount: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="loans")
    installments: Mapped[List["Installment"]] = relationship(
        "Installment", back_populates="loan", cascade="all, delete-orphan"
    )


class Installment(Base):
    __tablename__ = "installments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loan_id: Mapped[int] = mapped_column(Integer, ForeignKey("loans.id"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deposit_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    deposit_private_key: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    sweep_tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    last_reminded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    loan: Mapped["Loan"] = relationship("Loan", back_populates="installments")


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    deposit_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    deposit_private_key: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    deposit_tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    earned: Mapped[float] = mapped_column(Float, default=0.0)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="investments")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    admin_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="tickets")


class ProcessedTx(Base):
    __tablename__ = "processed_txs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tx_hash: Mapped[str] = mapped_column(String(66), unique=True, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    related_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    discount_percent: Mapped[float] = mapped_column(Float, default=5.0)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    min_loan_amount: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AdminReportLog(Base):
    __tablename__ = "admin_report_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    recipients: Mapped[int] = mapped_column(Integer, default=0)


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    bonus_amount: Mapped[float] = mapped_column(Float, default=0.5)
    reason: Mapped[str] = mapped_column(String(64), default="signup")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AdminAuditLog(Base):
    """Trail of sensitive admin actions for accountability."""
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
