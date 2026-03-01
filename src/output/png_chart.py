"""Static PNG scatter plot generator."""

import json
from pathlib import Path
from typing import Any

from output.common import EFFICIENCY_THRESHOLD_PCT


def generate_png_chart(
    items_data: list[dict[str, Any]], rules, output_file: Path, output_path: Path
):
    """Generate static PNG scatter plot."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.lines import Line2D
    except ImportError:
        print("Matplotlib not available, skipping PNG chart")
        return

    threshold = EFFICIENCY_THRESHOLD_PCT
    patch = rules.patch

    # Filter items
    items = [r for r in items_data if r.get("effective_cost", 0) > 0 and r.get("real_cost", 0) > 0]

    if not items:
        print("No data for chart")
        return

    real_costs = [r["real_cost"] for r in items]
    effective_costs = [r["effective_cost"] for r in items]

    # Create chart
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 10))

    MAX_X = 7500
    MAX_Y = 10000

    # Determine reference items from axioms
    axioms_file = output_path / "calculated_axioms.json"
    reference_items = set()
    if axioms_file.exists():
        with open(axioms_file, "r") as f:
            axioms_data = json.load(f)
        if "axioms" in axioms_data:
            for axiom_info in axioms_data["axioms"].values():
                calc = axiom_info.get("calculation", {})
                ref_item = calc.get("reference_item")
                if ref_item:
                    reference_items.add(ref_item)

    # Categorize and color items
    colors = []
    categories = []
    for r in items:
        item_id = r.get("id", "")
        if item_id in reference_items:
            colors.append("#f39c12")  # orange — reference
            categories.append("reference")
        elif r.get("ability_not_evaluated", False):
            colors.append("#e74c3c")  # red — ability not evaluated
            categories.append("unevaluated")
        else:
            colors.append("#86cef3")  # blue — regular
            categories.append("normal")

    ax.scatter(real_costs, effective_costs, c=colors, alpha=0.6, s=50)

    # y=x line
    ax.plot([0, MAX_X], [0, MAX_X], "w--", alpha=0.5, label="y = x (fair price)")

    ax.set_xlim(0, MAX_X)
    ax.set_ylim(0, MAX_Y)

    # Labels for outliers
    sorted_items = sorted(
        enumerate(items), key=lambda x: abs(x[1].get("difference_pct", 0)), reverse=True
    )
    labeled: list[tuple[float, float]] = []
    for i, item in sorted_items[:15]:
        if abs(item.get("difference_pct", 0)) > 40 or item["real_cost"] > 4000:
            x, y = real_costs[i], effective_costs[i]
            too_close = any(abs(x - lx) < 400 and abs(y - ly) < 400 for lx, ly in labeled)
            if not too_close:
                xytext = (5, 8) if item.get("difference_pct", 0) > 0 else (5, -12)
                ax.annotate(
                    item["name"],
                    (x, y),
                    fontsize=7,
                    alpha=0.85,
                    color="#ffffff",
                    xytext=xytext,
                    textcoords="offset points",
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        facecolor="#2d3436",
                        alpha=0.7,
                        edgecolor="none",
                    ),
                )
                labeled.append((x, y))

    ax.set_xlabel("Real Cost (gold)", fontsize=12)
    ax.set_ylabel("Effective Cost (gold)", fontsize=12)
    ax.set_title(f"Dota 2 Items: Real vs Effective Cost (Patch {patch})", fontsize=14)

    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#f39c12",
            markersize=10,
            label="Reference item (axiom base)",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#e74c3c",
            markersize=10,
            label="Ability not evaluated",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#86cef3",
            markersize=10,
            label="Evaluated item",
        ),
    ]
    ax.legend(handles=legend_elements, loc="lower right")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, facecolor="#1a1a2e")
    plt.close()

    print(f"PNG chart saved: {output_file}")
