#!/usr/bin/env python3
"""Alias kept so documented invocations keep working.

The experiment lives at aestheticbench.benchmark.order_bias; this shim exists
because the spec and two days of shell history say `python scripts/order_bias.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aestheticbench.benchmark.order_bias import main

if __name__ == "__main__":
    raise SystemExit(main())
