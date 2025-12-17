"""Service package exports.

We expose ``StripeService`` unconditionally, and ``WalletService`` on a
best-effort basis. In lightweight test environments (like this one) the
PostgreSQL driver might be missing, which would normally make importing
``wallet_service`` fail when SQLAlchemy tries to create a Postgres engine.

To keep the package importable for tests that only use Stripe-related
functionality, we gracefully degrade and expose ``WalletService = None``
if its import fails. Production setups with all dependencies installed
will still import the real implementation.
"""

from .stripe_service import StripeService

try:  # pragma: no cover - behaviour is environment-specific
    from .wallet_service import WalletService  # type: ignore
except Exception:  # ImportError, ModuleNotFoundError, DB driver issues, etc.
    WalletService = None  # type: ignore

__all__ = ["StripeService", "WalletService"]


