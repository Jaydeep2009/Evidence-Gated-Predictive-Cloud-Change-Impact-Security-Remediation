"""
Integration stubs for Part 2 (Evidence Collection).

Replace these with real implementations when teammates' code is available.
"""

from typing import Dict, Any, List


def stub_collect_evidence(namespace: str = "poc-app") -> Dict[str, Any]:
    """
    Stub for Part 2 evidence collector.
    
    Replace with real implementation from teammates' Part 2 code:
    from evgate.evidence.collector import collect_evidence
    
    Args:
        namespace: Kubernetes namespace
    
    Returns:
        Complete evidence bundle
    """
    return {
        "application_logs": [
            {
                "timestamp": "2026-10-19T10:00:00Z",
                "level": "ERROR",
                "service": "backend",
                "message": "Connection to database failed: timeout"
            }
        ],
        "runtime_metrics": {
            "backend_request_rate": 100.0,
            "backend_error_rate": 0.15,
            "database_connection_pool": 10
        },
        "infrastructure": {
            "pods": [],
            "services": [],
            "network_policies": []
        },
        "metadata": {
            "collection_timestamp": "2026-10-19T10:00:00Z",
            "namespace": namespace,
            "collector_version": "stub-1.0"
        }
    }


class StubEvidenceCollector:
    """
    Stub class for Part 2 evidence collector.
    
    Replace with real class:
    from evgate.evidence.collector import EvidenceCollector
    """
    
    def __init__(self, namespace: str = "poc-app"):
        self.namespace = namespace
    
    def collect_all(self) -> Dict[str, Any]:
        """Collect all evidence types."""
        return stub_collect_evidence(self.namespace)
    
    def collect_app_logs(self) -> List[Dict[str, Any]]:
        """Collect application logs."""
        return stub_collect_evidence(self.namespace)["application_logs"]
    
    def collect_runtime_metrics(self) -> Dict[str, Any]:
        """Collect runtime metrics."""
        return stub_collect_evidence(self.namespace)["runtime_metrics"]
    
    def collect_infrastructure(self) -> Dict[str, Any]:
        """Collect infrastructure state."""
        return stub_collect_evidence(self.namespace)["infrastructure"]
