"""Hard cap on live spend for the e2e suites (see backend/tests/spend_cap.py)."""

from tests.spend_cap import pytest_configure, pytest_runtest_setup, pytest_terminal_summary  # noqa: F401
