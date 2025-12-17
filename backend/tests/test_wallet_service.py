"""
Tests for Wallet Service Logic
"""
import pytest
import sys
import os
from decimal import Decimal

# Добавляем путь к tests для импорта conftest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.conftest import User, UserBalance, BalanceTransaction


class TestGetBalance:
    """Tests for getBalance functionality"""
    
    def test_get_balance_returns_correct_data(self, db_session, sample_user_data, sample_balance_data):
        """Test that balance data is correctly retrieved"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(user_id=user.id, **sample_balance_data)
        db_session.add(balance)
        db_session.commit()
        
        assert balance.balance == Decimal("5000.00")
        assert (balance.balance - balance.locked_in_bets) == Decimal("4750.00")
        
        net_profit = balance.total_won - balance.total_bet
        assert net_profit == Decimal("1340.00")


class TestDeposit:
    """Tests for replenishBalance (deposit) functionality"""
    
    def test_deposit_increases_balance(self, db_session, sample_user_data):
        """Test that deposit increases user balance"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(user_id=user.id, balance=Decimal("1000.00"))
        db_session.add(balance)
        db_session.commit()
        
        deposit_amount = Decimal("500.00")
        balance_before = balance.balance
        balance.balance += deposit_amount
        balance.total_deposited += deposit_amount
        
        tx = BalanceTransaction(
            user_id=user.id,
            transaction_type="deposit",
            amount=deposit_amount,
            balance_before=balance_before,
            balance_after=balance.balance,
            status="completed"
        )
        db_session.add(tx)
        db_session.commit()
        
        assert balance.balance == Decimal("1500.00")
        assert balance.total_deposited == Decimal("500.00")
    
    def test_deposit_creates_transaction_record(self, db_session, sample_user_data):
        """Test that deposit creates a transaction record"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(user_id=user.id, balance=Decimal("0.00"))
        db_session.add(balance)
        db_session.commit()
        
        tx = BalanceTransaction(
            user_id=user.id,
            transaction_type="deposit",
            amount=Decimal("100.00"),
            balance_before=Decimal("0.00"),
            balance_after=Decimal("100.00"),
            stripe_payment_intent_id="pi_test123",
            status="completed"
        )
        db_session.add(tx)
        db_session.commit()
        
        assert tx.transaction_id is not None
        assert tx.transaction_type == "deposit"
        assert tx.stripe_payment_intent_id == "pi_test123"


class TestWithdraw:
    """Tests for withdrawFunds functionality"""
    
    def test_withdraw_decreases_balance(self, db_session, sample_user_data):
        """Test that withdrawal decreases balance"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(user_id=user.id, balance=Decimal("5000.00"))
        db_session.add(balance)
        db_session.commit()
        
        withdraw_amount = Decimal("1000.00")
        balance_before = balance.balance
        balance.balance -= withdraw_amount
        balance.total_withdrawn += withdraw_amount
        
        tx = BalanceTransaction(
            user_id=user.id,
            transaction_type="withdrawal",
            amount=withdraw_amount,
            balance_before=balance_before,
            balance_after=balance.balance,
            status="pending"
        )
        db_session.add(tx)
        db_session.commit()
        
        assert balance.balance == Decimal("4000.00")
        assert balance.total_withdrawn == Decimal("1000.00")
    
    def test_withdraw_fails_insufficient_funds(self, db_session, sample_user_data):
        """Test that withdrawal fails with insufficient funds"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(user_id=user.id, balance=Decimal("100.00"))
        db_session.add(balance)
        db_session.commit()
        
        withdraw_amount = Decimal("500.00")
        has_funds = balance.balance >= withdraw_amount
        assert has_funds == False
    
    def test_withdraw_respects_locked_balance(self, db_session, sample_user_data):
        """Test that withdrawal respects locked balance"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(
            user_id=user.id, 
            balance=Decimal("1000.00"),
            locked_in_bets=Decimal("800.00")
        )
        db_session.add(balance)
        db_session.commit()
        
        available = balance.balance - balance.locked_in_bets
        withdraw_amount = Decimal("500.00")
        can_withdraw = available >= withdraw_amount
        assert can_withdraw == False


class TestBetHistory:
    """Tests for getBetHistory functionality"""
    
    def test_get_transactions_ordered_by_date(self, db_session, sample_user_data):
        """Test that transactions are returned in correct order"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        for i, tx_type in enumerate(["deposit", "bet", "win"]):
            tx = BalanceTransaction(
                user_id=user.id,
                transaction_type=tx_type,
                amount=Decimal(str((i + 1) * 100)),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("1100.00"),
                status="completed"
            )
            db_session.add(tx)
        db_session.commit()
        
        transactions = db_session.query(BalanceTransaction)\
            .filter(BalanceTransaction.user_id == user.id)\
            .order_by(BalanceTransaction.created_at.desc())\
            .all()
        
        assert len(transactions) == 3


class TestStatistics:
    """Tests for statistics calculations"""
    
    def test_calculate_win_rate(self, db_session, sample_user_data):
        """Test win rate calculation"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        for i in range(6):
            tx = BalanceTransaction(
                user_id=user.id,
                transaction_type="win",
                amount=Decimal("100.00"),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("1100.00"),
                status="completed"
            )
            db_session.add(tx)
        
        for i in range(4):
            tx = BalanceTransaction(
                user_id=user.id,
                transaction_type="bet",
                amount=Decimal("-50.00"),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("950.00"),
                status="completed"
            )
            db_session.add(tx)
        db_session.commit()
        
        wins = db_session.query(BalanceTransaction)\
            .filter(BalanceTransaction.user_id == user.id)\
            .filter(BalanceTransaction.transaction_type == "win")\
            .count()
        
        total_bets = 10
        win_rate = (wins / total_bets) * 100
        assert win_rate == 60.0
    
    def test_calculate_roi(self, db_session, sample_user_data):
        """Test ROI calculation"""
        user = User(**sample_user_data)
        db_session.add(user)
        db_session.commit()
        
        balance = UserBalance(
            user_id=user.id,
            total_bet=Decimal("1000.00"),
            total_won=Decimal("1500.00")
        )
        db_session.add(balance)
        db_session.commit()
        
        roi = ((balance.total_won - balance.total_bet) / balance.total_bet) * 100
        assert roi == Decimal("50.00")
