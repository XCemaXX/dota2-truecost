# Axiom Cookbook

Quick reference guides for AI agents working with the axiom system.

## When to Use Each Guide

| Guide | Use When |
|-------|----------|
| [01_add_axiom.md](01_add_axiom.md) | Adding a new stat to the axiom system |
| [02_add_item_override.md](02_add_item_override.md) | Item has abilities, switchable modes, or needs special handling |
| [03_debug_efficiency.md](03_debug_efficiency.md) | Item efficiency is >120% or <80% |
| [04_yaml_reference.md](04_yaml_reference.md) | Looking up YAML field syntax |
| [05_batch_validation.md](05_batch_validation.md) | Validating items systematically in batches |

## Quick Decision Tree

```
New stat found?
  +--> Pure reference item exists? --> 01 (reference_item)
  +--> % amplification of another stat? --> 01 (amplification_of)
  +--> Can calculate from other axioms? --> 01 (formula)
  +--> No reference? --> 01 (manual)

Item has special mechanics?
  +--> Compound mechanic (crit, CC, etc.) --> 02 (custom_stats)
  +--> Temporary buff with cooldown --> 02 (uptime_stats)
  +--> Switchable modes --> 02 (switchable_stats)
  +--> Pure ability item --> 02 (ability_value)

Efficiency looks wrong? --> 03

Need to validate many items? --> 05
```

## Key Files

- Rules: `src/axioms/axiom_rules.yaml`
- Items data: `output/items_parsed.json`
- Costs output: `output/effective_costs.json`
- Liquipedia data: `liquipedia_parsed/items_liquipedia.json`
- Liquipedia data: `liquipedia_parsed/items_liquipedia.json`
