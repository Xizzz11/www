"""
Lightweight stub for the ``asyncpg`` module used in tests.

This project primarily uses SQLite for testing, but SQLAlchemy's async
PostgreSQL dialect still tries to import ``asyncpg`` when creating the
async engine.

This stub is enough to let the code import successfully. **It is NOT a real
PostgreSQL async driver** and must not be used in production.
"""

class Connection:
    """Dummy connection class."""
    pass

class Pool:
    """Dummy pool class."""
    pass

def connect(*args, **kwargs):
    """Dummy connect function."""
    raise RuntimeError("asyncpg stub: real PostgreSQL async connection is not available in this test environment")
