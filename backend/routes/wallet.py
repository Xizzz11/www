"""
API роуты для работы с кошельком.

Endpoints:
- GET /api/wallet/balance - Получение баланса
- POST /api/wallet/deposit - Пополнение (новая карта)
- POST /api/wallet/deposit-saved - Пополнение (сохранённая карта)
- POST /api/wallet/withdraw - Вывод средств
- GET /api/wallet/history - История операций
- GET /api/wallet/export - Экспорт отчёта
- GET /api/wallet/payment-methods - Список способов оплаты
- POST /api/wallet/payment-methods - Добавить способ оплаты
- DELETE /api/wallet/payment-methods/{id} - Удалить способ оплаты
- GET /api/wallet/withdrawal-methods - Список способов вывода
- POST /api/wallet/withdrawal-methods - Добавить способ вывода
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from loguru import logger

from models.database import get_db
from models.orm_models import User, PaymentMethod, WithdrawalMethod
from services.wallet_service import WalletService
from services.stripe_service import StripeService
from schemas.wallet_schemas import (
    BalanceResponse,
    DepositRequest,
    DepositResponse,
    WithdrawRequest,
    WithdrawResponse,
    HistoryFilters,
    HistoryResponse,
    ExportRequest,
    ExportResponse,
    PaymentMethodCreate,
    PaymentMethodsListResponse,
    PaymentMethodResponse,
    WithdrawalMethodCreate,
    WithdrawalMethodsListResponse,
    WithdrawalMethodInfo,
    ErrorResponse
)

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


def get_client_ip(request: Request) -> Optional[str]:
    """Получает IP адрес клиента."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# Временная функция для получения user_id (в production используйте авторизацию)
def get_current_user_id(request: Request) -> str:
    """
    Получает ID текущего пользователя.
    
    В production это должно быть через JWT токен или сессию.
    Сейчас для тестирования берём из header X-User-ID.
    """
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    return user_id


# ============================================================================
# BALANCE ENDPOINTS
# ============================================================================

@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Получает текущий баланс и статистику пользователя.
    
    Returns:
        BalanceResponse: Баланс, статистика, pending операции
    
    Example Response:
        {
            "success": true,
            "balance": {
                "current_balance": 5000.00,
                "total_deposited": 10000.00,
                "net_profit": 2180.00,
                "roi_percent": 87.2
            }
        }
    """
    user_id = get_current_user_id(request)
    result = WalletService.get_balance(db, user_id)
    
    if not result['success']:
        raise HTTPException(status_code=404, detail=result.get('error', 'User not found'))
    
    return result


# ============================================================================
# DEPOSIT ENDPOINTS
# ============================================================================

@router.post("/deposit", response_model=DepositResponse)
async def create_deposit(
    request: Request,
    deposit: DepositRequest,
    db: Session = Depends(get_db)
):
    """
    Создаёт запрос на пополнение баланса.
    
    Если stripe_payment_method_id не указан:
    - Возвращает client_secret для формы оплаты Stripe
    
    Если stripe_payment_method_id указан:
    - Списывает деньги с сохранённой карты сразу
    
    Args:
        deposit: DepositRequest с суммой и опционально ID способа оплаты
    
    Returns:
        DepositResponse: client_secret для формы или результат платежа
    """
    user_id = get_current_user_id(request)
    ip_address = get_client_ip(request)
    
    result = WalletService.replenish_balance(
        db=db,
        user_id=user_id,
        amount=deposit.amount,
        stripe_payment_method_id=deposit.stripe_payment_method_id,
        payment_method=deposit.payment_method,
        save_method=deposit.save_method,
        ip_address=ip_address
    )
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result.get('error', 'Deposit failed'))
    
    return result


# ============================================================================
# WITHDRAWAL ENDPOINTS
# ============================================================================

@router.post("/withdraw", response_model=WithdrawResponse)
async def create_withdrawal(
    request: Request,
    withdrawal: WithdrawRequest,
    db: Session = Depends(get_db)
):
    """
    Создаёт запрос на вывод средств.
    
    Деньги вычитаются из баланса СРАЗУ (статус: pending).
    Фактический вывод обрабатывается позже администратором.
    
    Args:
        withdrawal: WithdrawRequest с суммой и ID способа вывода
    
    Returns:
        WithdrawResponse: Информация о созданном запросе на вывод
    
    Business Rules:
        - Минимум: 10.00 USD
        - Максимум: 100000.00 USD за раз
        - Дневной лимит: 50000.00 USD
        - Способ вывода должен быть верифицирован
    """
    user_id = get_current_user_id(request)
    ip_address = get_client_ip(request)
    
    result = WalletService.withdraw_funds(
        db=db,
        user_id=user_id,
        amount=withdrawal.amount,
        withdrawal_method_id=withdrawal.withdrawal_method_id,
        reason=withdrawal.reason,
        ip_address=ip_address
    )
    
    if not result['success']:
        error = result.get('error', 'Withdrawal failed')
        status_code = 400
        
        if error == "Insufficient balance":
            status_code = 400
        elif error == "Withdrawal method not found":
            status_code = 404
        elif error == "Withdrawal method not verified":
            status_code = 403
        elif error == "Daily withdrawal limit exceeded":
            status_code = 429
        
        raise HTTPException(status_code=status_code, detail=result)
    
    return result


# ============================================================================
# HISTORY ENDPOINTS
# ============================================================================

@router.get("/history", response_model=HistoryResponse)
async def get_history(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Количество результатов"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    status: Optional[str] = Query(None, description="Статус ставки: open, resolved, cancelled"),
    result: Optional[str] = Query(None, description="Результат: win, loss"),
    date_from: Optional[str] = Query(None, description="Начальная дата (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Конечная дата (YYYY-MM-DD)"),
    transaction_type: Optional[str] = Query(None, description="Тип транзакции"),
    db: Session = Depends(get_db)
):
    """
    Получает историю ставок и транзакций с фильтрацией и пагинацией.
    
    Args:
        limit: Количество результатов (1-100)
        offset: Смещение для пагинации
        status: Фильтр по статусу ставки
        result: Фильтр по результату
        date_from: Начальная дата
        date_to: Конечная дата
        transaction_type: Фильтр по типу транзакции
    
    Returns:
        HistoryResponse: Ставки, транзакции, статистика, пагинация
    """
    user_id = get_current_user_id(request)
    
    filters = {}
    if status:
        filters['status'] = status
    if result:
        filters['result'] = result
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    if transaction_type:
        filters['transaction_type'] = transaction_type
    
    history_result = WalletService.get_bet_history(
        db=db,
        user_id=user_id,
        limit=limit,
        offset=offset,
        filters=filters if filters else None
    )
    
    if not history_result['success']:
        raise HTTPException(status_code=500, detail=history_result.get('error', 'Failed to get history'))
    
    return history_result


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@router.post("/export", response_model=ExportResponse)
async def export_report(
    request: Request,
    export_request: ExportRequest,
    db: Session = Depends(get_db)
):
    """
    Экспортирует отчёт в CSV или PDF.
    
    Args:
        export_request: Параметры экспорта
    
    Returns:
        ExportResponse: Информация об отчёте и ссылка на скачивание
    """
    user_id = get_current_user_id(request)
    ip_address = get_client_ip(request)
    
    result = WalletService.export_report(
        db=db,
        user_id=user_id,
        format=export_request.format.value,
        date_from=export_request.date_from,
        date_to=export_request.date_to,
        include_bets=export_request.include_bets,
        include_transactions=export_request.include_transactions,
        include_statistics=export_request.include_statistics,
        ip_address=ip_address
    )
    
    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', 'Export failed'))
    
    return result


@router.get("/export", response_model=ExportResponse)
async def export_report_get(
    request: Request,
    format: str = Query("csv", description="Формат: csv или pdf"),
    date_from: Optional[str] = Query(None, description="Начальная дата"),
    date_to: Optional[str] = Query(None, description="Конечная дата"),
    include_bets: bool = Query(True),
    include_transactions: bool = Query(True),
    include_statistics: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Экспортирует отчёт (GET версия для простоты).
    """
    user_id = get_current_user_id(request)
    ip_address = get_client_ip(request)
    
    result = WalletService.export_report(
        db=db,
        user_id=user_id,
        format=format,
        date_from=date_from,
        date_to=date_to,
        include_bets=include_bets,
        include_transactions=include_transactions,
        include_statistics=include_statistics,
        ip_address=ip_address
    )
    
    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', 'Export failed'))
    
    return result


# ============================================================================
# PAYMENT METHODS ENDPOINTS
# ============================================================================

@router.get("/payment-methods", response_model=PaymentMethodsListResponse)
async def get_payment_methods(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Получает список сохранённых способов оплаты.
    
    Returns:
        PaymentMethodsListResponse: Список способов оплаты
    """
    user_id = get_current_user_id(request)
    
    # Получаем пользователя
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Если нет stripe_customer_id - возвращаем пустой список
    if not user.stripe_customer_id:
        return {
            "success": True,
            "payment_methods": []
        }
    
    # Получаем методы из Stripe
    stripe_result = StripeService.get_payment_methods(user.stripe_customer_id)
    
    # Получаем методы из БД для дополнительной информации
    db_methods = db.query(PaymentMethod).filter(
        PaymentMethod.user_id == user_id,
        PaymentMethod.is_active == True
    ).all()
    
    db_methods_dict = {m.stripe_payment_method_id: m for m in db_methods}
    
    payment_methods = []
    for pm in stripe_result.get('payment_methods', []):
        db_method = db_methods_dict.get(pm['id'])
        
        method_response = PaymentMethodResponse(
            method_id=db_method.method_id if db_method else None,
            stripe_payment_method_id=pm['id'],
            payment_type=pm['type'],
            card=pm.get('card'),
            is_default=db_method.is_default if db_method else False,
            is_active=True,
            created_at=db_method.created_at.isoformat() if db_method and db_method.created_at else None,
            last_used=db_method.last_used.isoformat() if db_method and db_method.last_used else None
        )
        payment_methods.append(method_response)
    
    return {
        "success": True,
        "payment_methods": payment_methods
    }


@router.post("/payment-methods", response_model=PaymentMethodResponse)
async def add_payment_method(
    request: Request,
    method: PaymentMethodCreate,
    db: Session = Depends(get_db)
):
    """
    Добавляет новый способ оплаты.
    
    Stripe Payment Method ID получается от Stripe Elements на frontend.
    
    Args:
        method: PaymentMethodCreate с stripe_payment_method_id
    
    Returns:
        PaymentMethodResponse: Информация о добавленном способе
    """
    user_id = get_current_user_id(request)
    
    # Получаем пользователя
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Создаём Stripe Customer если нет
    if not user.stripe_customer_id:
        stripe_result = StripeService.create_stripe_customer(
            user_id, user.email, user.name
        )
        
        if not stripe_result['success']:
            raise HTTPException(status_code=500, detail="Failed to create payment account")
        
        user.stripe_customer_id = stripe_result['stripe_customer_id']
        db.commit()
    
    # Сохраняем способ в Stripe
    save_result = StripeService.save_payment_method(
        user.stripe_customer_id,
        method.stripe_payment_method_id,
        method.set_as_default
    )
    
    if not save_result['success']:
        raise HTTPException(status_code=400, detail=save_result.get('error', 'Failed to save payment method'))
    
    # Сохраняем в БД
    pm_data = save_result.get('payment_method', {})
    card_data = pm_data.get('card', {})
    
    # Если set_as_default - снимаем флаг с других методов
    if method.set_as_default:
        db.query(PaymentMethod).filter(
            PaymentMethod.user_id == user_id
        ).update({"is_default": False})
    
    new_method = PaymentMethod(
        user_id=user_id,
        stripe_payment_method_id=method.stripe_payment_method_id,
        payment_type=pm_data.get('type', 'card'),
        card_brand=card_data.get('brand') if card_data else None,
        card_last4=card_data.get('last4') if card_data else None,
        card_exp_month=card_data.get('exp_month') if card_data else None,
        card_exp_year=card_data.get('exp_year') if card_data else None,
        is_default=method.set_as_default,
        is_active=True
    )
    db.add(new_method)
    db.commit()
    db.refresh(new_method)
    
    return PaymentMethodResponse(
        method_id=new_method.method_id,
        stripe_payment_method_id=new_method.stripe_payment_method_id,
        payment_type=new_method.payment_type,
        card={
            "brand": new_method.card_brand,
            "last4": new_method.card_last4,
            "exp_month": new_method.card_exp_month,
            "exp_year": new_method.card_exp_year
        } if new_method.card_last4 else None,
        is_default=new_method.is_default,
        is_active=new_method.is_active,
        created_at=new_method.created_at.isoformat() if new_method.created_at else None
    )


@router.delete("/payment-methods/{method_id}")
async def delete_payment_method(
    request: Request,
    method_id: int,
    db: Session = Depends(get_db)
):
    """
    Удаляет способ оплаты.
    
    Args:
        method_id: ID способа оплаты из БД
    
    Returns:
        dict: Результат удаления
    """
    user_id = get_current_user_id(request)
    
    # Находим метод в БД
    method = db.query(PaymentMethod).filter(
        PaymentMethod.method_id == method_id,
        PaymentMethod.user_id == user_id
    ).first()
    
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")
    
    # Удаляем из Stripe
    stripe_result = StripeService.delete_payment_method(method.stripe_payment_method_id)
    
    if not stripe_result['success']:
        logger.warning(f"Failed to delete payment method from Stripe: {stripe_result.get('error')}")
    
    # Помечаем как неактивный в БД
    method.is_active = False
    db.commit()
    
    return {"success": True, "message": "Payment method deleted"}


# ============================================================================
# WITHDRAWAL METHODS ENDPOINTS
# ============================================================================

@router.get("/withdrawal-methods", response_model=WithdrawalMethodsListResponse)
async def get_withdrawal_methods(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Получает список способов вывода.
    
    Returns:
        WithdrawalMethodsListResponse: Список способов вывода
    """
    user_id = get_current_user_id(request)
    
    methods = db.query(WithdrawalMethod).filter(
        WithdrawalMethod.user_id == user_id
    ).all()
    
    withdrawal_methods = []
    for m in methods:
        method_info = WithdrawalMethodInfo(
            method_id=m.method_id,
            withdrawal_type=m.withdrawal_type,
            bank_name=m.bank_name,
            account_holder_name=m.account_holder_name,
            bank_account_last4=m.bank_account_number[-4:] if m.bank_account_number else None,
            iban_last4=m.iban[-4:] if m.iban else None,
            crypto_wallet_address=m.crypto_wallet_address[:10] + "..." if m.crypto_wallet_address else None,
            is_default=m.is_default,
            is_verified=m.is_verified,
            verification_status=m.verification_status,
            created_at=m.created_at.isoformat() if m.created_at else None
        )
        withdrawal_methods.append(method_info)
    
    return {
        "success": True,
        "withdrawal_methods": withdrawal_methods
    }


@router.post("/withdrawal-methods", response_model=WithdrawalMethodInfo)
async def add_withdrawal_method(
    request: Request,
    method: WithdrawalMethodCreate,
    db: Session = Depends(get_db)
):
    """
    Добавляет новый способ вывода.
    
    Новый способ создаётся со статусом is_verified=False.
    Требуется верификация перед использованием.
    
    Args:
        method: WithdrawalMethodCreate с данными способа вывода
    
    Returns:
        WithdrawalMethodInfo: Информация о созданном способе
    """
    user_id = get_current_user_id(request)
    
    # Проверяем пользователя
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Если set_as_default - снимаем флаг с других методов
    if method.is_default:
        db.query(WithdrawalMethod).filter(
            WithdrawalMethod.user_id == user_id
        ).update({"is_default": False})
    
    new_method = WithdrawalMethod(
        user_id=user_id,
        withdrawal_type=method.withdrawal_type,
        bank_account_number=method.bank_account_number,
        bank_code=method.bank_code,
        bank_name=method.bank_name,
        account_holder_name=method.account_holder_name,
        swift_code=method.swift_code,
        iban=method.iban,
        crypto_wallet_address=method.crypto_wallet_address,
        is_default=method.is_default,
        is_verified=False,
        verification_status="pending"
    )
    db.add(new_method)
    db.commit()
    db.refresh(new_method)
    
    return WithdrawalMethodInfo(
        method_id=new_method.method_id,
        withdrawal_type=new_method.withdrawal_type,
        bank_name=new_method.bank_name,
        account_holder_name=new_method.account_holder_name,
        bank_account_last4=new_method.bank_account_number[-4:] if new_method.bank_account_number else None,
        iban_last4=new_method.iban[-4:] if new_method.iban else None,
        crypto_wallet_address=new_method.crypto_wallet_address[:10] + "..." if new_method.crypto_wallet_address else None,
        is_default=new_method.is_default,
        is_verified=new_method.is_verified,
        verification_status=new_method.verification_status,
        created_at=new_method.created_at.isoformat() if new_method.created_at else None
    )


@router.delete("/withdrawal-methods/{method_id}")
async def delete_withdrawal_method(
    request: Request,
    method_id: int,
    db: Session = Depends(get_db)
):
    """
    Удаляет способ вывода.
    
    Args:
        method_id: ID способа вывода
    
    Returns:
        dict: Результат удаления
    """
    user_id = get_current_user_id(request)
    
    method = db.query(WithdrawalMethod).filter(
        WithdrawalMethod.method_id == method_id,
        WithdrawalMethod.user_id == user_id
    ).first()
    
    if not method:
        raise HTTPException(status_code=404, detail="Withdrawal method not found")
    
    db.delete(method)
    db.commit()
    
    return {"success": True, "message": "Withdrawal method deleted"}


