#!/usr/bin/env bash
set -e

echo "=== black --check ==="
black --check src/ tests/ analyse_patch.py

echo "=== isort --check ==="
isort --check src/ tests/ analyse_patch.py

echo "=== mypy ==="
mypy src/ --ignore-missing-imports

echo "=== pytest ==="
python -m pytest tests/ -v

echo "=== All checks passed ==="
