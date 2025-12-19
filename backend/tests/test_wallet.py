"""
Тесты для модуля кошелька.

Покрывают 5 ключевых методов:
1. get_balance()
2. replenish_balance()
3. withdraw_funds()
4. get_bet_history()
5. export_report()

Запуск: pytest tests/test_wallet.py -v
"""

import pytest
import sys
import os
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Добавляем путь к tests для импорта conftest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.conftest import (
    User, UserBalance, BalanceTransaction, 
    WalletOperation, Bet, WithdrawalMethod,
    engine, db_session, TestBase
)

# Импортируем WalletService с подменой моделей (как в test_wallet_complete.py)
import sys
import importlib

# Подменяем модели перед импортом WalletService
class MockORMModelsModule:
    User = User
    UserBalance = UserBalance
    BalanceTransaction = BalanceTransaction
    WalletOperation = WalletOperation
    PaymentMethod = None  # Будет импортирован при необходимости
    WithdrawalMethod = WithdrawalMethod
    Bet = Bet
    AuditLog = None  # Будет импортирован при необходимости
    MonthlyStatement = None

# Подменяем модули
sys.modules['models.orm_models'] = MockORMModelsModule()

# Импортируем недостающие модели
from tests.conftest import PaymentMethod, AuditLog
MockORMModelsModule.PaymentMethod = PaymentMethod
MockORMModelsModule.AuditLog = AuditLog

# Импортируем WalletService
import services.wallet_service as ws_module

# Подменяем модели в уже импортированном модуле
ws_module.User = User
ws_module.UserBalance = UserBalance
ws_module.BalanceTransaction = BalanceTransaction
ws_module.WalletOperation = WalletOperation
ws_module.PaymentMethod = PaymentMethod
ws_module.WithdrawalMethod = WithdrawalMethod
ws_module.Bet = Bet
ws_module.AuditLog = AuditLog

# Перезагружаем модуль чтобы применить изменения
importlib.reload(ws_module)

from services.wallet_service import WalletService


# Используем фикстуры из conftest
@pytest.fixture
def db(db_session):
    """Алиас для db_session из conftest."""
    return db_session


@pytest.fixture
def test_user(db):
    """Создаёт тестового пользователя."""
    user = User(
        id="user_123",
        email="test@example.com",
        name="Test User",
        password_hash="hashed_password",
        stripe_customer_id="cus_test123",
        is_verified=True
    )
    db.add(user)
    
    balance = UserBalance(
        user_id="user_123",
        balance=Decimal("5000.00"),
        total_deposited=Decimal("10000.00"),
        total_withdrawn=Decimal("5000.00"),
        total_bet=Decimal("2500.00"),
        total_won=Decimal("3840.00"),
        total_lost=Decimal("1660.00"),
        currency="USD"
    )
    db.add(balance)
    db.commit()
    
    return user


@pytest.fixture
def test_withdrawal_method(db, test_user):
    """Создаёт тестовый способ вывода."""
    method = WithdrawalMethod(
        user_id="user_123",
        withdrawal_type="bank_transfer",
        bank_name="Test Bank",
        account_holder_name="Test User",
        is_default=True,
        is_verified=True
    )
    db.add(method)
    db.commit()
    return method


@pytest.fixture
def test_bets(db, test_user):
    """Создаёт тестовые ставки."""
    bets = []
    
    # Выигрышные ставки
    for i in range(16):
        bet = Bet(
            user_id="user_123",
            event_id=1000 + i,
            odds_id=1000 + i,
            bet_amount=Decimal("100.00"),
            coefficient=Decimal("1.85"),
            potential_win=Decimal("185.00"),
            status="resolved",
            result="win",
            actual_win=Decimal("185.00"),
            placed_at=datetime.utcnow() - timedelta(days=16-i),
            resolved_at=datetime.utcnow() - timedelta(days=15-i)
        )
        bets.append(bet)
        db.add(bet)
    
    # Проигрышные ставки
    for i in range(9):
        bet = Bet(
            user_id="user_123",
            event_id=2000 + i,
            odds_id=2000 + i,
            bet_amount=Decimal("100.00"),
            coefficient=Decimal("2.10"),
            potential_win=Decimal("210.00"),
            status="resolved",
            result="loss",
            actual_win=None,
            placed_at=datetime.utcnow() - timedelta(days=9-i),
            resolved_at=datetime.utcnow() - timedelta(days=8-i)
        )
        bets.append(bet)
        db.add(bet)
    
    db.commit()
    return bets


# ============================================================================
# ТЕСТЫ get_balance()
# ============================================================================

class TestGetBalance:
    """Тесты метода get_balance()."""
    
    def test_get_balance_success(self, db, test_user):
        """Тест: Получение баланса успешно."""
        result = WalletService.get_balance(db, "user_123")
        
        assert result['success'] is True
        assert result['balance']['current_balance'] == 5000.0
        assert result['balance']['currency'] == 'USD'
        assert result['balance']['total_deposited'] == 10000.0
        assert result['balance']['total_withdrawn'] == 5000.0
    
    def test_get_balance_user_not_found(self, db):
        """Тест: Пользователь не существует."""
        result = WalletService.get_balance(db, "nonexistent_user")
        
        assert result['success'] is False
        assert result['error'] == "User not found"
    
    def test_get_balance_with_bets(self, db, test_user, test_bets):
        """Тест: Баланс с подсчётом выигрышей/проигрышей."""
        result = WalletService.get_balance(db, "user_123")
        
        assert result['success'] is True
        assert result['balance']['win_count'] == 16
        assert result['balance']['lose_count'] == 9
        # Win rate = 16 / (16 + 9) * 100 = 64%
        assert result['balance']['win_rate'] == 64.0
    
    def test_get_balance_net_profit(self, db, test_user):
        """Тест: Расчёт чистой прибыли."""
        result = WalletService.get_balance(db, "user_123")
        
        # net_profit = total_won - total_lost = 3840 - 1660 = 2180
        assert result['balance']['net_profit'] == 2180.0
    
    def test_get_balance_roi_percent(self, db, test_user):
        """Тест: Расчёт ROI."""
        result = WalletService.get_balance(db, "user_123")
        
        # ROI = (total_won / total_bet) * 100 = (3840 / 2500) * 100 = 153.6%
        expected_roi = round(3840.0 / 2500.0 * 100, 2)
        assert result['balance']['roi_percent'] == expected_roi


# ============================================================================
# ТЕСТЫ replenish_balance()
# ============================================================================

class TestReplenishBalance:
    """Тесты метода replenish_balance()."""
    
    def test_replenish_minimum_amount(self, db, test_user):
        """Тест: Минимальная сумма 1.00 USD."""
        result = WalletService.replenish_balance(db, "user_123", 0.50)
        
        assert result['success'] is False
        assert "Minimum deposit" in result['error']
    
    def test_replenish_maximum_amount(self, db, test_user):
        """Тест: Максимальная сумма 100000.00 USD."""
        result = WalletService.replenish_balance(db, "user_123", 150000.0)
        
        assert result['success'] is False
        assert "Maximum deposit" in result['error']
    
    def test_replenish_user_not_found(self, db):
        """Тест: Пользователь не найден."""
        result = WalletService.replenish_balance(db, "nonexistent", 100.0)
        
        assert result['success'] is False
        assert result['error'] == "User not found"
    
    @patch('services.wallet_service.StripeService.create_payment_intent')
    def test_replenish_new_card_returns_client_secret(self, mock_stripe, db, test_user):
        """Тест: Новая карта возвращает client_secret."""
        mock_stripe.return_value = {
            'success': True,
            'client_secret': 'pi_test_secret',
            'intent_id': 'pi_test123',
            'amount': 100.0,
            'status': 'requires_payment_method'
        }
        
        result = WalletService.replenish_balance(
            db, "user_123", 100.0, 
            stripe_payment_method_id=None
        )
        
        assert result['success'] is True
        assert result['action'] == 'requires_payment_form'
        assert result['client_secret'] == 'pi_test_secret'
    
    @patch('services.wallet_service.StripeService.charge_customer')
    def test_replenish_saved_card_updates_balance(self, mock_charge, db, test_user):
        """Тест: Сохранённая карта обновляет баланс."""
        mock_charge.return_value = {
            'success': True,
            'status': 'succeeded',
            'charge_id': 'ch_test123',
            'intent_id': 'pi_test123',
            'amount': 100.0
        }
        
        result = WalletService.replenish_balance(
            db, "user_123", 100.0,
            stripe_payment_method_id="pm_test123"
        )
        
        assert result['success'] is True
        assert result['new_balance'] == 5100.0  # 5000 + 100
        assert result['status'] == 'completed'
    
    @patch('services.wallet_service.StripeService.charge_customer')
    def test_replenish_card_declined(self, mock_charge, db, test_user):
        """Тест: Карта отклонена."""
        mock_charge.return_value = {
            'success': False,
            'error': 'Your card was declined'
        }
        
        result = WalletService.replenish_balance(
            db, "user_123", 100.0,
            stripe_payment_method_id="pm_test123"
        )
        
        assert result['success'] is False
        assert 'declined' in result['error']
    
    @patch('services.wallet_service.StripeService.create_stripe_customer')
    @patch('services.wallet_service.StripeService.create_payment_intent')
    def test_replenish_first_time_creates_stripe_customer(self, mock_intent, mock_customer, db, test_user):
        """Тест 7: Первый раз → создание Stripe Customer."""
        # Убираем stripe_customer_id для первого пополнения
        test_user.stripe_customer_id = None
        db.commit()
        
        mock_customer.return_value = {
            'success': True,
            'stripe_customer_id': 'cus_new123'
        }
        mock_intent.return_value = {
            'success': True,
            'client_secret': 'pi_test_secret',
            'intent_id': 'pi_test123',
            'amount': 100.0,
            'status': 'requires_payment_method'
        }
        
        result = WalletService.replenish_balance(
            db, "user_123", 100.0,
            stripe_payment_method_id=None
        )
        
        assert result['success'] is True
        assert mock_customer.called
        # Проверяем что customer_id сохранён
        db.refresh(test_user)
        assert test_user.stripe_customer_id == 'cus_new123'


# ============================================================================
# ТЕСТЫ withdraw_funds()
# ============================================================================

class TestWithdrawFunds:
    """Тесты метода withdraw_funds()."""
    
    def test_withdraw_success(self, db, test_user, test_withdrawal_method):
        """Тест: Успешный вывод."""
        result = WalletService.withdraw_funds(
            db, "user_123", 1000.0,
            withdrawal_method_id=test_withdrawal_method.method_id
        )
        
        assert result['success'] is True
        assert result['new_balance'] == 4000.0  # 5000 - 1000
        assert result['withdrawal']['status'] == 'pending'
    
    def test_withdraw_insufficient_balance(self, db, test_user, test_withdrawal_method):
        """Тест: Недостаточно денег."""
        result = WalletService.withdraw_funds(
            db, "user_123", 10000.0,  # Больше чем баланс
            withdrawal_method_id=test_withdrawal_method.method_id
        )
        
        assert result['success'] is False
        assert result['error'] == 'Insufficient balance'
        assert result['available_balance'] == 5000.0
    
    def test_withdraw_minimum_amount(self, db, test_user, test_withdrawal_method):
        """Тест: Минимальная сумма 10.00 USD."""
        result = WalletService.withdraw_funds(
            db, "user_123", 5.0,
            withdrawal_method_id=test_withdrawal_method.method_id
        )
        
        assert result['success'] is False
        assert "Minimum withdrawal" in result['error']
    
    def test_withdraw_method_not_found(self, db, test_user):
        """Тест: Способ вывода не найден."""
        result = WalletService.withdraw_funds(
            db, "user_123", 100.0,
            withdrawal_method_id=9999
        )
        
        assert result['success'] is False
        assert result['error'] == 'Withdrawal method not found'
    
    def test_withdraw_method_not_verified(self, db, test_user):
        """Тест: Способ вывода не верифицирован."""
        # Создаём неверифицированный метод
        method = WithdrawalMethod(
            user_id="user_123",
            withdrawal_type="bank_transfer",
            bank_name="Unverified Bank",
            is_verified=False
        )
        db.add(method)
        db.commit()
        
        result = WalletService.withdraw_funds(
            db, "user_123", 100.0,
            withdrawal_method_id=method.method_id
        )
        
        assert result['success'] is False
        assert result['error'] == 'Withdrawal method not verified'
    
    def test_withdraw_balance_deducted_immediately(self, db, test_user, test_withdrawal_method):
        """Тест: Деньги вычтены сразу."""
        initial_balance = 5000.0
        withdrawal_amount = 1000.0
        
        result = WalletService.withdraw_funds(
            db, "user_123", withdrawal_amount,
            withdrawal_method_id=test_withdrawal_method.method_id
        )
        
        # Проверяем что баланс уменьшился
        balance = db.query(UserBalance).filter(
            UserBalance.user_id == "user_123"
        ).first()
        
        assert float(balance.balance) == initial_balance - withdrawal_amount
        assert result['withdrawal']['status'] == 'pending'


# ============================================================================
# ТЕСТЫ get_bet_history()
# ============================================================================

class TestGetBetHistory:
    """Тесты метода get_bet_history()."""
    
    def test_get_history_success(self, db, test_user, test_bets):
        """Тест: Получение истории успешно."""
        result = WalletService.get_bet_history(db, "user_123")
        
        assert result['success'] is True
        assert len(result['bets']) > 0
        assert 'statistics' in result
        assert 'pagination' in result
    
    def test_get_history_with_pagination(self, db, test_user, test_bets):
        """Тест: Пагинация работает."""
        result = WalletService.get_bet_history(
            db, "user_123", limit=10, offset=0
        )
        
        assert result['success'] is True
        assert len(result['bets']) <= 10
        assert result['pagination']['items_per_page'] == 10
    
    def test_get_history_filter_by_result(self, db, test_user, test_bets):
        """Тест: Фильтр по результату."""
        result = WalletService.get_bet_history(
            db, "user_123",
            filters={'result': 'win'}
        )
        
        assert result['success'] is True
        for bet in result['bets']:
            assert bet['result'] == 'win'
    
    def test_get_history_statistics(self, db, test_user, test_bets):
        """Тест: Статистика рассчитывается."""
        result = WalletService.get_bet_history(db, "user_123")
        
        stats = result['statistics']
        assert stats['total_bets'] == 25  # 16 wins + 9 losses
        assert stats['total_wins'] == 16
        assert stats['total_losses'] == 9
    
    def test_get_history_filter_by_period(self, db, test_user, test_bets):
        """Тест 5: Фильтр по периоду."""
        date_from = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        date_to = datetime.utcnow().strftime('%Y-%m-%d')
        
        result = WalletService.get_bet_history(
            db, "user_123",
            filters={'date_from': date_from, 'date_to': date_to}
        )
        
        assert result['success'] is True
        assert len(result['bets']) > 0
    
    def test_get_history_filter_by_status(self, db, test_user, test_bets):
        """Тест 6: Фильтр по статусу."""
        result = WalletService.get_bet_history(
            db, "user_123",
            filters={'status': 'resolved'}
        )
        
        assert result['success'] is True
        for bet in result['bets']:
            assert bet['status'] == 'resolved'
    
    def test_get_history_merges_bets_and_transactions(self, db, test_user, test_bets):
        """Тест 7: Слияние ставок и транзакций."""
        # Создаём транзакцию
        tx = BalanceTransaction(
            user_id="user_123",
            transaction_type="bet_placed",
            amount=Decimal("-100.00"),
            balance_before=Decimal("5000.00"),
            balance_after=Decimal("4900.00"),
            status="completed"
        )
        db.add(tx)
        db.commit()
        
        result = WalletService.get_bet_history(db, "user_123")
        
        assert result['success'] is True
        assert len(result['bets']) > 0
        assert len(result['transactions']) > 0


# ============================================================================
# ТЕСТЫ export_report()
# ============================================================================

class TestExportReport:
    """Тесты метода export_report()."""
    
    def test_export_csv_success(self, db, test_user, test_bets):
        """Тест: Экспорт CSV успешен."""
        result = WalletService.export_report(
            db, "user_123", format="csv"
        )
        
        assert result['success'] is True
        assert result['report']['format'] == 'csv'
        assert result['report']['filename'].endswith('.csv')
        assert 'content' in result['report']
    
    def test_export_invalid_format(self, db, test_user):
        """Тест: Неверный формат."""
        result = WalletService.export_report(
            db, "user_123", format="invalid"
        )
        
        assert result['success'] is False
        assert "Format must be" in result['error']
    
    def test_export_with_date_filter(self, db, test_user, test_bets):
        """Тест: Экспорт с фильтром по дате."""
        date_from = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        date_to = datetime.utcnow().strftime('%Y-%m-%d')
        
        result = WalletService.export_report(
            db, "user_123",
            format="csv",
            date_from=date_from,
            date_to=date_to
        )
        
        assert result['success'] is True
    
    def test_export_has_download_url(self, db, test_user):
        """Тест: Есть ссылка на скачивание."""
        result = WalletService.export_report(db, "user_123")
        
        assert result['success'] is True
        assert 'download_url' in result['report']
        assert result['report']['download_url'].startswith('http')
    
    def test_export_pdf_success(self, db, test_user, test_bets):
        """Тест 5: Экспорт PDF."""
        result = WalletService.export_report(
            db, "user_123", format="pdf"
        )
        
        assert result['success'] is True
        assert result['report']['format'] == 'pdf'
        assert result['report']['filename'].endswith('.pdf')
    
    def test_export_include_exclude_components(self, db, test_user, test_bets):
        """Тест 6: Включение/исключение компонентов."""
        # Только ставки
        result1 = WalletService.export_report(
            db, "user_123",
            format="csv",
            include_bets=True,
            include_transactions=False,
            include_statistics=False
        )
        assert result1['success'] is True
        
        # Только транзакции
        result2 = WalletService.export_report(
            db, "user_123",
            format="csv",
            include_bets=False,
            include_transactions=True,
            include_statistics=False
        )
        assert result2['success'] is True
        
        # Только статистика
        result3 = WalletService.export_report(
            db, "user_123",
            format="csv",
            include_bets=False,
            include_transactions=False,
            include_statistics=True
        )
        assert result3['success'] is True


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


