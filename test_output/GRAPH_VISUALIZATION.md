# Evidence Graph Visualization - G1 Bundle

## Graph Structure Summary

**Nodes:** 6
- 3 Components (frontend, backend, database)
- 1 Config node
- 2 Kubernetes Service nodes

**Edges:** 6
- 4 different relationship types
- Multiple edges between backend → database

---

## Visual Representation

```
┌─────────────────────────────────────────────────────────────────┐
│                      POC-APP NAMESPACE                          │
│                                                                 │
│  ┌────────────┐                                                │
│  │  frontend  │                                                │
│  │ (component)│                                                │
│  └────────────┘                                                │
│                                                                 │
│                                                                 │
│  ┌────────────┐        CONFIGURED_BY                          │
│  │  backend   │◄─────────────────────┐                        │
│  │ (component)│                       │                        │
│  └────┬───────┘                       │                        │
│       │                               │                        │
│       │  ┌─────────────────┐    ┌────────────────────────┐   │
│       │  │  DEPENDS_ON     │    │   config:              │   │
│       ├─►│  (infra: 0.5    │    │   DATABASE_HOST        │   │
│       │  │   app:   0.85)  │    │   = "database-service" │   │
│       │  └─────────────────┘    └────────────────────────┘   │
│       │                                                        │
│       │  ┌─────────────────┐                                  │
│       ├─►│ READINESS_COUPLED│                                 │
│       │  │   (app: 0.85)   │                                  │
│       │  └─────────────────┘                                  │
│       │                                                        │
│       │  ┌─────────────────┐                                  │
│       └─►│  CONNECTS_TO    │                                  │
│          │  (runtime: 1.0) │                                  │
│          └────────┬────────┘                                  │
│                   │                                            │
│                   ▼                                            │
│            ┌────────────┐                                      │
│            │  database  │                                      │
│            │ (component)│                                      │
│            └────────────┘                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                   KUBERNETES SERVICES                          │
│                                                                │
│  ┌──────────────────┐         EXPOSES         ┌─────────────┐│
│  │ backend-service  │─────────────────────────►│   backend   ││
│  │  (k8s-service)   │                          │ (component) ││
│  └──────────────────┘                          └─────────────┘│
│                                                                │
│  ┌──────────────────┐         EXPOSES         ┌─────────────┐│
│  │ database-service │─────────────────────────►│  database   ││
│  │  (k8s-service)   │                          │ (component) ││
│  └──────────────────┘                          └─────────────┘│
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Detailed Edge Analysis

### Edge 1: backend → config (CONFIGURED_BY)
- **Evidence:** E-infra-001
- **Type:** Infrastructure only
- **Confidence:** 1.0
- **Source:** kubernetes-deployment
- **Meaning:** Backend deployment references DATABASE_HOST env variable

### Edge 2: backend → database (DEPENDS_ON)
- **Evidence:** E-infra-002, E-app-001
- **Types:** Infrastructure (0.5) + Application (0.85)
- **Sources:** kubernetes-deployment-env, python-ast
- **Conflict:** No
- **Meaning:** Backend depends on database (seen in both config and code)

### Edge 3: backend → database (READINESS_COUPLED)
- **Evidence:** E-app-002
- **Type:** Application only
- **Confidence:** 0.85
- **Source:** python-ast-readiness
- **Meaning:** Backend's /health endpoint calls database

### Edge 4: backend → database (CONNECTS_TO)
- **Evidence:** E-runtime-001
- **Type:** Runtime only
- **Confidence:** 1.0
- **Source:** verification-probe
- **Meaning:** Actual network connection observed during baseline

### Edge 5: backend-service → backend (EXPOSES)
- **Evidence:** E-infra-003
- **Type:** Infrastructure
- **Confidence:** 1.0
- **Meaning:** K8s Service exposes backend pods

### Edge 6: database-service → database (EXPOSES)
- **Evidence:** E-infra-004
- **Type:** Infrastructure
- **Confidence:** 1.0
- **Meaning:** K8s Service exposes database pods

---

## Evidence Type Masking Results

### Mask A (Infrastructure Only)
**Edges:** 4
- backend → config (CONFIGURED_BY)
- backend → database (DEPENDS_ON) - infra evidence only
- backend-service → backend (EXPOSES)
- database-service → database (EXPOSES)

**Missing:** READINESS_COUPLED, CONNECTS_TO

### Mask B (Infrastructure + Application)
**Edges:** 5
- All from Mask A
- **+** backend → database (READINESS_COUPLED)

**Missing:** CONNECTS_TO (runtime)

### Mask C (Infrastructure + Runtime)
**Edges:** 5
- All from Mask A
- **+** backend → database (CONNECTS_TO)

**Missing:** READINESS_COUPLED (application)

### Mask D (All Evidence)
**Edges:** 6 - All edges present

---

## Dependency View Summary

### backend → database

**Belief:** 0.83 (High confidence)

**Relationships:**
1. DEPENDS_ON (infrastructure + application)
2. READINESS_COUPLED (application)
3. CONNECTS_TO (runtime)

**Evidence Types Present:**
- Infrastructure: conf = 0.5
- Application: conf = 0.85
- Runtime: conf = 1.0

**Flags:**
- Has conflict: ❌ No
- Already failing: ❌ No

**Supporting Evidence:**
- E-infra-002 (env variable reference)
- E-app-001 (psycopg2.connect call)
- E-app-002 (readiness probe coupling)
- E-runtime-001 (observed TCP connection)

---

## Key Insights

1. **Multi-evidence validation:** The backend → database dependency is supported by all three evidence types, giving high confidence (0.83).

2. **Critical dependency identified:** Three different relationship types confirm this is a critical dependency:
   - DEPENDS_ON: Functional dependency
   - READINESS_COUPLED: Backend health depends on database
   - CONNECTS_TO: Actual runtime communication

3. **Evidence aggregation:** Infrastructure evidence alone gives 0.5 confidence, but combined with application (0.85) and runtime (1.0), overall belief is high.

4. **No conflicts:** All evidence points in the same direction (supports), no refutations.

5. **Service topology:** The graph correctly captures Kubernetes service-to-pod relationships.

---

## What This Means for Impact Prediction

If a NetworkPolicy were to block `backend → database`:

- ✅ **DETECTED:** All three evidence types would signal this as a critical path
- ✅ **HIGH CONFIDENCE:** Belief of 0.83 means high certainty of impact
- ✅ **READINESS COUPLING:** Backend would become NotReady (cascading failure)
- ✅ **OPERATIONAL RISK:** Frontend would be affected via cascade
- ✅ **GATE DECISION:** Would correctly classify as RISKY

This is exactly what Milestone 2 verified: blocking this path breaks the application.
