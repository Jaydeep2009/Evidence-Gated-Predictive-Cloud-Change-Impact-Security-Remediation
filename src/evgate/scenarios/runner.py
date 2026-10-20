"""
P4-03: Ground Truth Runner
Executes scenarios and collects ground truth evidence.
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import requests

from .loader import Scenario, ProbeConfig
from ..common.kube_guard import assert_local_kind_context


@dataclass
class ProbeResult:
    """Result of a single probe execution."""
    url: str
    method: str
    status_code: Optional[int]
    success: bool
    content_matched: bool
    response_time_ms: float
    error: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


@dataclass
class GroundTruthResult:
    """Complete ground truth result for a scenario."""
    scenario_id: str
    scenario_name: str
    execution_timestamp: str
    cluster_context: str
    
    # Probe results
    probes: List[ProbeResult]
    all_probes_passed: bool
    
    # System state
    pod_status: Dict[str, Any]
    service_status: Dict[str, Any]
    policy_status: Dict[str, Any]
    
    # Timing
    setup_duration_sec: float
    probe_duration_sec: float
    total_duration_sec: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def save_json(self, output_path: Path):
        """Save result to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"✓ Ground truth saved: {output_path}")


class ScenarioRunner:
    """
    Executes experiment scenarios and collects ground truth.
    
    Features:
    - Poll-until-stable waiting for pod readiness
    - HTTP probes with content verification
    - Comprehensive system state capture
    - Safety guards against production execution
    
    Usage:
        runner = ScenarioRunner(namespace="poc-app")
        result = runner.run_scenario(scenario)
        result.save_json(Path("fixtures/ground_truth/N01.json"))
    """
    
    def __init__(
        self,
        namespace: str = "poc-app",
        poll_interval: int = 2,
        max_wait_sec: int = 120,
        probe_timeout: int = 10
    ):
        self.namespace = namespace
        self.poll_interval = poll_interval
        self.max_wait_sec = max_wait_sec
        self.probe_timeout = probe_timeout
        
        # Safety check: only run in Kind clusters
        assert_local_kind_context()
    
    def run_scenario(
        self,
        scenario: Scenario,
        apply_policies: bool = True
    ) -> GroundTruthResult:
        """
        Execute a scenario and collect ground truth.
        
        Args:
            scenario: Scenario to execute
            apply_policies: Whether to apply policy files
        
        Returns:
            GroundTruthResult with complete execution data
        """
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"Running Scenario: {scenario.id} - {scenario.name}")
        print(f"{'='*60}")
        
        # Get cluster context
        context = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True
        ).stdout.strip()
        
        # Apply policies if requested
        setup_start = time.time()
        if apply_policies:
            self._apply_policies(scenario.policy_files)
        setup_duration = time.time() - setup_start
        
        # Wait for pods to be ready
        print("\n→ Waiting for pods to be ready...")
        self._wait_for_pods_ready()
        
        # Execute probes
        print("\n→ Executing probes...")
        probe_start = time.time()
        probe_results = self._execute_probes(scenario.probes)
        probe_duration = time.time() - probe_start
        
        # Capture system state
        print("\n→ Capturing system state...")
        pod_status = self._get_pod_status()
        service_status = self._get_service_status()
        policy_status = self._get_policy_status()
        
        total_duration = time.time() - start_time
        
        all_passed = all(p.success for p in probe_results)
        
        result = GroundTruthResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            execution_timestamp=datetime.utcnow().isoformat() + "Z",
            cluster_context=context,
            probes=probe_results,
            all_probes_passed=all_passed,
            pod_status=pod_status,
            service_status=service_status,
            policy_status=policy_status,
            setup_duration_sec=round(setup_duration, 2),
            probe_duration_sec=round(probe_duration, 2),
            total_duration_sec=round(total_duration, 2)
        )
        
        # Print summary
        status_icon = "✓" if all_passed else "✗"
        print(f"\n{status_icon} Scenario {scenario.id}: {'PASSED' if all_passed else 'FAILED'}")
        print(f"  Probes: {sum(p.success for p in probe_results)}/{len(probe_results)} passed")
        print(f"  Duration: {total_duration:.2f}s")
        
        return result
    
    def _apply_policies(self, policy_files: List[str]):
        """Apply Kubernetes policy manifests."""
        if not policy_files:
            print("  No policies to apply")
            return
        
        for policy_file in policy_files:
            policy_path = Path(policy_file)
            if not policy_path.exists():
                print(f"  ⚠️  Policy file not found: {policy_file}")
                continue
            
            print(f"  Applying: {policy_file}")
            result = subprocess.run(
                ["kubectl", "apply", "-f", str(policy_path), "-n", self.namespace],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"  ⚠️  Failed to apply {policy_file}: {result.stderr}")
    
    def _wait_for_pods_ready(self):
        """Poll until all pods in namespace are ready."""
        elapsed = 0
        
        while elapsed < self.max_wait_sec:
            result = subprocess.run(
                ["kubectl", "get", "pods", "-n", self.namespace, "-o", "json"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"  ⚠️  kubectl error: {result.stderr}")
                time.sleep(self.poll_interval)
                elapsed += self.poll_interval
                continue
            
            pods = json.loads(result.stdout)
            
            if not pods.get("items"):
                print("  ⚠️  No pods found")
                time.sleep(self.poll_interval)
                elapsed += self.poll_interval
                continue
            
            all_ready = True
            for pod in pods["items"]:
                pod_name = pod["metadata"]["name"]
                conditions = pod.get("status", {}).get("conditions", [])
                ready_condition = next((c for c in conditions if c["type"] == "Ready"), None)
                
                if not ready_condition or ready_condition["status"] != "True":
                    all_ready = False
                    print(f"  Waiting for pod: {pod_name}")
                    break
            
            if all_ready:
                print("  ✓ All pods ready")
                return
            
            time.sleep(self.poll_interval)
            elapsed += self.poll_interval
        
        print(f"  ⚠️  Timeout waiting for pods ({self.max_wait_sec}s)")
    
    def _execute_probes(self, probes: List[ProbeConfig]) -> List[ProbeResult]:
        """Execute HTTP probes and verify results."""
        results = []
        
        for i, probe in enumerate(probes, 1):
            print(f"  Probe {i}/{len(probes)}: {probe.method} {probe.url}")
            
            start_time = time.time()
            
            try:
                response = requests.request(
                    method=probe.method,
                    url=probe.url,
                    timeout=probe.timeout
                )
                
                response_time = (time.time() - start_time) * 1000  # ms
                
                status_match = response.status_code == probe.expected_status
                content_match = True
                
                if probe.expected_content:
                    content_match = probe.expected_content in response.text
                
                success = status_match and content_match
                
                result = ProbeResult(
                    url=probe.url,
                    method=probe.method,
                    status_code=response.status_code,
                    success=success,
                    content_matched=content_match,
                    response_time_ms=round(response_time, 2)
                )
                
                icon = "✓" if success else "✗"
                print(f"    {icon} Status: {response.status_code} ({response_time:.0f}ms)")
                
            except Exception as e:
                result = ProbeResult(
                    url=probe.url,
                    method=probe.method,
                    status_code=None,
                    success=False,
                    content_matched=False,
                    response_time_ms=0,
                    error=str(e)
                )
                print(f"    ✗ Error: {e}")
            
            results.append(result)
        
        return results
    
    def _get_pod_status(self) -> Dict[str, Any]:
        """Get status of all pods in namespace."""
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", self.namespace, "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": result.stderr}
    
    def _get_service_status(self) -> Dict[str, Any]:
        """Get status of all services in namespace."""
        result = subprocess.run(
            ["kubectl", "get", "svc", "-n", self.namespace, "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": result.stderr}
    
    def _get_policy_status(self) -> Dict[str, Any]:
        """Get status of network policies in namespace."""
        result = subprocess.run(
            ["kubectl", "get", "networkpolicies", "-n", self.namespace, "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": result.stderr}
