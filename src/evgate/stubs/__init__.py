"""Stub implementations for C0 bootstrap.

These stubs return canned results for change_M2.json so that Part 4 can develop
against them before the real implementations from Parts 2 and 3 are ready.
"""

from .analysis_stub import analyze_stub
from .evidence_stub import collect_evidence_stub

__all__ = ["analyze_stub", "collect_evidence_stub"]
