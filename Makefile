.PHONY: help venv install install-dev test test-unit test-integration lint format security clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

venv: ## Create virtual environment
	python3 -m venv venv
	@echo ""
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate"

install: venv ## Install production dependencies
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt

install-dev: install ## Install dev dependencies
	./venv/bin/pip install -r requirements-dev.txt

test: ## Run all tests
	./venv/bin/pytest -v

test-unit: ## Run unit tests only
	./venv/bin/pytest tests/unit/ -v

test-integration: ## Run integration tests only
	./venv/bin/pytest tests/integration/ -v

coverage: ## Run tests with coverage report
	./venv/bin/pytest --cov=app --cov-report=html --cov-report=term
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

lint: ## Run linter (ruff)
	./venv/bin/ruff check app/ tests/

lint-fix: ## Run linter and auto-fix issues
	./venv/bin/ruff check --fix app/ tests/

format: ## Format code with black
	./venv/bin/black app/ tests/

format-check: ## Check code formatting
	./venv/bin/black --check app/ tests/

security: ## Run security scanner (bandit)
	./venv/bin/bandit -r app/ -f json -o bandit-report.json
	@echo "Security report generated: bandit-report.json"

type-check: ## Run type checker (mypy)
	./venv/bin/mypy app/

all-checks: lint format-check type-check security test ## Run all quality checks

docker-build: ## Build Docker image
	docker build -t stream-to-dlna:latest .

docker-run: ## Run Docker container
	docker run --rm -it -p 5000:5000 -p 8080:8080 \
		-v $(PWD)/config.yaml:/app/config.yaml:ro \
		stream-to-dlna:latest

docker-test: ## Build and test Docker image
	docker build -t stream-to-dlna:test .
	docker run --rm -d --name test-container -p 5001:5000 stream-to-dlna:test
	sleep 5
	curl -f http://localhost:5001/health || (docker stop test-container && exit 1)
	docker stop test-container
	@echo "Docker smoke test passed!"

clean: ## Clean generated files
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml bandit-report.json
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

clean-all: clean ## Clean everything including venv
	rm -rf venv
