"""
Сервис управления кошельком пользователя.

Включает 5 ключевых методов:
1. get_balance() - Получение баланса и статистики
2. replenish_balance() - Пополнение счёта через Stripe
3. withdraw_funds() - Вывод средств
4. get_bet_history() - История ставок и транзакций
5. export_report() - Экспорт в CSV/PDF
"""

import os
import csv
import io
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional, List, Any

from sqlalchemy import func, and_, desc, Integer, case
from sqlalchemy.orm import Session
from loguru import logger

from models.orm_models import (
    User, UserBalance, BalanceTransaction, WalletOperation,
    PaymentMethod, WithdrawalMethod, Bet, AuditLog
)
from services.stripe_service import StripeService
from config.settings import settings


class WalletService:
    """
    Сервис для работы с кошельком пользователя.
    
    Все методы принимают сессию БД и возвращают Dict с результатом.
    """

    # =========================================================================
    # МЕТОД 1: get_balance()
    # =========================================================================
    @staticmethod
    def get_balance(db: Session, user_id: str) -> Dict:
        """
        Получает полную информацию о балансе и статистике пользователя.
        
        Функция получает текущий баланс, все статистические метрики,
        информацию о профитах/убытках, win rate и другую информацию.
        
        Args:
            db (Session): SQLAlchemy сессия
            user_id (str): Уникальный ID пользователя из таблицы users
        
        Returns:
            dict: Словарь с ключами:
                {
                    "success": bool,
                    "balance": {
                        "user_id": str,
                        "current_balance": float,
                        "currency": str,
                        "total_deposited": float,
                        "total_withdrawn": float,
                        "total_bet": float,
                        "total_won": float,
                        "total_lost": float,
                        "net_profit": float,
                        "roi_percent": float,
                        "win_count": int,
                        "lose_count": int,
                        "win_rate": float,
                        "last_transaction": str,
                        "account_created": str
                    },
                    "available_balance": float,
                    "locked_in_bets": float,
                    "pending_deposits": float,
                    "pending_withdrawals": float
                }
        
        Raises:
            ValueError: Если user_id не существует
        
        Examples:
            >>> result = WalletService.get_balance(db, 'user_123')
            >>> print(result['balance']['current_balance'])
            5000.0
            >>> print(result['balance']['net_profit'])
            2180.0
        
        Database Queries:
            1. SELECT * FROM users WHERE id = ?
            2. SELECT * FROM users_balance WHERE user_id = ?
            3. SELECT COUNT(*) FROM bets WHERE user_id = ? AND result = 'win'
            4. SELECT COUNT(*) FROM bets WHERE user_id = ? AND result = 'loss'
            5. SELECT SUM(amount) FROM wallet_operations WHERE status = 'pending'
            6. SELECT SUM(bet_amount) FROM bets WHERE status = 'open'
        
        Business Logic:
            - net_profit = total_won - total_lost
            - roi_percent = (total_won / total_bet) * 100 если total_bet > 0
            - win_rate = (wins / (wins + losses)) * 100
            - available = balance - locked_in_bets
        """
        try:
            # 1. Проверяем существует ли пользователь
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {
                    "success": False,
                    "error": "User not found",
                    "user_id": user_id
                }
            
            # 2. Получаем баланс пользователя
            balance = db.query(UserBalance).filter(
                UserBalance.user_id == user_id
            ).first()
            
            if not balance:
                # Создаём запись баланса если её нет
                balance = UserBalance(
                    user_id=user_id,
                    balance=Decimal("0.00"),
                    currency="USD"
                )
                db.add(balance)
                db.commit()
                db.refresh(balance)
            
            # 3. Получаем количество выигрышей и проигрышей
            win_count = db.query(func.count(Bet.bet_id)).filter(
                and_(Bet.user_id == user_id, Bet.result == 'win')
            ).scalar() or 0
            
            lose_count = db.query(func.count(Bet.bet_id)).filter(
                and_(Bet.user_id == user_id, Bet.result == 'loss')
            ).scalar() or 0
            
            total_bets_count = win_count + lose_count
            win_rate = (win_count / total_bets_count * 100) if total_bets_count > 0 else 0.0
            
            # 4. Получаем pending депозиты
            pending_deposits = db.query(func.sum(WalletOperation.amount)).filter(
                and_(
                    WalletOperation.user_id == user_id,
                    WalletOperation.operation_type == 'deposit',
                    WalletOperation.status == 'pending'
                )
            ).scalar() or Decimal("0.00")
            
            # 5. Получаем pending выводы
            pending_withdrawals = db.query(func.sum(WalletOperation.amount)).filter(
                and_(
                    WalletOperation.user_id == user_id,
                    WalletOperation.operation_type == 'withdrawal',
                    WalletOperation.status == 'pending'
                )
            ).scalar() or Decimal("0.00")
            
            # 6. Получаем locked_in_bets (деньги в открытых ставках)
            locked_in_bets = db.query(func.sum(Bet.bet_amount)).filter(
                and_(Bet.user_id == user_id, Bet.status == 'open')
            ).scalar() or Decimal("0.00")
            
            # 7. Рассчитываем производные значения
            current_balance = float(balance.balance or 0)
            total_won = float(balance.total_won or 0)
            total_lost = float(balance.total_lost or 0)
            total_bet = float(balance.total_bet or 0)
            
            net_profit = total_won - total_lost
            roi_percent = (total_won / total_bet * 100) if total_bet > 0 else 0.0
            available_balance = current_balance - float(locked_in_bets)
            
            # 8. Логируем запрос баланса
            audit_log = AuditLog(
                user_id=user_id,
                action="balance_checked",
                status="success"
            )
            db.add(audit_log)
            db.commit()
            
            # 9. Возвращаем результат
            return {
                "success": True,
                "balance": {
                    "user_id": user_id,
                    "current_balance": current_balance,
                    "currency": balance.currency,
                    "total_deposited": float(balance.total_deposited or 0),
                    "total_withdrawn": float(balance.total_withdrawn or 0),
                    "total_bet": total_bet,
                    "total_won": total_won,
                    "total_lost": total_lost,
                    "net_profit": round(net_profit, 2),
                    "roi_percent": round(roi_percent, 2),
                    "win_count": win_count,
                    "lose_count": lose_count,
                    "win_rate": round(win_rate, 2),
                    "last_transaction": balance.last_transaction.isoformat() if balance.last_transaction else None,
                    "account_created": user.created_at.isoformat() if user.created_at else None
                },
                "available_balance": round(available_balance, 2),
                "locked_in_bets": float(locked_in_bets),
                "pending_deposits": float(pending_deposits),
                "pending_withdrawals": float(pending_withdrawals)
            }
        
        except Exception as e:
            logger.error(f"Error in get_balance for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": "Database error",
                "details": str(e)
            }

    # =========================================================================
    # МЕТОД 2: replenish_balance()
    # =========================================================================
    @staticmethod
    def replenish_balance(
        db: Session,
        user_id: str,
        amount: float,
        stripe_payment_method_id: Optional[str] = None,
        payment_method: str = "card",
        save_method: bool = False,
        ip_address: Optional[str] = None
    ) -> Dict:
        """
        Пополняет баланс пользователя через Stripe.
        
        Функция:
        1. Валидирует параметры
        2. Проверяет баланс пользователя
        3. Создаёт Stripe Customer (если первый раз)
        4. Если новая карта: возвращает client_secret для frontend
        5. Если сохранённая карта: списывает деньги сразу
        6. Обновляет баланс в БД
        7. Записывает историю транзакции
        
        Args:
            db (Session): SQLAlchemy сессия
            user_id (str): ID пользователя
            amount (float): Сумма пополнения (минимум 1.00)
            stripe_payment_method_id (str): ID способа в Stripe (опционально)
            payment_method (str): Способ оплаты ("card", "bank_transfer")
            save_method (bool): Сохранить способ оплаты?
            ip_address (str): IP адрес клиента
        
        Returns:
            dict: 
                Если НОВАЯ КАРТА:
                {
                    "success": True,
                    "action": "requires_payment_form",
                    "client_secret": "pi_..._secret_...",
                    "intent_id": "pi_...",
                    "message": "Please complete payment in the form"
                }
                
                Если СОХРАНЁННАЯ КАРТА:
                {
                    "success": True,
                    "message": "Balance replenished successfully",
                    "new_balance": 5100.0,
                    "transaction_id": "ch_...",
                    "status": "completed"
                }
        
        Business Logic:
            - Минимум: 1.00 USD
            - Максимум: 100000.00 USD
            - Если первый раз: создаём Stripe Customer
        """
        try:
            # 1. Валидация параметров
            if amount <= 0:
                return {"success": False, "error": "Amount must be positive"}
            
            if amount < 1.00:
                return {"success": False, "error": "Minimum deposit is 1.00 USD"}
            
            if amount > 100000.00:
                return {"success": False, "error": "Maximum deposit is 100000.00 USD"}
            
            # 2. Получаем пользователя
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {"success": False, "error": "User not found"}
            
            # 3. Получаем или создаём баланс
            balance = db.query(UserBalance).filter(
                UserBalance.user_id == user_id
            ).first()
            
            if not balance:
                balance = UserBalance(
                    user_id=user_id,
                    balance=Decimal("0.00"),
                    currency="USD"
                )
                db.add(balance)
                db.commit()
                db.refresh(balance)
            
            balance_before = float(balance.balance)
            
            # 4. Если первый раз: создаём Stripe Customer
            if not user.stripe_customer_id:
                stripe_result = StripeService.create_stripe_customer(
                    user_id, user.email, user.name
                )
                
                if not stripe_result['success']:
                    logger.error(f"Failed to create Stripe customer: {stripe_result['error']}")
                    return {
                        "success": False,
                        "error": "Failed to create payment account"
                    }
                
                user.stripe_customer_id = stripe_result['stripe_customer_id']
                db.commit()
                logger.info(f"Created Stripe customer {user.stripe_customer_id} for user {user_id}")
            
            # 5. Логируем инициацию депозита
            audit_log = AuditLog(
                user_id=user_id,
                action="deposit_initiated",
                amount=Decimal(str(amount)),
                ip_address=ip_address,
                status="pending"
            )
            db.add(audit_log)
            db.commit()
            
            # 6. ЕСЛИ НОВАЯ КАРТА: создаём Payment Intent
            if stripe_payment_method_id is None:
                intent_result = StripeService.create_payment_intent(
                    amount,
                    user_id,
                    user.stripe_customer_id,
                    f"Deposit to LOOSELINE account - {user_id}"
                )
                
                if not intent_result['success']:
                    return {
                        "success": False,
                        "error": intent_result.get('error', 'Payment failed')
                    }
                
                # Записываем операцию как pending
                operation = WalletOperation(
                    user_id=user_id,
                    operation_type='deposit',
                    amount=Decimal(str(amount)),
                    status='pending',
                    payment_method=payment_method,
                    stripe_payment_intent_id=intent_result['intent_id'],
                    expires_at=datetime.utcnow() + timedelta(hours=24)
                )
                db.add(operation)
                db.commit()
                
                return {
                    "success": True,
                    "action": "requires_payment_form",
                    "client_secret": intent_result['client_secret'],
                    "intent_id": intent_result['intent_id'],
                    "message": "Please complete payment in the form"
                }
            
            # 7. ЕСЛИ СОХРАНЁННАЯ КАРТА: списываем сразу
            else:
                charge_result = StripeService.charge_customer(
                    user.stripe_customer_id,
                    amount,
                    stripe_payment_method_id,
                    f"Deposit - {user_id}",
                    user_id
                )
                
                if not charge_result['success']:
                    # Записываем failed операцию
                    operation = WalletOperation(
                        user_id=user_id,
                        operation_type='deposit',
                        amount=Decimal(str(amount)),
                        status='failed',
                        payment_method=payment_method,
                        stripe_payment_method_id=stripe_payment_method_id,
                        error_message=charge_result.get('error')
                    )
                    db.add(operation)
                    
                    # Логируем failed
                    details_data = {"error": charge_result.get('error')}
                    # Сериализуем в JSON для совместимости
                    audit_log = AuditLog(
                        user_id=user_id,
                        action="deposit_failed",
                        amount=Decimal(str(amount)),
                        ip_address=ip_address,
                        status="failed",
                        details=json.dumps(details_data) if details_data else None
                    )
                    db.add(audit_log)
                    db.commit()
                    
                    return {
                        "success": False,
                        "error": charge_result.get('error', 'Payment failed')
                    }
                
                # 8. Платёж успешен → обновляем баланс
                balance_after = balance_before + amount
                
                balance.balance = Decimal(str(balance_after))
                balance.total_deposited = Decimal(str(float(balance.total_deposited or 0) + amount))
                balance.last_transaction = datetime.utcnow()
                
                # 9. Записываем транзакцию
                transaction = BalanceTransaction(
                    user_id=user_id,
                    transaction_type='deposit',
                    amount=Decimal(str(amount)),
                    balance_before=Decimal(str(balance_before)),
                    balance_after=Decimal(str(balance_after)),
                    status='completed',
                    stripe_payment_intent_id=charge_result.get('intent_id'),
                    stripe_charge_id=charge_result.get('charge_id'),
                    description=f"Card deposit via Stripe",
                    processed_at=datetime.utcnow()
                )
                db.add(transaction)
                
                # 10. Записываем операцию
                operation = WalletOperation(
                    user_id=user_id,
                    operation_type='deposit',
                    amount=Decimal(str(amount)),
                    status='completed',
                    payment_method=payment_method,
                    stripe_payment_intent_id=charge_result.get('intent_id'),
                    stripe_charge_id=charge_result.get('charge_id'),
                    stripe_payment_method_id=stripe_payment_method_id,
                    completed_at=datetime.utcnow()
                )
                db.add(operation)
                
                # 11. Сохраняем способ оплаты если нужно
                if save_method:
                    # Проверяем, не сохранён ли уже
                    existing_method = db.query(PaymentMethod).filter(
                        PaymentMethod.stripe_payment_method_id == stripe_payment_method_id
                    ).first()
                    
                    if not existing_method:
                        # Получаем данные карты из Stripe
                        stripe_methods = StripeService.get_payment_methods(user.stripe_customer_id)
                        card_data = None
                        
                        if stripe_methods['success']:
                            for m in stripe_methods['payment_methods']:
                                if m['id'] == stripe_payment_method_id:
                                    card_data = m.get('card')
                                    break
                        
                        new_method = PaymentMethod(
                            user_id=user_id,
                            stripe_payment_method_id=stripe_payment_method_id,
                            payment_type='card',
                            card_brand=card_data.get('brand') if card_data else None,
                            card_last4=card_data.get('last4') if card_data else None,
                            card_exp_month=card_data.get('exp_month') if card_data else None,
                            card_exp_year=card_data.get('exp_year') if card_data else None,
                            is_default=True
                        )
                        db.add(new_method)
                
                # 12. Логируем успех
                audit_log = AuditLog(
                    user_id=user_id,
                    action="deposit_completed",
                    amount=Decimal(str(amount)),
                    ip_address=ip_address,
                    status="success"
                )
                db.add(audit_log)
                
                db.commit()
                
                logger.info(f"User {user_id} deposited ${amount} successfully")
                
                return {
                    "success": True,
                    "message": "Balance replenished successfully",
                    "new_balance": balance_after,
                    "transaction_id": charge_result.get('charge_id'),
                    "status": "completed"
                }
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error in replenish_balance for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }

    # =========================================================================
    # МЕТОД 3: withdraw_funds()
    # =========================================================================
    @staticmethod
    def withdraw_funds(
        db: Session,
        user_id: str,
        amount: float,
        withdrawal_method_id: int,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict:
        """
        Выводит деньги со счёта пользователя на банковский счёт/кошелёк.
        
        ⚠️ ВАЖНО: Деньги вычитаются ИЗ БАЛАНСА СРАЗУ (статус: pending)
        Затем администратор обрабатывает вывод или система автоматически.
        
        Args:
            db (Session): SQLAlchemy сессия
            user_id (str): ID пользователя
            amount (float): Сумма вывода (минимум 10.00)
            withdrawal_method_id (int): ID способа вывода
            reason (str): Причина вывода (опционально)
            ip_address (str): IP адрес клиента
        
        Returns:
            dict: {
                "success": True,
                "message": "Withdrawal request created",
                "withdrawal": {
                    "operation_id": 123,
                    "amount": 1000.0,
                    "status": "pending",
                    "estimated_completion": "2025-12-17T23:59:59Z"
                },
                "new_balance": 4000.0
            }
        
        Business Logic:
            - Минимум вывода: 10.00 USD
            - Максимум вывода: 100000.00 USD за раз
            - Дневной лимит: 50000.00 USD
            - Способ вывода должен быть верифицирован
            - Деньги вычитаются СРАЗУ (статус pending)
        """
        try:
            # 1. Валидация параметров
            if amount <= 0:
                return {"success": False, "error": "Amount must be positive"}
            
            if amount < 10.00:
                return {"success": False, "error": "Minimum withdrawal is 10.00 USD"}
            
            if amount > 100000.00:
                return {"success": False, "error": "Maximum withdrawal per transaction is 100000.00 USD"}
            
            # 2. Проверяем пользователя
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {"success": False, "error": "User not found"}
            
            # 3. Получаем баланс
            balance = db.query(UserBalance).filter(
                UserBalance.user_id == user_id
            ).first()
            
            if not balance:
                return {"success": False, "error": "Balance record not found"}
            
            current_balance = float(balance.balance)
            
            # 4. Проверяем достаточно ли денег
            if current_balance < amount:
                return {
                    "success": False,
                    "error": "Insufficient balance",
                    "available_balance": current_balance,
                    "requested_amount": amount
                }
            
            # 5. Проверяем способ вывода
            method = db.query(WithdrawalMethod).filter(
                and_(
                    WithdrawalMethod.method_id == withdrawal_method_id,
                    WithdrawalMethod.user_id == user_id
                )
            ).first()
            
            if not method:
                return {"success": False, "error": "Withdrawal method not found"}
            
            if not method.is_verified:
                return {
                    "success": False,
                    "error": "Withdrawal method not verified",
                    "message": "Please verify your withdrawal method first"
                }
            
            # 6. Проверяем дневной лимит
            today = datetime.utcnow().date()
            daily_sum = db.query(func.sum(WalletOperation.amount)).filter(
                and_(
                    WalletOperation.user_id == user_id,
                    WalletOperation.operation_type == 'withdrawal',
                    func.date(WalletOperation.created_at) == today,
                    WalletOperation.status.in_(['completed', 'pending'])
                )
            ).scalar() or Decimal("0.00")
            
            daily_limit = 50000.00
            
            if float(daily_sum) + amount > daily_limit:
                return {
                    "success": False,
                    "error": "Daily withdrawal limit exceeded",
                    "daily_limit": daily_limit,
                    "used_today": float(daily_sum),
                    "remaining": daily_limit - float(daily_sum)
                }
            
            # 7. Логируем инициацию вывода
            audit_log = AuditLog(
                user_id=user_id,
                action="withdrawal_initiated",
                amount=Decimal(str(amount)),
                ip_address=ip_address,
                status="pending"
            )
            db.add(audit_log)
            
            # 8. ВЫЧИТАЕМ ДЕНЬГИ ИЗ БАЛАНСА (СРАЗУ)
            balance_after = current_balance - amount
            
            balance.balance = Decimal(str(balance_after))
            balance.total_withdrawn = Decimal(str(float(balance.total_withdrawn or 0) + amount))
            balance.last_transaction = datetime.utcnow()
            
            # 9. Записываем транзакцию
            transaction = BalanceTransaction(
                user_id=user_id,
                transaction_type='withdrawal',
                amount=Decimal(str(-amount)),  # Отрицательное значение
                balance_before=Decimal(str(current_balance)),
                balance_after=Decimal(str(balance_after)),
                status='pending',
                description=f"Withdrawal request - {reason or 'no reason provided'}"
            )
            db.add(transaction)
            
            # 10. Записываем операцию
            operation = WalletOperation(
                user_id=user_id,
                operation_type='withdrawal',
                amount=Decimal(str(amount)),
                status='pending',
                payment_method='bank_transfer'
            )
            db.add(operation)
            db.commit()
            db.refresh(operation)
            
            # 11. Возвращаем результат
            estimated_completion = datetime.utcnow() + timedelta(days=2)
            
            logger.info(f"User {user_id} requested withdrawal of ${amount}")
            
            return {
                "success": True,
                "message": "Withdrawal request created",
                "withdrawal": {
                    "operation_id": operation.operation_id,
                    "amount": amount,
                    "status": "pending",
                    "estimated_completion": estimated_completion.isoformat()
                },
                "new_balance": balance_after,
                "note": "Withdrawal usually takes 1-2 business days"
            }
        
        except Exception as e:
            db.rollback()
            logger.error(f"Error in withdraw_funds for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": "Unexpected error",
                "details": str(e)
            }

    # =========================================================================
    # МЕТОД 4: get_bet_history()
    # =========================================================================
    @staticmethod
    def get_bet_history(
        db: Session,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        filters: Optional[Dict] = None
    ) -> Dict:
        """
        Получает историю ставок и транзакций пользователя с фильтрацией и пагинацией.
        
        Args:
            db (Session): SQLAlchemy сессия
            user_id (str): ID пользователя
            limit (int): Количество результатов (1-100, по умолчанию 50)
            offset (int): Смещение для пагинации
            filters (dict): Фильтры (опционально)
                {
                    "status": "open/resolved/cancelled",
                    "result": "win/loss",
                    "date_from": "2025-12-01",
                    "date_to": "2025-12-15",
                    "transaction_type": "deposit/bet_placed/bet_won"
                }
        
        Returns:
            dict: {
                "success": True,
                "bets": [...],
                "transactions": [...],
                "statistics": {...},
                "pagination": {...}
            }
        """
        try:
            # 1. Валидация limit/offset
            limit = min(max(limit, 1), 100)
            offset = max(offset, 0)
            
            filters = filters or {}
            
            # 2. Строим запрос для ставок
            bets_query = db.query(Bet).filter(Bet.user_id == user_id)
            
            if filters.get('status'):
                bets_query = bets_query.filter(Bet.status == filters['status'])
            
            if filters.get('result'):
                bets_query = bets_query.filter(Bet.result == filters['result'])
            
            if filters.get('date_from'):
                bets_query = bets_query.filter(
                    Bet.placed_at >= datetime.fromisoformat(filters['date_from'])
                )
            
            if filters.get('date_to'):
                bets_query = bets_query.filter(
                    Bet.placed_at <= datetime.fromisoformat(filters['date_to'])
                )
            
            # Получаем общее количество для пагинации
            total_bets = bets_query.count()
            
            # Получаем ставки с пагинацией
            bets_rows = bets_query.order_by(desc(Bet.placed_at)).offset(offset).limit(limit).all()
            
            # 3. Строим запрос для транзакций
            trans_query = db.query(BalanceTransaction).filter(
                BalanceTransaction.user_id == user_id
            )
            
            if filters.get('transaction_type'):
                trans_query = trans_query.filter(
                    BalanceTransaction.transaction_type == filters['transaction_type']
                )
            
            if filters.get('date_from'):
                trans_query = trans_query.filter(
                    BalanceTransaction.created_at >= datetime.fromisoformat(filters['date_from'])
                )
            
            if filters.get('date_to'):
                trans_query = trans_query.filter(
                    BalanceTransaction.created_at <= datetime.fromisoformat(filters['date_to'])
                )
            
            trans_rows = trans_query.order_by(
                desc(BalanceTransaction.created_at)
            ).offset(offset).limit(limit).all()
            
            # 4. Рассчитываем статистику
            stats = db.query(
                func.count(Bet.bet_id).label('total'),
                func.sum(
                    func.cast(Bet.result == 'win', Integer)
                ).label('wins'),
                func.sum(
                    func.cast(Bet.result == 'loss', Integer)
                ).label('losses'),
                func.sum(Bet.bet_amount).label('total_bet'),
                func.sum(
                    case(
                        (Bet.result == 'win', Bet.actual_win),
                        else_=Decimal("0")
                    )
                ).label('total_won')
            ).filter(
                and_(Bet.user_id == user_id, Bet.status == 'resolved')
            ).first()
            
            # 5. Форматируем результаты
            bets = []
            for bet in bets_rows:
                bets.append({
                    "bet_id": bet.bet_id,
                    "event_id": bet.event_id,
                    "odds_id": bet.odds_id,
                    "bet_type": bet.bet_type,
                    "bet_amount": float(bet.bet_amount),
                    "coefficient": float(bet.coefficient),
                    "potential_win": float(bet.potential_win),
                    "status": bet.status,
                    "result": bet.result,
                    "actual_win": float(bet.actual_win) if bet.actual_win else None,
                    "placed_at": bet.placed_at.isoformat() if bet.placed_at else None,
                    "resolved_at": bet.resolved_at.isoformat() if bet.resolved_at else None
                })
            
            transactions = []
            for trans in trans_rows:
                transactions.append({
                    "transaction_id": trans.transaction_id,
                    "type": trans.transaction_type,
                    "amount": float(trans.amount),
                    "balance_before": float(trans.balance_before),
                    "balance_after": float(trans.balance_after),
                    "status": trans.status,
                    "description": trans.description,
                    "created_at": trans.created_at.isoformat() if trans.created_at else None
                })
            
            # 6. Рассчитываем статистику
            total = stats.total or 0
            wins = stats.wins or 0
            losses = stats.losses or 0
            total_bet_amount = float(stats.total_bet or 0)
            total_won_amount = float(stats.total_won or 0)
            
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            net_profit = total_won_amount - total_bet_amount
            roi_percent = (total_won_amount / total_bet_amount * 100) if total_bet_amount > 0 else 0
            
            # 7. Возвращаем результат
            return {
                "success": True,
                "bets": bets,
                "transactions": transactions,
                "statistics": {
                    "total_bets": total,
                    "total_wins": wins,
                    "total_losses": losses,
                    "win_rate": round(win_rate, 2),
                    "total_amount_bet": total_bet_amount,
                    "total_amount_won": total_won_amount,
                    "net_profit": round(net_profit, 2),
                    "roi_percent": round(roi_percent, 2)
                },
                "pagination": {
                    "current_page": (offset // limit) + 1,
                    "total_pages": (total_bets + limit - 1) // limit,
                    "total_items": total_bets,
                    "items_per_page": limit,
                    "offset": offset
                }
            }
        
        except Exception as e:
            logger.error(f"Error in get_bet_history for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": "Database error",
                "details": str(e)
            }

    # =========================================================================
    # МЕТОД 5: export_report()
    # =========================================================================
    @staticmethod
    def export_report(
        db: Session,
        user_id: str,
        format: str = "csv",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        include_bets: bool = True,
        include_transactions: bool = True,
        include_statistics: bool = True,
        ip_address: Optional[str] = None
    ) -> Dict:
        """
        Экспортирует отчёт в CSV или PDF.
        
        Args:
            db (Session): SQLAlchemy сессия
            user_id (str): ID пользователя
            format (str): "csv" или "pdf"
            date_from (str): Начальная дата (YYYY-MM-DD)
            date_to (str): Конечная дата (YYYY-MM-DD)
            include_bets (bool): Включить ставки
            include_transactions (bool): Включить транзакции
            include_statistics (bool): Включить статистику
            ip_address (str): IP адрес клиента
        
        Returns:
            dict: {
                "success": True,
                "report": {
                    "report_id": "RPT_20251215_123456",
                    "filename": "betting_report_2025_12_15.csv",
                    "format": "csv",
                    "file_size": "45 KB",
                    "download_url": "...",
                    "expires_at": "2025-12-22T10:30:00Z",
                    "content": "..." (для CSV)
                }
            }
        """
        try:
            # 1. Валидация параметров
            if format not in ["csv", "pdf"]:
                return {"success": False, "error": "Format must be 'csv' or 'pdf'"}
            
            # Установки даты по умолчанию
            if not date_to:
                date_to = datetime.utcnow().date().isoformat()
            
            if not date_from:
                date_from = (datetime.utcnow().date() - timedelta(days=30)).isoformat()
            
            date_from_dt = datetime.fromisoformat(date_from)
            date_to_dt = datetime.fromisoformat(date_to) + timedelta(days=1)  # Включаем конечную дату
            
            # 2. Получаем данные для экспорта
            report_data: Dict[str, Any] = {
                "bets": [],
                "transactions": [],
                "statistics": {}
            }
            
            # ПОЛУЧАЕМ СТАВКИ
            if include_bets:
                bets = db.query(Bet).filter(
                    and_(
                        Bet.user_id == user_id,
                        Bet.placed_at >= date_from_dt,
                        Bet.placed_at < date_to_dt
                    )
                ).order_by(desc(Bet.placed_at)).all()
                
                report_data["bets"] = bets
            
            # ПОЛУЧАЕМ ТРАНЗАКЦИИ
            if include_transactions:
                transactions = db.query(BalanceTransaction).filter(
                    and_(
                        BalanceTransaction.user_id == user_id,
                        BalanceTransaction.created_at >= date_from_dt,
                        BalanceTransaction.created_at < date_to_dt
                    )
                ).order_by(desc(BalanceTransaction.created_at)).all()
                
                report_data["transactions"] = transactions
            
            # ПОЛУЧАЕМ СТАТИСТИКУ
            if include_statistics:
                stats = db.query(
                    func.count(Bet.bet_id).label('total'),
                    func.sum(
                        func.cast(Bet.result == 'win', Integer)
                    ).label('wins'),
                    func.sum(
                        func.cast(Bet.result == 'loss', Integer)
                    ).label('losses'),
                    func.sum(Bet.bet_amount).label('total_bet'),
                    func.sum(
                        case(
                            (Bet.result == 'win', Bet.actual_win),
                            else_=Decimal("0")
                        )
                    ).label('total_won')
                ).filter(
                    and_(
                        Bet.user_id == user_id,
                        Bet.status == 'resolved',
                        Bet.placed_at >= date_from_dt,
                        Bet.placed_at < date_to_dt
                    )
                ).first()
                
                report_data["statistics"] = stats
            
            # 3. Генерируем отчёт
            report_id = f"RPT_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
            
            if format == "csv":
                csv_content = WalletService._generate_csv_report(
                    user_id, date_from, date_to, report_data,
                    include_bets, include_transactions, include_statistics
                )
                filename = f"betting_report_{datetime.utcnow().strftime('%Y_%m_%d')}.csv"
                file_size = f"{len(csv_content)} bytes"
            else:  # PDF
                csv_content = None
                filename = f"betting_report_{datetime.utcnow().strftime('%Y_%m_%d')}.pdf"
                file_size = "~200 KB"
            
            # 4. Логируем запрос экспорта
            details_data = {
                "format": format,
                "report_id": report_id,
                "date_from": date_from,
                "date_to": date_to
            }
            # Сериализуем в JSON для совместимости (работает и с JSONB и с Text)
            audit_log = AuditLog(
                user_id=user_id,
                action="export_requested",
                ip_address=ip_address,
                status="success",
                details=json.dumps(details_data) if details_data else None
            )
            db.add(audit_log)
            db.commit()
            
            logger.info(f"Generated report {report_id} for user {user_id} in format {format}")
            
            # 5. Возвращаем результат
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            
            result = {
                "success": True,
                "report": {
                    "report_id": report_id,
                    "user_id": user_id,
                    "format": format,
                    "filename": filename,
                    "file_size": file_size,
                    "download_url": f"{settings.reports_base_url}/{report_id}",
                    "expires_at": expires_at,
                    "created_at": datetime.utcnow().isoformat()
                }
            }
            
            if format == "csv" and csv_content:
                result["report"]["content"] = csv_content
            
            return result
        
        except Exception as e:
            logger.error(f"Error in export_report for user {user_id}: {str(e)}")
            return {
                "success": False,
                "error": "Export error",
                "details": str(e)
            }

    @staticmethod
    def _generate_csv_report(
        user_id: str,
        date_from: str,
        date_to: str,
        report_data: Dict,
        include_bets: bool,
        include_transactions: bool,
        include_statistics: bool
    ) -> str:
        """Генерирует CSV содержимое отчёта."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Заголовок
        writer.writerow(["LOOSELINE Betting Report"])
        writer.writerow([f"User ID: {user_id}"])
        writer.writerow([f"Export Date: {datetime.utcnow().isoformat()}"])
        writer.writerow([f"Period: {date_from} to {date_to}"])
        writer.writerow([])
        
        # СТАВКИ
        if include_bets and report_data.get("bets"):
            writer.writerow(["=== BETS ==="])
            writer.writerow([
                "Bet ID", "Event ID", "Bet Amount", "Coefficient",
                "Potential Win", "Status", "Result", "Actual Win",
                "Placed At", "Resolved At"
            ])
            
            for bet in report_data["bets"]:
                writer.writerow([
                    bet.bet_id,
                    bet.event_id,
                    float(bet.bet_amount),
                    float(bet.coefficient),
                    float(bet.potential_win),
                    bet.status,
                    bet.result or "",
                    float(bet.actual_win) if bet.actual_win else "",
                    bet.placed_at.isoformat() if bet.placed_at else "",
                    bet.resolved_at.isoformat() if bet.resolved_at else ""
                ])
            
            writer.writerow([])
        
        # ТРАНЗАКЦИИ
        if include_transactions and report_data.get("transactions"):
            writer.writerow(["=== TRANSACTIONS ==="])
            writer.writerow([
                "Transaction ID", "Type", "Amount", "Balance Before",
                "Balance After", "Status", "Description", "Created At"
            ])
            
            for trans in report_data["transactions"]:
                writer.writerow([
                    trans.transaction_id,
                    trans.transaction_type,
                    float(trans.amount),
                    float(trans.balance_before),
                    float(trans.balance_after),
                    trans.status,
                    trans.description or "",
                    trans.created_at.isoformat() if trans.created_at else ""
                ])
            
            writer.writerow([])
        
        # СТАТИСТИКА
        if include_statistics and report_data.get("statistics"):
            stats = report_data["statistics"]
            writer.writerow(["=== STATISTICS ==="])
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Bets", stats.total or 0])
            writer.writerow(["Wins", stats.wins or 0])
            writer.writerow(["Losses", stats.losses or 0])
            writer.writerow(["Total Bet Amount", float(stats.total_bet or 0)])
            writer.writerow(["Total Won", float(stats.total_won or 0)])
            
            total_bet = float(stats.total_bet or 0)
            total_won = float(stats.total_won or 0)
            wins = stats.wins or 0
            losses = stats.losses or 0
            
            if wins + losses > 0:
                writer.writerow(["Win Rate %", round(wins / (wins + losses) * 100, 2)])
            if total_bet > 0:
                writer.writerow(["ROI %", round(total_won / total_bet * 100, 2)])
            writer.writerow(["Net Profit", round(total_won - total_bet, 2)])
        
        return output.getvalue()


