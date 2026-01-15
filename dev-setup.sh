#!/bin/bash
set -e

# Cleanup on error
cleanup_on_error() {
    echo ""
    echo "ERROR: Setup failed! Rolling back..."
    if [ -d "venv" ] && [ ! -f "venv/.setup_complete" ]; then
        echo "   Removing incomplete venv..."
        rm -rf venv
    fi
    echo "   Run './dev-setup.sh' again to retry."
    exit 1
}

trap cleanup_on_error ERR

echo "Setting up stream-to-dlna development environment..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "[OK] Python version: $PYTHON_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment already exists"
fi

# Activate venv and install dependencies
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r requirements-dev.txt -q
echo "[OK] Dependencies installed"

# Create config if needed
if [ ! -f "config.yaml" ]; then
    echo "Creating config.yaml from example..."
    cp config.example.yaml config.yaml
    echo "[OK] config.yaml created (edit as needed)"
fi

# Run quick smoke test
echo ""
echo "Running smoke tests..."
pytest tests/unit/test_validation.py -q
echo "[OK] Smoke tests passed"

# Mark setup as complete
touch venv/.setup_complete

echo ""
echo "Development environment ready!"
echo ""
echo "To activate virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "Available commands (with venv activated):"
echo "  pytest                    # Run all tests"
echo "  pytest --cov=app         # Run with coverage"
echo "  ruff check app/          # Lint code"
echo "  black app/               # Format code"
echo ""
echo "Or use Makefile shortcuts:"
echo "  make test                # Run all tests"
echo "  make coverage            # Generate coverage report"
echo "  make lint                # Run linter"
echo "  make format              # Format code"
echo "  make help                # Show all available commands"
echo ""
