# Coding Standards

> **Note:** Where this file conflicts with implementation.md, implementation.md wins.

## General Principles

1. **Clarity over cleverness** - Write code that is easy to understand and maintain
2. **Documentation** - Document research decisions, not just code
3. **Reproducibility** - Code must be reproducible on other machines
4. **Modularity** - Keep components loosely coupled
5. **Testability** - Write testable code from the start

---

## Python Standards

### Style
- Follow **PEP 8**
- Use **type hints** (Pydantic models where appropriate)
- Use **docstrings** for functions and classes
- Maximum line length: **88 characters** (Black formatter standard)

### Naming Conventions
- **Functions/variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private methods:** `_leading_underscore`

### Code Organization
```python
# Standard library imports
import os
from typing import List, Dict

# Third-party imports
import pandas as pd
from fastapi import APIRouter

# Local imports
from app.models.evidence import Evidence
from app.graph.builder import GraphBuilder
```

### Error Handling
- Use specific exceptions, not bare `except:`
- Provide meaningful error messages
- Log errors with context

### Example Function Structure
```python
def extract_infrastructure_evidence(
    config_path: str,
    config_type: str
) -> List[Evidence]:
    """
    Extract evidence from infrastructure configuration files.
    
    Args:
        config_path: Absolute path to configuration file
        config_type: Type of configuration (terraform, kubernetes, etc.)
        
    Returns:
        List of Evidence objects extracted from configuration
        
    Raises:
        FileNotFoundError: If config_path does not exist
        ValueError: If config_type is not supported
    """
    # Implementation
    pass
```

---

## Evidence Model Standards

### All Evidence Must Include

```python
{
    "evidence_id": "E123",              # Unique identifier
    "source": "kubernetes-yaml",        # Where it came from
    "evidence_type": "infrastructure",  # infrastructure/application/runtime
    "subject": "backend",               # Component being described
    "relationship": "DEPENDS_ON",       # Relationship type
    "object": "database",               # Related component
    "timestamp": "2026-10-06T...",      # When collected
    "confidence": 0.85,                 # 0.0 to 1.0
    "provenance": {...}                 # Detailed source info
}
```

### Evidence Classification
- Mark evidence as: `observed`, `inferred`, or `verified`
- Never treat evidence as absolute truth
- Preserve full provenance chain

---

## Graph Standards

### Using NetworkX

```python
import networkx as nx

# Create directed graph
G = nx.DiGraph()

# Add nodes with attributes
G.add_node(
    "backend",
    type="service",
    namespace="default"
)

# Add edges with evidence
G.add_edge(
    "backend",
    "database",
    relationship="DEPENDS_ON",
    evidence_ids=["E123", "E456"],
    confidence=0.9,
    sources=["infrastructure", "application"]
)
```

### Graph Node Types
- Use consistent node types: `service`, `pod`, `deployment`, `database`, `api`, `network_rule`, `iam_identity`, `permission`

### Graph Edge Types
- Use consistent relationship types: `DEPENDS_ON`, `CALLS`, `CONNECTS_TO`, `ALLOWED`, `DENIED`, `HAS_PERMISSION`, `DEPLOYED_AS`, `OBSERVED_COMMUNICATION`, `CONFIGURED_BY`

---

## Configuration Management

### Environment Variables
- Use `.env` files for local development
- **NEVER commit secrets** to Git
- Use `.env.example` as template

### Configuration Files
- Use **YAML** for Kubernetes manifests
- Use **JSON** for evidence/results storage
- Use **Python** for application configuration

---

## Testing Standards

### Test Organization
```
tests/
├── unit/
│   ├── test_evidence_extraction.py
│   ├── test_graph_builder.py
│   └── test_prediction.py
├── integration/
│   ├── test_evidence_pipeline.py
│   └── test_prediction_pipeline.py
└── fixtures/
    ├── sample_terraform.tf
    ├── sample_kubernetes.yaml
    └── sample_telemetry.json
```

### Test Naming
```python
def test_infrastructure_evidence_extraction_from_terraform():
    """Should extract service dependencies from Terraform config"""
    pass

def test_evidence_gate_returns_insufficient_when_confidence_low():
    """Should return INSUFFICIENT EVIDENCE when confidence < threshold"""
    pass
```

### What to Test
- Evidence extraction correctness
- Graph construction
- Impact prediction logic
- Evidence gate decisions
- Remediation generation
- Prediction vs reality comparison

---

## Git Standards

### Commit Messages
```
[component] Brief description

Detailed explanation if needed

Related to: #issue-number
```

Example:
```
[evidence] Add runtime evidence extraction from Jaeger traces

Implements OpenTelemetry span parsing and dependency extraction
from Jaeger traces. Handles service-to-service communication
evidence with timestamp and confidence scoring.

Related to: #12
```

### Branch Naming
- `feature/description`
- `fix/description`
- `experiment/description`
- `docs/description`

### What NOT to Commit
- Credentials, API keys, tokens
- Large binary files
- Generated files (unless necessary for research)
- Local environment configurations
- IDE-specific files (except `.kiro/`)

---

## Documentation Standards

### Code Documentation
- Docstrings for all public functions/classes
- Inline comments for complex logic
- Type hints everywhere

### Research Documentation
- Document **why** decisions were made
- Record experiment parameters
- Keep research notes separate from code comments
- Use markdown for documentation

### README Files
Every major component should have a README explaining:
- Purpose
- How it works
- How to use it
- Dependencies
- Examples

---

## Performance Considerations

- **Do NOT optimize prematurely**
- Profile before optimizing
- Document performance-critical sections
- Keep scalability in mind but prioritize correctness

---

## Security Considerations

- Validate all inputs
- Sanitize file paths
- Use parameterized queries for databases
- Validate Kubernetes manifests before applying
- Never execute untrusted code
- Log security-relevant events
