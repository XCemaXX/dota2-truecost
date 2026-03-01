"""Axioms table HTML generator."""

from pathlib import Path
from typing import Any

from output.common import EFFICIENCY_THRESHOLD_PCT, SHARED_CSS, get_nav_html


def generate_axioms_table(axioms_data: dict[str, Any], rules, output_file: Path):
    """Generate axioms_table.html - sortable table of all axioms."""
    patch = axioms_data.get("patch", rules.patch)
    axioms = axioms_data.get("axioms", {})
    threshold = EFFICIENCY_THRESHOLD_PCT

    # Count by category
    categories: dict[str, int] = {}
    for ax in axioms.values():
        cat = ax.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axioms - Dota 2 Item Analysis (Patch {patch})</title>
    <style>
{SHARED_CSS}
.category-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.8em;
    background: rgba(93, 173, 226, 0.2);
    color: #5dade2;
}}
.category-badge.attributes {{ background: rgba(46, 204, 113, 0.2); color: #27a95d; }}
.category-badge.offense {{ background: rgba(231, 76, 60, 0.2); color: #e74c3c; }}
.category-badge.defense {{ background: rgba(52, 152, 219, 0.2); color: #3498db; }}
.category-badge.sustain {{ background: rgba(155, 89, 182, 0.2); color: #9b59b6; }}
.category-badge.aura {{ background: rgba(241, 196, 15, 0.2); color: #f1c40f; }}
.category-badge.utility {{ background: rgba(26, 188, 156, 0.2); color: #1abc9c; }}
.status-active {{ color: #27a95d; }}
.status-unknown {{ color: #e74c3c; }}
.depends {{ font-size: 0.8em; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{patch}: Axiom Definitions</h1>

        {get_nav_html('axioms_table.html')}

        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-value">{len(axioms)}</div>
                <div class="stat-label">Total Axioms</div>
            </div>
"""

    # Add category cards
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:5]:
        html += f"""            <div class="stat-card">
                <div class="stat-value">{count}</div>
                <div class="stat-label">{cat.title()}</div>
            </div>
"""

    html += """        </div>

        <div class="table-container">
            <table id="axiomsTable">
                <thead>
                    <tr>
                        <th data-col="name">Name</th>
                        <th data-col="gold">Gold/Point</th>
                        <th data-col="method">Method</th>
                        <th data-col="reference">Reference Item</th>
                        <th data-col="category">Category</th>
                        <th data-col="status">Status</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
"""

    # Sort axioms by category then name
    sorted_axioms = sorted(axioms.items(), key=lambda x: (x[1].get("category", "z"), x[0]))

    for name, ax in sorted_axioms:
        display_name = ax.get("display_name", name)
        gold = ax.get("gold_per_point", 0)
        category = ax.get("category", "other")
        status = ax.get("status", "active")
        calc = ax.get("calculation", {})
        method = calc.get("method", "unknown")
        ref_item = calc.get("reference_item", "-")
        formula = calc.get("formula", "")
        depends = ax.get("depends_on", [])

        # Format gold value
        if isinstance(gold, float):
            gold_str = f"{gold:.2f}g" if gold != int(gold) else f"{int(gold)}g"
        else:
            gold_str = f"{gold}g"

        # Status class
        status_class = "status-active" if status == "active" else "status-unknown"

        # Reference item display
        if ref_item and ref_item != "-":
            ref_display = ref_item.replace("item_", "").replace("_", " ").title()
        else:
            ref_display = "-"

        # Details (formula + depends)
        details = formula if formula else ""
        if depends:
            depends_str = ", ".join(depends)
            details += (
                f'<div class="depends">Depends: {depends_str}</div>'
                if details
                else f'<span class="depends">Depends: {depends_str}</span>'
            )

        html += f"""                    <tr>
                        <td><strong>{display_name}</strong><br><span class="text-muted">{name}</span></td>
                        <td class="text-green">{gold_str}</td>
                        <td>{method}</td>
                        <td>{ref_display}</td>
                        <td><span class="category-badge {category}">{category}</span></td>
                        <td class="{status_class}">{status}</td>
                        <td class="text-muted">{details}</td>
                    </tr>
"""

    html += """                </tbody>
            </table>
        </div>
    </div>

    <script>
    (function() {
        const table = document.getElementById('axiomsTable');
        const headers = table.querySelectorAll('th[data-col]');
        let currentSort = { col: null, desc: false };

        headers.forEach(th => {
            th.addEventListener('click', () => {
                const col = th.dataset.col;
                const desc = currentSort.col === col ? !currentSort.desc : false;
                currentSort = { col, desc };

                // Update header classes
                headers.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
                th.classList.add(desc ? 'sorted-desc' : 'sorted-asc');

                // Sort rows
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));

                rows.sort((a, b) => {
                    const colIndex = Array.from(headers).indexOf(th);
                    const aVal = a.cells[colIndex].textContent.trim().toLowerCase();
                    const bVal = b.cells[colIndex].textContent.trim().toLowerCase();

                    // Try numeric sort for gold column
                    if (col === 'gold') {
                        const aNum = parseFloat(aVal.replace(/[^0-9.-]/g, '')) || 0;
                        const bNum = parseFloat(bVal.replace(/[^0-9.-]/g, '')) || 0;
                        return desc ? bNum - aNum : aNum - bNum;
                    }

                    return desc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                });

                rows.forEach(row => tbody.appendChild(row));
            });
        });
    })();
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Axioms table saved: {output_file}")
