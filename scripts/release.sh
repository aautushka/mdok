#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./release.sh           # Test, build, and publish to PyPI
#   ./release.sh --test    # Test, build, and publish to TestPyPI
#   ./release.sh --dry-run # Test and build without uploading

TARGET="${1:-pypi}"

echo "========================================"
echo " 1. Running Test Suite"
echo "========================================"
pytest

echo ""
echo "========================================"
echo " 2. Cleaning Previous Artifacts"
echo "========================================"
rm -rf dist/ build/ src/*.egg-info

echo ""
echo "========================================"
echo " 3. Building Wheel and Source Archive"
echo "========================================"
python3 -m build

echo ""
echo "========================================"
echo " 4. Validating Package Metadata"
echo "========================================"
twine check dist/*

# Unset corporate/internal Nexus cluster environment overrides
unset TWINE_REPOSITORY_URL TWINE_REPOSITORY_DOMAIN TWINE_USERNAME TWINE_PASSWORD

echo ""
if [[ "$TARGET" == "--test" || "$TARGET" == "test" || "$TARGET" == "testpypi" ]]; then
    echo "========================================"
    echo " 5. Uploading to TestPyPI"
    echo "========================================"
    python3 -m twine upload --repository testpypi dist/*
elif [[ "$TARGET" == "--dry-run" || "$TARGET" == "dry-run" || "$TARGET" == "check" ]]; then
    echo "========================================"
    echo " 5. Dry Run Complete (No Upload)"
    echo "========================================"
    echo "Artifacts built and verified in dist/:"
    ls -lh dist/
else
    echo "========================================"
    echo " 5. Uploading to PyPI"
    echo "========================================"
    read -r -s -p "Enter PyPI API token (pypi-...): " PYPI_TOKEN
    echo ""
    if [[ -z "$PYPI_TOKEN" ]]; then
        echo "Error: Token cannot be empty."
        exit 1
    fi
    python3 -m twine upload \
        --username "__token__" \
        --password "$PYPI_TOKEN" \
        dist/*
    unset PYPI_TOKEN
fi

echo ""
echo "All done!"
