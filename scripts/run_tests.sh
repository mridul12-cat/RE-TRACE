#!/bin/bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"
export PYTHONPATH="$DIR/.venv/lib/python3.9/site-packages:$DIR"
"$DIR/.venv/bin/pytest" "$@"
