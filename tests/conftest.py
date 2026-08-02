import pytest

from agent import secret_scope


@pytest.fixture(autouse=True)
def reset_secret_scope_mode():
    """Keep host gateway multiplex state from contaminating local tests."""
    secret_scope.set_multiplex_active(False)
    yield
    secret_scope.set_multiplex_active(False)

