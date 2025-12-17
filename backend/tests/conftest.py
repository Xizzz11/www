"""
Test Configuration - Standalone models for testing
Matches real ORM models structure
"""
import pytest
from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Boolean, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

# Create test-specific Base
TestBase = declarative_base()

# === Test Models (mirrors production models) ===

class User(TestBase):
    __tablename__ = "users"
    id = Column(String(20), primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    username = Column(String(100))  # Для совместимости
    password_hash = Column(String(255), nullable=False)
    stripe_customer_id = Column(String(100), unique=True)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserBalance(TestBase):
    __tablename__ = "users_balance"
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    balance = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    locked_in_bets = Column(Numeric(15, 2), default=Decimal("0.00"))
    total_deposited = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_withdrawn = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_bet = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_won = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_lost = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    last_transaction = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BalanceTransaction(TestBase):
    __tablename__ = "balance_transactions"
    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(String(30), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    balance_before = Column(Numeric(15, 2), nullable=False)
    balance_after = Column(Numeric(15, 2), nullable=False)
    reference_type = Column(String(50))
    reference_id = Column(String(100))
    description = Column(Text)
    status = Column(String(20), default="completed")
    related_entity_type = Column(String(20))
    related_entity_id = Column(Integer)
    stripe_payment_intent_id = Column(String(100))
    stripe_charge_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    # metadata - зарезервированное имя в SQLAlchemy, не используем в тестах


class WalletOperation(TestBase):
    __tablename__ = "wallet_operations"
    operation_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    operation_type = Column(String(20), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    status = Column(String(20), default="pending")
    payment_method = Column(String(50))
    stripe_payment_intent_id = Column(String(100))
    stripe_charge_id = Column(String(100))
    stripe_payment_method_id = Column(String(100))
    withdrawal_method_id = Column(Integer)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)


class PaymentMethod(TestBase):
    __tablename__ = "payment_methods"
    method_id = Column(Integer, primary_key=True, autoincrement=True)  # SQLite лучше работает с Integer
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stripe_payment_method_id = Column(String(100), unique=True, nullable=False)
    payment_type = Column(String(30), nullable=False)
    card_brand = Column(String(20))
    card_last4 = Column(String(4))
    card_exp_month = Column(Integer)
    card_exp_year = Column(Integer)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WithdrawalMethod(TestBase):
    __tablename__ = "withdrawal_methods"
    method_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    withdrawal_type = Column(String(30), nullable=False)
    bank_name = Column(String(100))
    account_holder_name = Column(String(100))
    is_verified = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Bet(TestBase):
    __tablename__ = "bets"
    bet_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(Integer, nullable=False)
    odds_id = Column(Integer)  # Добавлено для совместимости
    bet_type = Column(String(20), default="single")
    bet_amount = Column(Numeric(15, 2), nullable=False)
    coefficient = Column(Numeric(10, 3), nullable=False)
    potential_win = Column(Numeric(15, 2), nullable=False)
    actual_win = Column(Numeric(15, 2))
    status = Column(String(20), default="open")
    result = Column(String(20))
    placed_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)  # Добавлено для совместимости (вместо settled_at)
    settled_at = Column(DateTime)  # Оставляем для обратной совместимости
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(TestBase):
    __tablename__ = "audit_log"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(100), nullable=False)
    amount = Column(Numeric(15, 2))
    ip_address = Column(String(45))
    user_agent = Column(Text)  # Добавлено для совместимости
    status = Column(String(20), default="success")
    details = Column(Text)  # Для совместимости (в реальной модели JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)


# Use SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def engine():
    """Create fresh test engine for each test"""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestBase.metadata.create_all(bind=engine)
    yield engine
    TestBase.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(engine):
    """Create a new database session for each test"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "id": "user_test123",
        "email": "test@example.com",
        "name": "Test User",
        "username": "testuser",  # Для совместимости
        "password_hash": "hashed_password_123",
        "stripe_customer_id": "cus_test123"
    }

@pytest.fixture
def sample_balance_data():
    """Sample balance data for testing"""
    return {
        "balance": Decimal("5000.00"),
        "locked_in_bets": Decimal("250.00"),
        "total_deposited": Decimal("10000.00"),
        "total_withdrawn": Decimal("5000.00"),
        "total_bet": Decimal("2500.00"),
        "total_won": Decimal("3840.00")
    }
