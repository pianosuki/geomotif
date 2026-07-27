"""Let ``python -m geomotif`` run the same command line as ``geomotif``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
