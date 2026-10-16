"""Evidence gate module: decision logic for SAFE/RISKY/INSUFFICIENT outcomes."""

from evgate.gate.gate import (
    apply_evidence_gate,
    forced_decision,
    generate_evidence_requests,
)

__all__ = [
    "apply_evidence_gate",
    "forced_decision",
    "generate_evidence_requests",
]
