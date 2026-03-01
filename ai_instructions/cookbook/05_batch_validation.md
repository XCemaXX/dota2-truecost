# Batch Validation Workflow

> Use `/validate-batch N` skill for the full interactive workflow.

## Overview

Batch validation processes items in manageable groups, tracking progress and ensuring consistency.

---

## Batch Definitions

Batch definitions (item lists per batch) are in `.claude/skills/parallel-fix/SKILL.md`.
```

---

## Item Complexity Levels

Prioritize by complexity:

### Simple (Priority 1)
- No abilities
- 1-3 stats
- Basic components
- **Examples:** Ring of Protection, Ogre Axe, Chainmail
- **Estimate:** Quick validation

### Medium (Priority 2)
- May have abilities OR 4-5 stats
- Some component subtraction
- **Examples:** Vanguard, Sange, Phase Boots
- **Estimate:** Moderate validation

### Complex (Priority 3)
- Has abilities AND 6+ stats
- Multiple overrides needed (ability_value, switchable_stats, uptime_stats)
- Switchable modes or uptime calculations
- **Examples:** Assault Cuirass, Spirit Vessel, Octarine Core
- **Estimate:** Extended validation

---

## Validation Workflow

### Step 1: Select Batch

Choose items with similar complexity or stats:

```yaml
# Good batch groupings
- "STR items": [item_sange, item_bracer, item_ogre_axe]
- "Armor items": [item_chainmail, item_platemail, item_buckler]
- "Blink variants": [item_blink, item_overwhelming_blink, item_arcane_blink]
```

### Step 2: For Each Item

1. **Read items_parsed.json** - source of truth for stat values
2. **Read items_liquipedia.json** - understand mechanics, abilities
3. **Check current rules** - is item already handled correctly?
4. **Identify issues:**
   - Missing axioms (stat has gold_value: 0)
   - Wrong ignored_stats (stat ignored but shouldn't be)
   - Missing ability_value or other overrides
5. **Fix issues** - update axiom_rules.yaml
6. **Regenerate** - run pipeline to verify
7. **Check efficiency** - should be 80-120%

### Step 3: Report Format

```markdown
## Batch X: [Theme]

### [Item Name]
- **Status:** verified / updated / needs_review
- **Efficiency:** X% -> Y%
- **Changes:**
  - Added axiom for stat_name
  - Fixed subtract_stats in axiom_name
  - Added ability_value: X
- **Questions:** (if any)
```

---

## Checklist Per Item

```markdown
### [Item Name] Validation

**Data Sources:**
- [ ] Read items_parsed.json for stat values
- [ ] Read items_liquipedia.json for mechanics
  - [ ] Check "stats" field (empty = ability item)
  - [ ] Check "abilities" for active effects

**Stats Check:**
- [ ] All stats have axioms (no gold_value: 0)
- [ ] No stats incorrectly ignored
- [ ] subtract_stats correct for derived axioms

**Abilities Check:**
- [ ] ability_value set if pure ability item
- [ ] ability_value for active abilities (heal, damage, debuff)
- [ ] All ability parameters in ignored_stats

**Efficiency:**
- [ ] Current efficiency: ___%
- [ ] After fixes: ___% (target: 80-120%)

**Notes:**
- ...
```

---

## Batch Report Template

```markdown
# Validation Report: Batch X

**Date:** YYYY-MM-DD
**Items:** X validated, Y updated, Z need review

## Summary
| Item | Before | After | Status |
|------|--------|-------|--------|
| item_name | 65% | 98% | fixed |
| item_name | 102% | 102% | verified |

## Changes Made

### axiom_rules.yaml
- Added axiom: stat_name
- Fixed: subtract_stats for axiom_name
- Added item_override for item_name

### Questions for Review
1. [Item] - question about mechanic
2. [Axiom] - unclear reference item

## Next Batch
Recommended: [batch_theme] with [items]
```

---

## Common Patterns

### Pattern: Stat Family Validation

Validate related stats together:

```markdown
# Movement Speed Family
1. bonus_movement_speed (flat)
2. bonus_movement_speed_pct (percentage)
3. phase_movement_speed (active)

# Verify:
- All use correct reference items
- No double-counting between flat/pct
- Phase has uptime applied
```

### Pattern: Item Upgrade Chain

Validate upgrades together:

```markdown
# Urn -> Vessel chain
1. item_urn_of_shadows (base)
2. item_spirit_vessel (upgrade)

# Verify:
- Vessel efficiency accounts for Urn stats
- Additional stats valued correctly
- Ability upgrade (HP drain %) valued
```

---

## After Validation

```bash
cd src && source venv/bin/activate
python -m pipeline.02_resolve_axioms && python -m pipeline.03_calculate_costs && python -m pipeline.04_generate_output
```

Update cookbook files if you discover new patterns or pitfalls.

---

## Known Pitfalls

Lessons learned from validating Arcane Boots and Mekansm (Feb 2026).

### Pitfall 1: ignored_stats blocks uptime_stats

**Symptom:** You add `uptime_stats` to an item, but the stat still shows
"Ability parameter (not priced)" in effective_costs.json.

**Cause:** The stat is in `ignored_stats` (global or item-specific). Stats in
`ignored_stats` are always skipped — there is no bypass mechanism.

**Rule:** If a stat is in `uptime_stats`, it must NOT be in `ignored_stats` for that item.

**How to verify:** If you add `uptime_stats` and the stat is still not priced, check:
1. Is the stat in global `ignored_stats`? If yes, remove it from global (or make it item-specific for other items only)
2. Is the stat in item-specific `ignored_stats`? If yes, remove it from that item's ignored_stats
3. Does the stat normalize to something in `ignored_stats`? Check both names
4. Run the pipeline and look at `calculation_trace` for the item

### Pitfall 2: stat_normalization maps to wrong economic concept

**Symptom:** Gold value is absurdly low or high for a stat with `uptime_stats`.

**Cause:** The stat normalizes to an axiom measured in different units.
Example: `heal_amount` → `bonus_health` (4g/point, measures HP pool).
With uptime `1/50`, you get: 250 * 4.0 * 0.02 = 20g — nearly zero.

**Solution:** Use `stat_as` in `uptime_stats` to override the axiom lookup:
```yaml
heal_amount:
  cooldown_stat: AbilityCooldown
  stat_as: aura_health_regen    # 212.5g/point instead of 4g/point
```

**How to detect:** After running the pipeline, check the `calc_str` field in
stat_breakdown. If it shows an unexpectedly small or large `gold_per_point`,
the stat might be normalized to the wrong axiom.

### Pitfall 3: Burst resource vs permanent pool

**Symptom:** Item's efficiency is ~100% but the breakdown shows the active ability
priced as permanent HP/mana instead of burst-with-cooldown.

**Cause:** Stats like `heal_amount` normalize to `bonus_health` and are priced
as if the item gives permanent HP. The number may accidentally look reasonable
(Mekansm: 250 * 4 = 1000g vs correct 1062.5g), masking the wrong calculation.

**How to detect:** Check the `calculation_trace` — if a burst heal/mana stat
has no `uptime` in the trace, it's being priced as permanent.

**Solution:** Always add `uptime_stats` for burst effects. Even if the final number
looks similar, the calculation must be correct for consistency.

### Pitfall 4: Same stat name, different items, different meaning

**Symptom:** Creating an axiom or normalization for a stat breaks other items.

**Cause:** Same stat name means different things for different items:
- `replenish_amount`: Arcane Boots (team burst, CD-based) vs Mango (one-time consumable)
- `heal_amount`: Mekansm (team burst) vs Tranquil Boots (personal regen) vs
  Overwhelming Blink (self burst)

**Solution:**
- **Global axiom/normalization** only works when all items use the stat the same way
- **Per-item handling** via `uptime_stats` + `stat_as` for items that differ
- **Item-specific ignored_stats** lets you ignore a stat for some items but price
  it (via `uptime_stats`) for others. Just don't add it to `ignored_stats` for items
  where it should be priced

### Pitfall 5: custom_stats naming must match axiom

**Symptom:** custom_stat is computed correctly but shows as "unpriceable".

**Cause:** The `axiom` field inside custom_stats is NOT used by the pipeline for
pricing lookup. The pipeline prices the custom_stat by its key name, looking it up
as an axiom.

**Solution:** Either:
1. Name the custom_stat key identically to an existing axiom (e.g. `cc_root`)
2. Add a `stat_normalization` entry mapping custom_stat name → axiom name

```yaml
# Option 1: key matches axiom directly
custom_stats:
  cc_root:
    formula: "duration / sqrt(AbilityCooldown)"

# Option 2: custom name + stat_normalization
custom_stats:
  charge_burst_heal:
    formula: "(health_restore + mana_restore) * max_charges * 0.3"
# In stat_normalization section:
stat_normalization:
  charge_burst_heal: damage
```

### Summary: Which approach to use

| Situation | Approach |
|-----------|----------|
| Compound mechanic (crit, CC, etc.) | `custom_stats` with formula |
| Temporary buff with cooldown | `uptime_stats` with `cooldown_stat` |
| Stat normalizes to wrong axiom | `uptime_stats` + `stat_as` |
| No measurable stat in items_parsed.json | `ability_value` (residual or manual) |
| Self-penalty during active (MoM silence) | `custom_stats` with negative formula |
| Same stat name, different meaning per item | Per-item `ignored_stats` + selective pricing |
