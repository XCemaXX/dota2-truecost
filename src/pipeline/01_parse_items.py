"""
Parser for items.txt (Valve KeyValue format) to extract item data.

This script:
1. Parses items.txt into structured format
2. Filters items (excludes recipes, consumables, neutral items)
3. Extracts cost and stats for each item
4. Exports to JSON for further processing
"""

import json
import logging
import sys
from pathlib import Path

# Disable .pyc cache to avoid stale bytecode issues after refactoring
sys.dont_write_bytecode = True

from typing import Any

logger = logging.getLogger(__name__)

from axioms.loader import get_items_path, is_item_excluded, load_axiom_rules


def format_item_name(item_id: str, rules=None) -> str:
    """Convert item_id to human-readable name.

    Checks item_overrides display_name first, falls back to auto-formatting.
    """
    if rules and item_id in rules.item_overrides:
        display_name = rules.item_overrides[item_id].display_name
        if display_name:
            return str(display_name)
    return item_id.replace("item_", "").replace("_", " ").title()


# Load axiom rules
RULES = load_axiom_rules()

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ITEMS_PATH = get_items_path()
OUTPUT_PATH = PROJECT_ROOT / "output"


class VDFParser:
    """Parser for Valve Data Format (VDF) / KeyValue format."""

    def __init__(self, content: str):
        self.content = content
        self.pos = 0
        self.length = len(content)

    def skip_whitespace_and_comments(self):
        """Skip whitespace and comments."""
        while self.pos < self.length:
            # Skip whitespace characters
            while self.pos < self.length and self.content[self.pos] in " \t\n\r":
                self.pos += 1

            # Check for comments
            if self.pos < self.length - 1 and self.content[self.pos : self.pos + 2] == "//":
                # Skip to end of line
                while self.pos < self.length and self.content[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def parse_string(self) -> str:
        """Parse a quoted string."""
        if self.content[self.pos] != '"':
            raise ValueError(f"Expected '\"' at position {self.pos}")

        self.pos += 1  # Skip opening quote
        start = self.pos

        while self.pos < self.length and self.content[self.pos] != '"':
            if self.content[self.pos] == "\\":
                # Skip escape sequence with bounds check
                self.pos += 1
                if self.pos < self.length:
                    self.pos += 1
            else:
                self.pos += 1

        result = self.content[start : self.pos]
        if self.pos < self.length:
            self.pos += 1  # Skip closing quote
        return result

    def parse_value(self) -> Any:
        """Parse a value (string or block)."""
        self.skip_whitespace_and_comments()

        if self.pos >= self.length:
            return None

        if self.content[self.pos] == '"':
            return self.parse_string()
        elif self.content[self.pos] == "{":
            return self.parse_block()
        else:
            raise ValueError(
                f"Unexpected character '{self.content[self.pos]}' at position {self.pos}"
            )

    def parse_block(self) -> dict[str, Any]:
        """Parse a block { ... }."""
        if self.content[self.pos] != "{":
            raise ValueError(f"Expected '{{' at position {self.pos}")

        self.pos += 1  # Skip '{'
        result = {}

        while True:
            self.skip_whitespace_and_comments()

            if self.pos >= self.length:
                break

            if self.content[self.pos] == "}":
                self.pos += 1
                break

            if self.content[self.pos] == '"':
                key = self.parse_string()
                value = self.parse_value()
                result[key] = value
            else:
                # Unexpected character, skip
                self.pos += 1

        return result

    def parse(self) -> dict[str, Any]:
        """Parse the entire document."""
        self.skip_whitespace_and_comments()

        if self.pos < self.length and self.content[self.pos] == '"':
            root_key = self.parse_string()
            root_value = self.parse_value()
            return {root_key: root_value}

        return {}


def parse_items_file(filepath: str) -> dict[str, Any]:
    """Parse items.txt and return dictionary of all items."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    parser = VDFParser(content)
    data = parser.parse()

    return dict(data.get("DOTAAbilities", {}))


def extract_item_stats(item_data: dict) -> dict[str, float]:
    """
    Extract item stats from AbilityValues.

    Handles space-separated values for upgradeable items (e.g., Dagon).
    Uses ItemBaseLevel to select the correct value from the list.

    Args:
        item_data: Item data dictionary

    Returns:
        Dictionary {stat_name: value}
    """
    stats = {}
    ability_values = item_data.get("AbilityValues", {})

    # Get base level for upgradeable items (1-indexed)
    # e.g., item_dagon has ItemBaseLevel=1, item_dagon_2 has ItemBaseLevel=2
    base_level = int(item_data.get("ItemBaseLevel", 1))
    level_index = base_level - 1  # Convert to 0-indexed

    for key, value in ability_values.items():
        # Handle nested structures with "value" key
        if isinstance(value, dict):
            actual_value = value.get("value")
            if actual_value is not None:
                parsed = _parse_stat_value(actual_value, level_index)
                if parsed is not None:
                    stats[key] = parsed
        else:
            # Simple value (may be space-separated for upgradeable items)
            parsed = _parse_stat_value(value, level_index)
            if parsed is not None:
                stats[key] = parsed

    return stats


def _parse_stat_value(value: str, level_index: int) -> float | None:
    """
    Parse a stat value, handling space-separated lists for upgradeable items.

    Args:
        value: String value like "7" or "7 9 11 13 15"
        level_index: 0-indexed level for upgradeable items

    Returns:
        Parsed float value or None if parsing fails
    """
    if not isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    # Check if it's a space-separated list
    parts = value.split()
    if len(parts) > 1:
        # Multiple values - select by level index
        if level_index < len(parts):
            try:
                return float(parts[level_index])
            except (ValueError, TypeError):
                return None
        else:
            # Level index out of range, use last value
            try:
                return float(parts[-1])
            except (ValueError, TypeError):
                return None
    else:
        # Single value
        try:
            return float(value)
        except (ValueError, TypeError):
            return None


def should_exclude_item(item_name: str, item_data: dict) -> tuple[bool, str]:
    """
    Check if item should be excluded from analysis.

    Returns:
        (should_exclude, reason)
    """
    # Use loader's is_item_excluded function with rules
    return is_item_excluded(item_name, item_data, RULES)


def process_items(
    raw_data: dict,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Process raw data and return filtered items.

    Returns:
        Tuple of (items, excluded_items, questions)
    """
    items = []
    excluded_items = []
    questions = []  # Questions for further analysis

    for item_name, item_data in raw_data.items():
        if not isinstance(item_data, dict):
            continue

        # Skip service entries
        if item_name in ["Version"]:
            continue

        # Check for exclusion
        should_exclude, reason = should_exclude_item(item_name, item_data)
        if should_exclude:
            excluded_items.append({"name": item_name, "reason": reason})
            continue

        # Extract data
        cost = int(item_data.get("ItemCost", 0))
        stats = extract_item_stats(item_data)

        # Determine quality/category
        quality = item_data.get("ItemQuality", "unknown")
        shop_tags = item_data.get("ItemShopTags", "")

        # TODO: parse ItemRequirements for recipe components

        # Flag: item drops to enemies on death (ItemKillable=0)
        # NOT EVALUATED: loss risk not factored into effective cost
        drops_on_death = item_data.get("ItemKillable") == "0"

        item_record = {
            "id": item_name,
            "name": format_item_name(item_name, RULES),
            "cost": cost,
            "quality": quality,
            "shop_tags": shop_tags,
            "stats": stats,
            "drops_on_death": drops_on_death,  # NOT EVALUATED: loss risk not factored
            "raw_data": item_data,  # For debugging
        }

        # Analyze stats for unknown ones
        unknown_stats = []
        for stat_name in stats.keys():
            if not stat_name.startswith("bonus_") and stat_name not in [
                "value",
                "duration",
                "radius",
                "damage",
                "cooldown",
                "mana_cost",
            ]:
                unknown_stats.append(stat_name)

        if unknown_stats:
            questions.append(
                {
                    "item": item_name,
                    "unknown_stats": unknown_stats,
                    "note": "Need to determine how to evaluate these stats",
                }
            )

        items.append(item_record)

    return items, excluded_items, questions


def main():
    logger.info("=" * 70)
    logger.info("PARSING items.txt (Patch %s)", RULES.patch)
    logger.info("=" * 70)

    # Create output directory
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    # Parse file
    logger.info("\nParsing items.txt...")
    raw_data = parse_items_file(ITEMS_PATH)
    logger.info("Found entries: %d", len(raw_data))

    # Process items
    logger.info("\nFiltering and processing...")
    items, excluded, questions = process_items(raw_data)

    logger.info("\nResults:")
    logger.info("  Items included: %d", len(items))
    logger.info("  Items excluded: %d", len(excluded))
    logger.info("  Questions for analysis: %d", len(questions))

    # Save results
    items_output = OUTPUT_PATH / "items_parsed.json"
    with open(items_output, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    logger.info("\nItems saved to: %s", items_output)

    # Print first few items for verification
    logger.debug("\n" + "=" * 70)
    logger.debug("SAMPLE ITEMS")
    logger.debug("=" * 70)

    for item in items[:10]:
        logger.debug("\n%s (cost: %dg)", item["name"], item["cost"])
        logger.debug("  ID: %s", item["id"])
        logger.debug("  Quality: %s", item["quality"])
        if item["stats"]:
            logger.debug("  Stats:")
            for stat, val in item["stats"].items():
                logger.debug("    - %s: %s", stat, val)

    # Print questions
    if questions:
        logger.debug("\n" + "=" * 70)
        logger.debug("QUESTIONS FOR ANALYSIS (first 10)")
        logger.debug("=" * 70)
        for q in questions[:10]:
            logger.debug("\n%s:", q["item"])
            logger.debug("  Unknown stats: %s", q["unknown_stats"])


if __name__ == "__main__":
    main()
