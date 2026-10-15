"""Graph construction and analysis for evidence-gated system.

This module builds the unified evidence/dependency graph from evidence bundles,
supports evidence masking for ablation studies, and provides dependency views.
"""

from __future__ import annotations

from .builder import build_graph
from .export import export_dot, export_json
from .view import DependencyRecord, dependency_view

__all__ = [
    "build_graph",
    "dependency_view",
    "DependencyRecord",
    "export_json",
    "export_dot",
]
