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
.compact-table th, .compact-table td {{ padding: 4px 10px; }}
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
.category-badge.debuff {{ background: rgba(192, 57, 43, 0.2); color: #e67e22; }}
.category-badge.movement {{ background: rgba(52, 73, 94, 0.2); color: #85c1e9; }}
.category-badge.disable {{ background: rgba(142, 68, 173, 0.2); color: #bb8fce; }}
.depends {{ font-size: 0.8em; color: #c4c4c4; }}
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

        <h2 style="color: #5dade2; margin: 20px 0 10px;">Constants</h2>
        <div class="table-container">
            <table class="compact-table" style="font-size: 0.9em;">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Key</th>
                        <th>Value</th>
                        <th>Comment</th>
                    </tr>
                </thead>
                <tbody>
"""

    settings = axioms_data.get("settings", {})
    for key, s in settings.items():
        s_name = s.get("name", key) if isinstance(s, dict) else key
        s_value = s.get("value", s) if isinstance(s, dict) else s
        s_comment = s.get("comment", "") if isinstance(s, dict) else ""
        s_comment = s_comment.strip().replace("\n", "<br>")
        html += f"""                    <tr>
                        <td><strong>{s_name}</strong></td>
                        <td class="text-muted">{key}</td>
                        <td class="text-green">{s_value}</td>
                        <td class="text-muted">{s_comment}</td>
                    </tr>
"""

    html += """                </tbody>
            </table>
        </div>

        <h2 style="color: #5dade2; margin: 20px 0 10px;">Axioms</h2>
        <div class="table-container">
            <table id="axiomsTable">
                <thead>
                    <tr>
                        <th data-col="name">Name</th>
                        <th data-col="gold">Gold/Point</th>
                        <th data-col="method">Method</th>
                        <th data-col="reference">Reference Item</th>
                        <th data-col="category">Category</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
"""

    # Sort axioms: reference_item first, then by category and name
    def axiom_sort_key(item):
        ax = item[1]
        has_ref = ax.get("calculation", {}).get("reference_item") not in (None, "", "-")
        return (0 if has_ref else 1, ax.get("category", "z"), item[0])

    sorted_axioms = sorted(axioms.items(), key=axiom_sort_key)

    for name, ax in sorted_axioms:
        display_name = ax.get("display_name", name)
        gold = ax.get("gold_per_point", 0)
        category = ax.get("category", "other")
        comment = ax.get("comment", "").strip().replace("\n", "<br>")
        calc = ax.get("calculation", {})
        method = calc.get("method", "unknown")
        ref_item = calc.get("reference_item", "-")
        formula = calc.get("formula", "")
        formula_symbolic = calc.get("formula_symbolic", "")

        # Format gold value
        if isinstance(gold, float):
            gold_str = f"{gold:.2f}g" if gold != int(gold) else f"{int(gold)}g"
        else:
            gold_str = f"{gold}g"

        # Reference item display
        if ref_item and ref_item != "-":
            ref_display = ref_item.replace("item_", "").replace("_", " ").title()
        else:
            ref_display = "-"

        # Details (comment + formula + depends)
        details = f"<div>{comment}</div>" if comment else ""
        if formula_symbolic:
            details += f'<div class="depends">{formula_symbolic}</div>'
        elif formula:
            details += f'<div class="depends">{formula}</div>'

        html += f"""                    <tr>
                        <td><strong>{display_name}</strong><br><span class="text-muted">{name}</span></td>
                        <td class="text-green">{gold_str}</td>
                        <td>{method}</td>
                        <td>{ref_display}</td>
                        <td><span class="category-badge {category}">{category}</span></td>
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
