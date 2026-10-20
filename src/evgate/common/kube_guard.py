"""
Kubernetes safety guards to prevent accidental production execution.
"""

import subprocess
import sys
from typing import Optional


class KubeContextError(Exception):
    """Raised when attempting to run in non-Kind context."""
    pass


def get_current_context() -> Optional[str]:
    """Get the current kubectl context."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def assert_local_kind_context():
    """
    Safety guard: Assert we're using a local Kind cluster.
    
    Raises:
        KubeContextError: If not in a Kind context
    
    This prevents accidentally running experiments against production clusters.
    """
    context = get_current_context()
    
    if context is None:
        raise KubeContextError("No kubectl context found. Is kubectl configured?")
    
    # Kind contexts typically contain 'kind-' prefix
    if "kind-" not in context.lower():
        raise KubeContextError(
            f"Safety check failed: Current context '{context}' is not a Kind cluster. "
            f"This tool should only run in local Kind clusters to prevent "
            f"accidental production changes. "
            f"\nTo create a Kind cluster: kind create cluster --name poc-cluster"
        )
    
    print(f"✓ Safety check passed: Using Kind context '{context}'")


def confirm_destructive_action(action_description: str) -> bool:
    """
    Prompt user to confirm a destructive action.
    
    Args:
        action_description: Description of the action to confirm
    
    Returns:
        True if user confirms, False otherwise
    """
    print(f"\n⚠️  DESTRUCTIVE ACTION: {action_description}")
    response = input("Type 'yes' to continue: ").strip().lower()
    return response == "yes"
