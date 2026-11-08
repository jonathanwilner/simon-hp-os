#!/usr/bin/env python3
"""Promote from trusted local validation and hardware evidence; no hosted jobs."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'fleet/release'))
from controller import main

if __name__ == '__main__':
    # Supply --config, --state, and --revision explicitly. The controller refuses
    # missing/failed evidence and requires the tracked nom-tmux execution path.
    sys.argv.append('--promote-only')
    sys.exit(main())
