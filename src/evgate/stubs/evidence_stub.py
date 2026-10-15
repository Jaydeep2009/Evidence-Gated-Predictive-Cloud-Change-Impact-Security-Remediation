"""Stub for evidence collection (Part 2's responsibility).

Returns G1_bundle_full.json for any input until the real collector is ready.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evgate.contracts import EvidenceBundle


def collect_evidence_stub(
    manifests_dir: Path | str,
    source_dirs: list[Path] | list[str] | None = None,
    runtime_dir: Path | str | None = None,
    snapshot_id: str = "baseline@m2",
    **kwargs: Any,
) -> EvidenceBundle:
    """Stub that returns G1_bundle_full.json.

    This allows Part 3 and Part 4 to develop against a known bundle structure
    before Part 2's real evidence collectors are implemented.

    Args:
        manifests_dir: Path to Kubernetes manifests (ignored by stub)
        source_dirs: Paths to application source code (ignored by stub)
        runtime_dir: Path to runtime telemetry (ignored by stub)
        snapshot_id: Snapshot identifier (ignored by stub)
        **kwargs: Additional arguments (ignored by stub)

    Returns:
        EvidenceBundle loaded from fixtures/golden/G1_bundle_full.json
    """
    # Find the fixtures directory relative to this file
    repo_root = Path(__file__).parent.parent.parent.parent
    fixture_path = repo_root / "fixtures" / "golden" / "G1_bundle_full.json"

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Golden fixture not found at {fixture_path}. "
            "Run C0 bootstrap to create it."
        )

    with open(fixture_path) as f:
        data = json.load(f)

    return EvidenceBundle(**data)
