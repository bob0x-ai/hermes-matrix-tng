"""Hermes Matrix TNG plugin entry point."""

try:
    from .adapter import register
except ImportError as exc:
    # Pytest may import a repository-level __init__.py as a standalone module
    # when this project contains its own tests. Hermes's plugin loader imports
    # the package normally, so preserve the normal relative import there and
    # use this narrow collection-time fallback only for the repository tests.
    if "no known parent package" not in str(exc):
        raise
    from adapter import register

__all__ = ["register"]
