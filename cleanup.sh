#!/bin/bash

echo "Cleaning up stream-to-dlna development environment..."
echo ""

# Deactivate venv if active
if [ -n "$VIRTUAL_ENV" ]; then
    echo "WARNING: Virtual environment is active. Deactivating..."
    deactivate 2>/dev/null || true
fi

# Remove venv
if [ -d "venv" ]; then
    echo "Removing virtual environment..."
    rm -rf venv
    echo "[OK] venv removed"
fi

# Remove test artifacts
echo "Removing test artifacts..."
rm -rf .pytest_cache .coverage coverage.xml htmlcov bandit-report.json pytest-report.html
echo "[OK] Test artifacts removed"

# Remove cache directories
echo "Removing cache..."
rm -rf .ruff_cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "[OK] Cache removed"

# Optional: remove config.yaml
read -p "Remove config.yaml? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f "config.yaml" ]; then
        rm config.yaml
        echo "[OK] config.yaml removed"
    fi
fi

echo ""
echo "Cleanup complete!"
echo ""
echo "To set up again:"
echo "  ./dev-setup.sh"
echo ""
