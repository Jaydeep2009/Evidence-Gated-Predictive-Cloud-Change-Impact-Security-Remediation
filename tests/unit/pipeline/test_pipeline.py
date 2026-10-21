"""Unit tests for analyze() pipeline.

Tests verify §8.5 pipeline integration:
- Config loading
- Evidence masking (A/B/C/D)
- Leakage guard
- End-to-end prediction with golden fixtures
- Determinism
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from evgate.contracts import ChangeSpec, Decision, EvidenceBundle, Provenance
from evgate.pipeline import analyze, get_evidence_mask, get_git_sha, load_config


@pytest.fixture
def fixtures_dir() -> Path:
    """Get fixtures directory path."""
    return Path(__file__).parent.parent.parent.parent / "fixtures" / "golden"


@pytest.fixture
def config_path() -> Path:
    """Get config file path."""
    return Path(__file__).parent.parent.parent.parent / "config" / "analysis.yaml"


@pytest.fixture
def load_g1(fixtures_dir: Path) -> EvidenceBundle:
    """Load G1 golden fixture (full evidence)."""
    with open(fixtures_dir / "G1_bundle_full.json") as f:
        data = json.load(f)
    return EvidenceBundle(**data)


@pytest.fixture
def load_g2(fixtures_dir: Path) -> EvidenceBundle:
    """Load G2 golden fixture (no runtime)."""
    with open(fixtures_dir / "G2_bundle_no_runtime.json") as f:
        data = json.load(f)
    return EvidenceBundle(**data)


@pytest.fixture
def load_g3(fixtures_dir: Path) -> EvidenceBundle:
    """Load G3 golden fixture (conflict)."""
    with open(fixtures_dir / "G3_bundle_conflict.json") as f:
        data = json.load(f)
    return EvidenceBundle(**data)


@pytest.fixture
def load_change_m2(fixtures_dir: Path) -> ChangeSpec:
    """Load M2 change fixture (isolate-database NetworkPolicy)."""
    with open(fixtures_dir / "change_M2.json") as f:
        data = json.load(f)
    return ChangeSpec(**data)


@pytest.mark.unit
def test_load_config_success(config_path: Path):
    """Test config loading with valid file."""
    config = load_config(config_path)

    # Check required keys
    assert "reliability" in config
    assert "tau_pos" in config
    assert "tau_risk" in config
    assert "tau_suff_pos" in config
    assert "tau_suff_neg" in config

    # Check reliability weights
    assert "infrastructure" in config["reliability"]
    assert "application" in config["reliability"]
    assert "runtime" in config["reliability"]


@pytest.mark.unit
def test_load_config_missing_file():
    """Test config loading with missing file."""
    with pytest.raises(FileNotFoundError):
        load_config(Path("nonexistent.yaml"))


@pytest.mark.unit
def test_get_evidence_mask_a():
    """Test evidence mask A (infrastructure only)."""
    from evgate.contracts import EvidenceType

    mask = get_evidence_mask("A")
    assert mask == {EvidenceType.INFRASTRUCTURE}


@pytest.mark.unit
def test_get_evidence_mask_b():
    """Test evidence mask B (infrastructure + application)."""
    from evgate.contracts import EvidenceType

    mask = get_evidence_mask("B")
    assert mask == {EvidenceType.INFRASTRUCTURE, EvidenceType.APPLICATION}


@pytest.mark.unit
def test_get_evidence_mask_c():
    """Test evidence mask C (infrastructure + runtime)."""
    from evgate.contracts import EvidenceType

    mask = get_evidence_mask("C")
    assert mask == {EvidenceType.INFRASTRUCTURE, EvidenceType.RUNTIME}


@pytest.mark.unit
def test_get_evidence_mask_d():
    """Test evidence mask D (all evidence types)."""
    from evgate.contracts import EvidenceType

    mask = get_evidence_mask("D")
    assert mask == {
        EvidenceType.INFRASTRUCTURE,
        EvidenceType.APPLICATION,
        EvidenceType.RUNTIME,
    }


@pytest.mark.unit
def test_get_evidence_mask_invalid():
    """Test evidence mask with invalid config."""
    with pytest.raises(ValueError, match="Unknown evidence_config"):
        get_evidence_mask("X")


@pytest.mark.unit
def test_get_git_sha():
    """Test git SHA retrieval."""
    sha = get_git_sha()
    # Should be 8 chars or "unknown"
    assert len(sha) == 8 or sha == "unknown"


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_analyze_g1_risky(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test analyze with G1 (full evidence) → RISKY prediction.

    G1 has full infrastructure + application + runtime evidence showing
    backend→database dependency. M2 blocks this path, so should be RISKY.
    """
    result = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    # Check basic structure
    assert result.change_id == load_change_m2.change_id
    assert result.evidence_config == "D"
    assert result.gate_enabled is True

    # G1 should predict RISKY (high-belief dependency being blocked)
    assert result.gate.decision == Decision.RISKY

    # Should have operational impacts
    assert len(result.prediction.affected_components) > 0

    # Versions should be populated
    assert "git_sha" in result.versions
    assert "evgate_version" in result.versions


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G2 golden fixture to be created by P2")
def test_analyze_g2_insufficient(
    load_g2: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test analyze with G2 (no runtime) → INSUFFICIENT.

    G2 lacks runtime evidence. When runtime is in the mask (config D),
    absence of runtime should trigger INSUFFICIENT per §8.4.
    """
    result = analyze(
        change=load_change_m2,
        bundle=load_g2,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    # G2 with config D should be INSUFFICIENT (no runtime evidence)
    assert result.gate.decision == Decision.INSUFFICIENT_EVIDENCE


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G3 golden fixture to be created by P2")
def test_analyze_g3_insufficient_conflict(
    load_g3: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test analyze with G3 (conflict) → INSUFFICIENT.

    G3 has conflicting evidence (infra says DENIES, runtime says CONNECTS_TO).
    This should trigger INSUFFICIENT per §8.4.
    """
    result = analyze(
        change=load_change_m2,
        bundle=load_g3,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    # G3 should be INSUFFICIENT due to conflict
    assert result.gate.decision == Decision.INSUFFICIENT_EVIDENCE
    # Should have CONFLICTING_EVIDENCE in reasons
    from evgate.contracts import ReasonCode

    assert ReasonCode.CONFLICTING_EVIDENCE in result.gate.reasons


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_analyze_forced_decision_mode(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test analyze with gate_enabled=False (forced decision mode).

    In D_NOGATE mode, the gate is bypassed and forced_decision() is used.
    """
    result = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="D_NOGATE",
        gate_enabled=False,
        config_path=config_path,
    )

    assert result.gate_enabled is False
    assert result.evidence_config == "D_NOGATE"
    # Forced decision should still return RISKY for high operational risk
    assert result.gate.decision == Decision.RISKY


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_analyze_evidence_mask_a(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test analyze with config A (infrastructure only).

    Config A should only use infrastructure evidence.
    """
    result = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="A",
        gate_enabled=True,
        config_path=config_path,
    )

    assert result.evidence_config == "A"
    # Infrastructure-only may have weaker belief than full evidence


@pytest.mark.unit
def test_leakage_guard_rejects_post_change():
    """Test that leakage guard rejects post-change evidence.

    Per D1: only pre-change evidence allowed in analyze().
    """
    from evgate.contracts import Evidence, EvidenceType, Relationship

    # Create evidence with suspicious provenance (post-change indicator)
    suspicious_evidence = Evidence(
        evidence_id="E-suspicious",
        evidence_type=EvidenceType.RUNTIME,
        source="jaeger-trace",
        subject="backend",
        relationship=Relationship.CONNECTS_TO,
        object="database",
        polarity="supports",
        classification="observed",
        confidence=0.9,
        observed_at=datetime(2026, 10, 15, 12, 0, 0),
        snapshot_id="test",
        provenance=Provenance(
            source_type="trace",
            source_path="post-change/traces.json",  # Suspicious path
            extractor="runtime.traces",
            extracted_at=datetime(2026, 10, 15, 12, 0, 0),
        ),
        metadata={"policy_active": True},  # Post-change indicator
    )

    bad_bundle = EvidenceBundle(
        bundle_id="test-bad",
        snapshot_id="test",
        phase="pre_change",  # Claims pre-change
        collected_at=datetime(2026, 10, 15, 12, 0, 0),
        config_fingerprint="abc123",
        inventory=[],
        evidence=[suspicious_evidence],  # But contains post-change evidence
    )

    change = ChangeSpec(
        change_id="TEST-001",
        category="network",
        kind="k8s_networkpolicy",
        operation="add",
        summary="Test change",
        after_ref="/test",
        supported=True,
        effects=[],
    )

    with pytest.raises(ValueError, match="post-change evidence"):
        analyze(
            change=change,
            bundle=bad_bundle,
            evidence_config="D",
            gate_enabled=True,
        )


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_determinism_same_input_same_output(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test that analyze() produces deterministic output.

    Per §10: same inputs should produce identical results.
    """
    # Run analysis twice
    result1 = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    result2 = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    # Convert to JSON (excluding versions which may vary)
    json1 = result1.model_dump(exclude={"versions"})
    json2 = result2.model_dump(exclude={"versions"})

    # Should be identical
    assert json1 == json2


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_determinism_json_serialization(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test that JSON serialization is deterministic.

    Per §10: same result should produce byte-identical JSON.
    """
    result = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    # Serialize twice (Pydantic v2 doesn't have sort_keys parameter)
    json1 = result.model_dump_json(exclude={"versions"}, indent=2)
    json2 = result.model_dump_json(exclude={"versions"}, indent=2)

    # Should be byte-identical
    assert json1 == json2


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_analyze_all_configs(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test analyze with all evidence configs (A/B/C/D).

    Verify that all configs produce valid results.
    """
    configs = ["A", "B", "C", "D"]

    for config in configs:
        result = analyze(
            change=load_change_m2,
            bundle=load_g1,
            evidence_config=config,  # type: ignore
            gate_enabled=True,
            config_path=config_path,
        )

        assert result.evidence_config == config
        assert result.gate.decision in [
            Decision.SAFE,
            Decision.RISKY,
            Decision.INSUFFICIENT_EVIDENCE,
        ]


@pytest.mark.unit
@pytest.mark.skip(reason="Requires G1 golden fixture to be created by P2")
def test_analyze_operational_impacts_sorted(
    load_g1: EvidenceBundle, load_change_m2: ChangeSpec, config_path: Path
):
    """Test that operational impacts are sorted for determinism."""
    result = analyze(
        change=load_change_m2,
        bundle=load_g1,
        evidence_config="D",
        gate_enabled=True,
        config_path=config_path,
    )

    # Get component names from affected_components
    components = [imp.component for imp in result.prediction.affected_components]

    # Should be sorted
    assert components == sorted(components)
