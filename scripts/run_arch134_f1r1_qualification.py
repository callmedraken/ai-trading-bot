"""Dedicated C1 launcher; use -I -S -B. No trading/package initialization."""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path[:] = [str(Path(__file__).resolve().parent), *sys.path]
    from arch134_f1r1_qualification import main

    raise SystemExit(main())
