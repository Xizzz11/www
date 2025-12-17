"""
Lightweight stub for the ``psycopg2`` module used in tests.

This project primarily uses SQLite for testing (see ``tests/conftest.py``),
but SQLAlchemy's PostgreSQL dialect still tries to import ``psycopg2`` when
creating the default engine.

On this environment installing the real ``psycopg2-binary`` package is not
possible (Python / build toolchain limitations), so this stub is enough to
let the code import successfully. **It is NOT a real PostgreSQL driver** and
must not be used in production.
"""

# SQLAlchemy expects DBAPI modules to expose this attribute. Psycopg2 uses
# the "pyformat" paramstyle.
paramstyle = "pyformat"


class _Extras:
    """
    Minimal stand-in for ``psycopg2.extras``.

    SQLAlchemy only imports this module to wire optional features; our tests
    never rely on those, so an empty placeholder is sufficient.
    """


extras = _Extras()


class Error(Exception):
    """Base DB-API error placeholder."""


def connect(*args, **kwargs):
    """
    Dummy connect function.

    It should never be called in our test suite because tests use an
    in-memory SQLite database. If it does get called, we raise a clear
    error to avoid any silent misuse.
    """
    raise Error("psycopg2 stub: real PostgreSQL connection is not available in this test environment")



