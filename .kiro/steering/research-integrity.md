# Research Integrity & Literature Foundation

## Literature-Based Research Approach

This is an **academic research project**.

All claims must be:
- **Literature-supported**
- **Experimentally validated**
- **Conservatively stated**

---

## Key Papers Reviewed

### 1. Bushong et al. (2021) - Microservice Analysis Survey

**Citation:** "On Microservice Analysis and Architecture Evolution: A Systematic Mapping Study," Applied Sciences, 11, 7856.

**Key Points:**
- Systematic mapping of microservice analysis research
- Analysis approaches: static, dynamic, graph-based, model-based, pattern-based
- Dynamic analysis supports fault/root-cause understanding using logs/traces
- Hybrid static + dynamic analysis for dependency recovery
- Graphs represent service dependencies
- Research gaps: benchmarks, temporal graphs, prediction and ML

**Relevance:**
- Supports dependency analysis, graph representation
- Supports static + dynamic evidence combination
- Does NOT itself provide cloud-security-change impact prediction with evidence gate

---

### 2. Chiari, De Pascalis & Pradella (2022) - IaC Static Analysis Survey

**Citation:** "Static Analysis of Infrastructure as Code: a Survey," arXiv:2206.10344.

**Key Points:**
- IaC can contain security/reliability/availability/performance defects
- Reviews IaC security analysis tools and techniques
- Covers Terraform, CloudFormation, Puppet, Ansible, Chef, etc.
- Techniques: syntactic analysis, ML, formal verification, model checking
- Highlights need for automated remediation

**Relevance:**
- Supports infrastructure evidence/security analysis
- Project extends to: "What happens if this change is applied, which components are affected, what evidence supports the prediction"

---

### 3. Hu et al. (2023) - Terraform Static Analysis Alerts

**Citation:** "Characterizing Static Analysis Alerts for Terraform Manifests: An Experience Report," IEEE.

**Key Points:**
- Studies Terraform static analysis alerts
- Builds Terraform dependency graph using NetworkX
- Uses PageRank and statistical analysis
- Dependency information correlated with alert frequency
- Practitioners suggest dependency graphs help visualization and change-impact analysis

**Relevance:**
- Very important for Terraform/IaC dependency graph approach
- Supports NetworkX usage
- Supports dependency-aware alert analysis
- Project extends with application evidence, runtime evidence, prediction, confidence, gate, remediation, verification

---

### 4. Minna, Massacci & Tuma (2024) - Helm Chart Security with LLMs

**Citation:** "Analyzing and Mitigating (with LLMs) the Security Misconfigurations of Helm Charts from Artifact Hub," MSR 2024.

**Key Points:**
- Studies security misconfigurations in Helm charts/Kubernetes
- Multiple analyzers can disagree
- Scanner passing does NOT prove semantic security
- Example: presence-based NetworkPolicy checks may be satisfied without meaningful protection
- LLM remediation can be correct, wrong, or refused
- Manual validation is required

**Relevance:**
- Strong support for remediation + post-remediation validation
- Scanner limitations
- Evidence not being absolute ground truth
- Need for controlled verification

---

### 5. War et al. (2025) - IaC Security Smells Taxonomy

**Citation:** "Security Smells in Infrastructure as Code Scripts: A Taxonomy Update Beyond the Seven Sins," arXiv:2509.18761.

**Key Points:**
- Extends IaC security smell taxonomy
- Covers 7 IaC tools
- 62 CWE-related categories
- Uses security-fix commits, human validation
- LLMs help categorization but don't replace expert judgment

**Relevance:**
- Supports security taxonomy
- Git history as evidence
- Validation requirement
- Not the core novelty of the project

---

### 6. Gomez et al. (2026) - Formal Verification in Microservices

**Citation:** "Formal Verification Under Evolution in Microservice-Based Systems: A Systematic Literature Review," Software 2026, 5, 32.

**Key Points:**
- Studies formal verification + microservice evolution
- Evolution changes: APIs, architecture, dependency topology
- Repository signals: commits, API diffs, dependency manifests, Dockerfiles, Helm charts
- Supports runtime verification
- Highlights limited shared benchmarks and public artifacts
- End-to-end design-time → runtime verification loops are relatively limited

**Relevance:**
- Supports evolution-aware analysis
- Git/repository evidence
- Controlled verification
- Prediction-vs-reality idea
- Reproducibility/benchmark motivation

---

### 7. Budigiri et al. - Kubernetes NetworkPolicy

**Citation:** "Network Policies in Kubernetes: Performance Evaluation and Security Analysis."

**Key Points:**
- Studies Kubernetes NetworkPolicy security
- Evaluates Calico/Cilium/eBPF environments
- Security topics: misconfiguration, weak policy design, privileged networking, policy leakage
- NetworkPolicy is additive
- Least privilege is important
- NetworkPolicy reduces attack surface/lateral movement but is not complete security solution
- Policy definition does not necessarily prove actual enforcement

**Relevance:**
- Important foundation for Kubernetes NetworkPolicy change category
- Supports least privilege, isolation, lateral movement analysis
- Supports operational/security trade-off concept
- Project extends toward predicting impact of proposed policy changes using multiple evidence sources

---

## Research Landscape

The literature falls into several areas:

1. Microservice analysis/evolution
2. IaC security/static analysis
3. Terraform dependency/alert analysis
4. Kubernetes NetworkPolicy security
5. Helm/Kubernetes remediation
6. Continuous/evolution-aware verification

**None of these individually is claimed as novel.**

The project's contribution is the **integration** of these research directions.

---

## How to Cite in Writing

### When Discussing Related Work

**GOOD:**
"Based on the literature reviewed, infrastructure-as-code static analysis is well-established [Chiari et al., 2022], as is dependency graph construction for Terraform [Hu et al., 2023]. This project investigates their integration with application and runtime evidence for cloud-security change impact prediction."

**BAD:**
"No existing system combines infrastructure, application, and runtime evidence for impact prediction."

---

### When Discussing Novelty

**GOOD:**
"While individual techniques such as IaC analysis, dependency graphs, and runtime monitoring are established, this project explores their integration for evidence-gated security change impact prediction with explicit confidence assessment and controlled verification."

**BAD:**
"This project is the first to use dependency graphs for security analysis."

---

### When Discussing Limitations

**GOOD:**
"Scanner-based analysis has known limitations [Minna et al., 2024], including false positives and semantic gaps. This motivates the multi-evidence approach and controlled verification component of this work."

**BAD:**
"Scanners are unreliable and should not be used."

---

## Research Integrity Principles

1. **Never overclaim novelty** - be conservative
2. **Always cite prior work** - give credit where due
3. **Report negative results** - failures are valuable
4. **Document limitations** - be honest about scope
5. **Reproduce before publishing** - verify claims
6. **Version control everything** - enable replication
7. **Share code and data** - open science
8. **Acknowledge help** - credit collaborators and tools

---

## Academic Writing Guidelines

### Language

- Use **passive voice** for methods: "Evidence was collected from..."
- Use **active voice** for contributions: "This work demonstrates..."
- Be **precise**: avoid "very," "extremely," "obviously"
- Be **conservative**: "suggests," "indicates," "may" rather than "proves," "demonstrates conclusively"

### Structure

- Introduction: problem, gap, contribution
- Related Work: what exists, what's missing
- Methodology: how it works
- Experiments: what was tested
- Results: what was found
- Discussion: what it means
- Limitations: what it doesn't cover
- Conclusion: summary and future work

### Claims

**Evidence-supported claims:**
"The results suggest that combining heterogeneous evidence improves prediction accuracy (F1=0.87) compared to infrastructure-only analysis (F1=0.72)."

**Speculative claims (avoid):**
"This approach will revolutionize cloud security."

---

## Open Science Commitment

This project follows open science principles:

- **Open source code** on GitHub
- **Public documentation**
- **Reproducible experiments**
- **Shared datasets** (where appropriate)
- **Transparent methodology**
- **Honest reporting** of results

---

## Ethical Considerations

- No real cloud environments should be disrupted
- No production systems should be tested without authorization
- No sensitive data should be collected or stored
- All experiments are in controlled, local environments
- Results should not be misrepresented
- Limitations should be clearly stated
