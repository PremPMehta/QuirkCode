"""QuirkCode entry point."""

from __future__ import annotations

import logging
import sys

from config import load_config, logs_dir
from ui import launch


def main() -> int:
    logs_dir()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = load_config()
    launch(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
