# How to Add a New Axiom

## Before Adding: Check Data Sources

1. **items_parsed.json** — source of truth for stat values
2. **liquipedia_parsed/items_liquipedia.json** — understand mechanics and abilities

---

## Decision Tree: Which Method?

```
Is there a "pure" reference item?
  |
  YES --> Does it have only this stat?
  |         |
  |         YES --> reference_item (simple)
  |         |
  |         NO --> reference_item + subtract_stats
  |
  NO --> Is it % amplification of another stat?
           |
           YES --> amplification_of
           |
           NO --> Is it a compound mechanic (chance × effect, etc.)?
                   |
                   YES --> Create axiom + custom_stats with formula
                   |        (e.g., crit = chance × (mult-100) → crit_expected_dps axiom)
                   |
                   NO --> Is there an economic equivalent? (see "Economic Equivalents")
                           |
                           YES --> formula referencing equivalent axiom
                           |        (e.g., manacost_reduction ≈ bonus_max_mana_percentage)
                           |
                           NO --> Can you calculate from other axioms or settings?
                                   |
                                   YES --> formula (supports axiom names, settings values, math)
                                   |
                                   NO --> Is the stat value always 0 or meaningless?
                                           |
                                           YES --> Add to ignored_stats (NOT manual with 0)
                                           |
                                           NO --> Can you estimate a value?
                                                   |
                                                   YES --> manual + comment
                                                   |
                                                   NO --> manual + status: unknown
```

---

## Method 1: reference_item (Simple)

**Use when:** Item gives ONLY (or mostly) this stat.

```yaml
# Template
stat_name:
  method: reference_item
  reference_item: item_xxx        # item ID from items_parsed.json
  stat: stat_name_in_item         # stat name as it appears in item
  display_name: "Human Name"
  category: "attributes"          # attributes/hp_mana/offense/defense/utility/caster
  comment: "Item (Xg) gives Y stat -> Zg/point"

# Example: Ogre Axe -> Strength
bonus_strength:
  method: reference_item
  reference_item: item_ogre_axe
  stat: bonus_strength
  display_name: "Strength"
  category: "attributes"
  comment: "Ogre Axe (1000g) gives 10 STR -> 100g/point"
```

---

## Method 1b: reference_item + subtract_stats

**Use when:** Reference item has multiple stats to subtract.

```yaml
# Template
stat_name:
  method: reference_item
  reference_item: item_xxx
  stat: stat_name
  subtract_stats:
    - other_stat_1
    - other_stat_2
  display_name: "Human Name"
  category: "category"
  comment: |
    Item (Xg) minus cost of other stats.
    Remaining / stat_value = gold_per_point.

# Example: Octarine Core -> CDR
bonus_cooldown_reduction:
  method: reference_item
  reference_item: item_octarine_core
  stat: bonus_cooldown_reduction
  subtract_stats:
    - bonus_health
    - bonus_mana
    - bonus_mana_regen_pct
  display_name: "Cooldown Reduction"
  category: "utility"
  comment: |
    Octarine Core (5150g) minus HP/Mana/Regen cost.
    Remaining / 25% CDR = gold per 1% CDR.
```

### WARNING: Double-Counting with subtract_stats

When **multiple stats share the same reference item**, be careful with `subtract_stats`. If stat A subtracts stat B's cost, and stat B also subtracts stat A's cost from the same item — that's circular.

**Safe pattern:** Use `subtract_stats` for one stat, derive the other via `amplification_of` or independent `reference_item`. Example: Kaya has `bonus_intellect`, `spell_amp`, and `mana_regen_multiplier`. We derive `mana_regen_multiplier` via `amplification_of` (independent of Kaya), then subtract both INT and mana_regen_multiplier from Kaya to get `spell_amp`:

```yaml
# mana_regen_multiplier derived independently (not from Kaya)
mana_regen_multiplier:
  method: amplification_of
  base_axiom: bonus_mana_regen
  expected_base_key: mana_regen

# spell_amp subtracts both other stats
spell_amp:
  method: reference_item
  reference_item: item_kaya
  stat: spell_amp
  subtract_stats:
    - bonus_intellect
    - mana_regen_multiplier
  # Result: (2100 - 1600 - 100) / 10 = 10g per 1%
```

**Rule:** Avoid subtracting a stat whose axiom is derived from the same reference item.

---

## Method 1c: reference_item + uptime

**Use when:** Stat is temporary (active ability bonus).

```yaml
# Template
stat_name:
  method: reference_item
  reference_item: item_xxx
  stat: stat_name
  uptime:
    duration_stat: duration_field_name
    cooldown_stat: cooldown_field_name
  display_name: "Human Name"
  category: "category"
  comment: "Uptime = duration / (duration + cooldown)"

# Example: Phase Boots -> Active Movement Speed
phase_movement_speed:
  method: reference_item
  reference_item: item_phase_boots
  stat: phase_movement_speed_range
  uptime:
    duration_stat: phase_duration
    cooldown_stat: AbilityCooldown
  display_name: "Phase Movement Speed"
  category: "utility"
  comment: "Phase active uptime applied. 3s duration / 11s cycle."
```

---

## Method 2: amplification_of

**Use when:** Stat is % amplification of a base stat.

```yaml
# Template
stat_name:
  method: amplification_of
  base_axiom: base_stat_name           # axiom being amplified
  expected_base_key: expected_xxx      # key from settings section
  display_name: "Human Name"
  category: "amplification"

# Example: HP Regen Amplification
hp_regen_amp:
  method: amplification_of
  base_axiom: bonus_health_regen       # 140g/point
  expected_base_key: expected_hp_regen  # 10 HP/s (from settings)
  display_name: "HP Regen Amplification"
  category: "amplification"
  # gold_per_1% = 140 × 10 × 0.01 = 14g
```

---

## Method 3: formula

**Use when:** Stat can be derived from other axioms or settings values.

Formulas can reference:
- Other axiom names (resolved gold_per_point values)
- Settings values from `settings:` section (e.g., `aura_avg_targets`)
- Numbers, operators: `+ - * / ( )`

```yaml
# Template
stat_name:
  method: formula
  formula: "axiom_name * number"    # or "axiom1 + axiom2"
  display_name: "Human Name"
  category: "category"
  comment: "Explain the formula logic"

# Example: Aura stat using settings value
damage_aura:
  method: formula
  formula: "bonus_damage * aura_avg_targets"  # aura_avg_targets comes from settings
  display_name: "Damage Aura"
  category: "aura"

# Example: Same value as another axiom (replaces alias method)
heal_amplification:
  method: formula
  formula: "hp_regen_amp"
  display_name: "Heal Amplification"
  category: "amplification"
  comment: "Same value as hp_regen_amp - heals scale identically"

# Example: Negative mirror of another axiom
aura_negative_armor:
  method: formula
  formula: "aura_positive_armor * -1"
  display_name: "Negative Armor Aura"
  category: "aura"
```

### Key pattern: Economic Equivalents

Many stats that look unique are economically equivalent to existing axioms.
**Before creating a manual axiom, ask: "Is there an existing stat with the same
economic effect?"**

| New stat | Equivalent to | Reasoning |
|----------|--------------|-----------|
| `manacost_reduction` (%) | `bonus_max_mana_percentage` | -25% mana cost = +25% effective mana pool |
| `movespeed_slow` (%) | `bonus_movement_speed_percent` | Slowing enemy = speeding yourself |
| `heal_reduction` (%) | `hp_regen_amp` | Reducing enemy heal = reducing enemy regen (lower bound) |
| `bonus_movement` (flat) | `bonus_movement_speed` | Same stat, different name → use stat_normalization |

**How to apply:**

```yaml
# Instead of hardcoding:
manacost_reduction:
  method: manual
  gold_per_point: 10  # BAD: arbitrary number

# Find the economic equivalent:
manacost_reduction:
  method: formula
  formula: "bonus_max_mana_percentage"  # GOOD: derived from data
  comment: |
    1% mana cost reduction ≈ 1% more effective mana pool (24.96 g/pt).
```

**Decision checklist for new stats:**
1. Does this stat give the same benefit as an existing stat? → `formula: "existing_axiom"`
2. Does it give the opposite effect on enemy? → Same value (slow = speed, heal reduction = regen)
3. Is it % amplification of a base resource? → `amplification_of`
4. Is it a compound of multiple stats? → `custom_stats` with formula
5. None of the above? → `manual` (last resort) or `ignored_stats`

---

## Method 4: manual

**Use when:** No reference available, must estimate.

```yaml
# Template (with value)
stat_name:
  method: manual
  gold_per_point: 12
  display_name: "Human Name"
  category: "category"
  comment: |
    Explanation of how value was estimated.
    Reference: similar stats or game design logic.

# Example: Mana Cost Reduction
manacost_reduction:
  method: manual
  gold_per_point: 12
  display_name: "Mana Cost Reduction"
  category: "caster"
  comment: |
    Unique to Kaya+Sange. No reference item.
    Estimate: similar to spell_amp (~10-15g/point).

# Template (unknown - needs work)
stat_name:
  method: manual
  gold_per_point: 0
  status: unknown
  display_name: "Human Name"
  category: "category"
  question: |
    What needs to be determined?
    Found on: item_name

# Example: Unknown stat
bonus_max_mana_percentage:
  method: manual
  gold_per_point: 0
  status: unknown
  display_name: "Max Mana %"
  category: "hp_mana"
  question: |
    How to value % mana increase?
    Found on: Null Talisman (3%)
```

---

## Game Mechanics Reference

### Stat Stacking Behaviors

Stacking behavior affects reference item choice. Non-stacking stats need careful handling.

| Stat Type | Stacking Behavior | Impact |
|-----------|-------------------|--------|
| Movement Speed (boots) | Highest value only | Use cheapest boots as reference |
| Movement Speed (Wind Lace) | Doesn't stack with itself | Not suitable as reference |
| Magic Resistance | Multiplicative | Cloak is the only pure MR item |
| Evasion | Diminishing (pseudo-random) | Talisman of Evasion is the only pure evasion item |
| Lifesteal | Additive | Physical attacks only |
| Armor, all other stats | Additive | Standard stacking |

### Attribute Derived Stats (Not Counted Separately)

Each attribute provides derived stats automatically. We only count the base attribute, not derived bonuses.

| Attribute | Derived Bonus |
|-----------|---------------|
| +1 STR | +22 HP, +0.1 HP regen |
| +1 AGI | +1 attack speed, +0.17 armor |
| +1 INT | +12 mana, +0.05 mana regen, +0.1% magic resistance |

### Sign Conventions for Slow Stats

Valve uses inconsistent sign conventions:
- `slow_melee: -8`, `cold_slow_melee: -25` — **negative** (reduces enemy speed)
- `movement_slow: 100` (Echo Sabre) — **positive**

Slow axioms use `formula: "-1 * movespeed_slow"` to invert negative values. Result: `(-6) × (-11.11) = +66.67g`.

### Secret Shop Premium

Secret Shop items are more expensive per stat point than basic items. Always use cheaper basic items as references to show the premium in efficiency calculations.

| Reference Item | Stat | Why reference |
|----------------|------|---------------|
| Boots of Speed | Movement Speed | Cheapest boots-based MS |
| Cloak | Magic Resistance | Only pure MR item |
| Ring of Regen | HP Regen | Cheapest pure HP regen |
| Sobi Mask | Mana Regen | Cheapest pure mana regen |

---

## After Adding

```bash
cd src && source venv/bin/activate
python -m pipeline.02_resolve_axioms && python -m pipeline.03_calculate_costs && python -m pipeline.04_generate_output
```

Check `output/effective_costs.json` for items using new axiom.
