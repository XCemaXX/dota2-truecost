"""Items table HTML generator."""

from pathlib import Path
from typing import Any

from common.formatting import format_calc_str
from output.common import EFFICIENCY_THRESHOLD_PCT, SHARED_CSS, get_nav_html


def generate_items_table(items_data: list[dict[str, Any]], rules, output_file: Path):
    """Generate items_table.html - sortable table with expandable stat breakdown."""
    patch = rules.patch
    threshold = EFFICIENCY_THRESHOLD_PCT

    # Filter and categorize
    items = [i for i in items_data if i.get("real_cost", 0) > 0]
    overvalued = [i for i in items if i.get("difference_pct", 0) > threshold]
    undervalued = [i for i in items if i.get("difference_pct", 0) < -threshold]
    fair = [i for i in items if -threshold <= i.get("difference_pct", 0) <= threshold]

    # Average efficiency
    eff_values = [i.get("efficiency_pct", 100) for i in items if i.get("effective_cost", 0) > 0]
    avg_eff = sum(eff_values) / len(eff_values) if eff_values else 100

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Items - Dota 2 Item Analysis (Patch {patch})</title>
    <style>
{SHARED_CSS}
.expandable {{ cursor: pointer; }}
.expandable::before {{ content: '\\25B6 '; font-size: 0.7em; color: #c4c4c4; }}
.expandable.expanded::before {{ content: '\\25BC '; }}
.chart-link {{ font-size: 0.8em; text-decoration: none; opacity: 0.4; margin-left: 4px; }}
.chart-link:hover {{ opacity: 1; }}
.breakdown {{
    display: none;
    background: rgba(0, 0, 0, 0.3);
    padding: 10px 15px;
    margin: 5px 0;
    border-radius: 5px;
    font-size: 0.9em;
}}
.breakdown.visible {{ display: block; }}
.breakdown-item {{
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.breakdown-item:last-child {{ border-bottom: none; }}
.breakdown-stat {{ color: #aaa; }}
.breakdown-value {{ color: #5dade2; }}
.breakdown-calc {{ color: #c4c4c4; font-size: 0.9em; }}
.info-stat {{ opacity: 0.6; }}
.breakdown-value.info {{ color: #c4c4c4; font-style: italic; }}
.breakdown-calc.info {{ color: #666; font-style: italic; }}
.stat-group-header {{
    font-weight: bold;
    padding: 6px 0 4px 0;
    margin-top: 8px;
    border-bottom: 2px solid rgba(255,255,255,0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.stat-group-header:first-child {{ margin-top: 0; }}
.stat-group-header .group-name {{ color: #f4d03f; }}
.stat-group-header .group-value {{ color: #5dade2; font-weight: bold; }}
.stat-group-header .group-meta {{ color: #c4c4c4; font-size: 0.85em; margin-left: 8px; }}
.stat-group-header.active {{ background: rgba(52, 152, 219, 0.15); padding: 6px 8px; border-radius: 4px; }}
.stat-group-header.active .group-name {{ color: #3498db; }}
.stat-group-header.aura {{ background: rgba(241, 196, 15, 0.15); padding: 6px 8px; border-radius: 4px; }}
.stat-group-header.aura .group-name {{ color: #f1c40f; }}
.stat-group-header.ignored {{ opacity: 0.5; }}
.stat-group-header.ignored .group-name {{ color: #c4c4c4; }}
.stat-group-header.risk {{ background: rgba(231, 76, 60, 0.15); padding: 6px 8px; border-radius: 4px; }}
.stat-group-header.risk .group-name {{ color: #e74c3c; }}
.stat-group-stats {{ padding-left: 12px; }}
.filter-controls {{
    display: flex; gap: 10px; flex-wrap: wrap;
    align-items: center; margin-bottom: 15px;
}}
.filter-controls label {{ font-size: 0.9em; color: #aaa; }}
.filter-controls select, .filter-controls input {{
    background: #2d3436; color: #eee;
    border: 1px solid #444; padding: 6px 10px;
    border-radius: 4px;
}}
.unpriceable {{ color: #e74c3c; font-size: 0.85em; }}
.item-comment {{ color: #f0ad4e; font-size: 0.85em; font-style: italic; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{patch}: Item Effective Cost Analysis</h1>

        {get_nav_html('items_table.html')}

        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-value">{len(items)}</div>
                <div class="stat-label">Total Items</div>
            </div>
            <div class="stat-card overvalued">
                <div class="stat-value">{len(overvalued)}</div>
                <div class="stat-label">Overvalued</div>
            </div>
            <div class="stat-card fair">
                <div class="stat-value">{len(fair)}</div>
                <div class="stat-label">Fair Price</div>
            </div>
            <div class="stat-card undervalued">
                <div class="stat-value">{len(undervalued)}</div>
                <div class="stat-label">Undervalued</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_eff:.0f}%</div>
                <div class="stat-label">Avg Efficiency</div>
            </div>
        </div>

        <div class="filter-controls">
            <label>Category:</label>
            <select id="categoryFilter">
                <option value="all">All</option>
                <option value="overvalued">Overvalued</option>
                <option value="fair">Fair</option>
                <option value="undervalued">Undervalued</option>
            </select>
            <label>Search:</label>
            <input type="text" id="searchInput" placeholder="Item name...">
        </div>

        <div class="table-container">
            <table id="itemsTable">
                <thead>
                    <tr>
                        <th data-col="name">Item</th>
                        <th data-col="cost">Cost</th>
                        <th data-col="effective">Effective</th>
                        <th data-col="diff">Difference</th>
                        <th data-col="efficiency">Efficiency</th>
                        <th data-col="category">Category</th>
                        <th>Stats</th>
                    </tr>
                </thead>
                <tbody>
"""

    # Sort by difference (descending)
    sorted_items = sorted(items, key=lambda x: x.get("difference_pct", 0), reverse=True)

    for item in sorted_items:
        item_id = item.get("id", "")
        name = item.get("name", item_id)
        cost = item.get("real_cost", 0)
        effective = item.get("effective_cost", 0)
        diff = item.get("difference", 0)
        diff_pct = item.get("difference_pct", 0)
        eff_pct = item.get("efficiency_pct", 100)

        # Category
        if diff_pct > threshold:
            category = "overvalued"
            cat_class = "text-green"
        elif diff_pct < -threshold:
            category = "undervalued"
            cat_class = "text-red"
        else:
            category = "fair"
            cat_class = "text-yellow"

        # Stat breakdown - use stat_groups if available, else fall back to stat_breakdown
        stat_groups = item.get("stat_groups", [])
        unpriceable = item.get("unpriceable_stats", [])

        breakdown_html = ""
        stats_count = 0

        if stat_groups:
            # Hierarchical display with groups
            for group in stat_groups:
                group_name = group.get("group_name", "Unknown")
                group_type = group.get("group_type", "passive")
                group_total = group.get("total_value", 0)
                group_stats = group.get("stats", [])

                # Build group header with metadata
                group_meta = ""
                if group_type == "active":
                    cooldown = group.get("cooldown", "")
                    duration = group.get("duration", "")
                    if cooldown and duration:
                        group_meta = (
                            f'<span class="group-meta">CD: {cooldown}s / Dur: {duration}s</span>'
                        )
                    elif cooldown:
                        group_meta = f'<span class="group-meta">CD: {cooldown}s</span>'

                # Add group header
                breakdown_html += f"""<div class="stat-group-header {group_type}">
                    <span class="group-name">{group_name} ({group_type})</span>
                    <span><span class="group-value">{group_total:.0f}g</span>{group_meta}</span>
                </div>"""

                # Add stats within the group
                if group_stats:
                    breakdown_html += '<div class="stat-group-stats">'
                    for stat in group_stats:
                        stat_name = stat.get("display_name", stat.get("stat", ""))
                        total = stat.get("total_value", 0)
                        calc_str = stat.get("calc_str", "")
                        stat_type = stat.get("type", "")

                        if stat_type == "info":
                            # Info stat: show amount, no gold value, lighter styling
                            amount = stat.get("amount", "")
                            note = stat.get("note", "Info")
                            breakdown_html += f"""<div class="breakdown-item info-stat">
                                <span class="breakdown-stat">{stat_name}</span>
                                <span class="breakdown-value info">{amount}</span>
                                <span class="breakdown-calc info">[info]</span>
                            </div>"""
                        else:
                            # Regular priced stat
                            breakdown_html += f"""<div class="breakdown-item">
                                <span class="breakdown-stat">{stat_name}</span>
                                <span class="breakdown-value">{total:.0f}g</span>
                                <span class="breakdown-calc">{calc_str}</span>
                            </div>"""
                        stats_count += 1
                    breakdown_html += "</div>"
        else:
            # Fallback: flat display using stat_breakdown
            breakdown = item.get("stat_breakdown", [])
            for stat in breakdown:
                stat_name = stat.get("display_name", stat.get("stat", ""))
                total = stat.get("total_value", 0)
                calc_str = stat.get("calc_str", "")
                if not calc_str:
                    # Fallback if calc_str not present
                    amount = stat.get("amount", 0)
                    gold = stat.get("gold_per_point", 0)
                    calc_str = format_calc_str(amount, gold, stat.get("multiplier"))
                breakdown_html += f"""<div class="breakdown-item">
                    <span class="breakdown-stat">{stat_name}</span>
                    <span class="breakdown-value">{total:.0f}g</span>
                    <span class="breakdown-calc">{calc_str}</span>
                </div>"""
                stats_count += 1

        if unpriceable:
            unpriceable_names = ", ".join([s.get("stat", "") for s in unpriceable[:3]])
            if len(unpriceable) > 3:
                unpriceable_names += f" (+{len(unpriceable) - 3} more)"
            breakdown_html += f'<div class="unpriceable">Unpriceable: {unpriceable_names}</div>'

        # Show item comment from overrides
        item_comment = item.get("comment", "")
        if item_comment:
            breakdown_html += f'<div class="item-comment">{item_comment}</div>'

        # Stats count for display
        stats_str = f"{stats_count} stats"
        if unpriceable:
            stats_str += f" (+{len(unpriceable)} unknown)"

        html += f"""                    <tr data-category="{category}">
                        <td>
                            <div class="expandable" data-item="{item_id}"><strong>{name}</strong> <a href="interactive_chart.html?item={item_id}" class="chart-link" title="Show on chart">&#x1f4c8;</a></div>
                            <div class="breakdown" id="breakdown-{item_id}">{breakdown_html}</div>
                            <span class="text-muted">{item_id}</span>
                        </td>
                        <td>{cost}g</td>
                        <td>{effective:.0f}g</td>
                        <td class="{cat_class}">{diff:+.0f}g ({diff_pct:+.1f}%)</td>
                        <td class="{cat_class}">{eff_pct:.1f}%</td>
                        <td class="{cat_class}">{category.title()}</td>
                        <td class="text-muted">{stats_str}</td>
                    </tr>
"""

    html += """                </tbody>
            </table>
        </div>
    </div>

    <script>
    (function() {
        const table = document.getElementById('itemsTable');
        const headers = table.querySelectorAll('th[data-col]');
        const categoryFilter = document.getElementById('categoryFilter');
        const searchInput = document.getElementById('searchInput');
        let currentSort = { col: 'diff', desc: true };

        // Expand/collapse stat breakdown
        document.querySelectorAll('.expandable').forEach(el => {
            el.addEventListener('click', () => {
                const itemId = el.dataset.item;
                const breakdown = document.getElementById('breakdown-' + itemId);
                el.classList.toggle('expanded');
                breakdown.classList.toggle('visible');
            });
        });

        // Filtering
        function applyFilters() {
            const cat = categoryFilter.value;
            const search = searchInput.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');

            rows.forEach(row => {
                const rowCat = row.dataset.category;
                const name = row.querySelector('td').textContent.toLowerCase();
                const catMatch = cat === 'all' || rowCat === cat;
                const searchMatch = !search || name.includes(search);
                row.style.display = catMatch && searchMatch ? '' : 'none';
            });
        }

        categoryFilter.addEventListener('change', applyFilters);
        searchInput.addEventListener('input', applyFilters);

        // Sorting
        headers.forEach(th => {
            th.addEventListener('click', () => {
                const col = th.dataset.col;
                const desc = currentSort.col === col ? !currentSort.desc : true;
                currentSort = { col, desc };

                headers.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
                th.classList.add(desc ? 'sorted-desc' : 'sorted-asc');

                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));

                rows.sort((a, b) => {
                    const colIndex = Array.from(headers).indexOf(th);
                    let aVal = a.cells[colIndex].textContent.trim();
                    let bVal = b.cells[colIndex].textContent.trim();

                    // Numeric columns
                    if (['cost', 'effective', 'diff', 'efficiency'].includes(col)) {
                        const aNum = parseFloat(aVal.replace(/[^0-9.-]/g, '')) || 0;
                        const bNum = parseFloat(bVal.replace(/[^0-9.-]/g, '')) || 0;
                        return desc ? bNum - aNum : aNum - bNum;
                    }

                    return desc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
                });

                rows.forEach(row => tbody.appendChild(row));
            });
        });

        // Initial sort indicator
        headers.forEach(th => {
            if (th.dataset.col === 'diff') th.classList.add('sorted-desc');
        });
    })();
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Items table saved: {output_file}")
