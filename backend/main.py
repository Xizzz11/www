"""
LOOSELINE Backend - Модуль управления деньгами пользователя с Stripe.

Основные функции:
- Пополнение баланса через Stripe
- Вывод средств на банк
- История транзакций и ставок
- Экспорт отчётов (CSV, PDF)
- Webhook обработка от Stripe

API Documentation: http://localhost:8000/docs
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from loguru import logger
import sys
from pathlib import Path

from config.settings import settings
from models.database import init_db
from routes.wallet import router as wallet_router
from routes.webhooks import router as webhook_router


# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if settings.app_debug else "INFO"
)
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="7 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle события приложения."""
    # Startup
    logger.info("Starting LOOSELINE Wallet Service...")
    
    # Инициализация БД (создание таблиц если не существуют)
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # Проверка Stripe конфигурации
    if not settings.stripe_secret_key:
        logger.warning("STRIPE_SECRET_KEY not configured!")
    else:
        logger.info("Stripe configured successfully")
    
    if not settings.stripe_webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured!")
    
    logger.info(f"Server starting on {settings.api_host}:{settings.api_port}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down LOOSELINE Wallet Service...")


# Создание приложения
app = FastAPI(
    title="LOOSELINE Wallet API",
    description="""
## Модуль управления деньгами пользователя с интеграцией Stripe

### Функции:
- 💳 **Пополнение баланса** через Stripe (новые и сохранённые карты)
- 💸 **Вывод средств** на банковский счёт
- 📊 **История операций** с фильтрацией и пагинацией
- 📈 **Статистика** (ROI, win rate, net profit)
- 📁 **Экспорт отчётов** в CSV и PDF
- 🔔 **Webhook** обработка событий Stripe

### Аутентификация:
Для тестирования используйте header `X-User-ID: user_123`

### Stripe тестовые карты:
- **Успешный платёж:** 4242 4242 4242 4242
- **Требует 3D Secure:** 4000 0025 0000 3155
- **Отклонённая карта:** 4000 0000 0000 0002
    """,
    version="1.0.0",
    contact={
        "name": "LOOSELINE Team",
        "email": "support@looseline.com"
    },
    license_info={
        "name": "MIT License"
    },
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка статических файлов и шаблонов
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

# Создаём директории если их нет
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)
(static_dir / "images").mkdir(exist_ok=True)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Настройка шаблонов
templates = Jinja2Templates(directory=str(templates_dir))

# Подключение роутеров
app.include_router(wallet_router)
app.include_router(webhook_router)


# Главная страница - веб-интерфейс кошелька
@app.get("/", response_class=HTMLResponse, tags=["web"])
async def index(request: Request):
    """Главная страница - веб-интерфейс кошелька."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "stripe_publishable_key": settings.stripe_publishable_key or ""
        }
    )


# Health check endpoint (API)
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "wallet",
        "stripe_configured": bool(settings.stripe_secret_key),
        "webhook_configured": bool(settings.stripe_webhook_secret)
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "wallet",
        "stripe_configured": bool(settings.stripe_secret_key),
        "webhook_configured": bool(settings.stripe_webhook_secret)
    }


# Запуск для разработки
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_debug
    )


