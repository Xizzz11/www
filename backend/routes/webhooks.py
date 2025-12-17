"""
Webhook обработчик для Stripe.
Получает события от Stripe и обновляет БД.

Обрабатываемые события:
- payment_intent.succeeded - Платёж успешен
- payment_intent.payment_failed - Платёж ошибка
- payment_intent.requires_action - Требует 3D Secure
- payment_intent.processing - Платёж обрабатывается
"""

from datetime import datetime
from decimal import Decimal
import json

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from loguru import logger

from models.database import get_db
from models.orm_models import (
    User, UserBalance, BalanceTransaction, WalletOperation, AuditLog
)
from services.stripe_service import StripeService

router = APIRouter(prefix="/api/webhook", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook от Stripe для подтверждения платежей.
    
    Stripe отправляет сюда события когда:
    - Платёж успешен (payment_intent.succeeded)
    - Платёж ошибка (payment_intent.payment_failed)
    - Требует действия (payment_intent.requires_action)
    - Платёж обрабатывается (payment_intent.processing)
    
    ⚠️ ВАЖНО: Подпись Stripe проверяется для безопасности!
    """
    try:
        # 1. Получаем тело запроса и подпись
        body = await request.body()
        sig_header = request.headers.get('Stripe-Signature')
        
        if not sig_header:
            logger.error("Missing Stripe-Signature header")
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # 2. Проверяем подпись Stripe (ОЧЕНЬ ВАЖНО!)
        result = StripeService.construct_webhook_event(body, sig_header)
        
        if not result['success']:
            logger.error(f"Invalid Stripe signature: {result['error']}")
            raise HTTPException(status_code=400, detail=result['error'])
        
        event = result['event']
        event_type = event['type']
        
        # 3. Логируем получение webhook
        logger.info(f"Received Stripe webhook: {event_type}")
        
        # 4. Обрабатываем разные события
        
        # EVENT 1: Платёж успешен!
        if event_type == 'payment_intent.succeeded':
            await _handle_payment_succeeded(db, event['data']['object'])
            return {"status": "success", "event": event_type}
        
        # EVENT 2: Платёж ошибка
        elif event_type == 'payment_intent.payment_failed':
            await _handle_payment_failed(db, event['data']['object'])
            return {"status": "success", "event": event_type}
        
        # EVENT 3: Требует 3D Secure подтверждения
        elif event_type == 'payment_intent.requires_action':
            await _handle_requires_action(db, event['data']['object'])
            return {"status": "success", "event": event_type}
        
        # EVENT 4: Платёж обработан
        elif event_type == 'payment_intent.processing':
            await _handle_processing(db, event['data']['object'])
            return {"status": "success", "event": event_type}
        
        # EVENT 5: Платёж отменён
        elif event_type == 'payment_intent.canceled':
            await _handle_canceled(db, event['data']['object'])
            return {"status": "success", "event": event_type}
        
        # Неизвестное событие
        else:
            logger.warning(f"Unhandled Stripe event type: {event_type}")
            return {"status": "received", "event": event_type}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_payment_succeeded(db: Session, payment_intent: dict):
    """
    Обрабатывает успешный платёж.
    
    1. Находит операцию по payment_intent_id
    2. Обновляет статус на 'completed'
    3. Обновляет баланс пользователя (если ещё не обновлён)
    4. Записывает в audit_log
    """
    intent_id = payment_intent['id']
    user_id = payment_intent.get('metadata', {}).get('user_id')
    amount = payment_intent['amount'] / 100  # Из центов в доллары
    charge_id = payment_intent.get('latest_charge')
    
    logger.info(f"Payment succeeded: {intent_id} for user {user_id}, amount: ${amount}")
    
    if not user_id:
        logger.warning(f"Payment intent {intent_id} has no user_id in metadata")
        return
    
    # Находим операцию
    operation = db.query(WalletOperation).filter(
        WalletOperation.stripe_payment_intent_id == intent_id
    ).first()
    
    if not operation:
        logger.warning(f"No operation found for payment intent {intent_id}")
        return
    
    # Если уже обработано - пропускаем
    if operation.status == 'completed':
        logger.info(f"Operation {operation.operation_id} already completed")
        return
    
    # Обновляем операцию
    operation.status = 'completed'
    operation.stripe_charge_id = charge_id
    operation.completed_at = datetime.utcnow()
    
    # Получаем баланс пользователя
    balance = db.query(UserBalance).filter(
        UserBalance.user_id == user_id
    ).first()
    
    if balance:
        balance_before = float(balance.balance)
        balance_after = balance_before + amount
        
        # Обновляем баланс
        balance.balance = Decimal(str(balance_after))
        balance.total_deposited = Decimal(str(float(balance.total_deposited or 0) + amount))
        balance.last_transaction = datetime.utcnow()
        
        # Записываем транзакцию
        transaction = BalanceTransaction(
            user_id=user_id,
            transaction_type='deposit',
            amount=Decimal(str(amount)),
            balance_before=Decimal(str(balance_before)),
            balance_after=Decimal(str(balance_after)),
            status='completed',
            stripe_payment_intent_id=intent_id,
            stripe_charge_id=charge_id,
            description="Deposit via Stripe (webhook confirmed)",
            processed_at=datetime.utcnow()
        )
        db.add(transaction)
    
    # Логируем в audit_log
    details_data = {
        "event": "payment_intent.succeeded",
        "intent_id": intent_id,
        "charge_id": charge_id
    }
    audit_log = AuditLog(
        user_id=user_id,
        action="stripe_webhook_received",
        amount=Decimal(str(amount)),
        status="success",
        details=json.dumps(details_data) if details_data else None
    )
    db.add(audit_log)
    
    db.commit()
    logger.info(f"Successfully processed payment {intent_id} for user {user_id}")


async def _handle_payment_failed(db: Session, payment_intent: dict):
    """
    Обрабатывает неудачный платёж.
    
    1. Находит операцию по payment_intent_id
    2. Обновляет статус на 'failed'
    3. НЕ обновляет баланс (деньги не были списаны)
    4. Записывает в audit_log
    """
    intent_id = payment_intent['id']
    user_id = payment_intent.get('metadata', {}).get('user_id')
    error = payment_intent.get('last_payment_error', {})
    error_message = error.get('message', 'Payment failed')
    
    logger.error(f"Payment failed: {intent_id} for user {user_id}, error: {error_message}")
    
    if not user_id:
        logger.warning(f"Payment intent {intent_id} has no user_id in metadata")
        return
    
    # Находим операцию
    operation = db.query(WalletOperation).filter(
        WalletOperation.stripe_payment_intent_id == intent_id
    ).first()
    
    if operation:
        operation.status = 'failed'
        operation.error_message = error_message
    
    # Логируем в audit_log
    details_data = {
        "event": "payment_intent.payment_failed",
        "intent_id": intent_id,
        "error": error_message
    }
    audit_log = AuditLog(
        user_id=user_id,
        action="stripe_webhook_received",
        status="failed",
        details=json.dumps(details_data) if details_data else None
    )
    db.add(audit_log)
    
    db.commit()
    logger.info(f"Processed failed payment {intent_id} for user {user_id}")


async def _handle_requires_action(db: Session, payment_intent: dict):
    """
    Обрабатывает платёж, требующий 3D Secure подтверждения.
    
    Просто логируем - пользователь должен подтвердить в UI.
    """
    intent_id = payment_intent['id']
    user_id = payment_intent.get('metadata', {}).get('user_id')
    
    logger.info(f"Payment requires action: {intent_id} for user {user_id}")
    
    if user_id:
        details_data = {
            "event": "payment_intent.requires_action",
            "intent_id": intent_id
        }
        audit_log = AuditLog(
            user_id=user_id,
            action="stripe_webhook_received",
            status="pending",
            details=json.dumps(details_data) if details_data else None
        )
        db.add(audit_log)
        db.commit()


async def _handle_processing(db: Session, payment_intent: dict):
    """
    Обрабатывает платёж в процессе обработки.
    
    Просто логируем - ждём финального статуса.
    """
    intent_id = payment_intent['id']
    user_id = payment_intent.get('metadata', {}).get('user_id')
    
    logger.info(f"Payment processing: {intent_id} for user {user_id}")
    
    if user_id:
        details_data = {
            "event": "payment_intent.processing",
            "intent_id": intent_id
        }
        audit_log = AuditLog(
            user_id=user_id,
            action="stripe_webhook_received",
            status="processing",
            details=json.dumps(details_data) if details_data else None
        )
        db.add(audit_log)
        db.commit()


async def _handle_canceled(db: Session, payment_intent: dict):
    """
    Обрабатывает отменённый платёж.
    """
    intent_id = payment_intent['id']
    user_id = payment_intent.get('metadata', {}).get('user_id')
    
    logger.info(f"Payment canceled: {intent_id} for user {user_id}")
    
    if not user_id:
        return
    
    # Находим операцию
    operation = db.query(WalletOperation).filter(
        WalletOperation.stripe_payment_intent_id == intent_id
    ).first()
    
    if operation:
        operation.status = 'cancelled'
    
    # Логируем в audit_log
    details_data = {
        "event": "payment_intent.canceled",
        "intent_id": intent_id
    }
    audit_log = AuditLog(
        user_id=user_id,
        action="stripe_webhook_received",
        status="cancelled",
        details=json.dumps(details_data) if details_data else None
    )
    db.add(audit_log)
    
    db.commit()


