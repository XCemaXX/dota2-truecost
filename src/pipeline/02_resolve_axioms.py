"""
Pipeline Step 02: Resolve Axioms

Loads axiom_rules.yaml and items_parsed.json, calculates all axiom
gold_per_point values, and outputs calculated_axioms.json.

Usage:
    cd src && source venv/bin/activate
    python -m pipeline.02_resolve_axioms

Output:
    output/calculated_axioms.json
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from axioms.calculator import resolve_all_axioms, resolved_to_dict
from axioms.loader import load_axiom_rules

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output"


def main():
    """Main entry point for axiom resolution."""
    items_parsed_path = OUTPUT_PATH / "items_parsed.json"
    output_path = OUTPUT_PATH / "calculated_axioms.json"

    logger.info("=" * 60)
    logger.info("AXIOM RESOLVER - Step 02")
    logger.info("=" * 60)

    # Load axiom rules
    logger.info("\n[1/4] Loading axiom rules...")
    try:
        rules = load_axiom_rules()
        logger.info("  Loaded %d axioms", len(rules.axioms))
        logger.info("  Patch version: %s", rules.patch)
        logger.info(
            "  Settings: max_iterations=%s",
            rules.settings.get("max_resolution_iterations"),
        )
    except Exception as e:
        logger.error("  ERROR: Failed to load axiom rules: %s", e)
        sys.exit(1)

    # Load items_parsed.json
    logger.info("\n[2/4] Loading items_parsed.json...")
    if not items_parsed_path.is_file():
        logger.error("  ERROR: File not found: %s", items_parsed_path)
        logger.error("  Run 01_parse_items.py first!")
        sys.exit(1)

    with open(items_parsed_path, "r", encoding="utf-8") as f:
        items_data = json.load(f)

    # Convert list to dict by item id for easier lookup
    if isinstance(items_data, list):
        items_parsed = {item["id"]: item for item in items_data}
    else:
        items_parsed = items_data.get("items", items_data)

    logger.info("  Loaded %d items", len(items_parsed))

    # Resolve axioms
    logger.info("\n[3/4] Resolving axioms...")
    max_iterations = rules.settings.get("max_resolution_iterations", 10)
    resolved, warnings = resolve_all_axioms(rules, items_parsed, max_iterations)

    # Count by method
    methods = {}
    for axiom in resolved.values():
        method = axiom.calculation.method
        methods[method] = methods.get(method, 0) + 1

    logger.info("  Resolved %d axioms:", len(resolved))
    for method, count in sorted(methods.items()):
        logger.info("    - %s: %d", method, count)

    if warnings:
        logger.warning("\n  Warnings (%d):", len(warnings))
        for w in warnings[:10]:
            logger.warning("    - %s: %s", w["axiom"], w["issue"])
        if len(warnings) > 10:
            logger.warning("    ... and %d more", len(warnings) - 10)

    # Write output
    logger.info("\n[4/4] Writing calculated_axioms.json...")
    output = {
        "version": rules.version,
        "patch": rules.patch,
        "generated_at": datetime.now().isoformat(),
        "total_axioms": len(resolved),
        "axioms": resolved_to_dict(resolved),
        "warnings": warnings,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("  Output: %s", output_path)

    # Summary
    logger.debug("\n" + "=" * 60)
    logger.debug("SUMMARY")
    logger.debug("=" * 60)

    # Show some sample values
    logger.debug("\nSample resolved values:")
    samples = [
        "bonus_strength",
        "bonus_health",
        "bonus_damage",
        "bonus_attack_speed",
        "hp_regen_amp",
        "spell_amp",
        "bonus_cooldown",
    ]
    for name in samples:
        if name in resolved:
            a = resolved[name]
            method_info = f"({a.calculation.method})"
            if a.calculation.reference_item:
                method_info = f"(from {a.calculation.reference_item})"
            logger.debug(
                "  %s: %.2f gold/point %s",
                a.display_name or name,
                a.gold_per_point,
                method_info,
            )

    # Check for issues
    errors = [a for a in resolved.values() if a.status == "error"]
    unknowns = [a for a in resolved.values() if a.status == "unknown"]

    if errors:
        logger.warning("\n%d axioms with errors!", len(errors))
        for a in errors[:5]:
            logger.warning("  - %s: %s", a.name, a.warning)

    if unknowns:
        logger.warning("\n%d axioms with unknown status (gold_per_point may be 0)", len(unknowns))

    logger.info("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
