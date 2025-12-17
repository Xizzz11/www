"""
Сервис для интеграции со Stripe.
Обрабатывает платежи, сохранение способов оплаты, webhook'и.

Включает 7 функций:
1. create_payment_intent() - Создаёт намерение платежа
2. confirm_payment() - Проверяет статус платежа
3. create_stripe_customer() - Создаёт Stripe Customer
4. save_payment_method() - Сохраняет способ оплаты
5. charge_customer() - Списывает деньги с сохранённой карты
6. get_payment_methods() - Получает способы оплаты
7. construct_webhook_event() - Обрабатывает webhook
"""

import stripe
from typing import Dict, Optional, List
from loguru import logger

from config.settings import settings

# Инициализируем Stripe с Secret Key
stripe.api_key = settings.stripe_secret_key


class StripeService:
    """
    Сервис для работы со Stripe.
    
    Все методы статические, возвращают Dict с ключами:
    - success: bool - успешно ли выполнена операция
    - error: str - сообщение об ошибке (если success=False)
    - ... дополнительные данные в зависимости от метода
    """

    @staticmethod
    def create_payment_intent(
        amount: float,
        user_id: str,
        stripe_customer_id: Optional[str] = None,
        description: str = "Deposit to LOOSELINE account",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Создаёт Payment Intent (намерение платежа) в Stripe.
        
        Payment Intent нужен для инициирования платежа.
        Frontend будет использовать client_secret для подтверждения платежа.
        
        Args:
            amount (float): Сумма в USD (например, 100.00)
            user_id (str): ID пользователя
            stripe_customer_id (str): ID Stripe Customer (опционально)
            description (str): Описание платежа
            metadata (dict): Дополнительные данные
        
        Returns:
            Dict: {
                "success": True,
                "client_secret": "pi_..._secret_...",
                "intent_id": "pi_...",
                "amount": 100.0,
                "status": "requires_payment_method"
            }
            или
            {
                "success": False,
                "error": "Card declined"
            }
        
        Database Queries:
            Никаких запросов к БД - только к Stripe API
        
        Raises:
            stripe.error.StripeError: Ошибка от Stripe
        
        Examples:
            >>> result = StripeService.create_payment_intent(100.0, "user_123")
            >>> if result['success']:
            ...     client_secret = result['client_secret']
        """
        try:
            # Stripe работает в центах (10000 = 100.00 USD)
            amount_cents = int(amount * 100)
            
            # Подготавливаем metadata
            intent_metadata = {
                "user_id": user_id,
                "type": "deposit"
            }
            if metadata:
                intent_metadata.update(metadata)
            
            # Создаём Payment Intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                customer=stripe_customer_id,
                description=description,
                metadata=intent_metadata,
                automatic_payment_methods={
                    "enabled": True,
                }
            )
            
            logger.info(f"Created Payment Intent {intent.id} for user {user_id}, amount: ${amount}")
            
            return {
                "success": True,
                "client_secret": intent.client_secret,
                "intent_id": intent.id,
                "amount": amount,
                "status": intent.status
            }
        
        except stripe.error.CardError as e:
            logger.error(f"Card error creating payment intent: {str(e)}")
            return {
                "success": False,
                "error": str(e.user_message),
                "code": e.code
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment intent: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def confirm_payment(payment_intent_id: str) -> Dict:
        """
        Проверяет статус платежа в Stripe.
        
        Используется после того как frontend отправит данные карты.
        Нужно проверить что платёж действительно прошёл.
        
        Args:
            payment_intent_id (str): ID Payment Intent (например, "pi_123...")
        
        Returns:
            Dict: {
                "success": True,
                "status": "succeeded",  # или "requires_action", "processing"
                "amount": 100.0,
                "currency": "usd",
                "charge_id": "ch_..."
            }
            или
            {
                "success": False,
                "error": "Payment intent not found"
            }
        
        Examples:
            >>> result = StripeService.confirm_payment("pi_8f7g9h0i1j")
            >>> if result['status'] == 'succeeded':
            ...     # Платёж успешен, обновляем баланс
            ...     update_balance()
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            logger.info(f"Retrieved Payment Intent {payment_intent_id}, status: {intent.status}")
            
            return {
                "success": True,
                "status": intent.status,
                "amount": intent.amount / 100,  # Переводим из центов в доллары
                "currency": intent.currency,
                "charge_id": intent.latest_charge,
                "metadata": intent.metadata
            }
        
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request retrieving payment intent: {str(e)}")
            return {
                "success": False,
                "error": "Payment intent not found"
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error confirming payment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def create_stripe_customer(
        user_id: str,
        email: str,
        name: str
    ) -> Dict:
        """
        Создаёт Customer в Stripe.
        
        Stripe Customer нужен для:
        - Сохранения способов оплаты
        - Повторных платежей без формы ввода данных
        - Отслеживания истории платежей
        
        Args:
            user_id (str): ID пользователя в нашей системе
            email (str): Email пользователя
            name (str): Имя пользователя
        
        Returns:
            Dict: {
                "success": True,
                "stripe_customer_id": "cus_8f7g9h0i1j..."
            }
            или
            {
                "success": False,
                "error": "Invalid email"
            }
        
        Examples:
            >>> result = StripeService.create_stripe_customer(
            ...     "user_123", "ivan@mail.com", "Ivan"
            ... )
            >>> if result['success']:
            ...     cus_id = result['stripe_customer_id']
        """
        try:
            customer = stripe.Customer.create(
                name=name,
                email=email,
                metadata={"user_id": user_id}
            )
            
            logger.info(f"Created Stripe Customer {customer.id} for user {user_id}")
            
            return {
                "success": True,
                "stripe_customer_id": customer.id
            }
        
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request creating customer: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def save_payment_method(
        stripe_customer_id: str,
        stripe_payment_method_id: str,
        set_as_default: bool = False
    ) -> Dict:
        """
        Сохраняет способ оплаты (карту) для customer'а в Stripe.
        
        После этого можно будет использовать эту карту для платежей
        без ввода данных пользователем.
        
        Args:
            stripe_customer_id (str): ID Stripe Customer
            stripe_payment_method_id (str): ID способа оплаты (вернёт frontend)
            set_as_default (bool): Установить как способ по умолчанию
        
        Returns:
            Dict: {
                "success": True,
                "message": "Payment method attached",
                "payment_method": {
                    "id": "pm_...",
                    "type": "card",
                    "card": {...}
                }
            }
            или
            {
                "success": False,
                "error": "Payment method not found"
            }
        """
        try:
            # Привязываем способ оплаты к customer
            payment_method = stripe.PaymentMethod.attach(
                stripe_payment_method_id,
                customer=stripe_customer_id
            )
            
            # Если нужно - устанавливаем как способ по умолчанию
            if set_as_default:
                stripe.Customer.modify(
                    stripe_customer_id,
                    invoice_settings={
                        "default_payment_method": stripe_payment_method_id
                    }
                )
            
            logger.info(f"Attached payment method {stripe_payment_method_id} to customer {stripe_customer_id}")
            
            return {
                "success": True,
                "message": "Payment method saved",
                "payment_method": {
                    "id": payment_method.id,
                    "type": payment_method.type,
                    "card": {
                        "brand": payment_method.card.brand,
                        "last4": payment_method.card.last4,
                        "exp_month": payment_method.card.exp_month,
                        "exp_year": payment_method.card.exp_year
                    } if payment_method.card else None
                }
            }
        
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request attaching payment method: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error attaching payment method: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def charge_customer(
        stripe_customer_id: str,
        amount: float,
        stripe_payment_method_id: str,
        description: str = "Deposit",
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Списывает деньги с сохранённого способа оплаты.
        
        Используется для:
        - Повторных платежей со сохранённой карты
        - Автоматических платежей
        - Платежей без интерактивного окна
        
        Args:
            stripe_customer_id (str): ID Stripe Customer
            amount (float): Сумма в USD
            stripe_payment_method_id (str): ID способа оплаты
            description (str): Описание платежа
            user_id (str): ID пользователя (для metadata)
        
        Returns:
            Dict: {
                "success": True,
                "status": "succeeded",
                "charge_id": "ch_8f7g9h0i1j...",
                "intent_id": "pi_8f7g9h0i1j..."
            }
            или
            {
                "success": False,
                "error": "Your card was declined"
            }
        
        Examples:
            >>> result = StripeService.charge_customer(
            ...     "cus_123", 100.0, "pm_456", "Deposit"
            ... )
            >>> if result['success']:
            ...     # Платёж прошёл, обновляем баланс
            ...     update_balance(amount)
        """
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # В центах
                currency="usd",
                customer=stripe_customer_id,
                payment_method=stripe_payment_method_id,
                off_session=True,  # Платёж БЕЗ интерактивного окна
                confirm=True,
                description=description,
                metadata={
                    "user_id": user_id,
                    "type": "deposit"
                } if user_id else {}
            )
            
            if intent.status == "succeeded":
                logger.info(f"Charged customer {stripe_customer_id} ${amount}")
                return {
                    "success": True,
                    "status": "succeeded",
                    "charge_id": intent.latest_charge,
                    "intent_id": intent.id,
                    "amount": amount
                }
            else:
                logger.warning(f"Payment intent status: {intent.status}")
                return {
                    "success": False,
                    "status": intent.status,
                    "error": f"Payment status: {intent.status}",
                    "intent_id": intent.id
                }
        
        except stripe.error.CardError as e:
            logger.error(f"Card error charging customer: {str(e)}")
            return {
                "success": False,
                "error": e.user_message,
                "code": e.code
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error charging customer: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def get_payment_methods(stripe_customer_id: str) -> Dict:
        """
        Получает все способы оплаты для customer'а.
        
        Args:
            stripe_customer_id (str): ID Stripe Customer
        
        Returns:
            Dict: {
                "success": True,
                "payment_methods": [
                    {
                        "id": "pm_123...",
                        "type": "card",
                        "card": {
                            "brand": "visa",
                            "last4": "1234",
                            "exp_month": 12,
                            "exp_year": 2025
                        }
                    }
                ]
            }
        """
        try:
            methods = stripe.PaymentMethod.list(
                customer=stripe_customer_id,
                type="card"
            )
            
            payment_methods = []
            for m in methods.data:
                method_data = {
                    "id": m.id,
                    "type": m.type,
                    "created": m.created
                }
                if m.card:
                    method_data["card"] = {
                        "brand": m.card.brand,
                        "last4": m.card.last4,
                        "exp_month": m.card.exp_month,
                        "exp_year": m.card.exp_year,
                        "funding": m.card.funding
                    }
                payment_methods.append(method_data)
            
            logger.info(f"Retrieved {len(payment_methods)} payment methods for customer {stripe_customer_id}")
            
            return {
                "success": True,
                "payment_methods": payment_methods
            }
        
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Invalid request getting payment methods: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "payment_methods": []
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting payment methods: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "payment_methods": []
            }

    @staticmethod
    def construct_webhook_event(request_body: bytes, sig_header: str) -> Dict:
        """
        Проверяет и конструирует event от Stripe webhook.
        
        ⚠️ ВАЖНО: Эта функция ПРОВЕРЯЕТ подпись от Stripe!
        Это гарантирует что webhook пришёл реально от Stripe, а не от хакера.
        
        Args:
            request_body (bytes): Тело запроса от Stripe
            sig_header (str): Заголовок Stripe-Signature
        
        Returns:
            Dict: {
                "success": True,
                "event": { "type": "payment_intent.succeeded", ... }
            }
            или
            {
                "success": False,
                "error": "Invalid signature"
            }
        
        Examples:
            >>> result = StripeService.construct_webhook_event(
            ...     request.data, request.headers.get('Stripe-Signature')
            ... )
            >>> if result['success']:
            ...     event = result['event']
            ...     if event['type'] == 'payment_intent.succeeded':
            ...         # Обновляем баланс пользователя
        """
        try:
            webhook_secret = settings.stripe_webhook_secret
            
            if not webhook_secret:
                logger.error("Stripe webhook secret not configured")
                return {
                    "success": False,
                    "error": "Webhook secret not configured"
                }
            
            event = stripe.Webhook.construct_event(
                request_body,
                sig_header,
                webhook_secret
            )
            
            logger.info(f"Received Stripe webhook event: {event['type']}")
            
            return {
                "success": True,
                "event": event
            }
        
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            return {
                "success": False,
                "error": "Invalid payload"
            }
        
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            return {
                "success": False,
                "error": "Invalid signature"
            }

    @staticmethod
    def delete_payment_method(stripe_payment_method_id: str) -> Dict:
        """
        Удаляет способ оплаты из Stripe.
        
        Args:
            stripe_payment_method_id (str): ID способа оплаты
        
        Returns:
            Dict: {
                "success": True,
                "message": "Payment method deleted"
            }
        """
        try:
            stripe.PaymentMethod.detach(stripe_payment_method_id)
            
            logger.info(f"Deleted payment method {stripe_payment_method_id}")
            
            return {
                "success": True,
                "message": "Payment method deleted"
            }
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error deleting payment method: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def create_refund(
        charge_id: str,
        amount: Optional[float] = None,
        reason: str = "requested_by_customer"
    ) -> Dict:
        """
        Создаёт возврат средств.
        
        Args:
            charge_id (str): ID платежа для возврата
            amount (float): Сумма возврата (None = полный возврат)
            reason (str): Причина возврата
        
        Returns:
            Dict: {
                "success": True,
                "refund_id": "re_...",
                "amount": 100.0,
                "status": "succeeded"
            }
        """
        try:
            refund_params = {
                "charge": charge_id,
                "reason": reason
            }
            
            if amount:
                refund_params["amount"] = int(amount * 100)
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(f"Created refund {refund.id} for charge {charge_id}")
            
            return {
                "success": True,
                "refund_id": refund.id,
                "amount": refund.amount / 100,
                "status": refund.status
            }
        
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating refund: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


