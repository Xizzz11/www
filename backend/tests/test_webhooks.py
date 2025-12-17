"""
Тесты для Stripe webhook обработчика.

Запуск: pytest tests/test_webhooks.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime

from fastapi.testclient import TestClient

from main import app
from models.orm_models import WalletOperation, UserBalance
from tests.conftest import db_session, User


client = TestClient(app)


class TestStripeWebhook:
    """Тесты webhook endpoint."""
    
    @patch('routes.webhooks.StripeService.construct_webhook_event')
    def test_webhook_missing_signature(self, mock_construct):
        """Тест: Отсутствует подпись."""
        response = client.post(
            "/api/webhook/stripe",
            content=b'{"test": "data"}',
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Missing signature" in response.json()['detail']
    
    @patch('routes.webhooks.StripeService.construct_webhook_event')
    def test_webhook_invalid_signature(self, mock_construct):
        """Тест: Невалидная подпись."""
        mock_construct.return_value = {
            'success': False,
            'error': 'Invalid signature'
        }
        
        response = client.post(
            "/api/webhook/stripe",
            content=b'{"test": "data"}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "invalid_sig"
            }
        )
        
        assert response.status_code == 400
    
    @patch('routes.webhooks.StripeService.construct_webhook_event')
    @patch('routes.webhooks._handle_payment_succeeded')
    def test_webhook_payment_succeeded(self, mock_handle, mock_construct):
        """Тест: Обработка успешного платежа."""
        mock_construct.return_value = {
            'success': True,
            'event': {
                'type': 'payment_intent.succeeded',
                'data': {
                    'object': {
                        'id': 'pi_test123',
                        'amount': 10000,
                        'metadata': {'user_id': 'user_123'},
                        'latest_charge': 'ch_test123'
                    }
                }
            }
        }
        
        response = client.post(
            "/api/webhook/stripe",
            content=b'{"type": "payment_intent.succeeded"}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "valid_sig"
            }
        )
        
        assert response.status_code == 200
        assert response.json()['status'] == 'success'
    
    @patch('routes.webhooks.StripeService.construct_webhook_event')
    @patch('routes.webhooks._handle_payment_failed')
    def test_webhook_payment_failed(self, mock_handle, mock_construct):
        """Тест: Обработка неудачного платежа."""
        mock_construct.return_value = {
            'success': True,
            'event': {
                'type': 'payment_intent.payment_failed',
                'data': {
                    'object': {
                        'id': 'pi_test123',
                        'metadata': {'user_id': 'user_123'},
                        'last_payment_error': {
                            'message': 'Card declined'
                        }
                    }
                }
            }
        }
        
        response = client.post(
            "/api/webhook/stripe",
            content=b'{"type": "payment_intent.payment_failed"}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "valid_sig"
            }
        )
        
        assert response.status_code == 200
        assert response.json()['status'] == 'success'
    
    @patch('routes.webhooks.StripeService.construct_webhook_event')
    def test_webhook_unhandled_event(self, mock_construct):
        """Тест: Неизвестное событие."""
        mock_construct.return_value = {
            'success': True,
            'event': {
                'type': 'unknown.event',
                'data': {'object': {}}
            }
        }
        
        response = client.post(
            "/api/webhook/stripe",
            content=b'{"type": "unknown.event"}',
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "valid_sig"
            }
        )
        
        assert response.status_code == 200
        assert response.json()['status'] == 'received'


class TestWebhookHandlers:
    """Тесты вспомогательных функций обработки webhook."""
    
    @pytest.mark.asyncio
    async def test_handle_payment_succeeded_updates_operation(self, db_session):
        """Тест: Успешный платёж обновляет операцию."""
        from routes.webhooks import _handle_payment_succeeded
        
        # Создаём пользователя
        user = User(id="user_123", email="test@example.com", name="Test", password_hash="hash")
        db_session.add(user)
        
        # Создаём pending операцию
        operation = WalletOperation(
            user_id="user_123",
            operation_type="deposit",
            amount=Decimal("100.00"),
            status="pending",
            stripe_payment_intent_id="pi_test123"
        )
        db_session.add(operation)
        db_session.commit()
        
        # Имитируем webhook
        payment_intent = {
            'id': 'pi_test123',
            'amount': 10000,
            'metadata': {'user_id': 'user_123'},
            'latest_charge': 'ch_test123'
        }
        
        # Вызываем handler
        await _handle_payment_succeeded(db_session, payment_intent)
        
        # Проверяем что операция обновлена
        db_session.refresh(operation)
        assert operation.status == 'completed'
        assert operation.stripe_charge_id == 'ch_test123'
    
    @pytest.mark.asyncio
    async def test_handle_payment_failed_updates_operation(self, db_session):
        """Тест: Неудачный платёж обновляет операцию."""
        from routes.webhooks import _handle_payment_failed
        
        # Создаём пользователя
        user = User(id="user_123", email="test@example.com", name="Test", password_hash="hash")
        db_session.add(user)
        
        # Создаём pending операцию
        operation = WalletOperation(
            user_id="user_123",
            operation_type="deposit",
            amount=Decimal("100.00"),
            status="pending",
            stripe_payment_intent_id="pi_test456"
        )
        db_session.add(operation)
        db_session.commit()
        
        # Имитируем webhook
        payment_intent = {
            'id': 'pi_test456',
            'metadata': {'user_id': 'user_123'},
            'last_payment_error': {'message': 'Card declined'}
        }
        
        # Вызываем handler
        await _handle_payment_failed(db_session, payment_intent)
        
        # Проверяем что операция обновлена
        db_session.refresh(operation)
        assert operation.status == 'failed'
        assert operation.error_message == 'Card declined'


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

