"""
P4-05: Network Remediation
Generates NetworkPolicy fixes for connectivity issues.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import yaml


@dataclass
class NetworkRemediationSuggestion:
    """A suggested NetworkPolicy remediation."""

    issue_type: str  # "missing_ingress", "missing_egress", "overly_restrictive"
    affected_pod: str
    affected_namespace: str
    suggested_policy: Dict[str, Any]
    rationale: str
    confidence: float  # 0.0 to 1.0


class NetworkRemediator:
    """
    Generates NetworkPolicy remediations for connectivity issues.

    Based on evidence of blocked connections, suggests specific
    NetworkPolicy changes to restore connectivity while maintaining security.
    """

    def __init__(self):
        pass

    def analyze_blocked_connection(
        self,
        source_pod: str,
        source_namespace: str,
        dest_service: str,
        dest_namespace: str,
        dest_port: int,
        protocol: str = "TCP",
    ) -> NetworkRemediationSuggestion:
        """
        Analyze a blocked connection and suggest remediation.

        Args:
            source_pod: Name of source pod
            source_namespace: Namespace of source pod
            dest_service: Name of destination service
            dest_namespace: Namespace of destination service
            dest_port: Destination port number
            protocol: Protocol (TCP/UDP)

        Returns:
            NetworkRemediationSuggestion with policy fix
        """

        # Generate policy allowing source -> dest traffic
        policy = self._generate_allow_policy(
            source_pod=source_pod,
            source_namespace=source_namespace,
            dest_service=dest_service,
            dest_namespace=dest_namespace,
            dest_port=dest_port,
            protocol=protocol,
        )

        rationale = (
            f"Allow {source_pod} in {source_namespace} to access "
            f"{dest_service} in {dest_namespace} on port {dest_port}/{protocol}"
        )

        return NetworkRemediationSuggestion(
            issue_type="missing_ingress",
            affected_pod=dest_service,
            affected_namespace=dest_namespace,
            suggested_policy=policy,
            rationale=rationale,
            confidence=0.85,
        )

    def _generate_allow_policy(
        self,
        source_pod: str,
        source_namespace: str,
        dest_service: str,
        dest_namespace: str,
        dest_port: int,
        protocol: str,
    ) -> Dict[str, Any]:
        """Generate a NetworkPolicy allowing specific traffic."""

        policy_name = f"allow-{source_pod}-to-{dest_service}"

        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": policy_name, "namespace": dest_namespace},
            "spec": {
                "podSelector": {"matchLabels": {"app": dest_service}},
                "policyTypes": ["Ingress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {"name": source_namespace}
                                },
                                "podSelector": {"matchLabels": {"app": source_pod}},
                            }
                        ],
                        "ports": [{"protocol": protocol, "port": dest_port}],
                    }
                ],
            },
        }

    def remediate_scenario(
        self, scenario_id: str, ground_truth: Dict[str, Any]
    ) -> List[NetworkRemediationSuggestion]:
        """
        Generate remediations for a complete scenario based on ground truth.

        Args:
            scenario_id: Scenario identifier
            ground_truth: Ground truth result with failed probes

        Returns:
            List of remediation suggestions
        """
        suggestions = []

        # Parse failed probes from ground truth
        probes = ground_truth.get("probes", [])

        for probe in probes:
            if not probe.get("success", True):
                # Example: generate remediation for failed probe
                # In real implementation, parse probe URL and evidence
                # to determine source/dest/port

                suggestion = NetworkRemediationSuggestion(
                    issue_type="probe_failed",
                    affected_pod="unknown",
                    affected_namespace="poc-app",
                    suggested_policy={
                        "placeholder": "analyze probe to generate policy"
                    },
                    rationale=f"Probe to {probe.get('url')} failed",
                    confidence=0.7,
                )
                suggestions.append(suggestion)

        return suggestions

    def export_policy_yaml(
        self, suggestion: NetworkRemediationSuggestion, output_path: str
    ):
        """Export a suggested policy to YAML file."""
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(suggestion.suggested_policy, f, default_flow_style=False)
        print(f"✓ Policy exported: {output_path}")
