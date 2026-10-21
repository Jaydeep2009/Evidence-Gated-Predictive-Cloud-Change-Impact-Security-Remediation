"""
P4-01: Scenario Loader
Loads experiment scenarios from YAML files with validation.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
from pydantic import BaseModel, Field, validator


class ProbeConfig(BaseModel):
    """Configuration for a ground truth probe."""
    url: str
    method: str = "GET"
    expected_status: int = 200
    expected_content: Optional[str] = None
    timeout: int = 10


class Scenario(BaseModel):
    """
    Experiment scenario definition.
    
    Validates structure and provides type-safe access to scenario properties.
    """
    id: str = Field(..., description="Unique scenario identifier (e.g., N01, R01, M01)")
    name: str = Field(..., description="Human-readable scenario name")
    category: str = Field(..., description="Category: network, rbac, mixed, typo")
    description: str = Field(..., description="What this scenario tests")
    
    # Change configuration
    change_type: str = Field(..., description="Type of change: policy, deployment, service")
    before_config: Optional[Dict[str, Any]] = Field(None, description="Initial configuration state")
    after_config: Optional[Dict[str, Any]] = Field(None, description="Modified configuration state")
    
    # Expected impact
    expected_impacts: List[str] = Field(default_factory=list, description="List of expected impacts")
    expected_behavior: str = Field(..., description="Expected system behavior after change")
    
    # Ground truth collection
    probes: List[ProbeConfig] = Field(default_factory=list, description="Probes to verify behavior")
    policy_files: List[str] = Field(default_factory=list, description="Kubernetes policy manifest paths")
    
    @validator("category")
    def validate_category(cls, v):
        allowed = ["network", "rbac", "mixed", "typo"]
        if v not in allowed:
            raise ValueError(f"Category must be one of {allowed}")
        return v
    
    @validator("change_type")
    def validate_change_type(cls, v):
        allowed = ["policy", "deployment", "service", "configmap", "secret"]
        if v not in allowed:
            raise ValueError(f"Change type must be one of {allowed}")
        return v


class ScenarioLoader:
    """
    Loads and validates experiment scenarios from YAML files.
    
    Usage:
        loader = ScenarioLoader("scenarios/")
        scenario = loader.load_scenario("N01-isolate-database-m2.yaml")
        all_scenarios = loader.load_all()
    """
    
    def __init__(self, scenarios_dir: Path | str):
        self.scenarios_dir = Path(scenarios_dir)
        if not self.scenarios_dir.exists():
            raise FileNotFoundError(f"Scenarios directory not found: {self.scenarios_dir}")
    
    def load_scenario(self, filename: str) -> Scenario:
        """Load and validate a single scenario file."""
        filepath = self.scenarios_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"Scenario file not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return Scenario(**data)
    
    def load_all(self) -> List[Scenario]:
        """Load all scenario YAML files in the directory."""
        scenarios = []
        
        for yaml_file in sorted(self.scenarios_dir.glob("*.yaml")):
            try:
                scenario = self.load_scenario(yaml_file.name)
                scenarios.append(scenario)
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file.name}: {e}")
        
        return scenarios
    
    def load_by_category(self, category: str) -> List[Scenario]:
        """Load all scenarios matching a specific category."""
        all_scenarios = self.load_all()
        return [s for s in all_scenarios if s.category == category]
    
    def get_scenario_by_id(self, scenario_id: str) -> Optional[Scenario]:
        """Find a scenario by its ID."""
        all_scenarios = self.load_all()
        for scenario in all_scenarios:
            if scenario.id == scenario_id:
                return scenario
        return None
    
    def validate_all(self) -> Dict[str, Any]:
        """
        Validate all scenarios and return a summary report.
        
        Returns:
            dict: {"valid": count, "invalid": count, "errors": [...]}
        """
        valid = 0
        invalid = 0
        errors = []
        
        for yaml_file in sorted(self.scenarios_dir.glob("*.yaml")):
            try:
                self.load_scenario(yaml_file.name)
                valid += 1
            except Exception as e:
                invalid += 1
                errors.append({"file": yaml_file.name, "error": str(e)})
        
        return {
            "valid": valid,
            "invalid": invalid,
            "total": valid + invalid,
            "errors": errors
        }


def load_scenario_yaml(yaml_path: Path | str) -> Scenario:
    """
    Convenience function to load a single scenario.
    
    Args:
        yaml_path: Path to scenario YAML file
    
    Returns:
        Validated Scenario object
    """
    yaml_path = Path(yaml_path)
    loader = ScenarioLoader(yaml_path.parent)
    return loader.load_scenario(yaml_path.name)
