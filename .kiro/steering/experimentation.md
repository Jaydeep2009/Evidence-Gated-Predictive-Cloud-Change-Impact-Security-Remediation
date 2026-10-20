# Experimentation Guidelines

## Initial Proof of Concept

### POC Application Architecture

```
Frontend
    ↓
Backend
    ↓
PostgreSQL
```

Run locally using **Kubernetes/Kind**.

Infrastructure defined using **OpenTofu** where practical.

Runtime communication observed using **OpenTelemetry/Jaeger**.

---

## First Major Experiment

### Scenario: NetworkPolicy Blocking Backend → PostgreSQL

**Steps:**

1. **Parse** the proposed NetworkPolicy/security change
2. **Collect** infrastructure evidence
3. **Collect** application evidence  
4. **Collect** runtime evidence
5. **Build** the evidence/dependency graph
6. **Identify** Backend → PostgreSQL as an important dependency
7. **Predict:**
   - **Security impact:** Potentially positive (communication restricted)
   - **Operational risk:** High (required backend→database communication may break)
   - **Affected components:** Backend, Database, potentially Frontend indirectly
8. **Evidence gate:** RISKY
9. **Apply** the change in controlled local environment
10. **Run** the workload
11. **Observe** actual behavior (backend database access should fail)
12. **Compare** predicted result vs actual result
13. **Record** the result for evaluation

This is the **first major working experiment**.

---

## Evidence Ablation Study

### Primary Experiment Design

Compare prediction performance across evidence configurations:

**Baseline A: Infrastructure Only**
- Only infrastructure configuration evidence
- No application or runtime evidence

**Baseline B: Infrastructure + Application**
- Infrastructure evidence
- Application source code evidence
- No runtime evidence

**Baseline C: Infrastructure + Runtime**
- Infrastructure evidence
- Runtime telemetry evidence
- No application evidence

**Proposed D: Infrastructure + Application + Runtime**
- All three evidence types
- Evidence gate
- Minimal remediation

### Hypothesis

D > A/B/C in relevant metrics

### Evaluation Approach

**DO NOT assume the answer before experiments.**

The research should **experimentally demonstrate** whether heterogeneous evidence improves prediction.

---

## Controlled Verification Process

### Standard Verification Flow

1. **Start** known baseline system
2. **Collect** baseline evidence
3. **Propose** change
4. **Predict** impact
5. **Apply** change in controlled environment
6. **Run** predefined workload
7. **Collect** telemetry/logs/metrics
8. **Determine** actual result
9. **Compare** prediction vs reality
10. **Store** result

### Reproducibility Requirements

- Experiments must be repeatable
- Environment state must be capturable
- Results must be version-controlled
- Parameters must be documented

---

## Prediction Approach

### Start Rule-Based, Not ML

**Initially use explainable/rule-based prediction.**

Do NOT start with complex ML.

### Example Rule-Based Logic

**IF:**
- Backend → Database dependency supported by:
  - infrastructure evidence
  - application evidence  
  - runtime evidence
- Proposed change: blocks Backend → Database

**THEN predict:**
- **Security impact:** Positive/strengthened restriction
- **Operational risk:** High
- **Affected:** Backend, Database, possibly Frontend
- **Confidence:** High (if evidence agrees)

**IF only infrastructure evidence exists:**
- **Confidence:** Lower

**IF evidence conflicts:**
- Potentially: **INSUFFICIENT EVIDENCE**

---

## Minimal Remediation Principles

### When to Apply Remediation

Only when a change is classified as **RISKY**.

### Remediation Goals

- Achieve the intended security goal
- Preserve necessary application functionality
- Follow least privilege
- Minimize unnecessary permissions/communication
- Avoid broad allow rules
- Avoid simply undoing the security change

### Example

**Instead of:**
- DENY everything

**OR:**
- ALLOW everything

**Generate:**
- Narrow rule that permits only the required Backend→Database communication while maintaining appropriate restrictions

### Validation Requirement

**Remediation must be validated.**

Scanner success alone is NOT enough to prove semantic correctness.

---

## Dataset Generation

### Controlled Scenarios

Create reproducible scenarios:
- Baseline (no change)
- IAM changes (restrictive, permissive)
- Network changes (blocking, allowing)
- NetworkPolicy changes (various isolation patterns)

### Scenario Attributes

Each scenario should record:
- Change type
- Proposed change configuration
- Infrastructure state
- Application configuration
- Workload definition
- Expected behavior
- Actual behavior
- Evidence collected
- Prediction made
- Outcome

### Ground Truth

Actual runtime behavior serves as ground truth.

---

## Machine Learning (Optional, Late-Stage)

### When to Add ML

**Only after:**
- Basic rule-based system works
- Dataset is generated
- Clear research/evaluation benefit is identified

### What ML Can Potentially Improve

- Confidence scoring
- Evidence aggregation weights
- Risk assessment
- Pattern recognition across scenarios

### What ML Should NOT Replace

- Explainability
- Evidence provenance
- Fundamental rule-based logic
- Evidence gate principle

---

## Evaluation Metrics by Component

### Impact Prediction

- Accuracy of affected component identification
- Precision/Recall for risk classification
- Confidence calibration

### Evidence Gate

- Safe/Risky/Insufficient classification accuracy
- Abstention rate
- Performance under incomplete evidence

### Remediation

- Security improvement achieved
- Operational failures prevented
- Residual risk assessment
- Minimality (over-permissiveness avoided)

### Prediction vs Reality

- Agreement rate
- Root cause of disagreements
- Evidence sufficiency correlation with prediction accuracy

---

## Experimental Environment Setup

### Local Kubernetes Cluster

```bash
# Create Kind cluster
kind create cluster --name impact-prediction

# Verify cluster
kubectl cluster-info --context kind-impact-prediction
```

### Telemetry Stack

- OpenTelemetry collector
- Jaeger for trace storage
- Prometheus for metrics
- Grafana for visualization

### Application Deployment

- Frontend service
- Backend service  
- PostgreSQL database
- Instrumentation for all services

---

## Experiment Recording

### What to Record

- Timestamp
- Environment state
- Change proposed
- Evidence collected
- Graph constructed
- Prediction made
- Actual outcome
- Metrics computed
- Notes/observations

### Storage Format

Use **JSON** for structured experiment results:

```json
{
  "experiment_id": "EXP001",
  "timestamp": "2026-10-06T16:42:00Z",
  "change_type": "kubernetes_networkpolicy",
  "evidence_configuration": "infrastructure+application+runtime",
  "prediction": {
    "security_impact": "positive",
    "operational_risk": "high",
    "affected_components": ["backend", "database"],
    "confidence": 0.87
  },
  "actual_result": {
    "operational_failure": true,
    "affected_components": ["backend", "database", "frontend"]
  },
  "metrics": {
    "affected_component_precision": 0.67,
    "affected_component_recall": 1.0
  }
}
```

---

## Important Experimental Principles

1. **Do NOT cherry-pick results** - report all experiments
2. **Document failures** - negative results are valuable
3. **Reproduce before claiming** - verify experiments are repeatable
4. **Version everything** - code, configs, data
5. **Compare fairly** - baselines must use same test scenarios
6. **Measure uncertainty** - include confidence intervals where appropriate
7. **Ablate systematically** - change one variable at a time
