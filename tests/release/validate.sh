#!/usr/bin/env bash
# Synchronous gate. Call through nom-tmux on managed hosts.
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 -m unittest discover -s tests/release -p 'test_*.py'
exec python3 tests/release/validate.py "${1:?Pass x86_64-linux or aarch64-linux}"
