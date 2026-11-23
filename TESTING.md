# Testing Guide

## Quick Start

```bash
# Automated setup (venv + dependencies + config.yaml + smoke test)
./dev-setup.sh
source venv/bin/activate

# Or manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_validation.py

# Run specific test class
pytest tests/unit/test_validation.py::TestValidateIPAddress

# Run specific test
pytest tests/unit/test_validation.py::TestValidateIPAddress::test_valid_ip_addresses
```

## Test Structure

```
tests/
├── conftest.py                  # Shared fixtures
├── unit/                        # Unit tests (fast, isolated)
│   ├── test_validation.py       # Input validation (IP, URL, boolean)
│   ├── test_device_manager.py
│   ├── test_dlna_client.py
│   └── test_streamer.py
└── integration/                 # Flask test client against the API
    └── test_api_endpoints.py
```

## Running Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/unit/ -v      # or: make test-unit

# Integration tests only
pytest tests/integration/ -v   # or: make test-integration
```

## Code Coverage

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Generate terminal report
pytest --cov=app --cov-report=term-missing

# Check coverage threshold (fail if < 80%)
pytest --cov=app --cov-fail-under=80
```

## Code Quality Checks

Also available as Makefile targets: `make lint`, `make format-check`, `make type-check`, `make security`, `make all-checks`.

ruff and black are enforced in CI — run `make lint format-check` before pushing. bandit is informational for now.

```bash
# Linting with ruff
ruff check app/ tests/

# Auto-fix issues
ruff check --fix app/ tests/

# Format code with black
black app/ tests/

# Check formatting
black --check app/ tests/

# Type checking with mypy
mypy app/

# Security scanning with bandit
bandit -r app/ -f json -o bandit-report.json
```

## Writing Tests

### Unit Test Example

```python
# tests/unit/test_example.py
import pytest

class TestExample:
    def test_something(self):
        """Test description."""
        result = some_function()
        assert result == expected

    @pytest.mark.parametrize("input,expected", [
        ("valid", True),
        ("invalid", False),
    ])
    def test_with_params(self, input, expected):
        """Test with multiple inputs."""
        assert validate(input) == expected
```

### Integration Test Example

```python
# tests/integration/test_api.py
def test_endpoint(client):
    """Test API endpoint."""
    response = client.get('/api/endpoint')
    assert response.status_code == 200
    data = response.json()
    assert 'key' in data
```

### Using Fixtures

```python
def test_with_fixtures(device_manager, sample_device):
    """Use shared fixtures from conftest.py."""
    device_manager.select_device(sample_device)
    assert device_manager.has_device()
```

## Continuous Integration

Tests run automatically on pushes and pull requests to `main` (`.github/workflows/tests.yml`):
1. Tests on Python 3.11, 3.12, 3.14
2. Linting (ruff) and formatting (black) — must pass; security scan (bandit) — informational
3. Unit tests with coverage
4. Integration tests
5. Pull requests only: builds the Docker image and smoke-tests `/health`
6. Uploads coverage to Codecov

Docker images are built and pushed by a separate workflow (`.github/workflows/docker-publish.yml`) — see README → *Image updates*.

Locally, `make docker-test` builds the image and checks `/health`.

## Mocking

```python
from unittest.mock import Mock, patch

def test_with_mock(mocker):
    """Use pytest-mock for mocking."""
    mock_requests = mocker.patch('requests.post')
    mock_requests.return_value.status_code = 200

    # Your test code here
```

## Debugging Tests

```bash
# Show print statements
pytest -s

# Show locals on failure
pytest --showlocals

# Stop on first failure
pytest -x

# Debug with pdb
pytest --pdb

# Run last failed tests
pytest --lf
```

## Pre-commit Hook (Optional)

Create `.git/hooks/pre-commit`:
```bash
#!/bin/bash
set -e

echo "Running pre-commit checks..."

# Format check
black --check app/ tests/ || {
    echo "ERROR: Code formatting issues found. Run: black app/ tests/"
    exit 1
}

# Linting
ruff check app/ tests/ || {
    echo "ERROR: Linting issues found. Run: ruff check --fix app/ tests/"
    exit 1
}

# Quick tests
pytest tests/unit/ -q || {
    echo "ERROR: Unit tests failed"
    exit 1
}

echo "All checks passed"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```
