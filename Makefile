.PHONY: help install test lint format schemas clean demo reproduce reproduce-full

help:
	@echo "Evidence-Gated Predictive Cloud Change Impact & Security Remediation"
	@echo ""
	@echo "Available targets:"
	@echo "  install          Install package and dependencies"
	@echo "  test             Run all tests (unit + integration)"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-cluster     Run cluster tests (requires local Kind)"
	@echo "  lint             Run linters (ruff, mypy)"
	@echo "  format           Format code with black"
	@echo "  schemas          Generate JSON Schemas from contracts"
	@echo "  clean            Remove generated files"
	@echo "  demo             Run M2 scenario end-to-end"
	@echo "  reproduce        Regenerate metrics/figures from existing results"
	@echo "  reproduce-full   Re-run all scenarios and regenerate results"
	@echo "  graph-figure     Generate graph figure for paper"
	@echo "  telemetry-up     Start telemetry stack"
	@echo "  telemetry-down   Stop telemetry stack"

install:
	pip install -e ".[dev,eval]"

test:
	pytest -v -m "not cluster"

test-unit:
	pytest -v -m "unit"

test-integration:
	pytest -v -m "integration"

test-cluster:
	pytest -v -m "cluster"

lint: lint-ruff lint-mypy

lint-ruff:
	ruff check src/ tests/

lint-mypy:
	mypy --strict src/evgate/contracts/
	mypy src/evgate/

format:
	black src/ tests/
	ruff check --fix src/ tests/

schemas:
	python -c "from evgate.contracts import export_schemas; export_schemas()"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/

demo:
	@echo "Running M2 scenario end-to-end..."
	@echo "Step 1: Collect evidence"
	python -m evgate collect --manifests kubernetes --src services/backend --runtime fixtures/ground_truth/m2 --snapshot baseline@m2 -o var/bundle_m2.json
	@echo "Step 2: Parse change"
	python -m evgate parse-change --kind k8s_networkpolicy --after kubernetes/policies/isolate-database.yaml --bundle var/bundle_m2.json -o var/change_m2.json
	@echo "Step 3: Analyze (config D)"
	python -m evgate analyze --change var/change_m2.json --bundle var/bundle_m2.json --config D -o var/result_m2.json
	@echo "Step 4: Generate report"
	python -m evgate report --result var/result_m2.json --ground-truth fixtures/golden/gt_M2_label.json -o var/report_m2.html
	@echo "Demo complete. See var/report_m2.html"

reproduce:
	@echo "Regenerating metrics and figures from experiments/results/..."
	python -m evgate.evaluation.stats experiments/results/latest/records.jsonl -o experiments/results/latest/

reproduce-full:
	@echo "Re-running all scenarios (this takes several hours)..."
	python -m evgate.scenarios.runner scenarios/*.yaml --runs 3 -o experiments/results/new/

graph-figure:
	python -m evgate.graph.export fixtures/golden/G1_bundle_full.json --format png -o paper/figures/graph.png

# --- Part 2 ---
telemetry-up:
	@echo "Starting telemetry stack..."
	kubectl apply -k telemetry/

telemetry-down:
	@echo "Stopping telemetry stack..."
	kubectl delete -k telemetry/ || true

# --- Part 3 ---
# (Additional targets owned by Part 3)

# --- Part 4 ---
# (Additional targets owned by Part 4)
