---
name: validate-batch
description: Validate a batch of Dota 2 items for axiom coverage, efficiency, and unvalued abilities.
user-invocable: true
argument-hint: [batch-number]
---

# Batch Item Validation Workflow

Validate batch **$ARGUMENTS**. Read `.claude/skills/parallel-fix/SKILL.md` to find the batch by number and get the list of items.

## Valuation Principles

### Single source of truth: axiom_rules.yaml
All valuation logic lives in `axiom_rules.yaml`. Edit ONLY the YAML — never hardcode values in Python.

### Residual method for ability valuation
```
ability_value = real_cost - sum(stat_values)
```

### Zero cost requires justification
Every zero effective_cost must have a documented reason:
- Flag parameter (illusion_multiplier_pct = 100% means "yes, works on illusions")
- Display-only tooltip (sheep_movement_speed = target speed while hexed)
- Genuinely unquantifiable without hero context (with `ability_not_evaluated: true`)

### Efficiency ranges
- **< 50%**: Significant unvalued ability — must be addressed
- **50-80%**: Acceptable if documented (hero-dependent, situational)
- **80-120%**: Normal range
- **120-200%**: Stat-dense or aura item — expected
- **> 200%**: Expected for cheap components (Branches, Gauntlets)

### Data sources priority
1. `items_parsed.json` — stat values (source of truth)
2. `items_liquipedia.json` — mechanics understanding (reference only)
3. Game knowledge — for ability valuation reasoning

### Valuation by item type

| Type | Method | Example |
|------|--------|---------|
| Pure stat item | Existing axioms | Heart (STR + HP) |
| Passive proc | custom_stats formula | Maelstrom (chain lightning) |
| Active ability | `ability_value` = remainder after subtracting stats | BKB, Force Staff |
| Pure active (no stats) | `ability_value` = real_cost | Blink (2250g) |
| Aura | Aura axioms (x2 multiplier) | Pipe, Vladmir |
| Switchable modes | `switchable_stats` with multiplier | Rapier, Power Treads |
| Uptime-dependent | `uptime_stats` | Armlet, MoM |
| Consumable | One-time effects in `ignored_stats`, permanent stats valued | Faerie Fire |
| Gold-generating | `ability_value` with economic reasoning | Hand of Midas |

### Comments are English, max 100 chars

## YAML Examples

### Ability value via residual method
```yaml
item_force_staff:
  ability_value: 780
  comment: "Force push ability. Residual: 2200 - 1420 stats."
```

### Switchable modes
```yaml
item_rapier:
  switchable_stats:
    bonus_damage:
      multiplier: 0.5
      reason: "Physical mode only"
    bonus_spell_amp:
      multiplier: 0.5
      reason: "Spell mode only"
```

### Custom stat with formula
```yaml
item_disperser:
  custom_stats:
    suppress_slow:
      formula: "60 * enemy_effect_duration / AbilityCooldown"
      axiom: bonus_movement_speed_percent
      comment: "Suppress: avg 60% slow (100→20 decay) × 5s / 15s CD"
```

### CC stat with sqrt-scaling
```yaml
item_abyssal_blade:
  custom_stats:
    cc_stun:
      formula: "stun_duration / sqrt(AbilityCooldown) + bash_duration * (bash_chance_melee + bash_chance_ranged) / 2 / 100"
      comment: "Overwhelm 1.6s/35s CD + Bash 1.2s × 17.5% chance"
```

### Uptime stats (temporary buff)
```yaml
item_silver_edge:
  uptime_stats:
    windwalk_movement_speed:
      cooldown_stat: AbilityCooldown
      duration_stat: windwalk_duration
      reason: "Shadow Walk: +25 MS for 17s / 20s CD"
```

### Charge-based item
```yaml
# Charge availability coefficient 0.3 for limited-charge abilities
item_urn_of_shadows:
  custom_stats:
    soul_release_value:
      formula: "(heal_hp * heal_duration + damage * damage_duration) / 2 * 0.3"
      axiom: damage
      comment: "Soul Release heal+dmg avg × 0.3 charge availability"
```

---

## Phase 1: Analysis (run via background agent)

Launch an agent to analyze ALL items in the batch. For EACH item collect:

1. **effective_costs.json** — real_cost, effective_cost, efficiency_pct, stat_breakdown, unpriceable_stats
2. **items_parsed.json** — ALL stats + raw_data (AbilityCooldown etc)
3. **liquipedia/items_liquipedia.json** — abilities, mechanics
4. **axiom_rules.yaml** — existing item_overrides (custom_stats, uptime_stats, ignored_stats, switchable_stats, comment)
5. **axiom_rules.yaml global ignored_stats** — which of this item's stats are globally ignored
6. **axiom_questions.json** — any unresolved stats
7. **`ability_not_evaluated` flag** — whether the item is marked as having unevaluated abilities

Agent must output a complete summary table + detailed per-item breakdown.

## Phase 2: Sequential discussion

Present items ONE AT A TIME to the user. For each item show:

### Item Header
```
## N/TOTAL: Item Name (cost, efficiency%)
```

### Full Stat Audit Table
| Stat | Value | Status | Source |
|------|-------|--------|--------|
Every stat from items_parsed.json must appear with one of:
- **Valued** — has axiom, shows gold value
- **Ignored (local)** — in item_overrides.ignored_stats, show reason
- **Ignored (global)** — in global ignored_stats, show reason
- **Unpriceable** — no axiom found
- **Custom stat** — valued via custom_stats formula

### ability_not_evaluated flag
Show whether the flag is set. If abilities ARE partially valued (e.g. Chain Lightning valued but Static Charge not), the flag should still be set with a comment explaining what's valued and what's not.

### Abilities (from liquipedia + game data)
Brief description of what each ability does.

### Assessment
- What's unvalued and why?
- Recommended approach (with options if ambiguous)

### Wait for user decision before proceeding.

## Phase 3: Apply changes

When user approves a change:
1. Edit `src/axioms/axiom_rules.yaml` — add custom_stats, ignored_stats, comments, stat_normalization
2. Run pipeline: `cd src && source venv/bin/activate && python -m pipeline.02_resolve_axioms && python -m pipeline.03_calculate_costs`
3. Verify the item's new efficiency
4. Show result, move to next item

**Rules:**
- Use `formula` in custom_stats, NOT hardcoded ability_value
- Add `stat_normalization` entries when custom_stat names don't match axiom names
- Always check ALL ignored stats (both local AND global) for every item
- Add `comment` field for items with unvalued abilities (renders in HTML)

### Cross-item impact check
When adding a NEW axiom or new stat_normalization entry, it may affect items OUTSIDE this batch (e.g. a `displacement` axiom affects all items with `push_length` or `blink_range`). In this case:
1. **Ask the user** whether to investigate cross-item impact
2. If yes — launch a **background agent** that writes an md report to `output/` listing all affected items with before/after efficiency
3. Do NOT try to analyze all affected items inline — this will consume too much context

## Phase 4: Finalize

After all items discussed:
1. Run full pipeline including `04_generate_output`
2. Run tests: `python -m pytest tests/ -v`
3. Regression check: verify reference items are 100%
4. Check `axiom_questions.json` has no NEW unmapped stats from this batch
5. Update cookbook files if you discover new patterns or pitfalls

### Definition of Done (per batch)
- All items have `efficiency_pct` calculated (not null/zero without reason)
- Zero-cost items have documented reason in `comment` field
- Items outside 80-120% range have explanation
- `axiom_questions.json` has no NEW unmapped stats from this batch
- Tests pass
- Reference items unchanged (see regression check below)

### Reference items for regression check
All should be exactly 100%. If ANY change by > 1%, investigate before proceeding.

| Item | Stat |
|------|------|
| item_ogre_axe | STR reference |
| item_blade_of_alacrity | AGI reference |
| item_staff_of_wizardry | INT reference |
| item_chainmail | armor reference |
| item_cloak | magic resistance reference |
| item_ring_of_regen | HP regen reference |
| item_blades_of_attack | damage reference |
| item_gloves | attack speed reference |
| item_boots | movement speed reference |
| item_sobi_mask | mana regen reference |

## Risks and Edge Cases

1. **New axioms affect ALL items**: Adding a new axiom can change efficiency for items already validated. Spot-check a few items from other batches after adding axioms.
2. **stat_normalization gaps**: Some stats in items_parsed.json may have unexpected names. Check `axiom_questions.json` after each pipeline run.
3. **Overcounting aura stats**: Some items have personal + aura versions of the same stat. Ensure both are counted but not double-counted.
4. **Consumable effects**: One-time effects (Faerie Fire heal, Mango mana) go to `ignored_stats`. Only permanent stats are valued.
5. **Circular ability_value**: If ability_value = real_cost - stats, and stats change due to axiom updates, ability_value becomes stale. Document the calculation in `comment`.

## Error Recovery

### Pipeline crash
1. Read the error message — usually YAML syntax or missing reference
2. Check `axiom_rules.yaml` for recent changes (use `git diff`)
3. Fix the YAML issue and re-run pipeline

### Regression in earlier batches
1. If change is < 5% — acceptable, document
2. If change is > 5% — investigate: does the earlier item need `ability_value` adjustment?
3. Never revert a correct new axiom just to preserve old numbers

### Test failures
1. Read pytest output — identify which test fails
2. If reference item test — a reference item's axiom may have changed
3. Fix the issue, do NOT commit with failing tests

## Key files
- `src/axioms/axiom_rules.yaml` — single source of truth
- `ai_instructions/cookbook/` — decision trees and YAML reference
- `liquipedia_parsed/items_liquipedia.json` — item mechanics data
