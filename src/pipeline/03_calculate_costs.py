"""
Calculate effective cost of Dota 2 items.
Uses axioms from axiom_rules.yaml and calculated_axioms.json.

This script:
1. Loads parsed items
2. Loads calculated axioms (gold_per_point values)
3. Loads rules (ignored_stats, item_overrides)
4. Applies axioms to calculate effective cost
5. Outputs comparison table and statistics
"""

import json
import logging
import math
import sys
from pathlib import Path

# Disable .pyc cache to avoid stale bytecode issues after refactoring
sys.dont_write_bytecode = True

from typing import Any

logger = logging.getLogger(__name__)

from axioms.loader import (
    AxiomRules,
    ItemOverride,
    load_axiom_rules,
    normalize_stat_name,
)
from common.formatting import format_calc_str

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output"
ITEMS_FILE = OUTPUT_PATH / "items_parsed.json"
CALCULATED_AXIOMS_FILE = OUTPUT_PATH / "calculated_axioms.json"


def _get_item_field_value(item: dict[str, Any], field_name: str) -> float:
    """
    Get a numeric value from item data by field name.

    Searches in: stats, then raw_data.
    Handles space-separated level values (e.g. "27 24 21 18 15")
    by selecting the value at the item's base level index.
    """
    if not field_name:
        return 0.0

    stats = item.get("stats", {})
    raw_data = item.get("raw_data", {})

    # Try stats first, then raw_data
    raw_value = stats.get(field_name, raw_data.get(field_name))
    if raw_value is None:
        return 0.0

    # Already a number
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    # Space-separated string (level values like "27 24 21 18 15")
    if isinstance(raw_value, str) and " " in raw_value.strip():
        parts = raw_value.strip().split()
        base_level = int(raw_data.get("ItemBaseLevel", 1))
        idx = max(0, min(base_level - 1, len(parts) - 1))
        try:
            return float(parts[idx])
        except (ValueError, IndexError):
            return 0.0

    # Single string value
    try:
        return float(raw_value)
    except (ValueError, TypeError):
        return 0.0


def load_calculated_axioms() -> dict[str, Any]:
    """Load calculated axioms from JSON file."""
    with open(CALCULATED_AXIOMS_FILE, "r", encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def is_stat_ignored(
    stat_name: str, rules: AxiomRules, item_name: str | None = None
) -> tuple[bool, str]:
    """
    Check if a stat should be ignored.

    Checks:
    1. Global ignored_stats (all categories)
    2. Item-specific ignored_stats from item_overrides

    Returns:
        (is_ignored, reason)
    """
    # Check item-specific ignored stats first
    if item_name and item_name in rules.item_overrides:
        override = rules.item_overrides[item_name]
        if stat_name in override.ignored_stats:
            reason = override.ignored_stats[stat_name].reason or "Item-specific exclusion"
            return True, reason

    # Check global ignored_stats (all categories)
    for category, stats in rules.ignored_stats.items():
        if stat_name in stats:
            return True, stats[stat_name].reason

    return False, ""


def calculate_stat_value(
    stat_name: str,
    value: float,
    item_name: str,
    axioms_data: dict[str, Any],
    rules: AxiomRules,
    override_axiom: str | None = None,
    item_stats: dict[str, Any] | None = None,
    skip_chance: bool = False,
) -> tuple[float, str, dict[str, Any] | None]:
    """
    Calculate gold value of a stat.

    Args:
        override_axiom: If set, use this axiom key instead of normalized stat name
        item_stats: Item's stats dict, used for chance_stat auto-apply
        skip_chance: If True, skip chance_stat auto-apply (when uptime_stats handles it)

    Returns:
        (gold_value, calculation_note, breakdown_entry or None)
    """
    # Check if stat is ignored (before normalization!)
    # This prevents ability-specific stats from being mapped to priced stats
    is_ignored, ignore_reason = is_stat_ignored(stat_name, rules, item_name)
    if is_ignored:
        return 0, f"ignored ({ignore_reason})", None

    # Normalize stat name using rules
    normalized = normalize_stat_name(stat_name, rules)

    # Check again after normalization
    is_ignored, ignore_reason = is_stat_ignored(normalized, rules, item_name)
    if is_ignored:
        return 0, f"ignored ({ignore_reason})", None

    # Look up axiom in calculated_axioms
    axioms = axioms_data.get("axioms", {})

    # Use override_axiom if provided (stat_as from uptime_stats)
    lookup_key = override_axiom or normalized

    if lookup_key in axioms:
        axiom = axioms[lookup_key]
        gold_per_point = axiom.get("gold_per_point", 0)

        if gold_per_point == 0:
            return 0, f"zero value axiom ({normalized})", None

        gold_value = value * gold_per_point

        # Auto-apply chance_stat: multiply by item's chance/100
        chance_factor = None
        chance_stat_name = axiom.get("chance_stat")
        if chance_stat_name and item_stats and not skip_chance:
            chance_pct = float(item_stats.get(chance_stat_name, 0))
            if chance_pct > 0:
                chance_factor = chance_pct / 100.0
                gold_value *= chance_factor

        if chance_factor is not None:
            note = f"{value} x {gold_per_point:.2f} x {chance_factor:.2f} = {gold_value:.1f}g"
        else:
            note = f"{value} x {gold_per_point:.2f} = {gold_value:.1f}g"

        breakdown = {
            "stat": stat_name,
            "normalized_stat": normalized,
            "amount": value,
            "gold_per_point": gold_per_point,
            "total_value": round(gold_value, 2),
            "display_name": axiom.get("display_name", normalized),
            "calc_str": format_calc_str(value, gold_per_point, chance_factor=chance_factor),
        }
        if chance_factor is not None:
            breakdown["chance_factor"] = chance_factor

        return gold_value, note, breakdown

    # Unknown stat
    return (
        0,
        f"unknown stat '{stat_name}' (normalized: '{normalized}', lookup: '{lookup_key}')",
        None,
    )


def group_stat_breakdown(
    item: dict[str, Any],
    stat_breakdown: list[dict[str, Any]],
    item_override,  # ItemOverride | None
    axioms_data: dict[str, Any],
    rules: AxiomRules,
    ignored_stats_collected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Group flat stat_breakdown into hierarchical stat_groups.

    Reads ability structure from item_override.abilities.
    Falls back to auto-detection if no abilities defined.

    Returns list of group dicts, each with:
      group_name, group_type, total_value, stats[],
      and optionally cooldown/duration for active abilities.
    """
    groups = []

    # Build a lookup from stat name to breakdown entry
    stat_lookup = {}
    for entry in stat_breakdown:
        stat_name = entry.get("stat", "")
        stat_lookup[stat_name] = entry

    # Check if item has explicit abilities defined
    has_abilities = (
        item_override and hasattr(item_override, "abilities") and item_override.abilities
    )

    if has_abilities:
        # Explicit mode: use abilities from YAML
        claimed_stats = set()
        for ability in item_override.abilities:
            claimed_stats.update(ability.stats)

        # 1. Passive "Stats" group: all stats NOT claimed by any ability
        #    Also exclude ability_value and drop_risk (they're special)
        special_stats = {"ability_value", "drop_risk"}
        passive_stats = [
            entry
            for entry in stat_breakdown
            if entry["stat"] not in claimed_stats and entry["stat"] not in special_stats
        ]
        if passive_stats:
            groups.append(
                {
                    "group_name": "Stats",
                    "group_type": "passive",
                    "total_value": round(sum(s["total_value"] for s in passive_stats), 2),
                    "stats": passive_stats,
                }
            )

        # 2. For each ability
        for ability in item_override.abilities:
            ability_stats = [stat_lookup[s] for s in ability.stats if s in stat_lookup]

            # Add info entries for ability stats that are globally ignored
            # These stats exist in the item's raw data but aren't priced
            item_stats = item.get("stats", {})
            for stat_name in ability.stats:
                if stat_name not in stat_lookup and stat_name in item_stats:
                    # This stat was globally ignored — add as info entry
                    raw_value = item_stats[stat_name]
                    # Format display name from stat_name
                    display_name = stat_name.replace("_", " ").title()
                    ability_stats.append(
                        {
                            "stat": stat_name,
                            "display_name": display_name,
                            "amount": raw_value,
                            "total_value": 0,
                            "type": "info",
                            "note": "Ability parameter (not priced)",
                        }
                    )

            group = {
                "group_name": ability.name,
                "group_type": ability.type,
                "total_value": round(sum(s["total_value"] for s in ability_stats), 2),
                "stats": ability_stats,
            }

            # For active abilities: resolve cooldown/duration display values
            if ability.type == "active" and item_override.uptime_stats:
                for stat_name in ability.stats:
                    if stat_name in item_override.uptime_stats:
                        uptime_cfg = item_override.uptime_stats[stat_name]
                        cooldown_val = _get_item_field_value(item, uptime_cfg.cooldown_stat)
                        duration_val = _get_item_field_value(item, uptime_cfg.duration_stat)
                        if cooldown_val > 0:
                            group["cooldown"] = cooldown_val
                        if duration_val > 0:
                            group["duration"] = duration_val
                        break  # Use first matching uptime entry

            # For ability with empty stats but item has ability_value
            if not ability_stats and item_override and item_override.ability_value:
                if "ability_value" in stat_lookup:
                    group["stats"] = [stat_lookup["ability_value"]]
                    group["total_value"] = stat_lookup["ability_value"]["total_value"]

            # Always add groups for YAML-defined abilities (even if empty/zero)
            # This ensures abilities like Ethereal Blade's "Ether Blast" appear
            groups.append(group)

        # 3. If ability_value exists and not claimed by any ability group
        if "ability_value" in stat_lookup:
            av_claimed = any(
                "ability_value" in [s.get("stat") for s in g.get("stats", [])] for g in groups
            )
            if not av_claimed:
                groups.append(
                    {
                        "group_name": "Active Ability",
                        "group_type": "active",
                        "total_value": stat_lookup["ability_value"]["total_value"],
                        "stats": [stat_lookup["ability_value"]],
                    }
                )

        # 4. Drop risk (if present)
        if "drop_risk" in stat_lookup:
            groups.append(
                {
                    "group_name": "Drop Risk",
                    "group_type": "risk",
                    "total_value": stat_lookup["drop_risk"]["total_value"],
                    "stats": [stat_lookup["drop_risk"]],
                }
            )

    else:
        # Fallback auto-detection mode (no abilities key in YAML)
        axioms = axioms_data.get("axioms", {})

        active_stats = []
        aura_stats = []
        passive_stats = []
        special_entries = []

        for entry in stat_breakdown:
            stat_name = entry.get("stat", "")

            if stat_name in ("ability_value", "drop_risk"):
                special_entries.append(entry)
                continue

            # Check if stat has uptime_factor -> active ability
            if entry.get("uptime_factor") is not None:
                active_stats.append(entry)
                continue

            # Check if stat's axiom has category: aura
            normalized = entry.get("normalized_stat", stat_name)
            axiom_data = axioms.get(normalized, {})
            if axiom_data.get("category") == "aura":
                aura_stats.append(entry)
                continue

            passive_stats.append(entry)

        # Build groups
        if passive_stats:
            groups.append(
                {
                    "group_name": "Stats",
                    "group_type": "passive",
                    "total_value": round(sum(s["total_value"] for s in passive_stats), 2),
                    "stats": passive_stats,
                }
            )

        if active_stats:
            group = {
                "group_name": "Active Ability",
                "group_type": "active",
                "total_value": round(sum(s["total_value"] for s in active_stats), 2),
                "stats": active_stats,
            }
            # Try to resolve cooldown/duration from first uptime stat
            if item_override and item_override.uptime_stats:
                for entry in active_stats:
                    stat_name = entry.get("stat", "")
                    if stat_name in item_override.uptime_stats:
                        uptime_cfg = item_override.uptime_stats[stat_name]
                        cooldown_val = _get_item_field_value(item, uptime_cfg.cooldown_stat)
                        duration_val = _get_item_field_value(item, uptime_cfg.duration_stat)
                        if cooldown_val > 0:
                            group["cooldown"] = cooldown_val
                        if duration_val > 0:
                            group["duration"] = duration_val
                        break
            groups.append(group)

        if aura_stats:
            groups.append(
                {
                    "group_name": "Aura",
                    "group_type": "aura",
                    "total_value": round(sum(s["total_value"] for s in aura_stats), 2),
                    "stats": aura_stats,
                }
            )

        # ability_value
        for entry in special_entries:
            if entry["stat"] == "ability_value":
                groups.append(
                    {
                        "group_name": "Active Ability",
                        "group_type": "active",
                        "total_value": entry["total_value"],
                        "stats": [entry],
                    }
                )
            elif entry["stat"] == "drop_risk":
                groups.append(
                    {
                        "group_name": "Drop Risk",
                        "group_type": "risk",
                        "total_value": entry["total_value"],
                        "stats": [entry],
                    }
                )

    # 5. Ignored stats group
    if ignored_stats_collected:
        ignored_entries = []
        for ign in ignored_stats_collected:
            ignored_entries.append(
                {
                    "stat": ign["stat"],
                    "display_name": ign["stat"],
                    "amount": ign.get("value", 0),
                    "total_value": 0,
                    "reason": ign.get("reason", ""),
                }
            )
        if ignored_entries:
            groups.append(
                {
                    "group_name": "Ignored",
                    "group_type": "ignored",
                    "total_value": 0,
                    "stats": ignored_entries,
                }
            )

    return groups


def _apply_custom_stats(
    stats: dict[str, Any],
    item: dict[str, Any],
    item_override: ItemOverride | None,
    rules: AxiomRules,
) -> dict[str, Any]:
    """Inject custom_stats: evaluate formulas from item stats, add as synthetic stats."""
    if not (item_override and item_override.custom_stats):
        return stats

    stats = dict(stats)  # avoid mutating original
    for cs_name, cs_config in item_override.custom_stats.items():
        if cs_config.formula:
            namespace: dict[str, Any] = {k: float(v) for k, v in stats.items()}
            raw_data = item.get("raw_data", {})
            for k, v in raw_data.items():
                if k not in namespace:
                    try:
                        namespace[k] = float(v)
                    except (ValueError, TypeError):
                        pass
            namespace["sqrt"] = math.sqrt
            for sk, sv in rules.settings.items():
                if sk not in namespace:
                    try:
                        namespace[sk] = float(sv)
                    except (ValueError, TypeError):
                        pass
            cs_value = float(eval(cs_config.formula, {"__builtins__": {}}, namespace))
            stats[cs_name] = cs_value
    return stats


def _apply_switchable_multiplier(
    gold_value: float,
    note: str,
    breakdown: dict[str, Any] | None,
    stat_name: str,
    item_override: ItemOverride | None,
) -> tuple[float, str]:
    """Apply multiplier for switchable stats (e.g., Rapier physical/spell modes)."""
    if not (item_override and stat_name in item_override.switchable_stats):
        return gold_value, note

    switch_config = item_override.switchable_stats[stat_name]
    multiplier = switch_config.multiplier
    gold_value *= multiplier
    note += f" x {multiplier} (switchable mode)"
    if breakdown:
        breakdown["multiplier"] = multiplier
        breakdown["total_value"] = round(gold_value, 2)
        breakdown["switchable_reason"] = switch_config.reason
        breakdown["calc_str"] = format_calc_str(
            breakdown["amount"],
            breakdown["gold_per_point"],
            multiplier=multiplier,
            chance_factor=breakdown.get("chance_factor"),
        )
    return gold_value, note


def _apply_uptime_factor(
    gold_value: float,
    note: str,
    breakdown: dict[str, Any] | None,
    stat_name: str,
    item: dict[str, Any],
    item_override: ItemOverride | None,
    rules: AxiomRules,
) -> tuple[float, str]:
    """Apply uptime for cooldown-based stats (active abilities).

    Reads cooldown/duration from item data fields (not hardcoded).
    Instant effects (no duration): factor = 1 / cooldown
    Duration buffs: factor = duration / cooldown
    """
    if not (item_override and stat_name in item_override.uptime_stats):
        return gold_value, note

    uptime_config = item_override.uptime_stats[stat_name]
    cooldown = _get_item_field_value(item, uptime_config.cooldown_stat)
    duration = _get_item_field_value(item, uptime_config.duration_stat)
    cd_efficiency = rules.settings.get("cooldown_efficiency", 1.0)

    if cooldown > 0:
        if duration > 0:
            uptime_factor = (duration / cooldown) * cd_efficiency
        else:
            uptime_factor = (1.0 / cooldown) * cd_efficiency
        gold_value *= uptime_factor
        note += f" x {uptime_factor:.4f} (uptime: CD={cooldown}s)"
        if breakdown:
            breakdown["uptime_factor"] = round(uptime_factor, 6)
            breakdown["total_value"] = round(gold_value, 2)
            breakdown["uptime_reason"] = uptime_config.reason
            breakdown["calc_str"] = format_calc_str(
                breakdown["amount"],
                breakdown["gold_per_point"],
                uptime_factor=uptime_factor,
                multiplier=breakdown.get("multiplier"),
                chance_factor=breakdown.get("chance_factor"),
            )
    elif duration > 0:
        # duration_stat without cooldown: multiply by duration directly
        # Use case: DoT damage = DPS × duration (e.g. Orb of Venom)
        gold_value *= duration
        note += f" x {duration} ({uptime_config.duration_stat})"
        if breakdown:
            breakdown["duration_multiplier"] = duration
            breakdown["total_value"] = round(gold_value, 2)
            breakdown["calc_str"] = format_calc_str(
                breakdown["amount"],
                breakdown["gold_per_point"],
                multiplier=duration,
            )
    elif uptime_config.manual_uptime is not None:
        # Fallback: manual_uptime for toggle abilities (Armlet)
        uptime_factor = uptime_config.manual_uptime
        gold_value *= uptime_factor
        note += f" x {uptime_factor:.4f} (manual uptime)"
        if breakdown:
            breakdown["uptime_factor"] = round(uptime_factor, 6)
            breakdown["total_value"] = round(gold_value, 2)
            breakdown["uptime_reason"] = uptime_config.reason
            breakdown["calc_str"] = format_calc_str(
                breakdown["amount"],
                breakdown["gold_per_point"],
                uptime_factor=uptime_factor,
                multiplier=breakdown.get("multiplier"),
                chance_factor=breakdown.get("chance_factor"),
            )

    return gold_value, note


def calculate_effective_cost(
    item: dict[str, Any],
    axioms_data: dict[str, Any],
    rules: AxiomRules,
    items_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Calculate effective cost of an item.

    Returns:
        Dict with calculation results
    """
    item_name = item["id"]
    real_cost = item["cost"]
    stats = item.get("stats", {})

    # Get item override if exists
    item_override = rules.item_overrides.get(item_name)

    total_effective = 0.0
    stat_breakdown = []
    unpriceable_stats = []
    calculation_trace = []
    ignored_stats_collected = []

    # Inject custom_stats: evaluate formulas from item stats, add as synthetic stats
    stats = _apply_custom_stats(stats, item, item_override, rules)

    for stat_name, raw_value in stats.items():
        value = raw_value

        # Check for stat_as override (use different axiom for pricing)
        override_axiom = None
        skip_chance = False
        if item_override and stat_name in item_override.uptime_stats:
            uptime_cfg = item_override.uptime_stats[stat_name]
            override_axiom = uptime_cfg.stat_as
            # If uptime_stats has manual_uptime for this stat, skip chance auto-apply
            # (the override handles chance differently)
            if uptime_cfg.manual_uptime is not None:
                skip_chance = True

        gold_value, note, breakdown = calculate_stat_value(
            stat_name,
            value,
            item_name,
            axioms_data,
            rules,
            override_axiom=override_axiom,
            item_stats=stats,
            skip_chance=skip_chance,
        )

        # Apply multiplier for switchable stats (e.g., Rapier physical/spell modes)
        gold_value, note = _apply_switchable_multiplier(
            gold_value, note, breakdown, stat_name, item_override
        )

        # Apply uptime for cooldown-based stats (active abilities)
        gold_value, note = _apply_uptime_factor(
            gold_value, note, breakdown, stat_name, item, item_override, rules
        )

        # Capture ignored stats (both global and item-specific)
        if breakdown is None and "ignored" in note:
            reason = note.replace("ignored (", "").rstrip(")")
            ignored_stats_collected.append(
                {"stat": stat_name, "value": raw_value, "reason": reason}
            )

        # Include all stats with breakdown (positive, negative, or zero)
        # This ensures penalty stats and zero-value uptime stats appear
        if gold_value != 0 or breakdown:
            if gold_value != 0:
                total_effective += gold_value
            if breakdown:
                stat_breakdown.append(breakdown)
            calculation_trace.append(
                {
                    "stat": stat_name,
                    "value": value,
                    "gold_value": round(gold_value, 2),
                    "note": note,
                }
            )
        elif "unknown" in note:
            unpriceable_stats.append({"stat": stat_name, "value": value, "note": note})
        elif "ignored" not in note and "zero value" not in note:
            calculation_trace.append(
                {"stat": stat_name, "value": value, "gold_value": 0, "note": note}
            )

    # Add ability value for ability items (e.g., Blink Dagger)
    # Resolve ability_value: direct number, item_cost reference, or formula
    resolved_ability_value = None
    if item_override:
        if item_override.ability_value:
            resolved_ability_value = item_override.ability_value
        elif item_override.ability_value_ref and items_by_id:
            ref_item = items_by_id.get(item_override.ability_value_ref)
            if ref_item:
                resolved_ability_value = float(ref_item["cost"])
        elif item_override.ability_value_formula:
            namespace2: dict[str, Any] = {k: float(v) for k, v in stats.items()}
            if "raw_data" in item:
                for k, v in item["raw_data"].items():
                    if k not in namespace2:
                        try:
                            namespace2[k] = float(v)
                        except (ValueError, TypeError):
                            pass
            namespace2["sqrt"] = math.sqrt
            for sk, sv in rules.settings.items():
                if sk not in namespace2:
                    try:
                        namespace2[sk] = float(sv)
                    except (ValueError, TypeError):
                        pass
            resolved_ability_value = float(
                eval(item_override.ability_value_formula, {"__builtins__": {}}, namespace2)
            )

    if resolved_ability_value:
        ability_value = resolved_ability_value
        total_effective += ability_value
        stat_breakdown.append(
            {
                "stat": "ability_value",
                "normalized_stat": "ability_value",
                "amount": 1,
                "gold_per_point": ability_value,
                "total_value": ability_value,
                "display_name": "Active Ability",
            }
        )
        calculation_trace.append(
            {
                "stat": "ability_value",
                "value": 1,
                "gold_value": ability_value,
                "note": f"Active ability worth {ability_value}g ({item_override.comment if item_override else ''})",
            }
        )

    # Account for drop on death risk
    drops_on_death = item.get("drops_on_death", False)
    drop_risk = 0.0
    if drops_on_death:
        drop_risk = real_cost  # Risk = item cost
        stat_breakdown.append(
            {
                "stat": "drop_risk",
                "normalized_stat": "drop_risk",
                "amount": -1,
                "gold_per_point": real_cost,
                "total_value": -drop_risk,
                "display_name": "Drop Risk",
            }
        )
        calculation_trace.append(
            {
                "stat": "drop_risk",
                "value": -1,
                "gold_value": -drop_risk,
                "note": f"Drops on death (risk = -{real_cost}g)",
            }
        )
        total_effective -= drop_risk

    # Calculate efficiency
    if real_cost > 0:
        efficiency = (total_effective / real_cost) * 100
    else:
        efficiency = 0

    # Difference
    difference = total_effective - real_cost
    difference_pct = (difference / real_cost * 100) if real_cost > 0 else 0

    return {
        "id": item_name,
        "name": item["name"],
        "real_cost": real_cost,
        "effective_cost": round(total_effective, 2),
        "difference": round(difference, 2),
        "difference_pct": round(difference_pct, 2),
        "efficiency_pct": round(efficiency, 2),
        "stat_breakdown": stat_breakdown,
        "unpriceable_stats": unpriceable_stats,
        "calculation_trace": calculation_trace,
        "ignored_stats_collected": ignored_stats_collected,
        "quality": item.get("quality", "unknown"),
        "drops_on_death": drops_on_death,
        "drop_risk": drop_risk if drops_on_death else 0,
        "comment": item_override.comment if item_override else "",
        "ability_not_evaluated": item_override.ability_not_evaluated if item_override else False,
    }


def main() -> None:
    # Load rules from YAML
    rules = load_axiom_rules()
    patch_version = rules.patch
    # Presentation threshold: items within ±N% of real cost are "fair priced"
    efficiency_threshold = 10

    logger.info("=" * 80)
    logger.info("EFFECTIVE COST CALCULATION (Patch %s)", patch_version)
    logger.info("=" * 80)

    # Load calculated axioms
    axioms_data = load_calculated_axioms()
    logger.info("\nLoaded axioms: %d", axioms_data.get("total_axioms", 0))

    # Load items
    with open(ITEMS_FILE, "r", encoding="utf-8") as f:
        items = json.load(f)

    logger.info("Loaded items: %d", len(items))

    # Build item lookup for ability_value references
    items_by_id = {item["id"]: item for item in items}

    # Calculate effective cost
    results = []
    unknown_stats: dict[str, list[str]] = {}  # stat -> list of items

    for item in items:
        result = calculate_effective_cost(item, axioms_data, rules, items_by_id)

        # Build hierarchical stat groups (presentation logic, separate from calculation)
        item_override = rules.item_overrides.get(item["id"])
        result["stat_groups"] = group_stat_breakdown(
            item,
            result["stat_breakdown"],
            item_override,
            axioms_data,
            rules,
            result.pop("ignored_stats_collected"),
        )
        results.append(result)

        # Track unknown stats
        for unpriceable in result["unpriceable_stats"]:
            stat = unpriceable["stat"]
            if stat not in unknown_stats:
                unknown_stats[stat] = []
            unknown_stats[stat].append(item["id"])

    # Sort by difference (most "overvalued" first)
    results.sort(key=lambda x: x["difference_pct"], reverse=True)

    # Save results
    output_file = OUTPUT_PATH / "effective_costs.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("\nResults saved: %s", output_file)

    # Save unknown stats for review (always write to clear stale data)
    questions_file = OUTPUT_PATH / "axiom_questions.json"
    questions = []
    for stat, items_list in sorted(unknown_stats.items(), key=lambda x: -len(x[1])):
        questions.append(
            {
                "stat": stat,
                "count": len(items_list),
                "items": items_list[:10],  # First 10 items
                "note": "Unknown stat - needs axiom",
            }
        )
    with open(questions_file, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    if questions:
        logger.info("Axiom questions: %s", questions_file)

    # Print statistics
    logger.info("\n" + "=" * 80)
    logger.info("STATISTICS")
    logger.info("=" * 80)

    effective_items = [r for r in results if r["effective_cost"] > 0]
    logger.info("\nItems with calculated effective cost: %d", len(effective_items))

    threshold = efficiency_threshold
    if effective_items:
        avg_efficiency = sum(r["efficiency_pct"] for r in effective_items) / len(effective_items)
        logger.info("Average efficiency: %.1f%%", avg_efficiency)

        overvalued = [r for r in effective_items if r["difference_pct"] > threshold]
        undervalued = [r for r in effective_items if r["difference_pct"] < -threshold]
        fair = [r for r in effective_items if -threshold <= r["difference_pct"] <= threshold]

        logger.info("\nOvervalued (effective > real + %d%%): %d", threshold, len(overvalued))
        logger.info("Undervalued (effective < real - %d%%): %d", threshold, len(undervalued))
        logger.info("Fair price (+/-%d%%): %d", threshold, len(fair))

    # Print top overvalued
    logger.debug("\n" + "=" * 80)
    logger.debug("TOP-15 OVERVALUED (effective > real)")
    logger.debug("=" * 80)

    for r in effective_items[:15]:
        logger.debug("\n%s (%s)", r["name"], r["id"])
        logger.debug("  Real: %dg | Effective: %sg", r["real_cost"], r["effective_cost"])
        logger.debug("  Difference: %+.0fg (%+.1f%%)", r["difference"], r["difference_pct"])
        if r["stat_breakdown"]:
            logger.debug("  Stats breakdown:")
            for s in r["stat_breakdown"][:5]:
                logger.debug(
                    "    - %s: %s x %.2f = %.1fg",
                    s.get("display_name", s["stat"]),
                    s["amount"],
                    s["gold_per_point"],
                    s["total_value"],
                )

    # Print top undervalued
    logger.debug("\n" + "=" * 80)
    logger.debug("TOP-15 UNDERVALUED (effective < real)")
    logger.debug("=" * 80)

    undervalued_sorted = sorted(effective_items, key=lambda x: x["difference_pct"])
    for r in undervalued_sorted[:15]:
        logger.debug("\n%s (%s)", r["name"], r["id"])
        logger.debug("  Real: %dg | Effective: %sg", r["real_cost"], r["effective_cost"])
        logger.debug("  Difference: %+.0fg (%+.1f%%)", r["difference"], r["difference_pct"])
        if r["unpriceable_stats"]:
            logger.debug("  Unpriceable stats: %s", [s["stat"] for s in r["unpriceable_stats"]])

    # Print unknown stats summary
    if unknown_stats:
        logger.debug("\n" + "=" * 80)
        logger.debug("UNKNOWN STATS (%d unique)", len(unknown_stats))
        logger.debug("=" * 80)

        for stat, items_list in sorted(unknown_stats.items(), key=lambda x: -len(x[1]))[:20]:
            logger.debug("\n%s: %d items", stat, len(items_list))
            logger.debug("  Examples: %s", items_list[:5])


if __name__ == "__main__":
    main()
