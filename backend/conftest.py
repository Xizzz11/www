"""
Compatibility shim so that ``from conftest import ...`` works in tests.

The actual pytest fixtures and test models live in ``tests/conftest.py``.
Some test modules import them as ``from conftest import ...``, which expects
``conftest`` to be importable as a top-level module. When running tests from
the backend package, that absolute import would otherwise fail.

This thin wrapper simply re-exports everything from ``tests.conftest`` so the
existing test code continues to work unchanged.
"""

from tests.conftest import *  # noqa: F401,F403


