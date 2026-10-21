# Frontend Specification

**Project:** Evidence-Gated Predictive Cloud Change Impact & Security Remediation  
**Document Version:** 1.0  
**Date:** October 21, 2026  
**Status:** DRAFT

---

## 1. Overview

### 1.1 Purpose

This document specifies the frontend/UI architecture for the research system. The frontend serves **two distinct purposes**:

1. **POC Application Frontend** (EXISTING) - Simple nginx-served static HTML that represents the application under test (Frontend → Backend → PostgreSQL)
2. **Research System UI** (TO BE BUILT) - Web interface for researchers to submit change proposals, view predictions, examine evidence graphs, and analyze results

### 1.2 Technology Stack (Per implementation.md §5.9)

**Primary Choice:** React or Next.js (lightweight approach preferred)

**Alternative:** Enhanced static HTML + vanilla JavaScript (for speed/simplicity if React is overkill)

**Backend API:** FastAPI (Python) - Part 3, `src/evgate/api/`

**Deployment:** Local development server or serve via nginx in Kind cluster

---

## 2. Architecture

### 2.1 Two Frontends

```
┌─────────────────────────────────────────────────────────────┐
│  RESEARCH SYSTEM (this specification)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Research UI (React/Next.js)                         │  │
│  │  - Change submission                                 │  │
│  │  - Evidence visualization                            │  │
│  │  - Prediction display                                │  │
│  │  - Graph explorer                                    │  │
│  │  - Report viewer                                     │  │
│  │  - Experiment dashboard                              │  │
│  └──────────────────────────────────────────────────────┘  │
│                      ↓                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FastAPI Backend (src/evgate/api/)                   │  │
│  │  - /changes, /analyze, /results, /reports            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  POC APPLICATION (existing - services/frontend/)            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  POC Frontend (nginx + static HTML)                  │  │
│  │  - Displays "Frontend→Backend→DB" status             │  │
│  │  - Minimal health check UI                           │  │
│  │  - Purpose: workload for experiments                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                      ↓                                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  POC Backend (services/backend/)                     │  │
│  │  - /health, /live endpoints                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**IMPORTANT:** These are separate systems. The POC frontend is the *subject* of analysis; the Research UI is the *tool* for analysis.

### 2.2 Deployment Options

**Option A: Local Development Server (RECOMMENDED for MVP)**
- Run React dev server on host machine: `npm run dev` → `http://localhost:3000`
- Connects to FastAPI backend exposed via Kind NodePort or port-forward
- Fastest iteration, no cluster complexity
- Good for development and single-researcher use

**Option B: Containerized in Kind**
- Build React production build, serve via nginx in cluster
- Deploy as separate namespace/service in Kind
- More "production-like" but slower iteration
- Better for multi-researcher access or demos

**Decision:** Start with **Option A** (local dev server) until API stabilizes, then optionally add Option B for paper demos.

---

## 3. Research UI Features

### 3.1 Core Features (MVP - Milestone 4)

These support the **primary research workflow**:

#### 3.1.1 Change Submission Interface

**Purpose:** Submit proposed security changes for analysis

**Inputs:**
- Change type dropdown: `iam` | `network` | `kubernetes`
- File upload: YAML manifest or OpenTofu plan JSON
- Text editor: Paste change configuration
- Optional: Scenario selector (load from `scenarios/*.yaml`)

**Output:** Change ID, queued for analysis

**API:** `POST /changes`

```json
{
  "change_type": "kubernetes",
  "change_content": "apiVersion: networking.k8s.io/v1...",
  "description": "Isolate database from frontend",
  "scenario_id": "M2"
}
```

#### 3.1.2 Analysis Results Display

**Purpose:** View prediction for a submitted change

**Display:**
- **Gate Decision:** `SAFE` | `RISKY` | `INSUFFICIENT_EVIDENCE` (large, color-coded badge)
- **Security Impact:** `improves` | `degrades` | `neutral` | `mixed`
- **Operational Risk:** `none` | `low` | `high` | `unknown`
- **Affected Components:** List with impact classification (`unavailable`, `degraded`, `isolated`, `none`)
- **Confidence Metrics:** Belief, sufficiency, confidence (0-1 scales with visual bars)
- **Evidence Summary:** Count by type (infra/app/runtime), conflicts flagged
- **Explanation:** Reasoning from evidence gate (§8.4)
- **Remediation:** If RISKY, show proposed patches

**API:** `GET /results/{analysis_id}`

#### 3.1.3 Evidence Graph Visualization

**Purpose:** Interactive dependency graph with evidence overlays

**Technology:** 
- D3.js (established, academic-friendly) or
- Cytoscape.js (better for large graphs) or
- React Flow (modern, simpler API)

**Features:**
- **Nodes:** Components (frontend, backend, database, policies, etc.)
- **Edges:** Relationships colored by type (DEPENDS_ON, CONNECTS_TO, ALLOWS, DENIES, etc.)
- **Evidence Filters:** Toggle infrastructure/application/runtime layers
- **Confidence Overlay:** Edge thickness = confidence level
- **Hover Details:** Show evidence IDs, provenance, timestamps
- **Highlight Affected Path:** When change blocks backend→database, highlight that edge and propagated impacts
- **Export:** PNG/SVG for papers

**API:** `GET /graphs/{bundle_id}` → returns NetworkX JSON or DOT format

**Reference:** You already generate graph visualizations in test output (`test_output/GRAPH_VISUALIZATION.md`)

#### 3.1.4 Report Viewer

**Purpose:** Display generated analysis reports

**Format:** Markdown rendered to HTML (or PDF download)

**Content:** (per `src/evgate/report/`)
- Executive summary
- Evidence breakdown
- Prediction details
- Remediation proposals
- Confidence assessment

**API:** `GET /reports/{analysis_id}` → Markdown or HTML

#### 3.1.5 Experiment Dashboard

**Purpose:** Track batch experiments (40 scenarios)

**Display:**
- Scenario list with status: pending | running | complete | failed
- Aggregate metrics: Accuracy, F1, calibration
- Evidence configuration comparison (A/B/C/D)
- Filters: by change type, by scenario family, by outcome

**API:** `GET /experiments` → list of experiment runs

---

### 3.2 Advanced Features (Post-MVP / Optional)

#### 3.2.1 Real-Time Analysis Progress

- WebSocket or Server-Sent Events for live updates
- Progress bar: Evidence collection → Graph build → Prediction → Gate
- Useful for long-running analyses

#### 3.2.2 Evidence Inspector

- Detailed view of individual evidence records
- Provenance chain visualization
- Conflict resolution viewer

#### 3.2.3 Scenario Builder

- Visual editor for creating new test scenarios
- Component selector, change composer
- Expected outcome annotation

#### 3.2.4 Comparison Mode

- Side-by-side: Prediction vs Ground Truth
- Diff view for affected components
- Root cause analysis when prediction fails

#### 3.2.5 Calibration Dashboard

- Calibration plots (predicted confidence vs actual accuracy)
- Per-evidence-type reliability tuning
- Threshold adjustment with live preview

---

## 4. API Specification

### 4.1 FastAPI Backend Endpoints (Part 3)

**Base URL:** `http://localhost:8080` (or Kind NodePort)

#### 4.1.1 Change Management

```
POST   /api/changes                     # Submit new change
GET    /api/changes                     # List all changes
GET    /api/changes/{change_id}         # Get change details
DELETE /api/changes/{change_id}         # Delete change
```

#### 4.1.2 Analysis

```
POST   /api/analyze                     # Trigger analysis
GET    /api/analyze/{analysis_id}       # Poll analysis status
GET    /api/results/{analysis_id}       # Get prediction result
```

Request body for `POST /api/analyze`:
```json
{
  "change_id": "CHG-123",
  "evidence_config": "infrastructure+application+runtime",
  "force_decision": null
}
```

Response:
```json
{
  "analysis_id": "ANL-456",
  "status": "running",
  "started_at": "2026-10-21T14:30:00Z"
}
```

#### 4.1.3 Evidence & Graphs

```
GET    /api/evidence/{bundle_id}        # Get evidence bundle
GET    /api/graphs/{bundle_id}          # Get graph JSON
GET    /api/graphs/{bundle_id}/export   # Export as PNG/DOT
```

#### 4.1.4 Reports

```
GET    /api/reports/{analysis_id}       # Get markdown report
GET    /api/reports/{analysis_id}/pdf   # Get PDF report (optional)
```

#### 4.1.5 Experiments

```
GET    /api/experiments                 # List experiments
POST   /api/experiments                 # Create experiment batch
GET    /api/experiments/{exp_id}        # Get experiment results
GET    /api/experiments/{exp_id}/metrics # Get aggregated metrics
```

#### 4.1.6 Scenarios

```
GET    /api/scenarios                   # List available scenarios
GET    /api/scenarios/{scenario_id}     # Get scenario spec
POST   /api/scenarios/{scenario_id}/run # Run scenario ground truth
```

### 4.2 Contract Models (Return Types)

All API responses use Pydantic models from `src/evgate/contracts/`:

- `ChangeSpec` - parsed change
- `EvidenceBundle` - evidence collection
- `Prediction` - prediction result
- `GateDecision` - gate outcome
- `Remediation` - remediation proposal
- `AnalysisResult` - full analysis output
- `ExperimentRecord` - experiment results

**CORS:** Enable CORS for local development (React dev server on different port)

---

## 5. Implementation Plan

### 5.1 Phase 1: API Backend (Part 3 - In Progress)

**Owner:** Member 3  
**Task:** P3-07 (API), P3-08 (Report)  
**Status:** Mentioned in architecture but not yet built

**Deliverables:**
- FastAPI app in `src/evgate/api/`
- Endpoints per §4.1
- OpenAPI/Swagger docs auto-generated
- CORS configuration
- Integration tests with pytest

**Dependencies:**
- P3-01 through P3-06 (COMPLETE - graph, belief, prediction, gate, pipeline)
- Contracts (COMPLETE - `src/evgate/contracts/`)

### 5.2 Phase 2: CLI Interface (Part 3 - Current)

**Owner:** Member 3  
**Task:** P3-07 (CLI)

**Purpose:** Command-line interface for researchers (alternative to web UI)

```bash
evgate analyze --change changes/M2.yaml --evidence-config D --output results/
evgate report --analysis ANL-456 --format markdown
evgate graph --bundle BUN-789 --export png
```

**Priority:** CLI first, then Web UI (research tool first, demo second)

### 5.3 Phase 3: Research UI Frontend (Future / Part 4?)

**Owner:** TBD (possibly Member 4 or shared)  
**Dependencies:** API backend complete

**Option A: React MVP (Recommended)**

**Setup:**
```bash
mkdir -p ui/research-frontend
cd ui/research-frontend
npx create-react-app . --template typescript
# or
npx create-next-app@latest . --typescript
```

**Structure:**
```
ui/research-frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── ChangeSubmission.tsx
│   │   ├── AnalysisResults.tsx
│   │   ├── EvidenceGraph.tsx
│   │   ├── ReportViewer.tsx
│   │   └── ExperimentDashboard.tsx
│   ├── services/
│   │   └── api.ts                # Axios/fetch wrapper
│   ├── types/
│   │   └── contracts.ts          # TypeScript interfaces matching Pydantic models
│   ├── App.tsx
│   └── index.tsx
├── package.json
└── README.md
```

**Libraries:**
- `axios` or `fetch` - API calls
- `react-router-dom` - routing
- `d3` or `cytoscape` or `react-flow` - graph visualization
- `react-markdown` - render reports
- `recharts` or `plotly.js` - metrics charts
- `tailwindcss` or `mui` - styling

**Effort:** ~5-7 days for MVP (submit, view results, basic graph)

**Option B: Enhanced Static HTML (Faster MVP)**

Extend the existing `services/frontend/static/index.html` pattern:
- Add forms for change submission
- Fetch API results with vanilla JS
- Render JSON responses in formatted HTML
- Use D3.js for graph visualization
- No build step, no npm dependencies

**Effort:** ~2-3 days for basic functionality

**Decision:** Recommend **Option B for initial MVP**, then upgrade to React if needed for paper demos or complexity grows.

### 5.4 Phase 4: Containerization (Optional)

If deploying Research UI to Kind cluster:

```dockerfile
# ui/research-frontend/Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

Kubernetes manifest:
```yaml
# kubernetes/research-ui/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: research-ui
  namespace: evgate-research
spec:
  replicas: 1
  selector:
    matchLabels:
      app: research-ui
  template:
    metadata:
      labels:
        app: research-ui
    spec:
      containers:
      - name: research-ui
        image: localhost:5001/research-ui:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: research-ui-service
  namespace: evgate-research
spec:
  type: NodePort
  ports:
  - port: 80
    targetPort: 80
    nodePort: 30090
  selector:
    app: research-ui
```

Access: `http://localhost:30090`

---

## 6. User Workflows

### 6.1 Primary Research Workflow

1. **Researcher submits change**
   - UI: Change Submission form
   - Upload `isolate-database.yaml`
   - Click "Analyze"

2. **System runs analysis**
   - UI: Progress indicator
   - Backend: Evidence collection → Graph → Prediction → Gate

3. **Researcher views results**
   - UI: Analysis Results page
   - Shows: RISKY, security improves, operational risk high
   - Affected: backend (unavailable), database (degraded), frontend (unavailable via cascade)

4. **Researcher examines evidence**
   - UI: Evidence Graph viewer
   - Toggle layers: see infrastructure config, application code, runtime traces
   - Hover over backend→database edge: see evidence IDs and confidence

5. **Researcher reviews remediation**
   - UI: Remediation section
   - Proposed patch: Allow only backend→database:5432
   - Static validation: passes
   - Dynamic validation: pending

6. **Researcher triggers ground truth**
   - UI: "Run in Cluster" button
   - Backend: Applies change, runs workload, collects telemetry
   - UI: Shows actual result vs prediction

7. **Researcher generates report**
   - UI: "Export Report" button
   - Download markdown or PDF
   - Include in paper

### 6.2 Batch Experiment Workflow

1. **Researcher creates experiment**
   - UI: Experiment Dashboard
   - Select: 40 scenarios, evidence config D
   - Click "Run Batch"

2. **System processes scenarios**
   - UI: Progress table (scenario-by-scenario)
   - Backend: Runs each scenario, stores results

3. **Researcher views metrics**
   - UI: Metrics summary
   - Accuracy: 0.87, Precision: 0.89, Recall: 0.85, F1: 0.87
   - Calibration plot

4. **Researcher compares configurations**
   - UI: Select configs A, B, C, D
   - Side-by-side metrics
   - Statistical significance tests

5. **Researcher exports for paper**
   - UI: "Export Figures" button
   - Download: metrics.csv, calibration.png, comparison.png

---

## 7. Design Considerations

### 7.1 Research Focus

**Priority:** Functionality > Polish

- Use standard UI libraries, don't reinvent
- Focus on data display, not fancy animations
- Academic aesthetics: clean, readable, professional
- Paper-ready exports (PNG, SVG, PDF)

### 7.2 Local Reproducibility

**All features must work offline:**

- No cloud dependencies (AWS/Azure/GCP not required)
- No external API calls (except optional LLM if added later)
- No telemetry to third parties

### 7.3 Determinism

**Consistent results for reproducibility:**

- Seeded RNG for any randomization
- Sorted outputs (component lists, evidence IDs)
- No timestamps in IDs (use deterministic hashes)

### 7.4 Literature Compliance

**Conservative claims in UI text:**

- Don't say "first system to..." or "novel approach to..."
- Use "integrates evidence from...", "predicts impact based on..."
- Link to papers in footer/about page

### 7.5 Security

**Local environment, but still secure:**

- No hardcoded secrets
- Sanitize file uploads (YAML/JSON validation)
- `assert_local_kind_context()` guard before kubectl
- CORS restricted to localhost

---

## 8. Testing Strategy

### 8.1 API Testing (Part 3)

**Unit tests:** `tests/unit/test_api.py`
- Test each endpoint with pytest fixtures
- Mock pipeline.analyze()
- Verify response schemas match contracts

**Integration tests:** `tests/integration/test_api_integration.py`
- Full pipeline: POST change → GET result
- Use golden fixtures (G1-G4)
- Verify CORS headers

### 8.2 UI Testing (Future)

**Manual testing:** (for MVP)
- Test each workflow in §6
- Verify on Chrome, Firefox, Safari

**Automated testing:** (if time permits)
- Jest + React Testing Library
- Cypress for end-to-end tests
- Snapshot tests for rendered components

### 8.3 Acceptance Criteria

**MVP is complete when:**
- [ ] Researcher can submit a change via UI
- [ ] Researcher can view prediction results
- [ ] Researcher can see evidence graph
- [ ] Researcher can download markdown report
- [ ] All API endpoints return correct contract types
- [ ] UI works in local dev mode
- [ ] No console errors on happy path

---

## 9. Documentation

### 9.1 For Developers

**Location:** `ui/research-frontend/README.md`

**Contents:**
- Setup instructions (npm install, env vars)
- Development: `npm run dev`
- Build: `npm run build`
- API endpoint configuration
- Component architecture

### 9.2 For Users (Researchers)

**Location:** `docs/USER_GUIDE.md`

**Contents:**
- How to submit a change
- How to interpret results
- How to use the graph explorer
- How to run experiments
- Troubleshooting

### 9.3 For the Paper

**Location:** `paper/sections/05-system-implementation.md`

**Contents:**
- System architecture diagram (include Research UI)
- Screenshot: Analysis Results page
- Screenshot: Evidence Graph with M2 scenario
- Discussion: UI supports reproducible research workflow

---

## 10. Timeline & Ownership

### 10.1 Current Status

**Complete:**
- Part 3 core engine (P3-01 through P3-06): graph, belief, prediction, gate, pipeline ✅
- 96 unit tests passing ✅
- Part 4 remediation + evaluation integrated ✅
- 4 integration tests passing ✅

**In Progress:**
- Part 2 evidence extraction (Member 2) 🔄
- Part 4 scenarios + experiments (Member 4) 🔄

**Pending:**
- P3-07: CLI interface (Member 3)
- P3-08: Report generation (Member 3)
- P3-09: FastAPI endpoints (Member 3)
- Research UI frontend (TBD)

### 10.2 Recommended Priority

1. **CLI first** (P3-07) - researchers can use immediately, no browser needed
2. **API second** (P3-09) - enables automation and future UI
3. **Report third** (P3-08) - generate paper-ready outputs
4. **Web UI last** (future) - nice-to-have for demos, not critical for research

### 10.3 Effort Estimates

| Task | Effort | Owner | Priority |
|------|--------|-------|----------|
| P3-07 CLI | 2 days | Member 3 | HIGH |
| P3-09 API | 3 days | Member 3 | MEDIUM |
| P3-08 Report | 2 days | Member 3 | MEDIUM |
| Static HTML UI (MVP) | 2-3 days | TBD | LOW |
| React UI (full) | 5-7 days | TBD | OPTIONAL |

---

## 11. Alternatives Considered

### 11.1 CLI Only (No Web UI)

**Pros:**
- Simpler, faster to implement
- Sufficient for research (batch experiments)
- Paper doesn't require screenshots

**Cons:**
- Less impressive for demos
- Harder to debug graph visualizations
- No interactive exploration

**Decision:** Start with CLI, add minimal web UI if time permits

### 11.2 Jupyter Notebook Interface

**Pros:**
- Familiar to researchers
- Good for exploratory analysis
- Easy to embed graphs and reports

**Cons:**
- Not a "system" UI (less impressive)
- Harder to share/deploy
- Requires Python environment

**Decision:** Could be a nice addition, but not primary interface

### 11.3 Desktop Application (Electron)

**Pros:**
- No browser needed
- Native feel

**Cons:**
- Overkill for local-only tool
- Longer development time
- Distribution complexity

**Decision:** Rejected - web UI is sufficient

---

## 12. Open Questions

1. **Who owns frontend development?**
   - Member 3 (has API) or Member 4 (has time)?
   - Or shared responsibility?

2. **React vs Static HTML?**
   - React for extensibility or static for speed?
   - Decision: Start static, upgrade if needed

3. **Deploy to Kind or run locally?**
   - Local dev server (faster iteration) or containerized (more realistic)?
   - Decision: Local first, Kind optional

4. **When to build UI?**
   - After P3-07/08/09 complete or in parallel?
   - Decision: CLI first, UI later (not blocking research)

5. **Graph visualization library?**
   - D3.js (academic standard) or Cytoscape (feature-rich) or React Flow (modern)?
   - Decision: Try D3 first (can export to PNG for papers)

---

## 13. Success Criteria

**The frontend is successful when:**

1. ✅ Researcher can submit change and view prediction without writing code
2. ✅ Evidence graph is visualized with confidence overlays
3. ✅ Prediction vs ground truth comparison is clear
4. ✅ Markdown reports are generated and downloadable
5. ✅ Experiment dashboard shows aggregate metrics
6. ✅ System works entirely on local machine (no cloud required)
7. ✅ UI supports all 40 scenarios without manual intervention
8. ✅ Screenshots and exports are paper-ready quality

---

## 14. References

- **Implementation.md §5.9:** "Frontend (lightweight, later phase) - React / Next.js or similar"
- **Task.md P3:** "Core engine + interfaces (contracts steward, graph, belief, prediction, evidence gate, pipeline, CLI, API, report, CI)"
- **Architecture.md:** "CHANGE SUBMISSION INTERFACE (Web UI / CLI / REST API)"
- **Existing POC Frontend:** `services/frontend/static/index.html` (simple health check UI)

---

## Appendix A: Environment Variables

```bash
# .env for Research UI (local development)
REACT_APP_API_BASE_URL=http://localhost:8080
REACT_APP_API_TIMEOUT=30000
REACT_APP_ENABLE_TELEMETRY=false
```

---

## Appendix B: Example API Response

```json
{
  "analysis_id": "ANL-M2-20261021-143000",
  "change_id": "CHG-M2",
  "gate_decision": {
    "decision": "RISKY",
    "reason_codes": ["HIGH_OP_RISK"],
    "explanation": "Change blocks backend→database communication. Evidence: infrastructure (NetworkPolicy ingress:[]), application (psycopg2 connection required), runtime (observed traffic in baseline). Belief: 0.92, Sufficiency: 0.85, Confidence: 0.87.",
    "evidence_requests": [],
    "thresholds_used": {
      "belief_risky": 0.7,
      "sufficiency_min": 0.6
    }
  },
  "prediction": {
    "security_impact": "improves",
    "operational_label": "high",
    "affected_components": [
      {
        "component": "backend",
        "impact": "unavailable",
        "reason": "Required database dependency blocked",
        "confidence": 0.92
      },
      {
        "component": "database",
        "impact": "degraded",
        "reason": "Isolated from backend",
        "confidence": 0.88
      },
      {
        "component": "frontend",
        "impact": "unavailable",
        "reason": "Upstream cascade via backend readiness",
        "confidence": 0.81
      }
    ],
    "belief": 0.92,
    "sufficiency": 0.85,
    "confidence": 0.87
  },
  "remediation": {
    "remediation_id": "REM-M2-001",
    "strategy": "narrow_allow",
    "patches": [
      {
        "manifest_type": "kubernetes",
        "action": "patch",
        "target": "networkpolicy/database-policy",
        "patch": {
          "spec": {
            "ingress": [
              {
                "from": [
                  {
                    "podSelector": {
                      "matchLabels": {
                        "app": "backend"
                      }
                    }
                  }
                ],
                "ports": [
                  {
                    "protocol": "TCP",
                    "port": 5432
                  }
                ]
              }
            ]
          }
        }
      }
    ],
    "static_validation": {
      "preserves_required": true,
      "keeps_objective": true,
      "introduces_wildcard": false
    },
    "minimality": {
      "allowed_pairs": 1,
      "required_pairs": 1,
      "excess_pairs": 0,
      "ratio": 1.0
    }
  },
  "evidence_summary": {
    "total_count": 18,
    "by_type": {
      "infrastructure": 6,
      "application": 7,
      "runtime": 5
    },
    "conflicts": 0,
    "coverage": {
      "workload_id": "baseline-full",
      "window_seconds": 120,
      "endpoints_exercised": ["GET /health", "GET /live", "POST /api/test"]
    }
  },
  "timestamp": "2026-10-21T14:30:00Z"
}
```

---

**END OF SPECIFICATION**
