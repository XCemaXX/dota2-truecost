"""
Generate output files for Phase 4 of the V2 architecture.

Thin orchestrator that delegates to focused generator modules in src/output/.

Outputs:
- output/axioms_table.html - Table of all axioms with sorting
- output/items_table.html - Table of items with expandable stat breakdown
- output/interactive_chart.html - Scatter plot with improved tooltips
- output/item_costs.csv - CSV export
- output/price_comparison.png - Static scatter plot (optional)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Disable .pyc cache
sys.dont_write_bytecode = True

logger = logging.getLogger(__name__)

from axioms.loader import load_axiom_rules
from output.axioms_table import generate_axioms_table
from output.csv_export import generate_csv
from output.interactive_chart import generate_interactive_chart
from output.items_table import generate_items_table
from output.png_chart import generate_png_chart

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output"
AXIOMS_FILE = OUTPUT_PATH / "calculated_axioms.json"
COSTS_FILE = OUTPUT_PATH / "effective_costs.json"


def load_axioms_data() -> dict[str, Any]:
    """Load calculated axioms data."""
    with open(AXIOMS_FILE, "r", encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def load_items_data() -> list[dict[str, Any]]:
    """Load effective costs data."""
    with open(COSTS_FILE, "r", encoding="utf-8") as f:
        result: list[dict[str, Any]] = json.load(f)
        return result


def main():
    logger.info("=" * 70)
    logger.info("GENERATING OUTPUT FILES (Phase 4)")
    logger.info("=" * 70)

    # Load rules
    logger.info("\nLoading axiom rules...")
    rules = load_axiom_rules()
    logger.info("  Patch: %s", rules.patch)

    # Load data
    logger.info("\nLoading data...")
    axioms_data = load_axioms_data()
    items_data = load_items_data()
    logger.info("  Axioms: %d", len(axioms_data.get("axioms", {})))
    logger.info("  Items: %d", len(items_data))

    # Generate outputs
    logger.info("\nGenerating outputs...")

    # 1. Axioms table
    axioms_file = OUTPUT_PATH / "axioms_table.html"
    generate_axioms_table(axioms_data, rules, axioms_file)

    # 2. Items table
    items_file = OUTPUT_PATH / "items_table.html"
    generate_items_table(items_data, rules, items_file)

    # 3. Interactive chart
    chart_file = OUTPUT_PATH / "interactive_chart.html"
    generate_interactive_chart(items_data, axioms_data, rules, chart_file)

    # 4. CSV
    csv_file = OUTPUT_PATH / "item_costs.csv"
    generate_csv(items_data, csv_file)

    # 5. PNG chart (optional)
    png_file = OUTPUT_PATH / "price_comparison.png"
    generate_png_chart(items_data, rules, png_file, OUTPUT_PATH)

    logger.info("\n" + "=" * 70)
    logger.info("DONE!")
    logger.info("=" * 70)
    logger.info("\nOutput files in: %s", OUTPUT_PATH)
    logger.info("  - axioms_table.html")
    logger.info("  - items_table.html")
    logger.info("  - interactive_chart.html")
    logger.info("  - item_costs.csv")
    logger.info("  - price_comparison.png")


if __name__ == "__main__":
    main()
