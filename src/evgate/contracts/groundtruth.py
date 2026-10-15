"""Ground truth models: measured runtime behavior and labels."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .vocab import NodeId


class ProbeSpec(BaseModel):
    """Specification for a runtime probe."""

    probe_id: str
    kind: Literal["http", "tcp", "k8s_auth"]
    via: Literal["host_nodeport", "pod_exec", "port_forward"]
    target: str  # URL / host:port / "<sa> <verb> <resource>"
    expect_status: int | None = None
    expect_body_contains: str | None = None  # content check (D8)
    touches: list[NodeId] = Field(default_factory=list)  # components this probe exercises
    required: bool = True  # a failing required probe == operational failure


class ProbeResult(BaseModel):
    """Result from executing a probe."""

    probe_id: str
    passed: bool
    observed: str
    attempts: int
    latency_ms: float | None = None


class ComponentState(BaseModel):
    """Observed state of a component."""

    ready: bool
    phase: str
    restart_count: int


class EnvironmentFingerprint(BaseModel):
    """Reproducibility fingerprint of the execution environment."""

    kind: str  # kind version
    kubectl: str  # kubectl version
    tofu: str | None = None  # tofu version
    docker: str  # docker version
    node_image: str  # kubernetes node image
    image_digests: dict[str, str] = Field(default_factory=dict)  # service -> digest
    git_sha: str  # code git commit
    manifests_sha256: str  # hash of manifests


class GroundTruthRun(BaseModel):
    """A single ground truth measurement run."""

    scenario_id: str
    run_index: int
    phase: Literal["baseline", "post_change", "post_remediation", "recovered"]
    started_at: datetime
    stable_after_s: float
    probes: list[ProbeResult] = Field(default_factory=list)
    components: dict[NodeId, ComponentState] = Field(default_factory=dict)
    reachability: dict[str, bool] = Field(
        default_factory=dict
    )  # "src->dst:port" -> reachable
    permissions: dict[str, bool] = Field(
        default_factory=dict
    )  # "<sa>|verb|resource" -> allowed
    env: EnvironmentFingerprint


class GroundTruthLabel(BaseModel):
    """Aggregate ground truth label from multiple runs."""

    scenario_id: str
    operational_failure: bool
    affected_components: list[NodeId] = Field(default_factory=list)
    security_effect: Literal["improves", "neutral", "degrades"]
    risky_label: bool  # operational_failure or security_effect == "degrades"
    stable: bool  # all R runs agree
    runs: int
    remediation_restores_function: bool | None = None
    remediation_keeps_objective: bool | None = None
