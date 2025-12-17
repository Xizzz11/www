#!/usr/bin/env python3
"""
Быстрая проверка конфигурации Stripe.
Используйте этот скрипт для быстрой проверки перед запуском приложения.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


def main():
    """Проверяет конфигурацию Stripe."""
    print("[*] Проверка конфигурации Stripe...\n")
    
    all_ok = True
    
    # Проверка Secret Key
    if not settings.stripe_secret_key:
        print("[X] STRIPE_SECRET_KEY не установлен")
        all_ok = False
    elif not settings.stripe_secret_key.startswith(('sk_test_', 'sk_live_')):
        print(f"[!] STRIPE_SECRET_KEY имеет неверный формат: {settings.stripe_secret_key[:10]}...")
        all_ok = False
    else:
        mode = "TEST" if "test" in settings.stripe_secret_key else "LIVE"
        print(f"[OK] STRIPE_SECRET_KEY установлен ({mode} mode)")
    
    # Проверка Publishable Key
    if not settings.stripe_publishable_key:
        print("[X] STRIPE_PUBLISHABLE_KEY не установлен")
        all_ok = False
    elif not settings.stripe_publishable_key.startswith(('pk_test_', 'pk_live_')):
        print(f"[!] STRIPE_PUBLISHABLE_KEY имеет неверный формат: {settings.stripe_publishable_key[:10]}...")
        all_ok = False
    else:
        print("[OK] STRIPE_PUBLISHABLE_KEY установлен")
    
    # Проверка Webhook Secret
    if not settings.stripe_webhook_secret:
        print("[!] STRIPE_WEBHOOK_SECRET не установлен (webhook'и не будут работать)")
    elif not settings.stripe_webhook_secret.startswith('whsec_'):
        print(f"[!] STRIPE_WEBHOOK_SECRET имеет неверный формат: {settings.stripe_webhook_secret[:10]}...")
    else:
        print("[OK] STRIPE_WEBHOOK_SECRET установлен")
    
    print()
    
    if all_ok:
        print("[OK] Конфигурация Stripe корректна!")
        sys.exit(0)
    else:
        print("[X] Обнаружены проблемы с конфигурацией")
        print("    Запустите 'python scripts/setup_stripe.py' для подробной диагностики")
        sys.exit(1)


if __name__ == "__main__":
    main()

