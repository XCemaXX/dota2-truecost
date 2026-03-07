"""Interactive scatter chart HTML generator."""

import json
from pathlib import Path
from typing import Any

from common.formatting import format_calc_str
from output.common import EFFICIENCY_THRESHOLD_PCT, SHARED_CSS, get_nav_html


def generate_interactive_chart(
    items_data: list[dict[str, Any]], axioms_data: dict[str, Any], rules, output_file: Path
):
    """Generate interactive_chart.html - scatter plot with improved tooltips."""
    patch = rules.patch
    threshold = EFFICIENCY_THRESHOLD_PCT

    # Build reference items set from axioms data
    reference_items = set()
    if axioms_data and "axioms" in axioms_data:
        for axiom_info in axioms_data["axioms"].values():
            calc = axiom_info.get("calculation", {})
            ref_item = calc.get("reference_item")
            if ref_item:
                reference_items.add(ref_item)

    # Filter items with valid costs
    items = [i for i in items_data if i.get("effective_cost", 0) > 0 and i.get("real_cost", 0) > 0]

    # Prepare chart data
    chart_data = []
    for item in items:
        item_id = item.get("id", "")

        # Detect category: reference > unevaluated_ability > normal
        if item_id in reference_items:
            category = "reference"
        elif item.get("ability_not_evaluated", False):
            category = "unevaluated_ability"
        else:
            category = "normal"

        # Estimated ability value (only for unevaluated, only if positive)
        estimated_ability_value = None
        if category == "unevaluated_ability":
            gap = item.get("real_cost", 0) - item.get("effective_cost", 0)
            if gap > 0:
                estimated_ability_value = round(gap, 0)

        # Build chart item with common fields
        unpriceable = item.get("unpriceable_stats", [])
        chart_item = {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "real_cost": item.get("real_cost", 0),
            "effective_cost": round(item.get("effective_cost", 0), 0),
            "difference": round(item.get("difference", 0), 0),
            "difference_pct": round(item.get("difference_pct", 0), 1),
            "efficiency_pct": round(item.get("efficiency_pct", 0), 1),
            "category": category,
            "unpriceable_count": len(unpriceable),
        }
        if item.get("comment"):
            chart_item["comment"] = item["comment"]
        if estimated_ability_value is not None:
            chart_item["estimated_ability_value"] = estimated_ability_value

        # Add stat breakdown - use stat_groups if available
        stat_groups = item.get("stat_groups", [])
        if stat_groups:
            # Use hierarchical groups
            groups_data = []
            for group in stat_groups:
                group_name = group.get("group_name", "Unknown")
                group_type = group.get("group_type", "passive")
                group_total = round(group.get("total_value", 0), 0)
                group_stats = group.get("stats", [])

                # Build group metadata
                group_meta = ""
                if group_type == "active":
                    cooldown = group.get("cooldown", "")
                    duration = group.get("duration", "")
                    if cooldown and duration:
                        group_meta = f"CD: {cooldown}s / Dur: {duration}s"
                    elif cooldown:
                        group_meta = f"CD: {cooldown}s"

                # Convert stats to simple format (limit to prevent tooltip overflow)
                stats_list = []
                for s in group_stats[:8]:  # Increase limit to accommodate info stats
                    stat_type = s.get("type", "")
                    if stat_type == "info":
                        stats_list.append(
                            {
                                "name": s.get("display_name", s.get("stat", "")),
                                "total": 0,
                                "calc_str": f"{s.get('amount', '')} [info]",
                                "type": "info",
                            }
                        )
                    else:
                        stats_list.append(
                            {
                                "name": s.get("display_name", s.get("stat", "")),
                                "total": round(s.get("total_value", 0), 0),
                                "calc_str": s.get("calc_str", ""),
                            }
                        )

                groups_data.append(
                    {
                        "group_name": group_name,
                        "group_type": group_type,
                        "group_total": group_total,
                        "group_meta": group_meta,
                        "stats": stats_list,
                    }
                )

            chart_item["stat_groups"] = groups_data
        else:
            # Fallback: use flat stat_breakdown
            breakdown = item.get("stat_breakdown", [])
            stat_lines = []
            for s in breakdown[:8]:  # Limit to 8 stats
                display_name = s.get("display_name", s.get("stat", ""))
                total = s.get("total_value", 0)
                calc_str = s.get("calc_str", "")
                if not calc_str:
                    amount = s.get("amount", 0)
                    gold_per = s.get("gold_per_point", 0)
                    calc_str = format_calc_str(amount, gold_per, s.get("multiplier"))
                stat_lines.append(
                    {"name": display_name, "total": round(total, 0), "calc_str": calc_str}
                )
            chart_item["stats"] = stat_lines

        chart_data.append(chart_item)

    chart_data_json = json.dumps(chart_data, ensure_ascii=False)

    # Stats
    total_items = len(chart_data)
    reference_count = len([i for i in chart_data if i["category"] == "reference"])
    unevaluated_count = len([i for i in chart_data if i["category"] == "unevaluated_ability"])
    normal_count = len([i for i in chart_data if i["category"] == "normal"])
    avg_eff = sum(i["efficiency_pct"] for i in chart_data) / total_items if total_items else 100

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chart - Dota 2 Item Analysis (Patch {patch})</title>
    <style>
{SHARED_CSS}
.chart-container {{
    background: rgba(26, 26, 46, 0.9);
    border-radius: 10px; padding: 20px; margin-bottom: 20px;
}}
.controls {{
    display: flex; gap: 15px; flex-wrap: wrap;
    align-items: center; margin-bottom: 15px;
}}
.control-group {{ display: flex; align-items: center; gap: 6px; }}
.control-group label {{ font-size: 12px; color: #aaa; }}
select, input[type="checkbox"] {{
    background: #2d3436; color: #eee;
    border: 1px solid #444; padding: 6px 10px;
    border-radius: 4px; cursor: pointer;
}}

#chartSvg {{
    width: 100%; height: 600px;
    background: rgba(0,0,0,0.2); border-radius: 5px;
}}
.point {{ cursor: pointer; transition: r 0.15s; }}
.point:hover {{ r: 9; }}
.point-label {{ font-size: 9px; fill: #bbb; pointer-events: none; }}
.axis-label {{ font-size: 12px; fill: #aaa; }}
.grid-line {{ stroke: rgba(255,255,255,0.08); stroke-width: 1; }}
.fair-line {{ stroke: rgba(255,255,255,0.3); stroke-width: 2; stroke-dasharray: 8,4; }}

.tooltip {{
    position: fixed;
    background: rgba(20, 20, 35, 0.98);
    border: 1px solid #444;
    border-radius: 8px;
    padding: 15px;
    pointer-events: none;
    display: none;
    z-index: 1000;
    max-width: 350px;
    max-height: calc(100vh - 20px);
    overflow-y: auto;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}}
.tooltip.visible {{ display: block; }}
.tooltip-title {{ color: #f4d03f; font-weight: bold; font-size: 1.1em; margin-bottom: 10px; }}
.tooltip-row {{ display: flex; justify-content: space-between; gap: 20px; padding: 4px 0; }}
.tooltip-label {{ color: #888; }}
.tooltip-value {{ font-weight: bold; }}
.tooltip-value.positive {{ color: #27a95d; }}
.tooltip-value.negative {{ color: #e74c3c; }}

.tooltip-section {{ margin-top: 12px; padding-top: 10px; border-top: 1px solid #444; }}
.tooltip-section-title {{ color: #5dade2; font-size: 0.85em; margin-bottom: 6px; text-transform: uppercase; }}
.tooltip-stat {{ display: flex; justify-content: space-between; font-size: 0.9em; padding: 2px 0; }}
.tooltip-stat-name {{ color: #aaa; }}
.tooltip-stat-value {{ color: #eee; }}
.tooltip-stat-calc {{ color: #666; font-size: 0.85em; }}
.tooltip-ignored {{ color: #e74c3c; font-size: 0.85em; margin-top: 8px; }}
.tooltip-group {{ margin-top: 8px; }}
.tooltip-group-header {{ font-weight: bold; color: #f4d03f; font-size: 0.9em; margin-bottom: 4px; }}
.tooltip-group-header.active {{ color: #3498db; }}
.tooltip-group-header.aura {{ color: #f1c40f; }}
.tooltip-group-header.ignored {{ color: #888; opacity: 0.7; }}
.tooltip-group-header.risk {{ color: #e74c3c; }}
.tooltip-group-meta {{ color: #888; font-weight: normal; font-size: 0.85em; }}
.tooltip-group-stats {{ padding-left: 12px; }}

.legend {{
    display: flex; gap: 20px; justify-content: center;
    margin-top: 15px; flex-wrap: wrap;
}}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
.legend-dot.reference {{ background: #86cef3; }}
.legend-dot.unevaluated_ability {{ background: #e74c3c; }}
.legend-dot.normal {{ background: #27a95d; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{patch}: Real vs Effective Cost Analysis</h1>

        {get_nav_html('interactive_chart.html')}

        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-value">{total_items}</div>
                <div class="stat-label">Items</div>
            </div>
            <div class="stat-card" style="border-color: #86cef3;">
                <div class="stat-value">{reference_count}</div>
                <div class="stat-label">Reference</div>
            </div>
            <div class="stat-card" style="border-color: #e74c3c;">
                <div class="stat-value">{unevaluated_count}</div>
                <div class="stat-label">Ability N/A</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{normal_count}</div>
                <div class="stat-label">Regular</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_eff:.0f}%</div>
                <div class="stat-label">Avg Efficiency</div>
            </div>
        </div>

        <div class="chart-container">
            <div class="controls">
                <div class="control-group">
                    <label>Category:</label>
                    <select id="categoryFilter">
                        <option value="all">All</option>
                        <option value="reference">Reference</option>
                        <option value="unevaluated_ability">Ability N/A</option>
                        <option value="normal">Regular</option>
                    </select>
                </div>
                <div class="control-group">
                    <label>Max Price:</label>
                    <select id="maxPrice">
                        <option value="1000">1k</option>
                        <option value="2000">2k</option>
                        <option value="3000">3k</option>
                        <option value="5000">5k</option>
                        <option value="7500" selected>7.5k</option>
                        <option value="0">Auto</option>
                    </select>
                </div>
                <div class="control-group">
                    <input type="checkbox" id="showLabels">
                    <label for="showLabels">Labels</label>
                </div>
            </div>

            <svg id="chartSvg" viewBox="0 0 1000 600" preserveAspectRatio="xMidYMid meet"></svg>

            <div class="legend">
                <div class="legend-item"><div class="legend-dot reference"></div>Reference item (axiom base)</div>
                <div class="legend-item"><div class="legend-dot unevaluated_ability"></div>Ability not evaluated</div>
                <div class="legend-item"><div class="legend-dot normal"></div>Regular item</div>
            </div>
        </div>

        <div id="tooltip" class="tooltip"></div>
    </div>

    <script>
    (function() {{
        const itemsData = {chart_data_json};

        const colors = {{
            reference: '#86cef3',
            unevaluated_ability: '#e74c3c',
            normal: '#27a95d'
        }};
        const highlightColor = '#f4d03f';

        const urlParams = new URLSearchParams(window.location.search);
        const highlightItemId = urlParams.get('item');

        const svg = document.getElementById('chartSvg');
        const tooltip = document.getElementById('tooltip');
        let pinnedItem = null;
        const padding = {{ top: 30, right: 30, bottom: 50, left: 70 }};
        const width = 1000, height = 600;
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;

        function getFilteredData() {{
            const cat = document.getElementById('categoryFilter').value;
            return itemsData.filter(item => cat === 'all' || item.category === cat);
        }}

        function render() {{
            const data = getFilteredData();
            const showLabels = document.getElementById('showLabels').checked;
            const maxPriceSetting = parseInt(document.getElementById('maxPrice').value);

            let maxX, maxY;
            if (maxPriceSetting > 0) {{
                maxX = maxPriceSetting;
                maxY = maxPriceSetting * 1.5;
            }} else {{
                maxX = Math.max(...data.map(d => d.real_cost), 100) * 1.05;
                maxY = Math.max(...data.map(d => d.effective_cost), 100) * 1.05;
            }}

            const scaleX = (v) => padding.left + (v / maxX) * chartW;
            const scaleY = (v) => padding.top + chartH - (v / maxY) * chartH;

            svg.innerHTML = '';

            // Grid
            const gridGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            const xTicks = Array.from({{length: 6}}, (_, i) => Math.round(maxX * i / 5));
            const yTicks = Array.from({{length: 6}}, (_, i) => Math.round(maxY * i / 5));

            xTicks.forEach(tick => {{
                const x = scaleX(tick);
                const vLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                vLine.setAttribute('x1', x); vLine.setAttribute('y1', padding.top);
                vLine.setAttribute('x2', x); vLine.setAttribute('y2', height - padding.bottom);
                vLine.setAttribute('class', 'grid-line');
                gridGroup.appendChild(vLine);

                const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                xLabel.setAttribute('x', x); xLabel.setAttribute('y', height - padding.bottom + 20);
                xLabel.setAttribute('text-anchor', 'middle'); xLabel.setAttribute('class', 'axis-label');
                xLabel.textContent = tick >= 1000 ? (tick/1000) + 'k' : tick;
                gridGroup.appendChild(xLabel);
            }});

            yTicks.forEach(tick => {{
                const y = scaleY(tick);
                const hLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                hLine.setAttribute('x1', padding.left); hLine.setAttribute('y1', y);
                hLine.setAttribute('x2', width - padding.right); hLine.setAttribute('y2', y);
                hLine.setAttribute('class', 'grid-line');
                gridGroup.appendChild(hLine);

                const yLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                yLabel.setAttribute('x', padding.left - 10); yLabel.setAttribute('y', y + 4);
                yLabel.setAttribute('text-anchor', 'end'); yLabel.setAttribute('class', 'axis-label');
                yLabel.textContent = tick >= 1000 ? (tick/1000) + 'k' : tick;
                gridGroup.appendChild(yLabel);
            }});

            // Axis labels
            const xAxisLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            xAxisLabel.setAttribute('x', width / 2); xAxisLabel.setAttribute('y', height - 10);
            xAxisLabel.setAttribute('text-anchor', 'middle'); xAxisLabel.setAttribute('class', 'axis-label');
            xAxisLabel.textContent = 'Real Cost (gold)';
            gridGroup.appendChild(xAxisLabel);

            const yAxisLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            yAxisLabel.setAttribute('x', 15); yAxisLabel.setAttribute('y', height / 2);
            yAxisLabel.setAttribute('text-anchor', 'middle'); yAxisLabel.setAttribute('class', 'axis-label');
            yAxisLabel.setAttribute('transform', `rotate(-90, 15, ${{height/2}})`);
            yAxisLabel.textContent = 'Effective Cost (gold)';
            gridGroup.appendChild(yAxisLabel);

            svg.appendChild(gridGroup);

            // Fair line (y=x)
            {{
                const fairLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                const endVal = Math.min(maxX, maxY);
                fairLine.setAttribute('x1', scaleX(0)); fairLine.setAttribute('y1', scaleY(0));
                fairLine.setAttribute('x2', scaleX(endVal)); fairLine.setAttribute('y2', scaleY(endVal));
                fairLine.setAttribute('class', 'fair-line');
                svg.appendChild(fairLine);
            }}

            // Points
            const pointsGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');

            data.forEach(item => {{
                const x = scaleX(item.real_cost);
                const y = scaleY(item.effective_cost);

                if (x < padding.left || x > width - padding.right || y < padding.top || y > height - padding.bottom) return;

                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', x);
                circle.setAttribute('cy', y);
                circle.setAttribute('r', 6);
                circle.setAttribute('fill', colors[item.category]);
                circle.setAttribute('class', 'point');
                circle.dataset.itemId = item.id;

                circle.addEventListener('mouseenter', (e) => {{ if (!pinnedItem) showTooltip(e, item); }});
                circle.addEventListener('mouseleave', () => {{ if (!pinnedItem) hideTooltip(); }});
                circle.addEventListener('click', (e) => {{
                    e.stopPropagation();
                    if (pinnedItem === item) {{
                        pinnedItem = null;
                        clearHighlight();
                        hideTooltip();
                    }} else {{
                        pinnedItem = item;
                        highlightPoint(item);
                        showTooltip(e, item);
                        tooltip.style.pointerEvents = 'auto';
                    }}
                }});

                pointsGroup.appendChild(circle);

                if (showLabels) {{
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', x); label.setAttribute('y', y - 10);
                    label.setAttribute('text-anchor', 'middle'); label.setAttribute('class', 'point-label');
                    label.textContent = item.name.length > 12 ? item.name.substring(0, 10) + '..' : item.name;
                    pointsGroup.appendChild(label);
                }}
            }});

            svg.appendChild(pointsGroup);
        }}

        function showTooltip(e, item) {{
            const diffClass = item.difference > 0 ? 'positive' : 'negative';
            const effClass = item.efficiency_pct > 100 ? 'positive' : 'negative';

            let statsHtml = '';
            if (item.stat_groups && item.stat_groups.length > 0) {{
                // Hierarchical display with groups
                statsHtml = '<div class="tooltip-section"><div class="tooltip-section-title">Stat Breakdown</div>';
                item.stat_groups.forEach(group => {{
                    const groupClass = group.group_type;
                    const metaStr = group.group_meta ? ` <span class="tooltip-group-meta">${{group.group_meta}}</span>` : '';
                    statsHtml += `<div class="tooltip-group">
                        <div class="tooltip-group-header ${{groupClass}}">
                            ${{group.group_name}} (${{group.group_type}}): ${{group.group_total}}g${{metaStr}}
                        </div>`;
                    if (group.stats && group.stats.length > 0) {{
                        statsHtml += '<div class="tooltip-group-stats">';
                        group.stats.forEach(s => {{
                            if (s.type === 'info') {{
                                statsHtml += `<div class="tooltip-stat" style="opacity: 0.6">
                                    <span class="tooltip-stat-name">${{s.name}}</span>
                                    <span class="tooltip-stat-value" style="color: #888; font-style: italic">${{s.calc_str}}</span>
                                </div>`;
                            }} else {{
                                statsHtml += `<div class="tooltip-stat">
                                    <span class="tooltip-stat-name">${{s.name}}</span>
                                    <span class="tooltip-stat-value">${{s.total}}g</span>
                                    <span class="tooltip-stat-calc">${{s.calc_str}}</span>
                                </div>`;
                            }}
                        }});
                        statsHtml += '</div>';
                    }}
                    statsHtml += '</div>';
                }});
                statsHtml += '</div>';
            }} else if (item.stats && item.stats.length > 0) {{
                // Fallback: flat display
                statsHtml = '<div class="tooltip-section"><div class="tooltip-section-title">Stat Breakdown</div>';
                item.stats.forEach(s => {{
                    statsHtml += `<div class="tooltip-stat">
                        <span class="tooltip-stat-name">${{s.name}}</span>
                        <span class="tooltip-stat-value">${{s.total}}g</span>
                        <span class="tooltip-stat-calc">${{s.calc_str}}</span>
                    </div>`;
                }});
                statsHtml += '</div>';
            }}

            let ignoredHtml = '';
            if (item.unpriceable_count > 0) {{
                ignoredHtml = `<div class="tooltip-ignored">${{item.unpriceable_count}} stat(s) without pricing</div>`;
            }}

            let abilityEstimateHtml = '';
            if (item.estimated_ability_value) {{
                abilityEstimateHtml = `<div class="tooltip-row" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #444;">
                    <span class="tooltip-label" style="color: #e74c3c;">Est. ability value</span>
                    <span class="tooltip-value" style="color: #e74c3c;">${{item.estimated_ability_value}}g</span>
                </div>`;
            }}

            tooltip.innerHTML = `
                <div class="tooltip-title">${{item.name}}</div>
                <div class="tooltip-row">
                    <span class="tooltip-label">Real Cost</span>
                    <span class="tooltip-value">${{item.real_cost}}g</span>
                </div>
                <div class="tooltip-row">
                    <span class="tooltip-label">Effective Cost</span>
                    <span class="tooltip-value">${{item.effective_cost}}g</span>
                </div>
                <div class="tooltip-row">
                    <span class="tooltip-label">Difference</span>
                    <span class="tooltip-value ${{diffClass}}">${{item.difference > 0 ? '+' : ''}}${{item.difference}}g (${{item.difference_pct > 0 ? '+' : ''}}${{item.difference_pct}}%)</span>
                </div>
                <div class="tooltip-row">
                    <span class="tooltip-label">Efficiency</span>
                    <span class="tooltip-value ${{effClass}}">${{item.efficiency_pct}}%</span>
                </div>
                ${{item.comment ? `<div style="margin-top: 8px; padding: 6px 8px; background: rgba(244, 208, 63, 0.1); border-left: 2px solid #f4d03f; font-size: 0.85em; color: #f4d03f; font-style: italic;">${{item.comment}}</div>` : ''}}
                ${{statsHtml}}
                ${{ignoredHtml}}
                ${{abilityEstimateHtml}}
            `;

            // Position tooltip: show first to measure real size
            tooltip.style.left = '0px';
            tooltip.style.top = '0px';
            tooltip.classList.add('visible');

            const tooltipRect = tooltip.getBoundingClientRect();
            let left = e.clientX + 15;
            let top = e.clientY + 15;

            if (left + tooltipRect.width > window.innerWidth) left = e.clientX - tooltipRect.width - 15;
            if (top + tooltipRect.height > window.innerHeight) top = window.innerHeight - tooltipRect.height - 10;
            if (top < 10) top = 10;

            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        }}

        function hideTooltip() {{
            tooltip.classList.remove('visible');
            tooltip.style.pointerEvents = 'none';
        }}

        function highlightPoint(item) {{
            clearHighlight();
            const circle = svg.querySelector(`circle[data-item-id="${{item.id}}"]`);
            if (circle) {{
                circle.setAttribute('r', 10);
                circle.setAttribute('fill', highlightColor);
                circle.setAttribute('stroke', '#fff');
                circle.setAttribute('stroke-width', '2');
            }}
        }}

        function clearHighlight() {{
            svg.querySelectorAll('circle[data-item-id]').forEach(c => {{
                const id = c.dataset.itemId;
                const item = itemsData.find(d => d.id === id);
                if (item) {{
                    c.setAttribute('r', 6);
                    c.setAttribute('fill', colors[item.category]);
                    c.removeAttribute('stroke');
                    c.removeAttribute('stroke-width');
                }}
            }});
        }}

        tooltip.addEventListener('click', (e) => {{ e.stopPropagation(); }});
        document.addEventListener('click', () => {{
            pinnedItem = null;
            clearHighlight();
            hideTooltip();
        }});

        // Event listeners
        document.getElementById('categoryFilter').addEventListener('change', render);
        document.getElementById('maxPrice').addEventListener('change', render);
        document.getElementById('showLabels').addEventListener('change', render);

        // Initial render
        render();

        // Auto-highlight item from URL parameter
        if (highlightItemId) {{
            const item = itemsData.find(d => d.id === highlightItemId);
            if (item) {{
                pinnedItem = item;
                highlightPoint(item);
                const circle = svg.querySelector(`circle[data-item-id="${{highlightItemId}}"]`);
                if (circle) {{
                    const rect = circle.getBoundingClientRect();
                    showTooltip({{ clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 }}, item);
                    tooltip.style.pointerEvents = 'auto';
                }}
            }}
        }}
    }})();
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Interactive chart saved: {output_file}")
