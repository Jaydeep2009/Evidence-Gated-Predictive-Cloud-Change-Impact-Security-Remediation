"""
P4-06: RBAC Remediation
Generates Role/RoleBinding fixes for permission issues.
"""

from typing import Dict, Any, List
from dataclasses import dataclass
import yaml


@dataclass
class RBACRemediationSuggestion:
    """A suggested RBAC remediation."""

    issue_type: str  # "missing_role", "missing_binding", "insufficient_permissions"
    affected_service_account: str
    affected_namespace: str
    suggested_role: Optional[Dict[str, Any]] = None
    suggested_binding: Optional[Dict[str, Any]] = None
    rationale: str = ""
    confidence: float = 0.8


class RBACRemediator:
    """
    Generates RBAC remediations for permission issues.

    Analyzes permission denials and suggests minimal Role/RoleBinding
    configurations to grant required access.
    """

    def __init__(self):
        pass

    def analyze_permission_denial(
        self,
        service_account: str,
        namespace: str,
        required_verb: str,  # get, list, create, etc.
        required_resource: str,  # pods, services, etc.
        api_group: str = "",
    ) -> RBACRemediationSuggestion:
        """
        Analyze a permission denial and suggest RBAC fix.

        Args:
            service_account: Name of service account
            namespace: Namespace
            required_verb: Required verb (get, list, create, etc.)
            required_resource: Required resource type
            api_group: API group (empty string for core)

        Returns:
            RBACRemediationSuggestion with Role and RoleBinding
        """

        role = self._generate_role(
            name=f"{service_account}-{required_resource}-role",
            namespace=namespace,
            verbs=[required_verb],
            resources=[required_resource],
            api_group=api_group,
        )

        binding = self._generate_role_binding(
            name=f"{service_account}-{required_resource}-binding",
            namespace=namespace,
            role_name=role["metadata"]["name"],
            service_account=service_account,
        )

        rationale = (
            f"Grant {service_account} permission to {required_verb} "
            f"{required_resource} in {namespace}"
        )

        return RBACRemediationSuggestion(
            issue_type="insufficient_permissions",
            affected_service_account=service_account,
            affected_namespace=namespace,
            suggested_role=role,
            suggested_binding=binding,
            rationale=rationale,
            confidence=0.85,
        )

    def _generate_role(
        self,
        name: str,
        namespace: str,
        verbs: List[str],
        resources: List[str],
        api_group: str = "",
    ) -> Dict[str, Any]:
        """Generate a Role manifest."""

        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "metadata": {"name": name, "namespace": namespace},
            "rules": [
                {"apiGroups": [api_group], "resources": resources, "verbs": verbs}
            ],
        }

    def _generate_role_binding(
        self, name: str, namespace: str, role_name: str, service_account: str
    ) -> Dict[str, Any]:
        """Generate a RoleBinding manifest."""

        return {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {"name": name, "namespace": namespace},
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": service_account,
                    "namespace": namespace,
                }
            ],
            "roleRef": {
                "kind": "Role",
                "name": role_name,
                "apiGroup": "rbac.authorization.k8s.io",
            },
        }

    def remediate_scenario(
        self, scenario_id: str, ground_truth: Dict[str, Any]
    ) -> List[RBACRemediationSuggestion]:
        """
        Generate RBAC remediations for a scenario.

        Args:
            scenario_id: Scenario identifier
            ground_truth: Ground truth result

        Returns:
            List of RBAC remediation suggestions
        """
        suggestions = []

        # Parse pod logs for permission errors
        # In real implementation, scan logs for RBAC denials

        # Example: if evidence shows "pods is forbidden"
        # suggestion = self.analyze_permission_denial(...)

        return suggestions

    def export_manifests(
        self,
        suggestion: RBACRemediationSuggestion,
        role_output_path: str,
        binding_output_path: str,
    ):
        """Export Role and RoleBinding to YAML files."""

        if suggestion.suggested_role:
            with open(role_output_path, "w", encoding="utf-8") as f:
                yaml.dump(suggestion.suggested_role, f, default_flow_style=False)
            print(f"✓ Role exported: {role_output_path}")

        if suggestion.suggested_binding:
            with open(binding_output_path, "w", encoding="utf-8") as f:
                yaml.dump(suggestion.suggested_binding, f, default_flow_style=False)
            print(f"✓ RoleBinding exported: {binding_output_path}")
