# Testing Guide

## Quick Start

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

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
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_validation.py   # Input validation
│   ├── test_device_manager.py
│   ├── test_dlna_client.py
│   ├── test_streamer.py
│   ├── test_discovery.py
│   └── test_config.py
├── integration/             # Integration tests (slower, real components)
│   ├── test_api_endpoints.py
│   ├── test_workflows.py
│   └── test_security.py
└── performance/             # Performance tests
    └── test_performance.py
```

## Running Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Security tests only
pytest -m security

# Skip slow tests
pytest -m "not slow"
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

Tests run automatically on:
- Push to `main`, `develop`, `claude/**` branches
- Pull requests to `main`, `develop`

The CI pipeline:
1. Tests on Python 3.11, 3.12, 3.14
2. Runs linting (ruff) and formatting checks (black)
3. Runs security scanning (bandit)
4. Runs unit tests with coverage
5. Runs integration tests
6. Builds Docker image and smoke tests it
7. Uploads coverage to Codecov

See `.github/workflows/tests.yml` for details.

## Test Markers

```python
@pytest.mark.unit        # Unit test
@pytest.mark.integration # Integration test
@pytest.mark.slow        # Slow test (skip in quick runs)
@pytest.mark.security    # Security test
```

Run specific markers:
```bash
pytest -m unit
pytest -m "integration and not slow"
```

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
    echo "❌ Code formatting issues found. Run: black app/ tests/"
    exit 1
}

# Linting
ruff check app/ tests/ || {
    echo "❌ Linting issues found. Run: ruff check --fix app/ tests/"
    exit 1
}

# Quick tests
pytest tests/unit/ -q || {
    echo "❌ Unit tests failed"
    exit 1
}

echo "✅ All checks passed"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```
