#!/usr/bin/env python3
"""Run the full pipeline from any directory."""

import argparse
import importlib
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.dont_write_bytecode = True

logger = logging.getLogger(__name__)

STEP_MODULES = [
    "pipeline.01_parse_items",
    "pipeline.02_resolve_axioms",
    "pipeline.03_calculate_costs",
    "pipeline.04_generate_output",
    "pipeline.05_publish",
]


def main():
    parser = argparse.ArgumentParser(
        description="Run the Dota 2 item analysis pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python run.py                    Run all steps (current patch)
  python run.py --version 7.50    Set patch version, then run all steps
  python run.py --from 4          Run from step 4
  python run.py --from 1 --to 3   Run steps 1 through 3""",
    )
    parser.add_argument("--version", help="patch version to set before running (e.g. 7.50)")
    parser.add_argument(
        "--from",
        dest="start",
        type=int,
        default=1,
        choices=range(1, 6),
        metavar="{1-5}",
        help="first step to run (default: 1)",
    )
    parser.add_argument(
        "--to",
        dest="end",
        type=int,
        default=5,
        choices=range(1, 6),
        metavar="{1-5}",
        help="last step to run (default: 5)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="verbose output (DEBUG level)")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="quiet output (WARNING level only)"
    )
    args = parser.parse_args()

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARNING
    logging.basicConfig(level=level, format="%(message)s")

    if args.version:
        from tools.make_latest import make_latest

        make_latest(args.version)
        logger.info("")

    for i in range(args.start - 1, args.end):
        mod = importlib.import_module(STEP_MODULES[i])
        mod.main()
        logger.info("")


if __name__ == "__main__":
    main()
