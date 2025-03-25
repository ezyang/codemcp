#!/bin/bash
set -e

echo "Running Pyright type checker with strict settings..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
"${SCRIPT_DIR}/.venv/bin/python" -m pyright $@

echo "Type checking completed successfully!"
