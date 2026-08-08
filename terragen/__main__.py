"""Allow `python -m terragen`."""

from terragen.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
