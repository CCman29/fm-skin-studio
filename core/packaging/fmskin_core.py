"""Entry point for the bundled engine (PyInstaller): the desktop app runs `fmskin-core rpc`."""
import sys

from fmskin.cli import main

if __name__ == "__main__":
    sys.exit(main())
