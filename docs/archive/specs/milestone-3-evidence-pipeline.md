# Milestone 3: Evidence Extraction Pipeline

**Status:** PLANNED  
**Dependencies:** Milestone 2 (COMPLETE)  
**Purpose:** Build Infrastructure + Application + Runtime evidence extraction, normalization, and unified graph construction

---

## Objectives

### Primary Objective
Implement an evidence extraction pipeline that collects, normalizes, and unifies heterogeneous evidence from Infrastructure (Kubernetes YAML), Application (Python source code), and Runtime (Milestone 2 verification JSON) sources into a common schema and dependency graph.

### Research Objectives
1. Demonstrate integration of three distinct evidence types (Infrastructure, Application, Runtime)
2. Implement evidence provenance tracking and confidence scoring
3. Handle missing, malformed, stale, and conflicting evidence explicitly
4. Build NetworkX-based Evidence/Dependency Graph with full attribution
5. Use Milestone 2 evidence as test fixtures without hardcoding outcomes

### Success Criteria
- [  ] Common Evidence schema (Pydantic model) with required fields
- [  ] Infrastructure evidence extractor (Kubernetes NetworkPolicy YAML parser)
- [  ] Application evidence extractor (Python AST parser for database dependencies)
- [  ] Runtime evidence extractor (Milestone 2 JSON parser)
- [  ] Evidence normalizer (validation, deduplication, conflict detection)
- [  ] Graph builder (NetworkX with nodes: services/policies, edges: relationships/evidence)
- [  ] Unit tests for each extractor (100% coverage of happy path + error cases)
- [  ] Integration test using Milestone 2 evidence files as fixtures
- [  ] Documentation (architecture, usage, examples)

---

## Architecture

### Component Overview

```
INPUT SOURCES
    ↓
┌─────────────────────────────────────────────────────────┐
│  EVIDENCE EXTRACTORS                                    │
│  ├── Infrastructure Extractor (Kubernetes YAML)         │
│  ├── Application Extractor (Python AST)                 │
│  └── Runtime Extractor (Verification JSON)              │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  EVIDENCE NORMALIZER                                    │
│  ├── Validation (schema, required fields)               │
│  ├── Deduplication (same source → same evidence)        │
│  ├── Conflict Detection (contradictory evidence)        │
│  └── Provenance Tracking (file, line, timestamp)        │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  UNIFIED EVIDENCE STORE                                 │
│  (List[Evidence] with full provenance)                  │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  GRAPH BUILDER (NetworkX)                               │
│  ├── Nodes: services, pods, policies                    │
│  ├── Edges: dependencies, communications, restrictions  │
│  └── Edge attributes: evidence_ids, confidence, sources │
└─────────────────────────────────────────────────────────┘
    ↓
OUTPUT: Evidence/Dependency Graph (NetworkX DiGraph)
```

---

## Common Evidence Schema

### Pydantic Model

```python
from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

class EvidenceProvenance(BaseModel):
    """Source provenance for evidence"""
    source_type: Literal["file", "runtime", "api", "manual"]
    source_path: str  # Absolute path or identifier
    line_number: Optional[int] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extractor_version: str = "1.0.0"
    
class Evidence(BaseModel):
    """Common evidence schema"""
    # Identity
    evidence_id: str = Field(default_factory=lambda: f"E{uuid4().hex[:8]}")
    
    # Classification
    evidence_type: Literal["infrastructure", "application", "runtime"]
    source: str  # kubernetes-yaml, python-ast, verification-json, etc.
    
    # Relationship
    subject: str  # Component being described (e.g., "backend")
    relationship: str  # DEPENDS_ON, CONNECTS_TO, BLOCKS, ALLOWS, etc.
    object: str  # Related component (e.g., "database")
    
    # Metadata
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0
    classification: Literal["observed", "inferred", "verified"] = "observed"
    
    # Provenance
    provenance: EvidenceProvenance
    
    # Optional context
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Conflict tracking
    conflicts_with: list[str] = Field(default_factory=list)  # Evidence IDs
```

---

## Infrastructure Evidence Extractor

### Purpose
Extract dependency and restriction evidence from Kubernetes NetworkPolicy YAML manifests.

### Input
- Path to Kubernetes YAML file (e.g., `kubernetes/policies/isolate-database.yaml`)

### Output
- List[Evidence] representing NetworkPolicy restrictions

### Example Evidence

From NetworkPolicy `isolate-database`:
```yaml
spec:
  podSelector:
    matchLabels:
      app: database
  policyTypes:
    - Ingress
  ingress: []
```

Extracted evidence:
```python
Evidence(
    evidence_id="E12ab34cd",
    evidence_type="infrastructure",
    source="kubernetes-networkpolicy",
    subject="database",
    relationship="BLOCKS_INGRESS_FROM",
    object="*",  # All sources
    timestamp=datetime.utcnow(),
    confidence=1.0,  # Directly observed in YAML
    classification="observed",
    provenance=EvidenceProvenance(
        source_type="file",
        source_path="/absolute/path/to/isolate-database.yaml",
        line_number=8,
        extracted_at=datetime.utcnow()
    ),
    metadata={
        "policy_name": "isolate-database",
        "namespace": "poc-app",
        "policy_type": "Ingress",
        "rule_type": "deny_all"
    }
)
```

### Implementation

**File:** `backend/app/evidence/infrastructure.py`

**Key functions:**
- `extract_networkpolicy_evidence(yaml_path: str) -> List[Evidence]`
- `parse_pod_selector(selector: dict) -> str`
- `parse_ingress_rules(rules: list) -> List[Evidence]`

**Error handling:**
- FileNotFoundError → empty list + log warning
- Invalid YAML → empty list + log error
- Missing required fields → skip rule + log warning

---

## Application Evidence Extractor

### Purpose
Extract dependency evidence from application source code (Python).

### Input
- Path to Python file (e.g., `services/backend/app/main.py`)

### Output
- List[Evidence] representing code-level dependencies (database connections, API calls)

### Example Evidence

From Python code:
```python
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@database-service:5432/app")
engine = create_engine(DATABASE_URL)
```

Extracted evidence:
```python
Evidence(
    evidence_id="E56ef78gh",
    evidence_type="application",
    source="python-ast",
    subject="backend",
    relationship="DEPENDS_ON",
    object="database-service",
    timestamp=datetime.utcnow(),
    confidence=0.9,  # Code exists, but may be conditional
    classification="inferred",
    provenance=EvidenceProvenance(
        source_type="file",
        source_path="/absolute/path/to/main.py",
        line_number=15,
        extracted_at=datetime.utcnow()
    ),
    metadata={
        "connection_type": "postgresql",
        "port": 5432,
        "variable_name": "DATABASE_URL",
        "engine_type": "sqlalchemy"
    }
)
```

### Implementation

**File:** `backend/app/evidence/application.py`

**Key functions:**
- `extract_python_dependencies(file_path: str) -> List[Evidence]`
- `parse_database_connections(ast_tree) -> List[Evidence]`
- `parse_service_calls(ast_tree) -> List[Evidence]`

**AST patterns to detect:**
- `create_engine(DATABASE_URL)` → database dependency
- `requests.get("http://service:port/...")` → service dependency
- `os.getenv("SERVICE_URL")` → potential external dependency

**Error handling:**
- FileNotFoundError → empty list + log warning
- Invalid Python syntax → empty list + log error
- No dependencies found → empty list (valid case)

---

## Runtime Evidence Extractor

### Purpose
Extract runtime behavior evidence from Milestone 2 verification JSON files.

### Input
- Path to verification JSON file (e.g., `network-policy-verification-20261011-133342.json`)

### Output
- List[Evidence] representing observed runtime behavior

### Example Evidence

From Stage 2 JSON (NetworkPolicy active):
```json
{
  "observed_behavior": {
    "backend_to_database": {
      "socket_code": "11",
      "status": "connection_timeout"
    },
    "backend_health": {
      "readiness": "not_ready"
    }
  }
}
```

Extracted evidence:
```python
Evidence(
    evidence_id="E90ij12kl",
    evidence_type="runtime",
    source="verification-json",
    subject="backend",
    relationship="FAILED_TO_CONNECT",
    object="database-service",
    timestamp=datetime.fromisoformat("2026-10-11T13:33:42.340Z"),
    confidence=1.0,  # Directly observed at runtime
    classification="verified",
    provenance=EvidenceProvenance(
        source_type="file",
        source_path="/absolute/path/to/network-policy-verification-20261011-133342.json",
        extracted_at=datetime.utcnow()
    ),
    metadata={
        "socket_code": 11,
        "socket_error": "EAGAIN",
        "readiness": "not_ready",
        "liveness": "healthy",
        "policy_active": True
    }
)
```

### Implementation

**File:** `backend/app/evidence/runtime.py`

**Key functions:**
- `extract_verification_evidence(json_path: str) -> List[Evidence]`
- `parse_connectivity_evidence(observed_behavior: dict) -> List[Evidence]`
- `parse_health_evidence(observed_behavior: dict) -> List[Evidence]`

**Mapping rules:**
- socket_code=0 + status=connected → CONNECTS_TO
- socket_code=11 + status=connection_timeout → FAILED_TO_CONNECT
- readiness=ready → HEALTHY
- readiness=not_ready → UNHEALTHY

**Error handling:**
- FileNotFoundError → empty list + log warning
- Invalid JSON → empty list + log error
- Missing required fields → skip evidence + log warning

---

## Evidence Normalizer

### Purpose
Validate, deduplicate, and detect conflicts in extracted evidence.

### Input
- List[Evidence] from multiple extractors

### Output
- List[Evidence] (validated, deduplicated, conflicts marked)

### Validation Rules

1. **Required fields present:** evidence_id, evidence_type, source, subject, relationship, object, timestamp, confidence, provenance
2. **Confidence in range:** 0.0 ≤ confidence ≤ 1.0
3. **Valid timestamps:** ISO 8601 format, not in future
4. **Valid relationships:** Must be from predefined set (DEPENDS_ON, CONNECTS_TO, BLOCKS, etc.)

### Deduplication Strategy

**Definition of duplicate:**
- Same subject + relationship + object + source + timestamp (within 1 second)

**Resolution:**
- Keep first occurrence
- Log duplicate count

### Conflict Detection

**Definition of conflict:**
- Same subject + relationship + object
- Different evidence (e.g., CONNECTS_TO vs FAILED_TO_CONNECT)
- Different timestamps OR different sources

**Resolution:**
- Keep BOTH evidence items
- Mark each with `conflicts_with: [other_evidence_id]`
- Log conflict for manual review

**Example:**
```python
# Evidence 1: Infrastructure says traffic is blocked
Evidence(
    subject="backend",
    relationship="BLOCKED_FROM",
    object="database",
    source="kubernetes-networkpolicy",
    confidence=1.0
)

# Evidence 2: Runtime says connection succeeded (before policy applied)
Evidence(
    subject="backend",
    relationship="CONNECTS_TO",
    object="database",
    source="verification-json",
    timestamp=earlier_time,
    confidence=1.0
)

# NOT a conflict — different timestamps explain the difference
```

### Staleness Handling

**Definition of stale evidence:**
- Runtime evidence older than 1 hour (configurable)

**Resolution:**
- Mark with `metadata["stale"] = True`
- Reduce confidence by 0.2 (min 0.1)
- Log staleness warning

### Implementation

**File:** `backend/app/evidence/normalization.py`

**Key functions:**
- `validate_evidence(evidence: Evidence) -> bool`
- `deduplicate_evidence(evidence_list: List[Evidence]) -> List[Evidence]`
- `detect_conflicts(evidence_list: List[Evidence]) -> List[Evidence]`
- `mark_stale_evidence(evidence_list: List[Evidence], max_age_hours: int = 1) -> List[Evidence]`

---

## Graph Builder

### Purpose
Construct NetworkX-based Evidence/Dependency Graph from normalized evidence.

### Input
- List[Evidence] (normalized)

### Output
- networkx.DiGraph with nodes (services, policies) and edges (relationships, evidence)

### Node Types

- `service`: Backend, Database, Frontend
- `policy`: NetworkPolicy (e.g., isolate-database)
- `pod`: Kubernetes pod instances

### Edge Types

- `DEPENDS_ON`: Application-level dependency
- `CONNECTS_TO`: Runtime-observed successful connection
- `FAILED_TO_CONNECT`: Runtime-observed connection failure
- `BLOCKS`: Infrastructure-level restriction
- `ALLOWS`: Infrastructure-level permission

### Edge Attributes

```python
{
    "evidence_ids": ["E12ab34cd", "E56ef78gh"],  # Supporting evidence
    "confidence": 0.9,  # Aggregated confidence
    "sources": ["kubernetes-networkpolicy", "verification-json"],
    "evidence_types": ["infrastructure", "runtime"],
    "relationship": "BLOCKS"  # Primary relationship type
}
```

### Confidence Aggregation

**Rule:** Multiple evidence sources increase confidence

- Single source: confidence = evidence.confidence
- Two sources: confidence = max(evidence.confidence) + 0.1 (cap at 1.0)
- Three sources: confidence = max(evidence.confidence) + 0.2 (cap at 1.0)

**Rationale:** Evidence from multiple independent sources (Infrastructure + Application + Runtime) is more reliable than a single source.

### Conflict Handling in Graph

**If conflicting evidence exists:**
- Create BOTH edges
- Mark with `metadata["conflicted"] = True`
- Edge label includes timestamp to distinguish

**Example:**
```
backend --[CONNECTS_TO, t=13:21:30]--> database
backend --[FAILED_TO_CONNECT, t=13:33:42]--> database
```

### Implementation

**File:** `backend/app/graph/builder.py`

**Key functions:**
- `build_evidence_graph(evidence_list: List[Evidence]) -> nx.DiGraph`
- `add_evidence_to_graph(graph: nx.DiGraph, evidence: Evidence)`
- `aggregate_confidence(evidence_list: List[Evidence]) -> float`
- `get_graph_summary(graph: nx.DiGraph) -> dict`

**Graph operations:**
- `nx.DiGraph()` → create directed graph
- `graph.add_node(name, **attributes)` → add service/policy node
- `graph.add_edge(source, target, **attributes)` → add relationship edge
- `nx.shortest_path(graph, source, target)` → dependency path analysis

---

## Testing Strategy

### Unit Tests

**File:** `backend/app/tests/unit/test_evidence_extraction.py`

**Coverage:**
- Infrastructure extractor: valid YAML, invalid YAML, missing file, empty rules
- Application extractor: valid Python, invalid syntax, no dependencies, multiple dependencies
- Runtime extractor: valid JSON, invalid JSON, missing fields, all three stages
- Normalizer: validation, deduplication, conflict detection, staleness
- Graph builder: single evidence, multiple evidence, conflicting evidence, confidence aggregation

### Integration Tests

**File:** `backend/app/tests/integration/test_evidence_pipeline.py`

**Test case: Milestone 2 Stage 2 (NetworkPolicy active)**

**Setup:**
- Input files:
  - `kubernetes/policies/isolate-database.yaml`
  - `services/backend/app/main.py`
  - `network-policy-verification-20261011-133342.json`

**Expected output:**
- Evidence count: ≥ 3 (infrastructure + application + runtime)
- Graph nodes: `backend`, `database`, `isolate-database`
- Graph edges: 
  - `backend --[DEPENDS_ON]--> database` (from application)
  - `backend --[FAILED_TO_CONNECT]--> database` (from runtime)
  - `isolate-database --[BLOCKS]--> database` (from infrastructure)
- Confidence: infrastructure=1.0, application=0.9, runtime=1.0

**Validation:**
- All evidence has required fields
- No duplicates
- Conflicts detected (DEPENDS_ON vs FAILED_TO_CONNECT) and marked
- Graph is connected (all nodes reachable)

### Reproducibility Tests

**File:** `backend/app/tests/reproducibility/test_milestone_2_replay.py`

**Purpose:** Verify pipeline produces consistent results when processing Milestone 2 evidence

**Test cases:**
- Stage 1 (Baseline): CONNECTS_TO edge present, no BLOCKS edge
- Stage 2 (Impact): BLOCKS edge present, FAILED_TO_CONNECT edge present
- Stage 3 (Recovery): Same as Stage 1

**Anti-pattern to avoid:** DO NOT hardcode "if NetworkPolicy active, predict failure" logic. The prediction engine (Milestone 4) will reason over the graph; the pipeline only extracts and represents evidence.

---

## Evaluation Metrics

### Evidence Quality Metrics

1. **Evidence completeness:** Percentage of expected evidence extracted
2. **Provenance tracking:** 100% of evidence has source file + line number
3. **Validation pass rate:** Percentage of extracted evidence passing validation
4. **Conflict detection rate:** Percentage of known conflicts detected

### Graph Quality Metrics

1. **Node coverage:** All services/policies in input appear in graph
2. **Edge accuracy:** Edges match expected relationships from input
3. **Confidence calibration:** High-confidence edges should have multiple evidence sources
4. **Connectivity:** Graph should be weakly connected (all nodes reachable)

---

## Dependencies

### Python Packages

- `pydantic >= 2.0` (evidence schema, validation)
- `networkx >= 3.0` (graph construction)
- `pyyaml >= 6.0` (Kubernetes YAML parsing)
- `pytest >= 7.0` (testing)

### Project Files

- Milestone 2 evidence files (test fixtures):
  - `network-policy-verification-20261011-132130.json`
  - `network-policy-verification-20261011-133342.json`
  - `network-policy-verification-20261011-135142.json`
- Kubernetes manifests:
  - `kubernetes/policies/isolate-database.yaml`
- Application source:
  - `services/backend/app/main.py`

---

## Implementation Order

### Phase 1: Foundation (Day 1-2)

1. Create common Evidence schema (Pydantic model)
2. Create EvidenceProvenance schema
3. Unit tests for schema validation
4. Documentation: evidence schema reference

### Phase 2: Extractors (Day 3-5)

1. Infrastructure extractor (NetworkPolicy YAML)
   - Parser
   - Unit tests (valid/invalid YAML)
   - Integration with Evidence schema
2. Application extractor (Python AST)
   - Parser
   - Unit tests (valid/invalid Python)
   - Integration with Evidence schema
3. Runtime extractor (Verification JSON)
   - Parser
   - Unit tests (all three Milestone 2 stages)
   - Integration with Evidence schema

### Phase 3: Normalization (Day 6-7)

1. Evidence normalizer
   - Validation logic
   - Deduplication logic
   - Conflict detection logic
   - Staleness marking
2. Unit tests for each normalization function
3. Integration test: extract + normalize pipeline

### Phase 4: Graph Construction (Day 8-9)

1. Graph builder
   - NetworkX graph creation
   - Evidence-to-edge mapping
   - Confidence aggregation
2. Unit tests for graph operations
3. Graph visualization helper (for debugging)

### Phase 5: Integration & Evaluation (Day 10)

1. End-to-end integration test (Milestone 2 replay)
2. Evaluation metrics calculation
3. Documentation: architecture, usage examples
4. README with examples

---

## Acceptance Criteria

### Code Quality
- [  ] All extractors pass unit tests (100% coverage)
- [  ] Integration test using Milestone 2 evidence passes
- [  ] No hardcoded outcomes (graph represents evidence, not predictions)
- [  ] Type hints on all functions
- [  ] Docstrings on all public functions

### Evidence Quality
- [  ] All evidence has required fields (evidence_id, type, source, subject, relationship, object, timestamp, confidence, provenance)
- [  ] Provenance includes source file + line number where applicable
- [  ] Confidence scores are justified (documentation explains calculation)
- [  ] Conflicts are detected and preserved (not silently discarded)

### Graph Quality
- [  ] Graph contains all services (backend, database, frontend)
- [  ] Graph contains all policies (isolate-database)
- [  ] Edges have evidence_ids attribute (full attribution)
- [  ] Confidence aggregation uses multiple sources (not just max)

### Documentation
- [  ] Architecture diagram (evidence flow)
- [  ] Evidence schema reference
- [  ] Usage examples (extract, normalize, build graph)
- [  ] Evaluation results (metrics from Milestone 2 replay)

### Research Integrity
- [  ] Milestone 2 evidence files used as fixtures (not modified)
- [  ] No assumptions about causation (graph represents evidence only)
- [  ] Conflicts preserved and reported (not hidden)
- [  ] Limitations documented (what evidence is NOT extracted)

---

## Limitations

### Evidence Scope
- **NetworkPolicy only:** Does not extract IAM, network security group rules, or other policy types
- **Python only:** Does not parse Java, Go, Node.js, or other application languages
- **Verification JSON only:** Does not parse OpenTelemetry traces, Prometheus metrics, or application logs
- **Static analysis:** Application extractor uses AST (no execution, no dynamic analysis)

### Confidence Scoring
- **Heuristic-based:** Confidence aggregation is rule-based, not ML-based
- **No validation:** Does not verify that extracted evidence is semantically correct
- **Context-independent:** Does not consider conditional dependencies (if statements, feature flags)

### Conflict Resolution
- **No automatic resolution:** Conflicts are detected but not resolved
- **Timestamp-based only:** Does not consider version control history or deployment events

---

## Future Extensions (Out of Scope for Milestone 3)

1. **Additional extractors:** IAM policies, Terraform, CloudFormation, Helm charts
2. **OpenTelemetry integration:** Parse Jaeger traces, Prometheus metrics
3. **Machine learning:** Confidence scoring based on historical accuracy
4. **Semantic analysis:** Understand conditional dependencies, feature flags
5. **Conflict resolution:** Automated resolution strategies (newest wins, most sources wins, etc.)

---

## References

### Literature
- Hu et al. (2023): Characterizing Static Analysis Alerts for Terraform Manifests (dependency graphs with NetworkX)
- Bushong et al. (2021): On Microservice Analysis and Architecture Evolution (evidence types: static, dynamic, hybrid)
- Chiari et al. (2022): Static Analysis of Infrastructure as Code (IaC analysis techniques)

### Project Files
- `.kiro/specs/milestone-2-networkpolicy-experiment.md`: Experiment design
- `docs/milestone-2-analysis.md`: Evidence analysis
- `docs/milestone-2-completion.md`: Research findings

---

**END OF SPECIFICATION**
