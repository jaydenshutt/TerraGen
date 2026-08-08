#!/usr/bin/env python3
"""
Backward-compatible entrypoint for TerraGen.

Prefer the installable CLI:
    pip install -e .
    terragen generate
    python -m terragen generate

Legacy usage still works:
    python TerraGen.py
    python TerraGen.py --answers answers.json --out ./out
"""

from terragen.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
