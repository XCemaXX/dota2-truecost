"""
Version management for Dota 2 items data files.

Renames data/items.txt to versioned name, updates latest.txt pointer,
and sets patch version in axiom_rules.yaml.

Usage:
    cd src && source venv/bin/activate
    python -m tools.make_latest --version "7.40c"
"""

import argparse
import logging
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RULES_PATH = Path(__file__).resolve().parent.parent / "axioms" / "axiom_rules.yaml"


def make_latest(version: str):
    """Version current items data and update pointers."""
    versioned_name = f"items_{version}.txt"
    versioned_path = DATA_DIR / versioned_name
    items_path = DATA_DIR / "items.txt"

    # Rename items.txt → items_{version}.txt if needed
    if items_path.is_file() and not versioned_path.is_file():
        items_path.rename(versioned_path)
        logger.info("Renamed: data/items.txt → data/%s", versioned_name)
    elif versioned_path.is_file():
        logger.info("Already exists: data/%s", versioned_name)
    else:
        logger.error("ERROR: Neither data/items.txt nor data/%s found", versioned_name)
        sys.exit(1)

    # Write latest.txt
    latest_path = DATA_DIR / "latest.txt"
    latest_path.write_text(versioned_name + "\n", encoding="utf-8")
    logger.info("Updated: data/latest.txt → %s", versioned_name)

    # Update patch field in axiom_rules.yaml (restrict to first 5 lines)
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    patched = False
    for i, line in enumerate(lines[:5]):
        new_line = re.sub(r"^(patch:\s*).*$", f'patch: "{version}"', line)
        if new_line != line:
            lines[i] = new_line
            patched = True
            break

    if patched:
        with open(RULES_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logger.info('Updated: axiom_rules.yaml patch → "%s"', version)
    else:
        logger.info('axiom_rules.yaml patch already set to "%s"', version)

    logger.info("\nDone! Run the pipeline: 01 → 02 → 03 → 04 → 05")


def main():
    parser = argparse.ArgumentParser(description="Version management for items data")
    parser.add_argument("--version", required=True, help='Patch version (e.g. "7.40c")')
    args = parser.parse_args()
    make_latest(args.version)


if __name__ == "__main__":
    main()
