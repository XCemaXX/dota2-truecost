# How to Debug Anomalous Efficiency

## Normal Efficiency Range

- **Expected:** 80% - 120%
- **Investigate if:** <80% or >120%
- **Alert if:** <60% or >150%

---

## Checklist: Efficiency > 120% (Undervalued)

Item seems more valuable than calculated. Check:

### 1. Missing Axiom?
```bash
# Check effective_costs.json for stats with gold_value: 0
grep -A5 "item_name" output/effective_costs.json | grep "gold_value.*: 0"
```

**Fix:** Add axiom for missing stat in `axiom_rules.yaml`. See [01_add_axiom.md](01_add_axiom.md).

### 2. Stat in Wrong ignored_stats?
Check both global `ignored_stats` and item-specific `item_overrides.{item}.ignored_stats`.

**Fix:** Remove from `ignored_stats`, add proper axiom.

### 3. Custom Stats Missing?
Does item have active ability not valued?

**Fix:** Add `item_overrides` with `custom_stats`. See [02_add_item_override.md](02_add_item_override.md).

### 4. Ability Value Missing?
Is there an active ability worth gold?

**Fix:** Add `ability_value` in `item_overrides`.

---

## Checklist: Efficiency < 80% (Overvalued)

Item seems less valuable than calculated. Check:

### 1. Wrong Reference Item?
Is the reference item for an axiom still correct in current patch?

```yaml
# Check axiom source
bonus_stat:
  method: reference_item
  reference_item: item_xxx  # <- Is this item still correct?
```

**Fix:** Update reference_item or add `subtract_stats` if item has multiple stats.

### 2. subtract_stats Incorrect?
Are all other stats being subtracted?

```yaml
bonus_cooldown_reduction:
  method: reference_item
  reference_item: item_octarine_core
  subtract_stats:
    - bonus_health
    - bonus_mana
    - bonus_mana_regen_pct
    # Missing a stat? Check items_parsed.json
```

**Fix:** Add missing stats to `subtract_stats` list.

### 3. Uptime Not Applied?
Is stat temporary but valued as permanent?

**Fix:** Add `uptime` modifier or `uptime_stats` in item_overrides.

### 4. Switchable Modes?
Does item have modes that don't stack?

**Fix:** Add `switchable_stats` with multiplier 0.5.

### 5. Situational Stat Overvalued?
Is stat like True Strike valued when it shouldn't be?

**Fix:** Set `gold_per_point: 0` with `status: situational`.

---

## How to Read effective_costs.json

```json
{
  "item_sange": {
    "name": "Sange",
    "real_cost": 2050,           // Actual shop price
    "effective_cost": 1950,      // Calculated stat value
    "efficiency_pct": 95.1,      // effective/real * 100
    "status": "overvalued",      // <100% = overvalued, >100% = undervalued
    "breakdown": {
      "stats": [
        {
          "stat": "bonus_strength",
          "value": 16,
          "gold_per_point": 100.0,
          "gold_value": 1600.0,       // <- This is the calculated value
          "axiom_ref": "bonus_strength"
        }
      ],
      "abilities": [],                 // ability_value goes here
      "ignored": [
        {
          "stat": "tooltip_stat",
          "reason": "tooltip_stats category"
        }
      ]
    }
  }
}
```

**Look for:**
- `gold_value: 0` in stats = missing axiom
- Stats in `ignored` that shouldn't be = wrong ignored_stats
- Empty `abilities` when item has active = missing ability_value

---

## Common Fixes

### Missing Axiom (efficiency > 120%)
```yaml
# Add to axioms section
new_stat_name:
  method: manual
  gold_per_point: 15
  display_name: "New Stat"
  category: "category"
  comment: "Explain value estimate"
```

### Wrong Ignored Stat (efficiency > 120%)
```yaml
# Remove from ignored_stats or add axiom
# Before: stat was in ignored_stats with wrong reason
# After: stat has axiom or is in item_overrides.custom_stats
```

### Missing subtract_stats (efficiency < 80%)
```yaml
# Before
bonus_cdr:
  method: reference_item
  reference_item: item_octarine_core
  stat: bonus_cooldown_reduction

# After - add all other stats
bonus_cdr:
  method: reference_item
  reference_item: item_octarine_core
  stat: bonus_cooldown_reduction
  subtract_stats:
    - bonus_health
    - bonus_mana
    - bonus_mana_regen_pct
```

### Missing ability_value (efficiency > 120%)
```yaml
item_overrides:
  item_blink:
    ability_value: 2250
    comment: "Pure ability item"
```

### Switchable Mode Not Applied (efficiency < 80%)
```yaml
item_overrides:
  item_rapier:
    switchable_stats:
      bonus_damage:
        multiplier: 0.5
        reason: "Physical mode"
      bonus_spell_amp:
        multiplier: 0.5
        reason: "Spell mode"
```

---

## Compare Similar Items

If one item has wrong efficiency, check similar items:

| Category | Items to Compare |
|----------|------------------|
| STR items | Sange, Ogre Axe, Bracer |
| AGI items | Yasha, Blade of Alacrity, Wraith Band |
| INT items | Kaya, Staff of Wizardry, Null Talisman |
| Armor items | Chainmail, Platemail, Buckler |

Similar items should have similar efficiency. Large deviation = wrong axiom.

---

## Audit: stat_normalization and ignored_stats

Periodically review these sections for correctness.

### Check stat_normalization (Aliases)

```yaml
# Question format for unclear aliases
stat_normalization:
  bonus_str: bonus_strength  # Is this alias used in items_parsed.json?
```

**Audit steps:**
1. Search items_parsed.json for the alias name
2. If NOT found → remove alias (dead code)
3. If found → keep alias, verify target axiom exists

```bash
# Check if alias is used
grep "bonus_str" output/items_parsed.json
```

### Check ignored_stats

Ignored stats exist at two levels:
- **Global** (`ignored_stats.global`): ~21 common ability parameters (radius, duration, etc.)
- **Item-specific** (`item_overrides.{item}.ignored_stats`): per-item ignored stats

```yaml
# Global (only common params, 3+ items)
ignored_stats:
  global:
    radius: { reason: "Generic ability radius parameter" }

# Item-specific
item_overrides:
  item_bfury:
    ignored_stats:
      cleave_damage_percent: { reason: "Cleave damage percentage" }
```

**Audit steps:**
1. Check if stat has meaningful value in items_parsed.json
2. If value > 0 and affects gameplay → should have axiom
3. If value = 0 or display-only → keep ignored
4. If stat is in `uptime_stats` for this item → must NOT be in ignored_stats

**Question format for unclear cases:**
```markdown
### Question: Should [stat_name] be ignored?

**Context:** Found in [item_name] with value [X].
Currently in ignored_stats as "[reason]".

**Options:**
A) **Keep ignored** - [reason why it's not a real stat]
B) **Add axiom** - [reason why it should be valued]
C) **Item-specific** - Ignore globally, but value for specific items

**My recommendation:** [X] because [reason]
```

---

## After Fixing

```bash
cd src && source venv/bin/activate
python -m pipeline.02_resolve_axioms && python -m pipeline.03_calculate_costs && python -m pipeline.04_generate_output
```

Verify:
1. Item efficiency is now 80-120%
2. Similar items still have reasonable efficiency
3. No new warnings in output
