#!/usr/bin/env bash
# Validate the package without publishing anything.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
PYTHON_BIN="${PYTHON:-python3}"
SKIP_TESTS=false
if [[ "${1:-}" == "--skip-tests" ]]; then
    SKIP_TESTS=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--skip-tests]" >&2
    exit 2
fi
"$PYTHON_BIN" - <<'PY'
import sys
from pathlib import Path
assert sys.version_info >= (3, 10), "Python 3.10+ required"
for name in ("pyproject.toml", "README.md", "LICENSE", "NOTICE", "src/easy_code_reader/server.py"):
    assert Path(name).is_file(), f"Missing: {name}"
import build
import twine
from easy_code_reader.server import EasyCodeReaderServer
from easy_code_reader.config import Config
assert Config.SERVER_NAME == "easy-code-reader"
print("Package files and build dependencies: OK")
PY
if [[ "$SKIP_TESTS" == false ]]; then
    "$PYTHON_BIN" -m pytest tests/ -q
    "$PYTHON_BIN" scripts/smoke_test.py
fi
"$PYTHON_BIN" -m easy_code_reader --help >/dev/null
git diff --check
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree contains changes; review them before publishing."
fi
echo "Pre-publish checks passed."
