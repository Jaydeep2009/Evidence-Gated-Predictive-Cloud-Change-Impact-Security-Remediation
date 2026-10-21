"""
P4-10: Baseline Comparisons
Implements baseline methods for comparison (B1-B6).
"""

from typing import Dict, Any, List
from enum import Enum
import random


class BaselineMethod(Enum):
    """Baseline comparison methods."""

    B1 = "static_analysis_only"
    B2 = "infrastructure_only"
    B3 = "random_predictor"
    B4 = "always_high_impact"
    B5 = "always_low_impact"
    B6 = "rule_based_simple"


class BaselineComparator:
    """
    Implements baseline prediction methods for comparison.

    These baselines establish performance bounds:
    - B1-B2: Component ablations (what if we remove evidence types?)
    - B3-B5: Naive strategies (random, always high, always low)
    - B6: Simple rule-based approach
    """

    def __init__(self, seed: int = 42):
        random.seed(seed)

    def predict(
        self, method: BaselineMethod, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate baseline prediction.

        Args:
            method: Baseline method to use
            scenario: Scenario being evaluated
            evidence: Available evidence

        Returns:
            Prediction in standard format
        """

        if method == BaselineMethod.B1:
            return self._static_analysis_only(scenario, evidence)

        elif method == BaselineMethod.B2:
            return self._infrastructure_only(scenario, evidence)

        elif method == BaselineMethod.B3:
            return self._random_predictor(scenario, evidence)

        elif method == BaselineMethod.B4:
            return self._always_high_impact(scenario, evidence)

        elif method == BaselineMethod.B5:
            return self._always_low_impact(scenario, evidence)

        elif method == BaselineMethod.B6:
            return self._rule_based_simple(scenario, evidence)

        return {"error": "Unknown baseline method"}

    def _static_analysis_only(
        self, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """B1: Only use static YAML analysis, ignore runtime evidence."""

        # Simple heuristic: if change_type is "policy", predict high impact
        change_type = scenario.get("change_type", "unknown")

        if change_type == "policy":
            impact = "high"
            confidence = 0.6
        else:
            impact = "low"
            confidence = 0.4

        return {
            "predicted_impact": impact,
            "confidence": confidence,
            "method": "static_analysis_only",
            "reasoning": f"Based solely on change_type={change_type}",
        }

    def _infrastructure_only(
        self, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """B2: Only use infrastructure evidence, ignore app/runtime."""

        # Check if infrastructure evidence shows NetworkPolicy
        infra = evidence.get("infrastructure", {})
        has_network_policy = "networkpolicies" in str(infra).lower()

        if has_network_policy:
            impact = "medium"
            confidence = 0.5
        else:
            impact = "low"
            confidence = 0.5

        return {
            "predicted_impact": impact,
            "confidence": confidence,
            "method": "infrastructure_only",
            "reasoning": f"Based on infrastructure evidence only",
        }

    def _random_predictor(
        self, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """B3: Random predictions (lower bound baseline)."""

        impacts = ["low", "medium", "high"]
        impact = random.choice(impacts)
        confidence = random.uniform(0.3, 0.7)

        return {
            "predicted_impact": impact,
            "confidence": confidence,
            "method": "random",
            "reasoning": "Random prediction",
        }

    def _always_high_impact(
        self, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """B4: Always predict high impact (pessimistic baseline)."""

        return {
            "predicted_impact": "high",
            "confidence": 1.0,
            "method": "always_high",
            "reasoning": "Conservative strategy: assume all changes are high impact",
        }

    def _always_low_impact(
        self, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """B5: Always predict low impact (optimistic baseline)."""

        return {
            "predicted_impact": "low",
            "confidence": 1.0,
            "method": "always_low",
            "reasoning": "Optimistic strategy: assume all changes are low impact",
        }

    def _rule_based_simple(
        self, scenario: Dict[str, Any], evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """B6: Simple rule-based approach."""

        # Rule 1: NetworkPolicy changes are high impact
        if scenario.get("change_type") == "policy":
            return {
                "predicted_impact": "high",
                "confidence": 0.8,
                "method": "rule_based",
                "reasoning": "Rule: Policy changes are high impact",
            }

        # Rule 2: Deployment changes with app evidence are medium impact
        if scenario.get("change_type") == "deployment":
            app_logs = evidence.get("application_logs", [])
            if len(app_logs) > 0:
                return {
                    "predicted_impact": "medium",
                    "confidence": 0.7,
                    "method": "rule_based",
                    "reasoning": "Rule: Deployment changes with app evidence are medium impact",
                }

        # Default: low impact
        return {
            "predicted_impact": "low",
            "confidence": 0.6,
            "method": "rule_based",
            "reasoning": "Rule: Default to low impact",
        }
