"""
ДЕМО версия LOOSELINE Wallet API.
Использует SQLite для демонстрации без PostgreSQL.

Запуск: python demo.py
Затем откройте: http://127.0.0.1:8000/docs
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from fastapi import FastAPI, HTTPException, Request, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, Boolean, DECIMAL, TIMESTAMP, Text
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# ============================================================================
# DATABASE SETUP (SQLite для демо)
# ============================================================================

SQLALCHEMY_DATABASE_URL = "sqlite:///./demo_wallet.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ============================================================================
# MODELS
# ============================================================================

class User(Base):
    __tablename__ = "users"
    id = Column(String(20), primary_key=True)
    email = Column(String(100), unique=True)
    name = Column(String(100))
    stripe_customer_id = Column(String(100))
    balance = Column(DECIMAL(15, 2), default=0.00)
    total_deposited = Column(DECIMAL(15, 2), default=0.00)
    total_withdrawn = Column(DECIMAL(15, 2), default=0.00)
    total_bet = Column(DECIMAL(15, 2), default=0.00)
    total_won = Column(DECIMAL(15, 2), default=0.00)
    total_lost = Column(DECIMAL(15, 2), default=0.00)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(20))
    type = Column(String(30))
    amount = Column(DECIMAL(15, 2))
    balance_after = Column(DECIMAL(15, 2))
    status = Column(String(20), default="completed")
    created_at = Column(String(50))


# Create tables
Base.metadata.create_all(bind=engine)


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class BalanceInfo(BaseModel):
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

class BalanceResponse(BaseModel):
    success: bool
    balance: Optional[BalanceInfo] = None
    error: Optional[str] = None

class DepositRequest(BaseModel):
    amount: float = Field(..., gt=0, le=100000, description="Сумма пополнения (1.00 - 100000.00 USD)")
    stripe_payment_method_id: Optional[str] = Field(None, description="ID сохранённого способа оплаты")
    save_method: bool = Field(False, description="Сохранить способ оплаты")

    class Config:
        json_schema_extra = {
            "example": {
                "amount": 100.00,
                "stripe_payment_method_id": None,
                "save_method": True
            }
        }

class DepositResponse(BaseModel):
    success: bool
    action: Optional[str] = None
    client_secret: Optional[str] = None
    intent_id: Optional[str] = None
    message: Optional[str] = None
    new_balance: Optional[float] = None
    error: Optional[str] = None

class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0, le=100000, description="Сумма вывода (10.00 - 100000.00 USD)")
    withdrawal_method_id: int = Field(..., description="ID способа вывода")
    reason: Optional[str] = None

class WithdrawResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    new_balance: Optional[float] = None
    withdrawal: Optional[dict] = None
    error: Optional[str] = None

class TransactionInfo(BaseModel):
    id: int
    type: str
    amount: float
    balance_after: float
    status: str
    created_at: str

class HistoryResponse(BaseModel):
    success: bool
    transactions: List[TransactionInfo] = []
    statistics: dict = {}

class ExportFormat(str, Enum):
    CSV = "csv"
    PDF = "pdf"

class ExportRequest(BaseModel):
    format: ExportFormat = ExportFormat.CSV
    date_from: Optional[str] = None
    date_to: Optional[str] = None


# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID", "demo_user")
    return user_id


# ============================================================================
# CREATE DEMO USER
# ============================================================================

def create_demo_user(db: Session):
    user = db.query(User).filter(User.id == "demo_user").first()
    if not user:
        user = User(
            id="demo_user",
            email="demo@looseline.com",
            name="Demo User",
            stripe_customer_id="cus_demo123",
            balance=Decimal("5000.00"),
            total_deposited=Decimal("10000.00"),
            total_withdrawn=Decimal("5000.00"),
            total_bet=Decimal("2500.00"),
            total_won=Decimal("3840.00"),
            total_lost=Decimal("1660.00")
        )
        db.add(user)
        db.commit()
    return user


# ============================================================================
# FASTAPI APP
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - create demo user
    db = SessionLocal()
    create_demo_user(db)
    db.close()
    print("\n" + "="*60)
    print("LOOSELINE Wallet API Demo Started!")
    print("="*60)
    print("\nDocs: http://127.0.0.1:8000/docs")
    print("ReDoc: http://127.0.0.1:8000/redoc")
    print("\nUse header X-User-ID: demo_user for testing")
    print("="*60 + "\n")
    yield


app = FastAPI(
    title="💰 LOOSELINE Wallet API",
    description="""
## 🎯 Модуль управления деньгами пользователя с интеграцией Stripe

### 📋 Функции:
- 💳 **Пополнение баланса** через Stripe
- 💸 **Вывод средств** на банковский счёт
- 📊 **История транзакций** с фильтрацией
- 📈 **Статистика** (ROI, net profit)
- 📁 **Экспорт отчётов** в CSV/PDF

### 🔑 Аутентификация:
Используйте header `X-User-ID: demo_user` для тестирования

### 💳 Stripe тестовые карты:
| Номер | Результат |
|-------|-----------|
| 4242 4242 4242 4242 | ✅ Успех |
| 4000 0000 0000 0002 | ❌ Отклонено |
    """,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["🏠 Health"])
async def root():
    """API информация"""
    return {
        "service": "LOOSELINE Wallet API",
        "version": "1.0.0",
        "status": "✅ healthy",
        "docs": "/docs",
        "demo_user": "demo_user"
    }


@app.get("/api/wallet/balance", response_model=BalanceResponse, tags=["💰 Баланс"])
async def get_balance(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    📊 Получает текущий баланс и статистику пользователя.
    
    **Возвращает:**
    - Текущий баланс
    - Статистику (total_deposited, total_bet, net_profit)
    - ROI в процентах
    """
    user_id = get_user_id(request)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        # Create user if not exists
        user = User(id=user_id, email=f"{user_id}@demo.com", name=user_id, balance=Decimal("0"))
        db.add(user)
        db.commit()
    
    total_won = float(user.total_won or 0)
    total_lost = float(user.total_lost or 0)
    total_bet = float(user.total_bet or 0)
    
    net_profit = total_won - total_lost
    roi = (total_won / total_bet * 100) if total_bet > 0 else 0
    
    return BalanceResponse(
        success=True,
        balance=BalanceInfo(
            user_id=user.id,
            current_balance=float(user.balance or 0),
            total_deposited=float(user.total_deposited or 0),
            total_withdrawn=float(user.total_withdrawn or 0),
            total_bet=total_bet,
            total_won=total_won,
            total_lost=total_lost,
            net_profit=round(net_profit, 2),
            roi_percent=round(roi, 2)
        )
    )


@app.post("/api/wallet/deposit", response_model=DepositResponse, tags=["💳 Пополнение"])
async def create_deposit(
    deposit: DepositRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    💳 Создаёт запрос на пополнение баланса через Stripe.
    
    **Сценарии:**
    - Без `stripe_payment_method_id` → возвращает `client_secret` для формы
    - С `stripe_payment_method_id` → списывает сразу
    
    **Лимиты:**
    - Минимум: 1.00 USD
    - Максимум: 100,000.00 USD
    """
    user_id = get_user_id(request)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if deposit.amount < 1.00:
        return DepositResponse(success=False, error="Minimum deposit is 1.00 USD")
    
    # Simulate Stripe
    if deposit.stripe_payment_method_id is None:
        # Return client_secret for new card
        return DepositResponse(
            success=True,
            action="requires_payment_form",
            client_secret="pi_demo_secret_xxx",
            intent_id="pi_demo_123",
            message="Please complete payment in the Stripe form"
        )
    else:
        # Charge saved card
        new_balance = float(user.balance or 0) + deposit.amount
        user.balance = Decimal(str(new_balance))
        user.total_deposited = Decimal(str(float(user.total_deposited or 0) + deposit.amount))
        
        # Record transaction
        trans = Transaction(
            user_id=user_id,
            type="deposit",
            amount=Decimal(str(deposit.amount)),
            balance_after=user.balance,
            created_at=datetime.utcnow().isoformat()
        )
        db.add(trans)
        db.commit()
        
        return DepositResponse(
            success=True,
            message="✅ Balance replenished successfully!",
            new_balance=new_balance
        )


@app.post("/api/wallet/withdraw", response_model=WithdrawResponse, tags=["💸 Вывод"])
async def create_withdrawal(
    withdrawal: WithdrawRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    💸 Создаёт запрос на вывод средств.
    
    ⚠️ **Важно:** Деньги вычитаются из баланса СРАЗУ (статус: pending)
    
    **Лимиты:**
    - Минимум: 10.00 USD
    - Максимум: 100,000.00 USD
    - Дневной лимит: 50,000.00 USD
    """
    user_id = get_user_id(request)
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_balance = float(user.balance or 0)
    
    if withdrawal.amount < 10.00:
        return WithdrawResponse(success=False, error="Minimum withdrawal is 10.00 USD")
    
    if withdrawal.amount > current_balance:
        return WithdrawResponse(
            success=False, 
            error=f"Insufficient balance. Available: ${current_balance:.2f}"
        )
    
    new_balance = current_balance - withdrawal.amount
    user.balance = Decimal(str(new_balance))
    user.total_withdrawn = Decimal(str(float(user.total_withdrawn or 0) + withdrawal.amount))
    
    trans = Transaction(
        user_id=user_id,
        type="withdrawal",
        amount=Decimal(str(-withdrawal.amount)),
        balance_after=user.balance,
        status="pending",
        created_at=datetime.utcnow().isoformat()
    )
    db.add(trans)
    db.commit()
    
    return WithdrawResponse(
        success=True,
        message="✅ Withdrawal request created",
        new_balance=new_balance,
        withdrawal={
            "operation_id": trans.id,
            "amount": withdrawal.amount,
            "status": "pending",
            "estimated_completion": (datetime.utcnow() + timedelta(days=2)).isoformat()
        }
    )


@app.get("/api/wallet/history", response_model=HistoryResponse, tags=["📊 История"])
async def get_history(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    type: Optional[str] = Query(None, description="Тип: deposit, withdrawal, bet_placed"),
    db: Session = Depends(get_db)
):
    """
    📊 Получает историю транзакций с фильтрацией и пагинацией.
    
    **Фильтры:**
    - `type`: deposit, withdrawal, bet_placed, bet_won, bet_lost
    - `limit`: количество записей (1-100)
    - `offset`: смещение для пагинации
    """
    user_id = get_user_id(request)
    
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    if type:
        query = query.filter(Transaction.type == type)
    
    transactions = query.order_by(Transaction.id.desc()).offset(offset).limit(limit).all()
    
    trans_list = [
        TransactionInfo(
            id=t.id,
            type=t.type,
            amount=float(t.amount),
            balance_after=float(t.balance_after),
            status=t.status,
            created_at=t.created_at
        )
        for t in transactions
    ]
    
    return HistoryResponse(
        success=True,
        transactions=trans_list,
        statistics={
            "total_count": len(trans_list),
            "limit": limit,
            "offset": offset
        }
    )


@app.post("/api/wallet/export", tags=["📁 Экспорт"])
async def export_report(
    export: ExportRequest,
    request: Request
):
    """
    📁 Экспортирует отчёт в CSV или PDF.
    
    **Форматы:**
    - `csv`: Табличные данные
    - `pdf`: Красиво оформленный отчёт
    
    **Срок жизни:** Ссылка действует 7 дней
    """
    user_id = get_user_id(request)
    
    report_id = f"RPT_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    return {
        "success": True,
        "report": {
            "report_id": report_id,
            "user_id": user_id,
            "format": export.format.value,
            "filename": f"report_{report_id}.{export.format.value}",
            "download_url": f"https://api.looseline.com/reports/{report_id}",
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
        }
    }


@app.get("/api/wallet/payment-methods", tags=["💳 Способы оплаты"])
async def get_payment_methods(request: Request):
    """
    💳 Получает список сохранённых способов оплаты.
    """
    return {
        "success": True,
        "payment_methods": [
            {
                "id": "pm_demo_1",
                "type": "card",
                "card": {
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 12,
                    "exp_year": 2025
                },
                "is_default": True
            },
            {
                "id": "pm_demo_2",
                "type": "card",
                "card": {
                    "brand": "mastercard",
                    "last4": "5555",
                    "exp_month": 6,
                    "exp_year": 2026
                },
                "is_default": False
            }
        ]
    }


@app.post("/api/webhook/stripe", tags=["🔔 Webhooks"])
async def stripe_webhook(request: Request):
    """
    🔔 Webhook endpoint для Stripe.
    
    **Обрабатывает события:**
    - `payment_intent.succeeded` - Платёж успешен
    - `payment_intent.payment_failed` - Платёж не прошёл
    - `payment_intent.requires_action` - Требует 3D Secure
    """
    return {
        "status": "received",
        "message": "Webhook processed (demo mode)"
    }


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

