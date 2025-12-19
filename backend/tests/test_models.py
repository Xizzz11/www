"""
Tests for Database Models
"""
import pytest
import sys
import os
from decimal import Decimal

# Добавляем путь к tests для импорта conftest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.conftest import (
    User, UserBalance, BalanceTransaction, 
    WalletOperation, PaymentMethod, WithdrawalMethod,
    Bet, AuditLog
)


class TestUserModel:
    """Tests for User model"""
    
    def test_create_user(self, db_session, sample_user_data):
        """Test creating a new user"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.email == sample_user_data["email"]
        assert user.name == sample_user_data["name"]
        assert user.is_verified == False
    
    def test_user_unique_email(self, db_session, sample_user_data):
        """Test that email must be unique"""
        user1 = User(**sample_user_data)
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(**sample_user_data)
        user2.username = "different_user"
        db_session.add(user2)
        
        with pytest.raises(Exception):
            db_session.commit()


class TestUserBalanceModel:
    """Tests for UserBalance model"""
    
    def test_create_balance(self, db_session, sample_user_data, sample_balance_data):
        """Test creating user balance"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(user_id=user.id, **sample_balance_data)
        db_session.add(balance)
        db_session.commit()
        
        assert balance.user_id is not None
        assert balance.balance == Decimal("5000.00")
        assert balance.locked_in_bets == Decimal("250.00")
    
    def test_available_balance_calculation(self, db_session, sample_user_data):
        """Test available balance = balance - locked_in_bets"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(
            user_id=user.id,
            balance=Decimal("1000.00"),
            locked_in_bets=Decimal("200.00")
        )
        db_session.add(balance)
        db_session.commit()
        
        available = balance.balance - balance.locked_in_bets
        assert available == Decimal("800.00")


class TestBalanceTransactionModel:
    """Tests for BalanceTransaction model"""
    
    def test_create_deposit_transaction(self, db_session, sample_user_data):
        """Test creating a deposit transaction"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        tx = BalanceTransaction(
            user_id=user.id,
            transaction_type="deposit",
            amount=Decimal("500.00"),
            balance_before=Decimal("1000.00"),
            balance_after=Decimal("1500.00"),
            description="Test deposit",
            status="completed"
        )
        db_session.add(tx)
        db_session.commit()
        
        assert tx.transaction_id is not None
        assert tx.transaction_type == "deposit"
        assert tx.amount == Decimal("500.00")
    
    def test_create_bet_transaction(self, db_session, sample_user_data):
        """Test creating a bet transaction"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        tx = BalanceTransaction(
            user_id=user.id,
            transaction_type="bet",
            amount=Decimal("-100.00"),
            balance_before=Decimal("1000.00"),
            balance_after=Decimal("900.00"),
            reference_type="bet",
            reference_id="bet_123",
            status="completed"
        )
        db_session.add(tx)
        db_session.commit()
        
        assert tx.transaction_type == "bet"
        assert tx.reference_type == "bet"


class TestWalletOperationModel:
    """Tests for WalletOperation model"""
    
    def test_create_deposit_operation(self, db_session, sample_user_data):
        """Test creating a deposit operation"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        op = WalletOperation(
            user_id=user.id,
            operation_type="deposit",
            amount=Decimal("500.00"),
            status="pending",
            stripe_payment_intent_id="pi_test123"
        )
        db_session.add(op)
        db_session.commit()
        
        assert op.operation_id is not None
        assert op.operation_type == "deposit"
        assert op.status == "pending"
    
    def test_create_withdrawal_operation(self, db_session, sample_user_data):
        """Test creating a withdrawal operation"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        op = WalletOperation(
            user_id=user.id,
            operation_type="withdrawal",
            amount=Decimal("1000.00"),
            status="processing",
            withdrawal_method_id=1
        )
        db_session.add(op)
        db_session.commit()
        
        assert op.operation_type == "withdrawal"
        assert op.status == "processing"


class TestPaymentMethodModel:
    """Tests for PaymentMethod model"""
    
    def test_create_payment_method(self, db_session, sample_user_data):
        """Test creating a payment method"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        pm = PaymentMethod(
            user_id=user.id,
            stripe_payment_method_id="pm_test123",
            payment_type="card",
            card_brand="Visa",
            card_last4="4242",
            card_exp_month=12,
            card_exp_year=2025,
            is_default=True
        )
        db_session.add(pm)
        db_session.commit()
        
        assert pm.method_id is not None
        assert pm.card_brand == "Visa"
        assert pm.is_default == True


class TestWithdrawalMethodModel:
    """Tests for WithdrawalMethod model"""
    
    def test_create_bank_withdrawal_method(self, db_session, sample_user_data):
        """Test creating a bank withdrawal method"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        wm = WithdrawalMethod(
            user_id=user.id,
            withdrawal_type="bank_account",
            bank_name="Chase Bank",
            account_holder_name="Test User",
            is_verified=True,
            is_default=True
        )
        db_session.add(wm)
        db_session.commit()
        
        assert wm.method_id is not None
        assert wm.bank_name == "Chase Bank"
        assert wm.is_verified == True


class TestBetModel:
    """Tests for Bet model"""
    
    def test_create_bet(self, db_session, sample_user_data):
        """Test creating a bet"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        bet = Bet(
            user_id=user.id,
            event_id=123,
            bet_type="single",
            bet_amount=Decimal("100.00"),
            coefficient=Decimal("2.10"),
            potential_win=Decimal("210.00"),
            status="open"
        )
        db_session.add(bet)
        db_session.commit()
        
        assert bet.bet_id is not None
        assert bet.coefficient == Decimal("2.10")
        assert bet.potential_win == Decimal("210.00")
    
    def test_settle_bet_win(self, db_session, sample_user_data):
        """Test settling a bet as won"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        bet = Bet(
            user_id=user.id,
            event_id=456,
            bet_type="single",
            bet_amount=Decimal("50.00"),
            coefficient=Decimal("1.85"),
            potential_win=Decimal("92.50"),
            status="open"
        )
        db_session.add(bet)
        db_session.commit()
        
        bet.status = "resolved"
        bet.result = "win"
        bet.actual_win = bet.potential_win
        db_session.commit()
        
        assert bet.status == "resolved"
        assert bet.result == "win"
        assert bet.actual_win == Decimal("92.50")


class TestAuditLogModel:
    """Tests for AuditLog model"""
    
    def test_create_audit_log(self, db_session, sample_user_data):
        """Test creating an audit log entry"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        log = AuditLog(
            user_id=user.id,
            action="deposit_initiated",
            ip_address="192.168.1.1",
            status="success"
        )
        db_session.add(log)
        db_session.commit()
        
        assert log.log_id is not None
        assert log.action == "deposit_initiated"
        assert log.status == "success"
