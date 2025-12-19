"""
Pydantic схемы для валидации данных кошелька.

Используются для:
- Валидации входных данных API
- Сериализации ответов
- Документации OpenAPI
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class TransactionType(str, Enum):
    """Типы транзакций."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BET_PLACED = "bet_placed"
    BET_WON = "bet_won"
    BET_LOST = "bet_lost"
    BET_CANCELLED = "bet_cancelled"
    COUPON_WON = "coupon_won"
    COUPON_LOST = "coupon_lost"
    BONUS_ADDED = "bonus_added"
    FEE_CHARGED = "fee_charged"
    REFUND = "refund"


class TransactionStatus(str, Enum):
    """Статусы транзакций."""
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BetStatus(str, Enum):
    """Статусы ставок."""
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class BetResult(str, Enum):
    """Результаты ставок."""
    WIN = "win"
    LOSS = "loss"
    REFUND = "refund"


class ExportFormat(str, Enum):
    """Форматы экспорта."""
    CSV = "csv"
    PDF = "pdf"


# ============================================================================
# BALANCE SCHEMAS
# ============================================================================

class BalanceInfo(BaseModel):
    """Информация о балансе."""
    user_id: str
    current_balance: float
    currency: str = "USD"
    total_deposited: float
    total_withdrawn: float
    total_bet: float
    total_won: float
    total_lost: float
    net_profit: float
    roi_percent: float
    win_count: int
    lose_count: int
    win_rate: float
    last_transaction: Optional[str] = None
    account_created: Optional[str] = None


class BalanceResponse(BaseModel):
    """Ответ на запрос баланса."""
    success: bool
    balance: Optional[BalanceInfo] = None
    available_balance: Optional[float] = None
    locked_in_bets: Optional[float] = None
    pending_deposits: Optional[float] = None
    pending_withdrawals: Optional[float] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "balance": {
                    "user_id": "user_123",
                    "current_balance": 5000.00,
                    "currency": "USD",
                    "total_deposited": 10000.00,
                    "total_withdrawn": 5000.00,
                    "total_bet": 2500.00,
                    "total_won": 3840.00,
                    "total_lost": 1660.00,
                    "net_profit": 2180.00,
                    "roi_percent": 87.2,
                    "win_count": 16,
                    "lose_count": 9,
                    "win_rate": 64.0
                },
                "available_balance": 4750.00,
                "locked_in_bets": 250.00,
                "pending_deposits": 0.00,
                "pending_withdrawals": 0.00
            }
        }


# ============================================================================
# DEPOSIT SCHEMAS
# ============================================================================

class DepositRequest(BaseModel):
    """Запрос на пополнение баланса."""
    amount: float = Field(..., gt=0, le=100000, description="Сумма пополнения (1.00 - 100000.00 USD)")
    stripe_payment_method_id: Optional[str] = Field(None, description="ID сохранённого способа оплаты в Stripe")
    payment_method: str = Field("card", description="Способ оплаты (card, bank_transfer)")
    save_method: bool = Field(False, description="Сохранить способ оплаты для будущих платежей")

    @validator('amount')
    def validate_amount(cls, v):
        if v < 1.00:
            raise ValueError('Minimum deposit is 1.00 USD')
        if v > 100000.00:
            raise ValueError('Maximum deposit is 100000.00 USD')
        return round(v, 2)

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 100.00,
                "stripe_payment_method_id": None,
                "payment_method": "card",
                "save_method": True
            }
        }


class DepositResponse(BaseModel):
    """Ответ на запрос пополнения."""
    success: bool
    action: Optional[str] = None  # "requires_payment_form" или None
    client_secret: Optional[str] = None
    intent_id: Optional[str] = None
    message: Optional[str] = None
    new_balance: Optional[float] = None
    transaction_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "action": "requires_payment_form",
                "client_secret": "pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_...",
                "intent_id": "pi_3MtwBwLkdIwHu7ix28a3tqPa",
                "message": "Please complete payment in the form"
            }
        }


# ============================================================================
# WITHDRAWAL SCHEMAS
# ============================================================================

class WithdrawRequest(BaseModel):
    """Запрос на вывод средств."""
    amount: float = Field(..., gt=0, le=100000, description="Сумма вывода (10.00 - 100000.00 USD)")
    withdrawal_method_id: int = Field(..., description="ID способа вывода из withdrawal_methods")
    reason: Optional[str] = Field(None, max_length=500, description="Причина вывода")

    @validator('amount')
    def validate_amount(cls, v):
        if v < 10.00:
            raise ValueError('Minimum withdrawal is 10.00 USD')
        if v > 100000.00:
            raise ValueError('Maximum withdrawal is 100000.00 USD')
        return round(v, 2)

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 1000.00,
                "withdrawal_method_id": 1,
                "reason": "Personal expenses"
            }
        }


class WithdrawalInfo(BaseModel):
    """Информация о выводе."""
    operation_id: int
    amount: float
    status: str
    estimated_completion: str


class WithdrawResponse(BaseModel):
    """Ответ на запрос вывода."""
    success: bool
    message: Optional[str] = None
    withdrawal: Optional[WithdrawalInfo] = None
    new_balance: Optional[float] = None
    note: Optional[str] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Withdrawal request created",
                "withdrawal": {
                    "operation_id": 123,
                    "amount": 1000.00,
                    "status": "pending",
                    "estimated_completion": "2025-12-17T23:59:59Z"
                },
                "new_balance": 4000.00,
                "note": "Withdrawal usually takes 1-2 business days"
            }
        }


# ============================================================================
# HISTORY SCHEMAS
# ============================================================================

class HistoryFilters(BaseModel):
    """Фильтры для истории."""
    status: Optional[BetStatus] = Field(None, description="Статус ставки")
    result: Optional[BetResult] = Field(None, description="Результат ставки")
    date_from: Optional[str] = Field(None, description="Начальная дата (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Конечная дата (YYYY-MM-DD)")
    transaction_type: Optional[TransactionType] = Field(None, description="Тип транзакции")


class BetInfo(BaseModel):
    """Информация о ставке."""
    bet_id: int
    event_id: int
    odds_id: Optional[int] = None
    bet_type: str = "single"
    bet_amount: float
    coefficient: float
    potential_win: float
    status: str
    result: Optional[str] = None
    actual_win: Optional[float] = None
    placed_at: Optional[str] = None
    resolved_at: Optional[str] = None


class TransactionInfo(BaseModel):
    """Информация о транзакции."""
    transaction_id: int
    type: str
    amount: float
    balance_before: float
    balance_after: float
    status: str
    description: Optional[str] = None
    created_at: Optional[str] = None


class Statistics(BaseModel):
    """Статистика пользователя."""
    total_bets: int
    total_wins: int
    total_losses: int
    win_rate: float
    total_amount_bet: float
    total_amount_won: float
    net_profit: float
    roi_percent: float


class Pagination(BaseModel):
    """Информация о пагинации."""
    current_page: int
    total_pages: int
    total_items: int
    items_per_page: int
    offset: int


class HistoryResponse(BaseModel):
    """Ответ на запрос истории."""
    success: bool
    bets: Optional[List[BetInfo]] = None
    transactions: Optional[List[TransactionInfo]] = None
    statistics: Optional[Statistics] = None
    pagination: Optional[Pagination] = None
    error: Optional[str] = None


# ============================================================================
# EXPORT SCHEMAS
# ============================================================================

class ExportRequest(BaseModel):
    """Запрос на экспорт отчёта."""
    format: ExportFormat = Field(ExportFormat.CSV, description="Формат экспорта (csv, pdf)")
    date_from: Optional[str] = Field(None, description="Начальная дата (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Конечная дата (YYYY-MM-DD)")
    include_bets: bool = Field(True, description="Включить ставки")
    include_transactions: bool = Field(True, description="Включить транзакции")
    include_statistics: bool = Field(True, description="Включить статистику")

    class Config:
        json_schema_extra = {
            "example": {
                "format": "csv",
                "date_from": "2025-12-01",
                "date_to": "2025-12-15",
                "include_bets": True,
                "include_transactions": True,
                "include_statistics": True
            }
        }


class ReportInfo(BaseModel):
    """Информация об отчёте."""
    report_id: str
    user_id: str
    format: str
    filename: str
    file_size: str
    download_url: str
    expires_at: str
    created_at: str
    content: Optional[str] = None  # Для CSV


class ExportResponse(BaseModel):
    """Ответ на запрос экспорта."""
    success: bool
    report: Optional[ReportInfo] = None
    error: Optional[str] = None


# ============================================================================
# PAYMENT METHOD SCHEMAS
# ============================================================================

class CardInfo(BaseModel):
    """Информация о карте."""
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    funding: Optional[str] = None


class PaymentMethodResponse(BaseModel):
    """Информация о способе оплаты."""
    method_id: Optional[int] = None
    stripe_payment_method_id: str
    payment_type: str
    card: Optional[CardInfo] = None
    is_default: bool = False
    is_active: bool = True
    created_at: Optional[str] = None
    last_used: Optional[str] = None


class PaymentMethodCreate(BaseModel):
    """Запрос на создание способа оплаты."""
    stripe_payment_method_id: str = Field(..., description="ID способа оплаты от Stripe")
    set_as_default: bool = Field(False, description="Установить как способ по умолчанию")

    class Config:
        json_schema_extra = {
            "example": {
                "stripe_payment_method_id": "pm_1MtwBwLkdIwHu7ix28a3tqPa",
                "set_as_default": True
            }
        }


class PaymentMethodsListResponse(BaseModel):
    """Список способов оплаты."""
    success: bool
    payment_methods: List[PaymentMethodResponse] = []
    error: Optional[str] = None


# ============================================================================
# WITHDRAWAL METHOD SCHEMAS
# ============================================================================

class WithdrawalMethodInfo(BaseModel):
    """Информация о способе вывода."""
    method_id: int
    withdrawal_type: str
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    bank_account_last4: Optional[str] = None
    iban_last4: Optional[str] = None
    crypto_wallet_address: Optional[str] = None
    is_default: bool = False
    is_verified: bool = False
    verification_status: str = "pending"
    created_at: Optional[str] = None


class WithdrawalMethodCreate(BaseModel):
    """Запрос на создание способа вывода."""
    withdrawal_type: str = Field(..., description="bank_transfer или crypto")
    bank_account_number: Optional[str] = None
    bank_code: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    swift_code: Optional[str] = None
    iban: Optional[str] = None
    crypto_wallet_address: Optional[str] = None
    is_default: bool = False


class WithdrawalMethodsListResponse(BaseModel):
    """Список способов вывода."""
    success: bool
    withdrawal_methods: List[WithdrawalMethodInfo] = []
    error: Optional[str] = None


# ============================================================================
# ERROR RESPONSE
# ============================================================================

class ErrorResponse(BaseModel):
    """Ответ с ошибкой."""
    success: bool = False
    error: str
    details: Optional[str] = None
    code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "Insufficient balance",
                "details": "Available balance: 100.00, requested: 500.00"
            }
        }


