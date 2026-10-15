# Research Constraints & Principles

## Research Contribution

### What NOT to Claim as Novel

Do NOT claim individual novelty for these existing research areas:
- Infrastructure-as-Code analysis
- Kubernetes security analysis
- Dependency graphs
- Runtime monitoring
- Change Impact Analysis
- Selective prediction/abstention
- Security remediation
- NetworkPolicy analysis
- IAM analysis
- Static analysis
- Dynamic analysis

These areas already have substantial literature.

### What IS the Research Contribution

The research contribution is the **COMBINATION / INTEGRATION** of:

1. Heterogeneous evidence (Infrastructure + Application + Runtime)
2. Evidence/dependency graph construction
3. Security + operational impact prediction
4. Explicit confidence/evidence gating
5. Ability to abstain when evidence is insufficient
6. Minimal security remediation that attempts to preserve required functionality
7. Controlled execution/verification
8. Prediction-vs-reality evaluation

### Conservative Novelty Claim

**Do NOT say:**
"No existing system does this."

**Instead use wording such as:**
- "Based on the literature reviewed..."
- "The reviewed literature provides these capabilities largely as separate research directions; this project investigates their integration..."

---

## Main Research Question

**"Does combining infrastructure, application, and runtime evidence improve prediction of the security and operational impact of cloud-security changes compared with infrastructure-only analysis?"**

### Experimental Comparison

Compare evidence configurations:

- **Baseline A:** Infrastructure only
- **Baseline B:** Infrastructure + Application
- **Baseline C:** Infrastructure + Runtime
- **Proposed D:** Infrastructure + Application + Runtime + Evidence Gate + Minimal Remediation

Purpose: Determine whether adding heterogeneous evidence actually improves prediction rather than merely claiming that it does.

---

## Critical Evidence Principle

### "Absence of Evidence ≠ Evidence of Absence"

**Key principle:**
"Absence of observed runtime usage does NOT automatically mean absence of dependency."

**Example:**
If PostgreSQL was not observed during a short runtime test, DO NOT conclude:
"Backend does not depend on PostgreSQL."

**Possible explanations:**
- Functionality was not exercised
- Insufficient workload
- Telemetry was incomplete
- Dependency is conditional
- Evidence collection failed

**Therefore:**
Incomplete/conflicting evidence should **reduce confidence**.

The system should be able to say:
**"INSUFFICIENT EVIDENCE"**

rather than making an unsafe high-confidence decision.

---

## Evidence Quality Standards

### Evidence Provenance

Evidence must preserve:
- evidence_id
- source
- evidence_type
- subject/component
- relationship
- object/target
- timestamp
- confidence
- provenance
- optional metadata

### Evidence Classification

Evidence should be distinguishable as:
- **observed** (directly captured)
- **inferred** (logically derived)
- **verified** (confirmed through testing)

**Do not treat:**
- Scanner output as absolute truth
- Runtime absence as proof of non-dependency
- Single evidence source as sufficient

---

## Security Analysis Constraints

### Security ≠ Always More Restrictive

**Important principle:**
Security improvement can create operational risk.

The system must evaluate **BOTH** security impact and operational risk.

**Do NOT treat:**
"more restrictive = always better"

**Example:**
Blocking all backend→database traffic may improve isolation but break the application.

### Security Considerations

- Privilege reduction/increase
- Attack surface
- Access control
- Least privilege
- Isolation
- Lateral movement
- Unauthorized communication
- Network exposure
- Overly permissive rules
- Denied required communication

---

## Evaluation Requirements

### Must Include

**Prediction metrics:**
- Accuracy
- Precision
- Recall
- F1
- ROC-AUC where appropriate

**Risk metrics:**
- False positives
- False negatives
- Affected-component identification accuracy

**Confidence metrics:**
- Calibration
- Reliability
- Accuracy by confidence bucket
- Abstention rate

**Evidence Gate evaluation:**
- Safe/risky/insufficient classification quality
- Abstention quality
- Performance under incomplete evidence

**Remediation evaluation:**
- Security improvement
- Operational failures
- Residual risk
- Minimality
- Functionality preservation

**Verification evaluation:**
- Prediction vs actual runtime behavior alignment

---

## Scope Limitations

### Initial Scope

Focus on **THREE** change categories:
1. IAM permission/access changes
2. Network/security-rule changes
3. Kubernetes access/network-policy changes

**Do NOT expand** into every possible cloud security configuration without explicit need.

### Environment Scope

- **Core experiment MUST work locally**
- Do NOT require AWS/Azure/GCP for core research
- Cloud integration is optional/future work
- Reproducibility is paramount
