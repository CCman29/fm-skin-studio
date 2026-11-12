"""Entry point for the skin installer players run (PyInstaller, one file): see fmskin.installer_app."""
import sys

from fmskin.installer_app import main

if __name__ == "__main__":
    sys.exit(main())
