# Dota 2 Item Efficiency Analysis

Calculates the **effective cost** of every Dota 2 item by pricing each stat through basic reference items and comparing the total to the shop price.

**Live demo:** [xcemaxx.github.io/dota2-truecost](https://xcemaxx.github.io/dota2-truecost/)

## Quick Start

```bash
source src/venv/bin/activate
python analyse_patch.py --version 7.40c
```

Results are in `docs/`. View locally:

```bash
cd docs && python -m http.server 8080
```

## How It Works

Each stat has a gold-per-point rate (**axiom**) derived from a basic item (e.g. Ogre Axe: 1000g / 10 STR = 100 g/point). The pipeline sums all stat values on an item to get its effective cost, then compares it to the real price.

Items with active abilities, cooldown-based buffs, crit, CC, and other compound mechanics are handled via per-item overrides in config.

## Configuration

All rules are in `src/axioms/axiom_rules.yaml`:
- **Axioms** — how each stat is valued (reference item, formula, manual, or amplification)
- **Item overrides** — ability values, custom stats, uptime buffs, ignored stats
- **Excluded items** — recipes, consumables, neutral items, etc.

Technical config (stat normalization, global ignored stats) is in `src/axioms/axiom_technical.yaml`.

## Adding a New Patch

```bash
cp /path/to/new/items.txt data/items_7.50.txt
source src/venv/bin/activate
python analyse_patch.py --version 7.50
```

## Data Sources

### Valve Game Files

Extract `scripts/npc/items.txt` from:

```
Steam\steamapps\common\dota 2 beta\game\dota\pak01_dir.vpk
```

Tool: [ValveResourceFormat](https://github.com/ValveResourceFormat/ValveResourceFormat)

### Liquipedia

Item mechanics and ability descriptions from [Liquipedia Dota 2](https://liquipedia.net/dota2/) — used as context for analysis, since `items.txt` contains only raw stat values without explaining how abilities work. Not used at runtime.

Data licensed under [CC-BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) per [API Terms of Use](https://liquipedia.net/api-terms-of-use).
