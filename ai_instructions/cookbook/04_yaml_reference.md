# YAML Field Reference

Complete field reference for `src/axioms/axiom_rules.yaml`.

## Top-Level Structure

```yaml
version: "1.0"
patch: "7.40c"

settings:
  max_resolution_iterations: 10
  cooldown_efficiency: 0.75
  aura_avg_targets: 1.5
  base_disable_gold: 2000  # CC disable base rate (used by cc_* axioms)
  # ... expected_* values for formulas and amplification

axioms:         # stat pricing definitions
stat_normalization:  # alternative name → canonical axiom name
ignored_stats:  # global ignored stats
excluded_items: # items to exclude from analysis
item_overrides: # per-item special rules
```

---

## Axiom Fields

### Common Fields (All Methods)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | string | **Yes** | `reference_item`, `formula`, `manual`, `amplification_of` |
| `display_name` | string | **Yes** | Human-readable name for tables |
| `category` | string | **Yes** | Grouping category |
| `comment` | string | Yes* | Explanation (*required for manual) |
| `status` | string | No | `unknown` if not yet evaluated |
| `question` | string | No | Question if status is unknown |

### Valid Categories

```yaml
category: "attributes"     # STR, AGI, INT, all_stats
category: "sustain"        # HP, mana, regen
category: "offense"        # damage, attack speed, crit
category: "defense"        # armor, magic resist, evasion
category: "utility"        # move speed, CDR
category: "mobility"       # phase speed, cast range
category: "aura"           # team aura effects
category: "disable"        # stun, hex duration
category: "amplification"  # % amplifications
```

### comment Field Guidelines

**Rules:**
- **DO NOT include calculated numbers** - numbers are shown in Formula column
- **Max 100 characters** - for clean display in tables
- **Explain WHY**, not WHAT - reader can see the values
- **English only** - for consistency

### reference_item Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reference_item` | string | **Yes** | Item ID (e.g., `item_ogre_axe`) |
| `stat` | string | **Yes** | Stat name in this item |
| `subtract_stats` | list | No | Stats to subtract from cost |
| `uptime` | object | No | For temporary bonuses (axiom-level) |

```yaml
# Full reference_item example with uptime
phase_movement_speed:
  method: reference_item
  reference_item: item_phase_boots
  stat: phase_movement_speed
  display_name: "Phase Movement Speed"
  category: mobility
  uptime:
    duration_stat: phase_duration        # stat name for duration
    cooldown_stat: AbilityCooldown       # stat or raw_data field for CD
  comment: |
    Temporary bonus: uptime = duration / (duration + cooldown)
```

**Uptime formula (axiom-level):** `uptime = duration / (duration + cooldown)`.
This is baked into the axiom's gold_per_point, so all items using this axiom
automatically get the discounted value.

### formula Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `formula` | string | **Yes** | Math expression referencing axiom names and/or settings values |

```yaml
# Supported operators: + - * / ( )
# Can reference other axioms and numeric settings values

# Reference another axiom (replaces alias method)
heal_amplification:
  method: formula
  formula: "hp_regen_amp"

# Use settings value
damage_aura:
  method: formula
  formula: "bonus_damage * aura_avg_targets"  # aura_avg_targets from settings

# Negative mirror
aura_negative_armor:
  method: formula
  formula: "aura_positive_armor * -1"
```

### manual Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `gold_per_point` | number | **Yes** | Direct gold value per 1 point of stat |

```yaml
# Standard manual axiom
movespeed_slow:
  method: manual
  gold_per_point: 10
  display_name: "Movement Slow"
  category: offense
  comment: "ASSUMPTION: 300g / 15% / 2s = 10g (Orb of Venom)"

# Axiom for burst resource restore (use with uptime_stats on items)
replenish_amount:
  method: manual
  gold_per_point: 425
  display_name: "Mana Replenish"
  category: aura
  comment: |
    Priced as aura_mana_regen (team mana restore). Use with uptime_stats + cooldown
```

**NOTE:** Prefer `reference_item` or `formula` over `manual` when possible. Stats with gold_per_point=0 should go to `ignored_stats` instead of manual axioms.

### amplification_of Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_axiom` | string | **Yes** | Axiom being amplified |
| `expected_base_key` | string | **Yes** | Key from `settings` (e.g. `expected_hp_regen`) |

```yaml
hp_regen_amp:
  method: amplification_of
  base_axiom: bonus_health_regen
  expected_base_key: expected_hp_regen
  # Formula: base_gold x expected_base x 0.01
```

---

## item_overrides Fields

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | Override display name |
| `comment` | string | General comment |
| `ability_value` | number/string | Gold value of active ability |
| `custom_stats` | object | Computed stats from formulas (see below) |
| `ignored_stats` | object | Stats to ignore for this item |
| `switchable_stats` | object | Stats with multiplier |
| `uptime_stats` | object | Stats with cooldown or manual uptime |
| `abilities` | list | Ability grouping for display |

### ability_value

Three formats supported:

```yaml
# 1. Direct number (hardcoded gold value)
item_ghost:
  ability_value: 937

# 2. Reference to another item's cost (resolved at runtime)
item_blink:
  ability_value: "item_cost:item_blink"
  comment: "100% ability item — cost taken from items_parsed"

# Upgrade items can reference base item cost:
item_overwhelming_blink:
  ability_value: "item_cost:item_blink"
  comment: "Base blink ability from Blink Dagger cost"

# 3. No ability_value — use custom_stats instead (see below)
```

**Prefer `item_cost:` references** over hardcoded numbers. This way prices
auto-update when patch data changes.

### custom_stats (Computed Stats from Formulas)

**Use when:** A compound mechanic combines multiple item stats into one
synthetic stat that maps to an axiom. Instead of hardcoding ability_value,
create an axiom for the mechanic and compute the stat value from item data.

The formula has access to all item stats as variables.

```yaml
# Example: Crit is a compound mechanic (chance × bonus multiplier)
# Step 1: Define axiom for expected DPS increase
# axioms:
#   crit_expected_dps:
#     method: amplification_of
#     base_axiom: bonus_damage        # 50g/pt
#     expected_base_key: attack_damage # 200
#     # Result: 100g per 1% DPS increase

# Step 2: In item_overrides, compute the stat from item data
item_greater_crit:
  custom_stats:
    crit_expected_dps:
      formula: "crit_chance / 100 * (crit_multiplier - 100)"
      comment: "30% × 125% = 37.5% DPS increase"
  abilities:
    - name: "Critical Strike"
      type: passive
      stats:
        - crit_chance
        - crit_multiplier
        - crit_expected_dps  # synthetic stat appears in ability group
```

**How it works:**
1. Pipeline evaluates formula using item's own stats from items_parsed.json
2. Result is injected as a new stat (e.g., `crit_expected_dps = 37.5`)
3. Normal axiom pricing applies: 37.5 × 100g = 3750g
4. Original stats (`crit_chance`, `crit_multiplier`) must be in `ignored_stats`

**Example: CC disable (simple stat pass-through)**

```yaml
# Step 1: Define CC axiom (gold per second of disable)
# axioms:
#   cc_root:
#     method: formula
#     formula: "base_disable_gold * 0.4"
#     category: disable

# Step 2: In item_overrides, pass duration stat through
item_rod_of_atos:
  custom_stats:
    cc_root:
      formula: "duration"            # duration=2.0 from items_parsed.json
      comment: "Cripple root 2.0s"
  abilities:
    - name: "Cripple"
      type: active
      stats:
        - cc_root                    # 2.0 × 400g = 800g
```

**When to use custom_stats vs ability_value:**
- **custom_stats**: Compound mechanics where value depends on item's own stats
  (crit, bash+chance, CC duration, etc.). No hardcoded prices.
- **ability_value**: Pure utility abilities with no stat equivalent
  (Blink teleport, Ghost Form). Use `item_cost:` reference.

### ignored_stats (item-specific)

```yaml
item_xxx:
  ignored_stats:
    stat_name:
      reason: "Why ignored"        # required
      status: unknown              # optional
      question: "What's unclear?"  # optional
```

### switchable_stats

```yaml
item_rapier:
  switchable_stats:
    bonus_damage:
      multiplier: 0.5
      reason: "Physical mode - only one active"
    bonus_spell_amp:
      multiplier: 0.5
      reason: "Spell mode - only one active"
```

### uptime_stats

Three modes of operation:

#### 1. Duration-based (buff with cooldown)

```yaml
# uptime_factor = (duration / cooldown) * cooldown_efficiency
item_mask_of_madness:
  uptime_stats:
    berserk_bonus_attack_speed:
      cooldown_stat: AbilityCooldown     # reads CD from raw_data
      duration_stat: berserk_duration    # reads duration from stats
      reason: "Berserk: +100 AS for 6s / 16s CD"
```

#### 2. Instant effect (no duration)

```yaml
# uptime_factor = (1 / cooldown) * cooldown_efficiency
# Converts burst amount to per-second equivalent
item_dagon:
  uptime_stats:
    damage:
      cooldown_stat: AbilityCooldown
      reason: "Active burst damage on cooldown"
```

#### 3. Manual uptime (toggle/estimate)

```yaml
# uptime_factor = manual_uptime (directly)
item_armlet:
  uptime_stats:
    unholy_bonus_strength:
      manual_uptime: 0.7
      reason: "Unholy Strength toggle: assumed 70% uptime"
```

#### Additional uptime_stats fields

| Field | Type | Description |
|-------|------|-------------|
| `cooldown_stat` | string | Field name for cooldown (usually `AbilityCooldown`) |
| `duration_stat` | string | Field name for duration |
| `manual_uptime` | number | Direct uptime value 0.0-1.0 (for toggles) |
| `stat_as` | string | **Use different axiom** for pricing (see below) |
| `reason` | string | Human-readable explanation |

#### stat_as: Override axiom lookup

When a stat is globally normalized to the wrong axiom, `stat_as` overrides which
axiom is used for pricing. The stat's value is multiplied by the `stat_as` axiom's
gold_per_point instead of the default normalized axiom.

```yaml
# Problem: heal_amount normalizes to bonus_health (4g/point = mana pool)
# But Mekansm's heal is a burst team heal, should be priced as regen
item_mekansm:
  uptime_stats:
    heal_amount:
      cooldown_stat: AbilityCooldown
      stat_as: aura_health_regen       # use 212.5g/point instead of 4g/point
      reason: "250 HP / 50s CD to team. Priced as aura health regen equivalent"
```

**When to use stat_as:**
- Stat has global `stat_normalization` that maps to wrong economic concept
- Example: `heal_amount -> bonus_health` (pool) but should be valued as regen
- The stat exists in items_parsed.json under the original name
- You want the pipeline to price it using a different axiom

### abilities (display grouping)

```yaml
item_arcane_boots:
  abilities:
    - name: "Replenish"
      type: active         # active, passive, aura
      stats:
        - replenish_amount
        - replenish_radius
    - name: "Basilius Aura"
      type: aura
      stats:
        - aura_mana_regen
        - aura_radius
    - name: "Passive Stats"
      type: passive
      stats:
        - bonus_movement
        - mana_regen
```

---

## ignored_stats (Global)

Global ignored_stats contains ~21 stats that are common ability parameters (3+ items).
All other ignored stats are item-specific in `item_overrides`.

```yaml
ignored_stats:
  global:
    radius: { reason: "Generic ability radius parameter" }
    duration: { reason: "Generic ability duration" }
    aura_radius: { reason: "Area of effect radius for aura abilities" }
    max_charges: { reason: "Maximum charge capacity" }
    # ... ~21 stats total
```

**Rules:**
- Global: only stats used by 3+ items (common ability parameters like radius, duration)
- Item-specific: all other ignored stats go into `item_overrides.{item}.ignored_stats`
- Stats in `uptime_stats` must NOT be in `ignored_stats` for that item
- If a stat needs to be ignored for some items but priced for others, use item-specific
  `ignored_stats` only on the items where it should be ignored

---

## excluded_items

```yaml
excluded_items:
  patterns:
    - pattern: "^item_recipe_"
      reason: "Recipe items"

  items:
    item_aegis:
      reason: "Special drop"
```

---

## stat_normalization

Maps alternative stat names to canonical axiom names.

```yaml
stat_normalization:
  # Attributes
  bonus_str: bonus_strength
  bonus_agi: bonus_agility
  bonus_int: bonus_intellect

  # HP/Mana
  bonus_hp: bonus_health
  mana: bonus_mana
  heal_amount: bonus_health        # CAUTION: wrong for burst heals, use stat_as

  # Movement
  movement_speed: bonus_movement_speed

  # Regen
  mana_regen: bonus_mana_regen
  hp_regen: bonus_health_regen
```

**CAUTION:** Some normalizations map stats to wrong economic concepts.
Example: `heal_amount -> bonus_health` treats burst heal as permanent HP pool.
For burst heals with cooldown, use `uptime_stats` with `stat_as` to override.

---

## Available Penalty Axioms

- `penalty_armor` (-137.5 g/pt)
- `penalty_health_regen` (-140 g/pt)
