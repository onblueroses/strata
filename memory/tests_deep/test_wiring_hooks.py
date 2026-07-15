import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Lifecycle hook and settings wiring is intentionally deferred; this port is "
        "restricted to memory code, eval tooling, fixtures, and tests."
    )
)


def test_session_start_and_end_wiring_contract_is_preserved_for_later_port() -> None:
    """Reserved intent: digest/table at start and access-log reconcile at end."""
