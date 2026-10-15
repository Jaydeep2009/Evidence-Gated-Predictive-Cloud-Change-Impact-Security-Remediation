"""Vocabulary: IDs, enums, and type aliases for the evidence-gated system."""

from __future__ import annotations

from enum import Enum

# Node ID format: "<kind>:<namespace>/<name>" or "<kind>:/<name>" for cluster-scoped
# kinds: component | workload | k8s-service | policy | principal | role | config | iac | external
# examples:
#   component:poc-app/backend
#   k8s-service:poc-app/backend-service
#   policy:poc-app/isolate-database
#   principal:poc-app/backend-sa
#   permission:get:/configmaps
#   external:/node
#   external:/internet
NodeId = str


class Relationship(str, Enum):
    """Types of relationships between nodes in the evidence graph."""

    # Application-level dependency
    DEPENDS_ON = "DEPENDS_ON"  # A needs B to function

    # Code/trace-level communication
    CALLS = "CALLS"  # code/trace-level call A -> B

    # Runtime observations
    CONNECTS_TO = "CONNECTS_TO"  # observed successful connection
    FAILED_TO_CONNECT = "FAILED_TO_CONNECT"  # observed failed connection
    OBSERVED_COMMUNICATION = "OBSERVED_COMMUNICATION"  # generic runtime link

    # Readiness coupling
    READINESS_COUPLED = "READINESS_COUPLED"  # A's readiness probe exercises B

    # Policy/configuration effects
    ALLOWS = "ALLOWS"  # config/policy allows path A -> B
    DENIES = "DENIES"  # config/policy denies path A -> B

    # Infrastructure relationships
    SELECTS = "SELECTS"  # policy -> component
    EXPOSES = "EXPOSES"  # k8s-service -> component
    DEPLOYED_AS = "DEPLOYED_AS"  # component -> workload
    CONFIGURED_BY = "CONFIGURED_BY"  # component/workload -> config/iac

    # Permission relationships
    RUNS_AS = "RUNS_AS"  # component -> principal
    HAS_PERMISSION = "HAS_PERMISSION"  # principal -> permission
    NEEDS_PERMISSION = "NEEDS_PERMISSION"  # component -> permission


class EvidenceType(str, Enum):
    """Source type of evidence."""

    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    RUNTIME = "runtime"


class Classification(str, Enum):
    """How the evidence was obtained."""

    OBSERVED = "observed"  # directly captured
    INFERRED = "inferred"  # logically derived
    VERIFIED = "verified"  # confirmed through testing


class Decision(str, Enum):
    """Evidence gate decision outcomes."""

    SAFE = "SAFE"
    RISKY = "RISKY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
