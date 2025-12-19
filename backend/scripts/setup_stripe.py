#!/usr/bin/env python3
"""
Скрипт для настройки и проверки Stripe интеграции.
Проверяет конфигурацию, тестирует подключение и создаёт тестовые данные.
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import stripe
from loguru import logger
from config.settings import settings


def check_stripe_config():
    """Проверяет наличие всех необходимых Stripe ключей."""
    logger.info("[*] Проверка конфигурации Stripe...")
    
    issues = []
    
    if not settings.stripe_secret_key:
        issues.append("[X] STRIPE_SECRET_KEY не установлен")
    elif not settings.stripe_secret_key.startswith(('sk_test_', 'sk_live_')):
        issues.append("[!] STRIPE_SECRET_KEY имеет неверный формат (должен начинаться с sk_test_ или sk_live_)")
    else:
        logger.info("[OK] STRIPE_SECRET_KEY установлен")
    
    if not settings.stripe_publishable_key:
        issues.append("[X] STRIPE_PUBLISHABLE_KEY не установлен")
    elif not settings.stripe_publishable_key.startswith(('pk_test_', 'pk_live_')):
        issues.append("[!] STRIPE_PUBLISHABLE_KEY имеет неверный формат (должен начинаться с pk_test_ или pk_live_)")
    else:
        logger.info("[OK] STRIPE_PUBLISHABLE_KEY установлен")
    
    if not settings.stripe_webhook_secret:
        issues.append("[!] STRIPE_WEBHOOK_SECRET не установлен (необходим для webhook'ов)")
    elif not settings.stripe_webhook_secret.startswith('whsec_'):
        issues.append("[!] STRIPE_WEBHOOK_SECRET имеет неверный формат (должен начинаться с whsec_)")
    else:
        logger.info("[OK] STRIPE_WEBHOOK_SECRET установлен")
    
    return issues


def test_stripe_connection():
    """Тестирует подключение к Stripe API."""
    logger.info("[*] Тестирование подключения к Stripe API...")
    
    if not settings.stripe_secret_key:
        logger.error("[X] Нельзя протестировать подключение: STRIPE_SECRET_KEY не установлен")
        return False
    
    try:
        stripe.api_key = settings.stripe_secret_key
        
        # Пробуем получить аккаунт
        account = stripe.Account.retrieve()
        logger.info(f"[OK] Подключение успешно! Аккаунт: {account.id}")
        logger.info(f"     Тип ключа: {'TEST' if 'test' in settings.stripe_secret_key else 'LIVE'}")
        logger.info(f"     Страна: {account.country}")
        logger.info(f"     Email: {account.email if hasattr(account, 'email') else 'N/A'}")
        
        return True
    except stripe.error.AuthenticationError:
        logger.error("[X] Ошибка аутентификации: неверный STRIPE_SECRET_KEY")
        return False
    except stripe.error.APIConnectionError:
        logger.error("[X] Ошибка подключения: проверьте интернет-соединение")
        return False
    except Exception as e:
        logger.error(f"[X] Неожиданная ошибка: {str(e)}")
        return False


def create_test_customer():
    """Создаёт тестового клиента в Stripe."""
    logger.info("[*] Создание тестового клиента...")
    
    if not settings.stripe_secret_key:
        logger.error("[X] Нельзя создать клиента: STRIPE_SECRET_KEY не установлен")
        return None
    
    try:
        stripe.api_key = settings.stripe_secret_key
        
        customer = stripe.Customer.create(
            email="test@looseline.com",
            name="Test Customer",
            metadata={
                "user_id": "test_user_123",
                "source": "setup_script"
            }
        )
        
        logger.info(f"[OK] Тестовый клиент создан: {customer.id}")
        logger.info(f"     Email: {customer.email}")
        return customer.id
    except Exception as e:
        logger.error(f"[X] Ошибка создания клиента: {str(e)}")
        return None


def test_payment_intent():
    """Тестирует создание Payment Intent."""
    logger.info("[*] Тестирование создания Payment Intent...")
    
    if not settings.stripe_secret_key:
        logger.error("[X] Нельзя создать Payment Intent: STRIPE_SECRET_KEY не установлен")
        return False
    
    try:
        stripe.api_key = settings.stripe_secret_key
        
        intent = stripe.PaymentIntent.create(
            amount=1000,  # $10.00 в центах
            currency="usd",
            metadata={
                "test": "true",
                "source": "setup_script"
            }
        )
        
        logger.info(f"[OK] Payment Intent создан: {intent.id}")
        logger.info(f"     Статус: {intent.status}")
        logger.info(f"     Сумма: ${intent.amount / 100:.2f} {intent.currency.upper()}")
        
        # Отменяем тестовый intent
        stripe.PaymentIntent.cancel(intent.id)
        logger.info("     Тестовый Payment Intent отменён")
        
        return True
    except Exception as e:
        logger.error(f"[X] Ошибка создания Payment Intent: {str(e)}")
        return False


def print_setup_instructions():
    """Выводит инструкции по настройке Stripe."""
    print("\n" + "="*70)
    print("📋 ИНСТРУКЦИИ ПО НАСТРОЙКЕ STRIPE")
    print("="*70)
    print("\n1. Создайте аккаунт на https://dashboard.stripe.com/register")
    print("\n2. Получите API ключи:")
    print("   - Перейдите в https://dashboard.stripe.com/apikeys")
    print("   - Скопируйте 'Publishable key' (pk_test_...)")
    print("   - Скопируйте 'Secret key' (sk_test_...)")
    print("\n3. Настройте Webhook:")
    print("   - Перейдите в https://dashboard.stripe.com/webhooks")
    print("   - Нажмите 'Add endpoint'")
    print("   - URL: https://your-domain.com/api/webhooks/stripe")
    print("   - События: payment_intent.succeeded, payment_intent.payment_failed")
    print("   - Скопируйте 'Signing secret' (whsec_...)")
    print("\n4. Добавьте ключи в .env файл:")
    print("   STRIPE_SECRET_KEY=sk_test_...")
    print("   STRIPE_PUBLISHABLE_KEY=pk_test_...")
    print("   STRIPE_WEBHOOK_SECRET=whsec_...")
    print("\n5. Для тестирования используйте тестовые карты:")
    print("   - Успешный платёж: 4242 4242 4242 4242")
    print("   - Отклонённый платёж: 4000 0000 0000 0002")
    print("   - Требует 3D Secure: 4000 0025 0000 3155")
    print("   - Любая дата истечения (будущая)")
    print("   - Любой CVC")
    print("\n" + "="*70 + "\n")


def main():
    """Основная функция."""
    logger.info("[*] Запуск настройки Stripe для LOOSELINE")
    logger.info("="*70)
    
    # Проверка конфигурации
    issues = check_stripe_config()
    
    if issues:
        logger.warning("\n[!] Обнаружены проблемы с конфигурацией:")
        for issue in issues:
            logger.warning(f"    {issue}")
        print_setup_instructions()
        
        if not settings.stripe_secret_key:
            logger.error("\n[X] Невозможно продолжить без STRIPE_SECRET_KEY")
            sys.exit(1)
    else:
        logger.info("\n[OK] Все ключи настроены корректно!")
    
    # Тестирование подключения
    if not test_stripe_connection():
        logger.error("\n[X] Не удалось подключиться к Stripe API")
        sys.exit(1)
    
    # Создание тестового клиента
    customer_id = create_test_customer()
    
    # Тестирование Payment Intent
    test_payment_intent()
    
    logger.info("\n" + "="*70)
    logger.info("[OK] Настройка Stripe завершена успешно!")
    logger.info("="*70)
    
    if customer_id:
        logger.info(f"\n[*] Тестовый клиент создан: {customer_id}")
        logger.info("    Вы можете использовать его для тестирования")


if __name__ == "__main__":
    main()

