# Project Overview

## Title
"Evidence-Gated Predictive Cloud Change Impact & Security Remediation"

## Project Type
Final-year engineering research project

## Core Problem
Cloud/security changes can improve security but can unintentionally break applications or services. Dependency information is distributed across infrastructure configuration, application/source code, and runtime behavior/telemetry.

## Solution Approach
A research-oriented, open-source, locally reproducible system that predicts the security and operational impact of proposed cloud/infrastructure security changes BEFORE they are applied.

## Key Innovation
Combining heterogeneous evidence sources:
- **Infrastructure Evidence** (OpenTofu/Terraform, Kubernetes YAML, IAM/RBAC, NetworkPolicy)
- **Application Evidence** (source code, API calls, configurations, database connections)
- **Runtime Evidence** (OpenTelemetry, Jaeger, logs, metrics, traces)

These are unified into an **Evidence/Dependency Graph** to predict:
- Security impact
- Operational risk
- Affected components
- Confidence level
- Supporting evidence/reasoning

## Evidence Gate
The decision layer supports three outcomes:
- **SAFE** - Change can proceed
- **RISKY** - Change may cause issues, remediation attempted
- **INSUFFICIENT EVIDENCE** - Not enough data to make a confident prediction

## Research Flow
```
Proposed Cloud/Security Change
→ Change Parser
→ Evidence Collection (Infrastructure + Application + Runtime)
→ Unified Evidence/Dependency Graph
→ Impact Prediction
→ Evidence Gate (SAFE/RISKY/INSUFFICIENT EVIDENCE)
→ Minimal Safe Remediation (if risky)
→ Controlled Verification
→ Actual Runtime Result
→ Prediction vs Reality Comparison
→ Final Decision Report
```

## Initial Change Categories
1. IAM permission/access changes
2. Network/security-rule changes
3. Kubernetes access/network-policy changes (especially important for POC)

## Local Environment
- Windows → WSL2 → Ubuntu → Docker → Kind Kubernetes cluster
- Must be locally reproducible, no cloud provider required for core experiments

## Initial POC Application
```
Frontend
    ↓
Backend
    ↓
PostgreSQL
```

Test scenario: Introduce a Kubernetes NetworkPolicy that blocks Backend → PostgreSQL communication and verify the system correctly predicts the operational risk.
