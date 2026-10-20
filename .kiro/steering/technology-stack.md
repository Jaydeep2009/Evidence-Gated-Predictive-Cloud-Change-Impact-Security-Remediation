# Technology Stack

## Operating System
- **Windows** (host)
- **WSL2 + Ubuntu** (Linux environment)

## Development Tools
- **Kiro** (IDE)
- **Git**
- **GitHub**

## Containerization & Orchestration
- **Docker / Docker Desktop**
- **Kubernetes**
- **Kind** (Kubernetes in Docker - for local cluster)

## Infrastructure as Code
- **OpenTofu** (primary)
- Terraform-compatible concepts where useful

## Backend
- **Python**
- **FastAPI** (web framework)
- **Pydantic** (data validation)

## Parsing
- **PyYAML**

## Graph & Analysis
- **NetworkX** (graph library)
- **Pandas** (data analysis)

## Machine Learning (optional, late-stage)
- **scikit-learn**

## Database
- **PostgreSQL**

## Observability & Telemetry
- **OpenTelemetry**
- **Jaeger** (distributed tracing)
- **Prometheus** (metrics)
- **Grafana** (visualization)

## Testing
- **Pytest**

## CI/CD
- **GitHub Actions**

## Frontend (lightweight, later phase)
- **React / Next.js** or similar

---

## Technologies to AVOID (unless explicitly needed)

Do NOT add these unless a specific research/implementation need is demonstrated:

- Kafka
- Redis
- Spark
- Airflow
- Neo4j
- Elasticsearch
- Complex message queues
- Unnecessary microservices frameworks
- Heavy ML frameworks before basic system works

---

## Technology Selection Principles

1. **Local reproducibility first** - core experiments must work without cloud providers
2. **Simplicity over complexity** - use established, well-documented tools
3. **Research focus** - technology should support research goals, not become the research
4. **Incremental adoption** - start simple, add complexity only when needed
5. **Open source** - prefer open-source tools for reproducibility
