"""
SQLAlchemy ORM модели для LOOSELINE.
Соответствуют таблицам из tables.sql.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, 
    DECIMAL, TIMESTAMP, Text, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """
    Модель пользователя.
    
    Attributes:
        id: Уникальный ID пользователя (user_123)
        email: Email пользователя (уникальный)
        name: Имя пользователя
        password_hash: Хэш пароля
        stripe_customer_id: ID клиента в Stripe
        is_verified: Верифицирован ли аккаунт
    """
    __tablename__ = "users"
    
    id = Column(String(20), primary_key=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    stripe_customer_id = Column(String(100), unique=True, index=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    balance = relationship("UserBalance", back_populates="user", uselist=False, cascade="all, delete-orphan")
    transactions = relationship("BalanceTransaction", back_populates="user", cascade="all, delete-orphan")
    wallet_operations = relationship("WalletOperation", back_populates="user", cascade="all, delete-orphan")
    payment_methods = relationship("PaymentMethod", back_populates="user", cascade="all, delete-orphan")
    withdrawal_methods = relationship("WithdrawalMethod", back_populates="user", cascade="all, delete-orphan")
    monthly_statements = relationship("MonthlyStatement", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    bets = relationship("Bet", back_populates="user", cascade="all, delete-orphan")


class UserBalance(Base):
    """
    Баланс пользователя.
    
    Attributes:
        user_id: ID пользователя (PRIMARY KEY)
        balance: Текущий баланс
        total_deposited: Сумма всех пополнений
        total_withdrawn: Сумма всех выводов
        total_bet: Сумма всех ставок
        total_won: Сумма всех выигрышей
        total_lost: Сумма всех проигрышей
        currency: Валюта (по умолчанию USD)
    """
    __tablename__ = "users_balance"
    
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance = Column(DECIMAL(15, 2), nullable=False, default=0.00)
    total_deposited = Column(DECIMAL(15, 2), default=0.00)
    total_withdrawn = Column(DECIMAL(15, 2), default=0.00)
    total_bet = Column(DECIMAL(15, 2), default=0.00)
    total_won = Column(DECIMAL(15, 2), default=0.00)
    total_lost = Column(DECIMAL(15, 2), default=0.00)
    currency = Column(String(3), default="USD")
    last_transaction = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="balance")
    
    @property
    def net_profit(self) -> Decimal:
        """Чистая прибыль: выигрыши - проигрыши."""
        return Decimal(self.total_won or 0) - Decimal(self.total_lost or 0)
    
    @property
    def roi_percent(self) -> float:
        """ROI в процентах."""
        if self.total_bet and self.total_bet > 0:
            return float((Decimal(self.total_won or 0) / Decimal(self.total_bet)) * 100)
        return 0.0


class BalanceTransaction(Base):
    """
    История всех транзакций.
    
    transaction_type варианты:
        - deposit: пополнение счёта
        - withdrawal: вывод средств
        - bet_placed: размещение ставки
        - bet_won: выигрыш ставки
        - bet_lost: проигрыш ставки
        - bet_cancelled: отмена ставки
        - coupon_won: выигрыш купона
        - coupon_lost: проигрыш купона
        - bonus_added: добавлен бонус
        - fee_charged: списана комиссия
        - refund: возврат денег
    
    status варианты:
        - completed: завершено
        - pending: в ожидании
        - failed: ошибка
        - cancelled: отменено
    """
    __tablename__ = "balance_transactions"
    
    transaction_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(String(30), nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    balance_before = Column(DECIMAL(15, 2), nullable=False)
    balance_after = Column(DECIMAL(15, 2), nullable=False)
    status = Column(String(20), default="completed")
    description = Column(Text)
    related_entity_type = Column(String(20))
    related_entity_id = Column(Integer)
    stripe_payment_intent_id = Column(String(100))
    stripe_charge_id = Column(String(100))
    transaction_metadata = Column("metadata", JSONB)  # Используем "metadata" как имя колонки в БД
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    processed_at = Column(TIMESTAMP)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    
    __table_args__ = (
        Index("idx_user_transactions", "user_id", "created_at"),
        Index("idx_transaction_type", "transaction_type"),
        Index("idx_stripe_intent_transactions", "stripe_payment_intent_id"),
    )


class WalletOperation(Base):
    """
    Операции пополнения/вывода через Stripe.
    
    operation_type: deposit, withdrawal
    status: pending, completed, failed, cancelled
    """
    __tablename__ = "wallet_operations"
    
    operation_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    operation_type = Column(String(20), nullable=False)
    amount = Column(DECIMAL(15, 2), nullable=False)
    status = Column(String(20), default="pending")
    payment_method = Column(String(50))
    stripe_payment_intent_id = Column(String(100), unique=True)
    stripe_charge_id = Column(String(100))
    stripe_payment_method_id = Column(String(100))
    error_message = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    completed_at = Column(TIMESTAMP)
    expires_at = Column(TIMESTAMP)
    
    # Relationships
    user = relationship("User", back_populates="wallet_operations")
    
    __table_args__ = (
        Index("idx_user_operations", "user_id", "created_at"),
        Index("idx_stripe_intent_operations", "stripe_payment_intent_id"),
    )


class PaymentMethod(Base):
    """
    Сохранённые способы оплаты.
    
    payment_type: card, bank_account
    """
    __tablename__ = "payment_methods"
    
    method_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stripe_payment_method_id = Column(String(100), unique=True, nullable=False)
    payment_type = Column(String(30), nullable=False)
    card_brand = Column(String(20))
    card_last4 = Column(String(4))
    card_exp_month = Column(Integer)
    card_exp_year = Column(Integer)
    bank_name = Column(String(100))
    bank_account_last4 = Column(String(4))
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    last_used = Column(TIMESTAMP)
    
    # Relationships
    user = relationship("User", back_populates="payment_methods")
    
    __table_args__ = (
        Index("idx_user_methods", "user_id"),
    )


class WithdrawalMethod(Base):
    """
    Методы вывода средств.
    
    withdrawal_type: bank_transfer, crypto
    verification_status: pending, verified, rejected
    """
    __tablename__ = "withdrawal_methods"
    
    method_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    withdrawal_type = Column(String(30), nullable=False)
    bank_account_number = Column(String(100))
    bank_code = Column(String(20))
    bank_name = Column(String(100))
    account_holder_name = Column(String(100))
    swift_code = Column(String(20))
    iban = Column(String(100))
    crypto_wallet_address = Column(String(200))
    is_default = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_status = Column(String(20), default="pending")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    verified_at = Column(TIMESTAMP)
    
    # Relationships
    user = relationship("User", back_populates="withdrawal_methods")
    
    __table_args__ = (
        Index("idx_user_withdrawal_methods", "user_id"),
    )


class MonthlyStatement(Base):
    """Месячные финансовые отчёты."""
    __tablename__ = "monthly_statements"
    
    statement_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    opening_balance = Column(DECIMAL(15, 2))
    closing_balance = Column(DECIMAL(15, 2))
    total_deposits = Column(DECIMAL(15, 2), default=0.00)
    total_withdrawals = Column(DECIMAL(15, 2), default=0.00)
    total_bets = Column(DECIMAL(15, 2), default=0.00)
    total_wins = Column(DECIMAL(15, 2), default=0.00)
    total_losses = Column(DECIMAL(15, 2), default=0.00)
    net_profit = Column(DECIMAL(15, 2))
    roi_percent = Column(DECIMAL(10, 2))
    transaction_count = Column(Integer, default=0)
    win_rate_percent = Column(DECIMAL(10, 2))
    generated_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="monthly_statements")
    
    __table_args__ = (
        Index("idx_user_statements", "user_id", "year", "month"),
    )


class AuditLog(Base):
    """
    Аудит логирование всех операций.
    
    action варианты:
        - deposit_initiated: инициирован депозит
        - deposit_completed: депозит завершён
        - withdrawal_initiated: инициирован вывод
        - withdrawal_completed: вывод завершён
        - balance_checked: проверка баланса
        - export_requested: запрос экспорта отчёта
        - suspicious_activity: подозрительная активность
        - stripe_webhook_received: получен webhook от Stripe
    """
    __tablename__ = "audit_log"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False)
    amount = Column(DECIMAL(15, 2))
    ip_address = Column(INET)
    user_agent = Column(Text)
    status = Column(String(20))
    details = Column(JSONB)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index("idx_user_audit", "user_id", "created_at"),
        Index("idx_action", "action"),
    )


class Bet(Base):
    """
    Ставки пользователей.
    
    status: open, resolved, cancelled
    result: win, loss, refund
    """
    __tablename__ = "bets"
    
    bet_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(Integer, nullable=False)
    odds_id = Column(Integer)
    bet_type = Column(String(20), default="single")
    bet_amount = Column(DECIMAL(15, 2), nullable=False)
    coefficient = Column(DECIMAL(10, 3), nullable=False)
    potential_win = Column(DECIMAL(15, 2), nullable=False)
    status = Column(String(20), default="open")
    result = Column(String(20))
    actual_win = Column(DECIMAL(15, 2))
    placed_at = Column(TIMESTAMP, default=datetime.utcnow)
    resolved_at = Column(TIMESTAMP)
    bet_metadata = Column("metadata", JSONB)  # Используем "metadata" как имя колонки в БД
    
    # Relationships
    user = relationship("User", back_populates="bets")
    
    __table_args__ = (
        Index("idx_user_bets", "user_id", "placed_at"),
        Index("idx_bet_status", "status"),
        Index("idx_bet_result", "result"),
    )


