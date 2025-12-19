"""
Конфигурация приложения LOOSELINE.
Загружает настройки из переменных окружения.
"""

import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения."""
    
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "looseline"
    db_user: str = "postgres"
    db_password: str = ""
    database_url: str = ""
    
    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    
    # Application
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me-in-production"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Reports
    reports_dir: str = "./reports"
    reports_base_url: str = "https://api.looseline.com/reports"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def database_connection_string(self) -> str:
        """Строка подключения к БД."""
        if self.database_url:
            return self.database_url
        # SQL Server connection string
        password = self.db_password or "YourStrong@Passw0rd"
        return f"mssql+pyodbc://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
    
    @property
    def async_database_connection_string(self) -> str:
        """Асинхронная строка подключения к БД (SQL Server не поддерживает async через pyodbc, используем синхронный)."""
        # SQL Server через pyodbc не поддерживает async, возвращаем синхронный
        return self.database_connection_string
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Список разрешённых CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Возвращает кэшированные настройки."""
    return Settings()


settings = get_settings()


