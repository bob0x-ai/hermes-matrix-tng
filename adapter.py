"""Phase 1 compatibility bridge for the Hermes Matrix platform plugin.

This is intentionally not the TNG adapter implementation yet. It exposes the
same registration and factory surface as the installed bundled adapter while
keeping the project independently versioned. Phase 2 will replace the bridge
with an instance-isolated adapter derived from the recorded upstream base.
"""

from __future__ import annotations

from plugins.platforms.matrix import adapter as _bundled

UPSTREAM_BASE_COMMIT = "bc747001eec58150aba08e586ff1e7a25fc532aa"
UPSTREAM_ORIGIN_MAIN_AT_BASELINE = "024f3e044bfd89ee226afc604fffafc1c2005f7ec"
TNG_PHASE = 1

register = _bundled.register
MatrixAdapter = _bundled.MatrixAdapter
check_matrix_requirements = _bundled.check_matrix_requirements

__all__ = [
    "MatrixAdapter",
    "UPSTREAM_BASE_COMMIT",
    "UPSTREAM_ORIGIN_MAIN_AT_BASELINE",
    "TNG_PHASE",
    "check_matrix_requirements",
    "register",
]
