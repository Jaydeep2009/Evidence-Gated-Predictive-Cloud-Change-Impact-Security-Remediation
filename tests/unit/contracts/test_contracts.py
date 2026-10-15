"""Basic tests to verify contract models load and validate correctly."""

import json
from pathlib import Path

import pytest

from evgate.contracts import (
    ChangeSpec,
    EvidenceBundle,
    GroundTruthLabel,
    make_evidence_id,
)


@pytest.mark.unit
def test_contracts_import():
    """Verify all contract models can be imported."""
    from evgate.contracts import (
        Evidence,
        Prediction,
    )

    assert Evidence is not None
    assert EvidenceBundle is not None
    assert ChangeSpec is not None
    assert Prediction is not None


@pytest.mark.unit
def test_golden_fixture_g1_loads():
    """Verify G1 golden fixture loads and validates."""
    fixture_path = Path("fixtures/golden/G1_bundle_full.json")
    assert fixture_path.exists(), "G1 fixture must exist"

    with open(fixture_path) as f:
        data = json.load(f)

    bundle = EvidenceBundle(**data)
    assert bundle.schema_version == "1.0"
    assert bundle.snapshot_id == "baseline@m2"
    assert bundle.phase == "pre_change"
    assert len(bundle.inventory) == 3
    assert len(bundle.evidence) > 0


@pytest.mark.unit
def test_golden_fixture_change_m2_loads():
    """Verify change_M2 fixture loads and validates."""
    fixture_path = Path("fixtures/golden/change_M2.json")
    assert fixture_path.exists(), "change_M2 fixture must exist"

    with open(fixture_path) as f:
        data = json.load(f)

    change = ChangeSpec(**data)
    assert change.schema_version == "1.0"
    assert change.change_id == "change-m2-isolate-database"
    assert change.category == "kubernetes"
    assert change.direction == "tightens"
    assert len(change.effects) > 0


@pytest.mark.unit
def test_golden_fixture_gt_m2_loads():
    """Verify gt_M2_label fixture loads and validates."""
    fixture_path = Path("fixtures/golden/gt_M2_label.json")
    assert fixture_path.exists(), "gt_M2_label fixture must exist"

    with open(fixture_path) as f:
        data = json.load(f)

    label = GroundTruthLabel(**data)
    assert label.scenario_id == "M2-isolate-database"
    assert label.operational_failure is True
    assert label.security_effect == "improves"
    assert label.risky_label is True
    assert len(label.affected_components) == 3


@pytest.mark.unit
def test_make_evidence_id_is_deterministic():
    """Verify evidence ID generation is deterministic."""
    from datetime import datetime

    from evgate.contracts import (
        Classification,
        Evidence,
        EvidenceType,
        Provenance,
        Relationship,
    )

    prov = Provenance(
        source_type="file",
        source_path="test.yaml",
        extractor="test",
        extracted_at=datetime.now(),
    )

    e1 = Evidence(
        evidence_id="temp",
        evidence_type=EvidenceType.INFRASTRUCTURE,
        source="test",
        subject="component:test/a",
        relationship=Relationship.DEPENDS_ON,
        object="component:test/b",
        classification=Classification.OBSERVED,
        confidence=1.0,
        observed_at=datetime.now(),
        snapshot_id="test@1",
        provenance=prov,
    )

    e2 = Evidence(
        evidence_id="temp",
        evidence_type=EvidenceType.INFRASTRUCTURE,
        source="test",
        subject="component:test/a",
        relationship=Relationship.DEPENDS_ON,
        object="component:test/b",
        classification=Classification.OBSERVED,
        confidence=1.0,
        observed_at=datetime.now(),  # Different timestamp
        snapshot_id="test@1",
        provenance=prov,
    )

    id1 = make_evidence_id(e1)
    id2 = make_evidence_id(e2)

    assert id1 == id2, "Evidence IDs must be deterministic regardless of timestamp"
    assert id1.startswith("E-"), "Evidence IDs must start with E-"


@pytest.mark.unit
def test_evidence_bundle_leakage_check():
    """Verify bundle rejects post-change evidence."""
    from datetime import datetime

    from evgate.contracts import (
        Classification,
        ComponentInfo,
        Evidence,
        EvidenceBundle,
        EvidenceType,
        Provenance,
        Relationship,
    )

    prov = Provenance(
        source_type="file",
        source_path="post-change/test.yaml",  # Suspicious path
        extractor="test",
        extracted_at=datetime.now(),
    )

    evidence = Evidence(
        evidence_id="E-test",
        evidence_type=EvidenceType.INFRASTRUCTURE,
        source="test",
        subject="component:test/a",
        relationship=Relationship.DEPENDS_ON,
        object="component:test/b",
        classification=Classification.OBSERVED,
        confidence=1.0,
        observed_at=datetime.now(),
        snapshot_id="baseline@test",
        provenance=prov,
    )

    bundle = EvidenceBundle(
        bundle_id="test",
        snapshot_id="baseline@test",
        phase="pre_change",
        collected_at=datetime.now(),
        config_fingerprint="test",
        inventory=[
            ComponentInfo(
                node_id="component:test/a",
                namespace="test",
            )
        ],
        evidence=[evidence],
    )

    with pytest.raises(ValueError, match="post"):
        bundle.assert_no_leakage()
