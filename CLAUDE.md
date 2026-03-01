# Claude Code Instructions

## Quick Start

**ALWAYS activate venv before running Python scripts:**
```bash
source src/venv/bin/activate
python analyse_patch.py --version 7.40c
```

## Project Overview

**Goal:** Scripts and prompts for AI agents that compute the "effective cost" of Dota 2 items. The system allows automatic or semi-automatic updates when new patches are released.

**Patch version:** defined in `src/axioms/axiom_rules.yaml`, set automatically by `make_latest`

## Project Structure

```
2parser/
├── analyse_patch.py              # Entry point: runs full pipeline from any directory
├── data/                         # Input data
│   ├── items_7.40c.txt           # Versioned items source (Valve KeyValue format)
│   └── latest.txt                # Points to active items file
├── docs/                         # Published output (multi-version website)
│   ├── index.html                # Redirect to latest patch chart
│   ├── comparison.html           # Patch-to-patch diff page
│   ├── patches.js                # Shared patches list (loaded by all pages)
│   ├── patches.json              # Machine-readable patches manifest
│   └── patch_7.40c/              # Per-patch output
│       ├── axioms_table.html
│       ├── items_table.html
│       ├── interactive_chart.html
│       └── data.js               # Effective costs for comparison
├── src/                          # Source code
│   ├── axioms/                   # Core logic and configuration
│   │   ├── axiom_rules.yaml      # Main rules (axioms, overrides, items)
│   │   ├── axiom_technical.yaml  # Technical config (settings, normalization, excluded, ignored)
│   │   ├── loader.py             # YAML loader with validation
│   │   └── calculator.py         # Axiom calculation engine
│   ├── common/                   # Shared utilities
│   │   ├── paths.py              # Centralized path constants (PROJECT_ROOT, etc.)
│   │   ├── formatting.py         # Shared formatting helpers
│   │   └── shared_styles.py      # CSS shared between 04 and 05
│   ├── pipeline/                 # Main processing scripts
│   │   ├── 01_parse_items.py     # Parse items → items_parsed.json
│   │   ├── 02_resolve_axioms.py  # Calculate axiom gold_per_point values
│   │   ├── 03_calculate_costs.py # Calculate effective costs for items
│   │   ├── 04_generate_output.py # Generate HTML/CSV/PNG outputs
│   │   └── 05_publish.py         # Publish output → docs/patch_{version}/
│   ├── tools/                    # Standalone utilities
│   │   ├── make_latest.py        # Version management (set active patch)
│   │   └── fetch_liquipedia.py   # Fetch item descriptions from Liquipedia
│   ├── venv/                     # Python virtual environment (USE THIS!)
│   └── requirements.txt          # Python dependencies
├── output/                       # Working directory (current patch intermediate files)
│   ├── items_parsed.json
│   ├── calculated_axioms.json
│   ├── effective_costs.json
│   └── ...
├── liquipedia_parsed/            # Liquipedia data (separate from pipeline)
│   ├── items_liquipedia.json     # Parsed item data from Liquipedia
│   └── cache/                    # Raw API response cache
├── ai_instructions/              # AI agent prompts
│   └── cookbook/                  # Step-by-step guides (see README.md)
├── tests/                        # Pytest tests
├── todo.txt                      # Author's personal notes (DO NOT read or modify)
└── readme.md                     # Project documentation
```

## Key Points

1. **Venv is required** - exists at `src/venv/`, do not create new one
2. **Pipeline scripts** run in order: 01 → 02 → 03 → 04 → 05
3. **`analyse_patch.py`** — entry point, runs all steps from any directory
4. **axiom_rules.yaml** + **axiom_technical.yaml** are the source of truth (loader merges both)
5. **Input data** is in `data/items_{version}.txt`, pointed by `data/latest.txt`
6. **`output/`** — working directory for current patch (intermediate files)
7. **`docs/`** — published multi-version website
8. **drops_on_death** flag tracks items that drop on death (risk not evaluated)
9. **fetch_liquipedia.py** — separate script, output in `liquipedia_parsed/` (not part of main pipeline)
10. **No .pyc cache** - disabled via `PYTHONDONTWRITEBYTECODE=1` in venv
11. **todo.txt** - author's personal notes, DO NOT read or modify

## Environment Setup

### Virtual Environment (REQUIRED)

```bash
source src/venv/bin/activate
python analyse_patch.py
```

**DO NOT:**
- Run `pip install` globally - use the venv
- Run `python3` directly without activating venv
- Create a new venv - one already exists at `src/venv/`

### Dependencies (already installed in venv)
- pandas - DataFrame operations
- openpyxl - Excel file reading
- matplotlib - Plotting
- numpy - Numerical operations
- requests - HTTP requests (for Liquipedia API)
- beautifulsoup4 - HTML parsing
- PyYAML - YAML parsing for axiom_rules.yaml

## YAML Configuration

Configuration is split into two files (merged by loader.py):
- `src/axioms/axiom_rules.yaml` — axioms, item_overrides (domain rules)
- `src/axioms/axiom_technical.yaml` — settings, stat_normalization, excluded_items, ignored_stats

See `ai_instructions/cookbook/04_yaml_reference.md` for full field reference.

## Pipeline: Regenerate All Outputs

```bash
source src/venv/bin/activate
python analyse_patch.py --version 7.40c
```

Or run individual steps:
```bash
python analyse_patch.py --from 4          # From step 4
python analyse_patch.py --from 1 --to 3   # Steps 1-3 only
python analyse_patch.py -v                # Verbose (DEBUG level)
python analyse_patch.py -q                # Quiet (WARNING level only)
```

### What each step produces:
- **01_parse_items.py** → `items_parsed.json`
- **02_resolve_axioms.py** → `calculated_axioms.json`
- **03_calculate_costs.py** → `effective_costs.json`, `axiom_questions.json`
- **04_generate_output.py** → `axioms_table.html`, `items_table.html`, `item_costs.csv`, `price_comparison.png`, `interactive_chart.html`
- **05_publish.py** → `docs/patch_{version}/` + `index.html` + `comparison.html` + `patches.js`

## Common Tasks

### Add a new patch
```bash
cp /path/to/new/items.txt data/items_7.50.txt
source src/venv/bin/activate
python analyse_patch.py --version 7.50
```

### Add/remove item from analysis
Edit `excluded_items` section in `src/axioms/axiom_rules.yaml`, then regenerate.

### Add/change stat axiom
1. Edit `axioms` section in `src/axioms/axiom_rules.yaml`
   - Use appropriate method: `reference_item`, `manual`, `formula`, or `amplification_of`
   - Add `display_name` for human-readable name in HTML table
2. Regenerate outputs

### Add item-specific override
Edit `item_overrides` section in `src/axioms/axiom_rules.yaml`:
- `custom_stats` - formula-based synthetic stats (crit, CC, etc.)
- `uptime_stats` - temporary buffs with cooldown
- `switchable_stats` - stats that can be toggled (like Power Treads)
- `ignored_stats` - stats to ignore for this item
- `ability_value` - manual override for ability gold value
- `comment` - rendered in HTML output (yellow italic)

### Fetch Liquipedia data
```bash
cd src && source venv/bin/activate
python -m tools.fetch_liquipedia --test        # Parse 4 test items
python -m tools.fetch_liquipedia --all         # Parse all items (~150)
python -m tools.fetch_liquipedia --cache-only  # Only use cached data
python -m tools.fetch_liquipedia --force       # Re-fetch and update cache
```
**Output:** `liquipedia_parsed/items_liquipedia.json`
**Rate limit:** 30 seconds between API requests (per Liquipedia API Terms)

## Key Source Files

- `src/axioms/loader.py` — YAML loader: `load_axiom_rules()`, `normalize_stat_name()`, `is_item_excluded()`, `get_items_path()`
- `src/axioms/calculator.py` — Axiom calculation engine (reference_item, formula, amplification_of, manual)
- `src/common/paths.py` — Centralized path constants (PROJECT_ROOT, DATA_DIR, OUTPUT_PATH, etc.)
- `src/common/formatting.py` — Shared formatting helpers (format_calc_str, etc.)
- `src/common/shared_styles.py` — CSS shared between output generators

## Testing

Run tests from project root:
```bash
source src/venv/bin/activate
python -m pytest tests/ -v
```

## Cookbook (Step-by-Step Guides)

Located in `ai_instructions/cookbook/` — see `README.md` there for index.

## Item Validation

All 168 items validated across 18 batches. Use `/validate-batch N` to re-validate a batch after patch changes.
