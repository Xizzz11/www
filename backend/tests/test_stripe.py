"""
Тесты для Stripe сервиса.

Покрывают 7 функций:
1. create_payment_intent()
2. confirm_payment()
3. create_stripe_customer()
4. save_payment_method()
5. charge_customer()
6. get_payment_methods()
7. construct_webhook_event()

Запуск: pytest tests/test_stripe.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
import stripe

from services.stripe_service import StripeService


# ============================================================================
# ТЕСТЫ create_payment_intent()
# ============================================================================

class TestCreatePaymentIntent:
    """Тесты создания Payment Intent."""
    
    @patch('services.stripe_service.stripe.PaymentIntent.create')
    def test_create_payment_intent_success(self, mock_create):
        """Тест: Успешное создание Payment Intent."""
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.client_secret = "pi_test123_secret_xxx"
        mock_intent.status = "requires_payment_method"
        mock_create.return_value = mock_intent
        
        result = StripeService.create_payment_intent(
            amount=100.0,
            user_id="user_123"
        )
        
        assert result['success'] is True
        assert result['intent_id'] == "pi_test123"
        assert result['client_secret'] == "pi_test123_secret_xxx"
        assert result['amount'] == 100.0
    
    @patch('services.stripe_service.stripe.PaymentIntent.create')
    def test_create_payment_intent_with_customer(self, mock_create):
        """Тест: С указанием Stripe Customer."""
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.client_secret = "secret"
        mock_intent.status = "requires_payment_method"
        mock_create.return_value = mock_intent
        
        result = StripeService.create_payment_intent(
            amount=100.0,
            user_id="user_123",
            stripe_customer_id="cus_test456"
        )
        
        assert result['success'] is True
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args.kwargs['customer'] == "cus_test456"
    
    @patch('services.stripe_service.stripe.PaymentIntent.create')
    def test_create_payment_intent_stripe_error(self, mock_create):
        """Тест: Ошибка Stripe."""
        mock_create.side_effect = stripe.error.StripeError("API Error")
        
        result = StripeService.create_payment_intent(100.0, "user_123")
        
        assert result['success'] is False
        assert 'error' in result


# ============================================================================
# ТЕСТЫ confirm_payment()
# ============================================================================

class TestConfirmPayment:
    """Тесты подтверждения платежа."""
    
    @patch('services.stripe_service.stripe.PaymentIntent.retrieve')
    def test_confirm_payment_success(self, mock_retrieve):
        """Тест: Успешное подтверждение."""
        mock_intent = MagicMock()
        mock_intent.status = "succeeded"
        mock_intent.amount = 10000  # В центах
        mock_intent.currency = "usd"
        mock_intent.latest_charge = "ch_test123"
        mock_intent.metadata = {"user_id": "user_123"}
        mock_retrieve.return_value = mock_intent
        
        result = StripeService.confirm_payment("pi_test123")
        
        assert result['success'] is True
        assert result['status'] == "succeeded"
        assert result['amount'] == 100.0  # Конвертировано из центов
        assert result['charge_id'] == "ch_test123"
    
    @patch('services.stripe_service.stripe.PaymentIntent.retrieve')
    def test_confirm_payment_not_found(self, mock_retrieve):
        """Тест: Payment Intent не найден."""
        mock_retrieve.side_effect = stripe.error.InvalidRequestError(
            "No such payment intent", "id"
        )
        
        result = StripeService.confirm_payment("pi_invalid")
        
        assert result['success'] is False
        assert result['error'] == "Payment intent not found"


# ============================================================================
# ТЕСТЫ create_stripe_customer()
# ============================================================================

class TestCreateStripeCustomer:
    """Тесты создания Stripe Customer."""
    
    @patch('services.stripe_service.stripe.Customer.create')
    def test_create_customer_success(self, mock_create):
        """Тест: Успешное создание Customer."""
        mock_customer = MagicMock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer
        
        result = StripeService.create_stripe_customer(
            "user_123", "test@example.com", "Test User"
        )
        
        assert result['success'] is True
        assert result['stripe_customer_id'] == "cus_test123"
    
    @patch('services.stripe_service.stripe.Customer.create')
    def test_create_customer_invalid_email(self, mock_create):
        """Тест: Неверный email."""
        mock_create.side_effect = stripe.error.InvalidRequestError(
            "Invalid email", "email"
        )
        
        result = StripeService.create_stripe_customer(
            "user_123", "invalid", "Test"
        )
        
        assert result['success'] is False


# ============================================================================
# ТЕСТЫ save_payment_method()
# ============================================================================

class TestSavePaymentMethod:
    """Тесты сохранения способа оплаты."""
    
    @patch('services.stripe_service.stripe.PaymentMethod.attach')
    def test_save_payment_method_success(self, mock_attach):
        """Тест: Успешное сохранение."""
        mock_pm = MagicMock()
        mock_pm.id = "pm_test123"
        mock_pm.type = "card"
        mock_pm.card = MagicMock()
        mock_pm.card.brand = "visa"
        mock_pm.card.last4 = "4242"
        mock_pm.card.exp_month = 12
        mock_pm.card.exp_year = 2025
        mock_attach.return_value = mock_pm
        
        result = StripeService.save_payment_method(
            "cus_test123", "pm_test456"
        )
        
        assert result['success'] is True
        assert result['payment_method']['id'] == "pm_test123"
        assert result['payment_method']['card']['last4'] == "4242"


# ============================================================================
# ТЕСТЫ charge_customer()
# ============================================================================

class TestChargeCustomer:
    """Тесты списания с сохранённой карты."""
    
    @patch('services.stripe_service.stripe.PaymentIntent.create')
    def test_charge_customer_success(self, mock_create):
        """Тест: Успешное списание."""
        mock_intent = MagicMock()
        mock_intent.status = "succeeded"
        mock_intent.latest_charge = "ch_test123"
        mock_intent.id = "pi_test123"
        mock_create.return_value = mock_intent
        
        result = StripeService.charge_customer(
            "cus_test123", 100.0, "pm_test456"
        )
        
        assert result['success'] is True
        assert result['status'] == "succeeded"
        assert result['charge_id'] == "ch_test123"
    
    @patch('services.stripe_service.stripe.PaymentIntent.create')
    def test_charge_customer_card_declined(self, mock_create):
        """Тест: Карта отклонена."""
        # Создаём мок CardError с user_message
        class MockCardError(stripe.error.CardError):
            def __init__(self):
                super().__init__(
                    message="Your card was declined",
                    param="card",
                    code="card_declined"
                )
                self._user_message = "Your card was declined"
            
            @property
            def user_message(self):
                return self._user_message
        
        error = MockCardError()
        mock_create.side_effect = error
        
        result = StripeService.charge_customer(
            "cus_test123", 100.0, "pm_test456"
        )
        
        assert result['success'] is False
        assert "declined" in result['error'].lower() or "error" in result['error'].lower()


# ============================================================================
# ТЕСТЫ get_payment_methods()
# ============================================================================

class TestGetPaymentMethods:
    """Тесты получения способов оплаты."""
    
    @patch('services.stripe_service.stripe.PaymentMethod.list')
    def test_get_payment_methods_success(self, mock_list):
        """Тест: Успешное получение."""
        mock_pm = MagicMock()
        mock_pm.id = "pm_test123"
        mock_pm.type = "card"
        mock_pm.created = 1234567890
        mock_pm.card = MagicMock()
        mock_pm.card.brand = "visa"
        mock_pm.card.last4 = "4242"
        mock_pm.card.exp_month = 12
        mock_pm.card.exp_year = 2025
        mock_pm.card.funding = "credit"
        
        mock_list.return_value = MagicMock(data=[mock_pm])
        
        result = StripeService.get_payment_methods("cus_test123")
        
        assert result['success'] is True
        assert len(result['payment_methods']) == 1
        assert result['payment_methods'][0]['card']['brand'] == "visa"


# ============================================================================
# ТЕСТЫ construct_webhook_event()
# ============================================================================

class TestConstructWebhookEvent:
    """Тесты обработки webhook."""
    
    @patch('services.stripe_service.stripe.Webhook.construct_event')
    @patch('services.stripe_service.settings')
    def test_webhook_valid_signature(self, mock_settings, mock_construct):
        """Тест: Валидная подпись."""
        mock_settings.stripe_webhook_secret = "whsec_test123"
        mock_event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123"}}
        }
        mock_construct.return_value = mock_event
        
        result = StripeService.construct_webhook_event(
            b'{"test": "body"}',
            "sig_header"
        )
        
        assert result['success'] is True
        assert result['event']['type'] == "payment_intent.succeeded"
    
    @patch('services.stripe_service.stripe.Webhook.construct_event')
    @patch('services.stripe_service.settings')
    def test_webhook_invalid_signature(self, mock_settings, mock_construct):
        """Тест: Невалидная подпись."""
        mock_settings.stripe_webhook_secret = "whsec_test123"
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig"
        )
        
        result = StripeService.construct_webhook_event(
            b'{"test": "body"}',
            "invalid_sig"
        )
        
        assert result['success'] is False
        assert result['error'] == "Invalid signature"


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


