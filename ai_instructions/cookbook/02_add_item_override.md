# How to Add Item Override

> See also: [04_yaml_reference.md](04_yaml_reference.md) for field details.

## When to Use item_overrides

| Situation | Use |
|-----------|-----|
| Pure ability item (Blink) | `ability_value` |
| Burst heal/mana to team (Mekansm, Arcane Boots) | `uptime_stats` with `cooldown_stat` (+ `stat_as` if needed) |
| Burst damage (Dagon) | `uptime_stats` with `cooldown_stat` |
| Temporary buff with duration (MoM, Silver Edge) | `uptime_stats` with `cooldown_stat` + `duration_stat` |
| Toggle ability (Armlet) | `uptime_stats` with `manual_uptime` |
| Penalty during active (MoM armor, Armlet drain) | `uptime_stats` with `stat_as: penalty_*` axiom |
| CC disable (stun, root, silence, hex, cyclone) | `custom_stats` with `cc_*` axiom |
| Compound mechanic (crit, bash) | `custom_stats` with axiom |
| Switchable modes (Rapier, Power Treads) | `switchable_stats` |
| Stats to ignore for this item | `ignored_stats` |

**IMPORTANT:** `custom_stats` naming — the custom_stat key must either match an existing axiom name exactly (e.g. `cc_root`), OR have a `stat_normalization` entry mapping it to an axiom. The `axiom` field inside custom_stats is NOT used by the pipeline for pricing lookup.

---

## Decision Tree: How to Value an Active Ability

```
Does the item have an active ability?
├── No → Just check passive stats have axioms
└── Yes → Does the ability have a measurable stat in items_parsed.json?
    ├── No (pure ability, e.g. Blink, BKB)
    │   └── Use ability_value (residual or manual estimate)
    └── Yes → Is the stat already priced by an axiom?
        ├── Yes, but wrong axiom (e.g. heal_amount → bonus_health)
        │   └── Use uptime_stats + stat_as to override the axiom
        ├── Yes, correct axiom exists
        │   └── Use uptime_stats with cooldown_stat
        ├── No axiom, but it's a CC disable (stun/root/silence/hex/cyclone)
        │   └── Use custom_stats with cc_* axiom (see CC Disable pattern below)
        └── No axiom exists
            └── Create manual axiom, then use uptime_stats
```

---

## Pattern: Burst Resource Restore to Team

**Items:** Arcane Boots (mana), Mekansm (HP), Guardian Greaves (both)

These items give a burst of resource (HP/mana) to nearby allies on cooldown.
The value comes from the equivalent regen rate, priced as an aura effect.

### Math

```
equivalent_regen = burst_amount / cooldown
gold_value = burst_amount * aura_regen_axiom * (1 / cooldown)
```

### Case A: Stat has its own axiom (Arcane Boots)

`replenish_amount` is not globally normalized — it has its own axiom (425g/point,
same as `aura_mana_regen`). Just add `uptime_stats` with cooldown.

```yaml
# Axiom (already exists):
replenish_amount:
  method: manual
  gold_per_point: 425          # same as aura_mana_regen
  display_name: "Mana Replenish"
  category: aura

# Item override:
item_arcane_boots:
  uptime_stats:
    replenish_amount:
      cooldown_stat: AbilityCooldown
      reason: "150 mana / 55s CD to team. Priced as aura regen equivalent"
  # Result: 150 * 425 * (1/55) = 1159g
```

**Why it works:** `replenish_amount` is not in `ignored_stats` for Arcane Boots (only
ignored for consumables like Mango via item-specific ignored_stats). The axiom's
gold_per_point (425) matches `aura_mana_regen` because replenish is a team effect.

### Case B: Stat normalizes to wrong axiom (Mekansm)

`heal_amount` globally normalizes to `bonus_health` (4g/point = HP pool).
But Mekansm's heal is a burst team heal — should be priced as aura HP regen (212.5g/point).
Use `stat_as` to override the axiom lookup.

```yaml
item_mekansm:
  uptime_stats:
    heal_amount:
      cooldown_stat: AbilityCooldown
      stat_as: aura_health_regen     # override: use 212.5 instead of 4
      reason: "250 HP / 50s CD to team. Priced as aura health regen equivalent"
  # Result: 250 * 212.5 * (1/50) = 1062.5g
```

**Why stat_as is needed:** Without it, the pipeline normalizes `heal_amount` →
`bonus_health` → gold_per_point = 4.0, giving: 250 * 4.0 * (1/50) = 20g — wrong.

### Choosing between personal and aura regen axiom

| Effect target | HP axiom | Mana axiom |
|--------------|----------|------------|
| Self only | `bonus_health_regen` (140g) | `bonus_mana_regen` (250g) |
| Team (AoE) | `aura_health_regen` (212.5g) | `aura_mana_regen` (425g) |

---

## CC Disable Pattern (Stun, Root, Silence, Hex, Cyclone)

**Use when:** Item has a CC ability with a duration stat in items_parsed.json.

CC axioms (`cc_hex`, `cc_stun`, `cc_silence`, `cc_root`, `cc_cyclone`) provide
gold_per_second of disable, computed from `base_disable_gold` setting.

Use `custom_stats` with formula `duration / sqrt(AbilityCooldown)`:

```yaml
item_rod_of_atos:
  custom_stats:
    cc_root:
      formula: "duration / sqrt(AbilityCooldown)"
      comment: "Cripple root 2.0s"
```

The custom_stat name `cc_root` matches the axiom name directly, so no stat_normalization needed.

**Available CC axioms** (base_disable_gold=2000):

| Axiom | Coefficient | Gold/normalized-sec | Best for |
|-------|-------------|---------------------|----------|
| `cc_hex` | 1.0 | 2000 | Scythe of Vyse |
| `cc_stun` | 0.8 | 1600 | Skull Basher |
| `cc_silence` | 0.6 | 1200 | Orchid, Bloodthorn |
| `cc_root` | 0.4 | 800 | Rod of Atos, Gleipnir |
| `cc_cyclone` | 0.3 | 600 | Eul's, Wind Waker |

**Duration stat name varies by item** — check items_parsed.json:
- `duration` (Rod of Atos, Gleipnir)
- `silence_duration` (Orchid, Bloodthorn)
- `cyclone_duration` (Eul's, Wind Waker)
- `sheep_duration` (Scythe of Vyse — already priced via sheep_duration axiom)

---

## ability_value (Pure Ability Items)

**Use when:** Item has no measurable stats for the ability, value is from the ability itself.

```yaml
# 100% ability item
item_blink:
  ability_value: 2250
  comment: "Blink is 100% ability. 2250g = ability cost."

# Residual method: ability_value = real_cost - sum(stat_values)
item_force_staff:
  ability_value: 780
  comment: "Force push. Residual: 2200 - 1420 stats."

# Cannot value universally
item_refresher:
  ability_value: 0
  comment: "Value depends on hero ultimate."
```

---

## uptime_stats (Temporary Bonuses)

See [04_yaml_reference.md](04_yaml_reference.md#uptime_stats) for all fields.

### Duration buff with cooldown

```yaml
item_mask_of_madness:
  uptime_stats:
    berserk_bonus_attack_speed:
      cooldown_stat: AbilityCooldown
      duration_stat: berserk_duration
      reason: "Berserk: +100 AS for 6s / 16s CD"
    berserk_armor_reduction:
      cooldown_stat: AbilityCooldown
      duration_stat: berserk_duration
      stat_as: penalty_armor              # penalty: use negative g/pt axiom
      reason: "Berserk penalty: -8 armor for 6s / 16s CD"
```

### Instant burst damage

```yaml
item_dagon:
  uptime_stats:
    damage:
      cooldown_stat: AbilityCooldown
      reason: "Active burst damage on cooldown"
  # 400 * 4.0 * (1/27) = 59g
```

### Toggle with estimated uptime

```yaml
item_armlet:
  uptime_stats:
    unholy_bonus_strength:
      manual_uptime: 0.7
      reason: "Unholy Strength toggle: assumed 70% uptime"
```

---

## switchable_stats (Switchable Modes)

**Use when:** Item has mutually exclusive modes or melee/ranged variants.

```yaml
item_rapier:
  switchable_stats:
    bonus_damage:
      multiplier: 0.5
      reason: "Physical mode - 50% weight"
    bonus_spell_amp:
      multiplier: 0.5
      reason: "Spell mode - 50% weight"
```

---

## ignored_stats (Item-Specific)

**Use when:** Stat should be ignored only for this item.

```yaml
item_overwhelming_blink:
  ability_value: 2250
  ignored_stats:
    blink_range:
      reason: "Ability parameter"
    movement_slow:
      reason: "Ability effect, not stat"
```

---

## Pattern: Charge-Based Abilities (Urn, Holy Locket)

**Use when:** Item has charges that grant burst heal/damage/mana.

Charge-based items have limited availability compared to cooldown-only items.
Use a **charge coefficient** (typically 0.3) to discount the value.

```yaml
# Urn of Shadows: 2 charges, heals 240 total or damages 200 total
item_urn_of_shadows:
  custom_stats:
    urn_burst:
      formula: "(heal_total + dmg_total) / 2 * 0.3"
      comment: "Charge-based heal/damage, 0.3 availability coefficient"
# In stat_normalization:
#   urn_burst: damage    # maps to damage axiom (4 g/pt)
```

**Coefficient 0.3** reflects: charges are earned from kills (not guaranteed), and
you can't use them freely like cooldown abilities.

---

## Pattern: DoT via duration_stat (Orb of Venom)

**Use when:** Item deals damage per second with a fixed duration (no cooldown).

Use `uptime_stats` with `duration_stat` but **no `cooldown_stat`**. The pipeline
multiplies gold value by the duration instead of calculating uptime.

```yaml
# Orb of Venom: 10 DPS × 3 seconds = 30 total damage
item_orb_of_venom:
  uptime_stats:
    damage:
      duration_stat: poison_duration    # multiplier: × 3
      reason: "10 DPS × 3s = 30 total. Priced via damage axiom × duration"
  # Result: 10 × 4 g/pt × 3 = 120g
```

---

## Pattern: Self-Penalty with Discount (Mask of Madness)

**Use when:** Active ability imposes a penalty on the user (silence, armor loss).

Self-penalties use existing axioms (e.g., `cc_silence`) with a **discount factor**
(typically 0.5) because the player controls when to activate.

```yaml
item_mask_of_madness:
  custom_stats:
    cc_silence:
      formula: "-0.5 * berserk_duration / sqrt(AbilityCooldown)"
      comment: "Self-silence during Berserk. 0.5 discount: player-controlled timing"
  # -0.5 × 6 / sqrt(16) = -0.75 → -0.75 × 1200 g/pt = -900g
```

**Why 0.5 discount:** Player chooses when to activate, can pre-cast spells, BKB
pierces self-silence. Enemy CC is more impactful.

---

## After Adding

```bash
cd src && source venv/bin/activate
python -m pipeline.02_resolve_axioms && python -m pipeline.03_calculate_costs && python -m pipeline.04_generate_output
```

Check the item in `output/effective_costs.json`.
