"""CSV export generator."""

import csv
from pathlib import Path
from typing import Any


def generate_csv(items_data: list[dict[str, Any]], output_file: Path):
    """Generate CSV export."""
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "ID",
                "Name",
                "Real Cost (gold)",
                "Effective Cost (gold)",
                "Difference (gold)",
                "Difference (%)",
                "Efficiency (%)",
                "Category",
                "Stats Count",
                "Unpriceable Stats",
                "Drops On Death",
            ]
        )

        for item in items_data:
            diff_pct = item.get("difference_pct", 0)
            if diff_pct > 10:
                category = "Overvalued"
            elif diff_pct < -10:
                category = "Undervalued"
            else:
                category = "Fair"

            unpriceable = item.get("unpriceable_stats", [])
            unpriceable_str = "; ".join([s.get("stat", "") for s in unpriceable])

            writer.writerow(
                [
                    item.get("id", ""),
                    item.get("name", ""),
                    item.get("real_cost", 0),
                    round(item.get("effective_cost", 0), 2),
                    round(item.get("difference", 0), 2),
                    round(item.get("difference_pct", 0), 2),
                    round(item.get("efficiency_pct", 0), 2),
                    category,
                    len(item.get("stat_breakdown", [])),
                    unpriceable_str,
                    "Yes" if item.get("drops_on_death", False) else "",
                ]
            )

    print(f"CSV saved: {output_file}")
