"""
Axiom Calculator

Calculates gold_per_point values for all axioms using various methods:
- reference_item: Calculate from item price / stat value
- formula: Math expression referencing other axioms
- amplification_of: Percentage amplification of another axiom
- manual: Direct gold_per_point value

Modifiers:
- subtract_stats: Subtract other stats' cost first
- uptime: Apply duration/(duration+cooldown) multiplier
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import Axiom, AxiomRules, load_axiom_rules, normalize_stat_name

# =============================================================================
# Exceptions
# =============================================================================


class CalculationError(Exception):
    """Error during axiom calculation."""

    pass


class UnresolvedDependencyError(CalculationError):
    """Referenced axiom not yet resolved."""

    pass


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CalculationTrace:
    """Trace of how an axiom value was calculated."""

    method: str
    formula: str = ""
    formula_symbolic: str = ""
    reference_item: str | None = None
    item_cost: float | None = None
    stat_value: float | None = None
    subtracted_value: float | None = None
    uptime: float | None = None
    base_axiom: str | None = None
    base_value: float | None = None
    expected_base: float | None = None


@dataclass
class ResolvedAxiom:
    """Axiom with calculated gold_per_point value."""

    name: str
    gold_per_point: float
    display_name: str
    category: str
    comment: str
    calculation: CalculationTrace
    depends_on: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)
    status: str = "active"
    warning: str | None = None
    chance_stat: str | None = None


# =============================================================================
# Formula Parser
# =============================================================================


def get_formula_dependencies(formula: str, settings_keys: set[str] | None = None) -> set[str]:
    """Extract axiom names referenced in a formula.

    Args:
        formula: Math expression like "bonus_lifesteal * aura_avg_targets"
        settings_keys: Setting names to exclude from dependencies (resolved from settings, not axioms)
    """
    # Pattern: word that's not a number
    pattern = r"\b([a-z_][a-z0-9_]*)\b"
    matches = re.findall(pattern, formula)
    deps = set(matches)
    if settings_keys:
        deps -= settings_keys
    return deps


def eval_formula(
    formula: str,
    resolved_axioms: dict[str, ResolvedAxiom],
    settings: dict[str, Any] | None = None,
) -> float:
    """
    Evaluate a simple formula like "bonus_lifesteal * aura_avg_targets" or "bonus_armor + 10".

    Supports: axiom_name, settings values, numbers, +, -, *, /
    """

    # Replace axiom names with their values
    def replace_axiom(match):
        name = match.group(0)
        if name in resolved_axioms:
            return str(resolved_axioms[name].gold_per_point)
        if settings and name in settings:
            val = settings[name]
            if isinstance(val, (int, float)):
                return str(val)
        raise UnresolvedDependencyError(f"Unknown axiom in formula: {name}")

    # Pattern: word that's not a number
    expr = re.sub(r"\b([a-z_][a-z0-9_]*)\b", replace_axiom, formula)

    # Validate characters (only math operations allowed)
    allowed = set("0123456789.+-*/()")
    if not all(c in allowed or c.isspace() for c in expr):
        raise CalculationError(f"Invalid characters in formula: {formula}")

    try:
        result = eval(expr)  # Safe because we validated characters
        return float(result)
    except Exception as e:
        raise CalculationError(f"Error evaluating formula '{formula}': {e}")


# =============================================================================
# Calculation Methods
# =============================================================================


def calculate_reference_item(
    axiom: Axiom,
    items_parsed: dict[str, Any],
    resolved_axioms: dict[str, ResolvedAxiom],
    rules: AxiomRules,
) -> tuple[float, CalculationTrace, list[str]]:
    """
    Calculate gold_per_point from reference item.

    Returns: (gold_per_point, trace, dependencies)
    """
    ref_item_id = axiom.reference_item
    stat_key = axiom.stat

    # Find item in items_parsed (dict keyed by item_id)
    if ref_item_id not in items_parsed:
        raise CalculationError(f"Reference item '{ref_item_id}' not found in items_parsed.json")

    item_data = items_parsed[ref_item_id]
    item_cost = float(item_data.get("ItemCost", item_data.get("cost", 0)))
    # Look for stat in 'stats' dict first, then in item_data directly
    stats = item_data.get("stats", item_data)
    stat_value = float(stats.get(stat_key, 0))

    if stat_value == 0:
        return (
            0.0,
            CalculationTrace(
                method="reference_item",
                formula=f"{item_cost} / 0 = ERROR",
                reference_item=ref_item_id,
                item_cost=item_cost,
                stat_value=0,
            ),
            [],
        )

    # Subtract stats if specified
    subtracted_value = 0.0
    subtracted_parts: list[str] = []  # symbolic: ["stat_name × value"]
    dependencies = []

    if axiom.subtract_stats:
        for sub_stat in axiom.subtract_stats:
            # Get stat value from item — try direct name first,
            # then search item stats that normalize to this axiom name
            sub_stat_value = float(stats.get(sub_stat, 0))
            if sub_stat_value == 0:
                for raw_stat, raw_value in stats.items():
                    if normalize_stat_name(raw_stat, rules) == sub_stat:
                        sub_stat_value = float(raw_value)
                        break
            if sub_stat_value == 0:
                continue

            # Get gold_per_point for this stat (must be already resolved)
            if sub_stat not in resolved_axioms:
                raise UnresolvedDependencyError(f"Subtract stat '{sub_stat}' not yet resolved")

            dependencies.append(sub_stat)
            gold_per_point = resolved_axioms[sub_stat].gold_per_point
            subtracted_value += sub_stat_value * gold_per_point
            sub_display = resolved_axioms[sub_stat].display_name
            subtracted_parts.append(f"{sub_display}({sub_stat_value:g}) × {gold_per_point:g}g")

    effective_cost = item_cost - subtracted_value

    # Apply uptime if specified
    uptime_multiplier = 1.0
    if axiom.uptime:
        duration = float(stats.get(axiom.uptime.duration_stat, 0))
        # Try stats first, then raw_data for AbilityCooldown
        cooldown = float(stats.get(axiom.uptime.cooldown_stat, 0))
        if cooldown == 0 and axiom.uptime.cooldown_stat == "AbilityCooldown":
            raw_data = item_data.get("raw_data", {})
            cooldown = float(raw_data.get("AbilityCooldown", 0))

        if duration > 0:
            uptime_multiplier = duration / (duration + cooldown)

    gold_per_point = (effective_cost / stat_value) * uptime_multiplier

    # Apply chance_stat: divide by chance probability to get cost per raw point
    chance_value = None
    if axiom.chance_stat:
        chance_value = float(stats.get(axiom.chance_stat, 0))
        if chance_value > 0:
            gold_per_point = gold_per_point / (chance_value / 100.0)

    # Build numeric formula string
    if axiom.subtract_stats and subtracted_value > 0:
        formula = f"({item_cost} - {subtracted_value:.1f}) / {stat_value}"
    else:
        formula = f"{item_cost} / {stat_value}"

    if uptime_multiplier < 1.0:
        formula += f" * {uptime_multiplier:.2f}"

    if chance_value and chance_value > 0:
        formula += f" / {chance_value}%"

    formula += f" = {gold_per_point:.2f}"

    # Build symbolic formula string
    ref_name = ref_item_id.replace("item_", "").replace("_", " ").title()
    stat_display = axiom.display_name or stat_key
    if subtracted_parts:
        subtract_str = " + ".join(subtracted_parts)
        formula_sym = f"({ref_name}({item_cost:g}g) - {subtracted_value:g}g [{subtract_str}]) / {stat_display}({stat_value:g})"
    else:
        formula_sym = f"{ref_name}({item_cost:g}g) / {stat_display}({stat_value:g})"

    if uptime_multiplier < 1.0:
        formula_sym += f" × uptime({uptime_multiplier:.2f})"

    if chance_value and chance_value > 0:
        formula_sym += f" / chance({chance_value:g}%)"

    formula_sym += f" = {gold_per_point:.2f}"

    trace = CalculationTrace(
        method="reference_item",
        formula=formula,
        formula_symbolic=formula_sym,
        reference_item=ref_item_id,
        item_cost=item_cost,
        stat_value=stat_value,
        subtracted_value=subtracted_value if subtracted_value > 0 else None,
        uptime=uptime_multiplier if uptime_multiplier < 1.0 else None,
    )

    return gold_per_point, trace, dependencies


def calculate_formula(
    axiom: Axiom,
    resolved_axioms: dict[str, ResolvedAxiom],
    settings: dict[str, Any] | None = None,
    settings_meta: dict | None = None,
) -> tuple[float, CalculationTrace, list[str]]:
    """
    Calculate gold_per_point using formula.

    Returns: (gold_per_point, trace, dependencies)
    """
    assert axiom.formula is not None, f"Formula axiom missing formula field"
    formula = axiom.formula
    settings_keys = set(settings.keys()) if settings else None
    dependencies = list(get_formula_dependencies(formula, settings_keys))

    # Check all dependencies are resolved
    for dep in dependencies:
        if dep not in resolved_axioms:
            raise UnresolvedDependencyError(f"Formula dependency '{dep}' not yet resolved")

    gold_per_point = eval_formula(formula, resolved_axioms, settings)

    # Build symbolic formula: replace axiom names with DisplayName(value)
    def replace_with_display(m):
        name = m.group(0)
        if name in resolved_axioms:
            ra = resolved_axioms[name]
            return f"{ra.display_name}({ra.gold_per_point:g}g)"
        if settings and name in settings:
            display = settings_meta[name].name if settings_meta and name in settings_meta else name
            return f"{display}({settings[name]:g})"
        return name

    formula_sym = re.sub(r"\b([a-z_][a-z0-9_]*)\b", replace_with_display, formula)
    formula_sym += f" = {gold_per_point:.2f}"

    trace = CalculationTrace(
        method="formula",
        formula=f"{formula} = {gold_per_point:.2f}",
        formula_symbolic=formula_sym,
    )

    return gold_per_point, trace, dependencies


def calculate_amplification(
    axiom: Axiom,
    resolved_axioms: dict[str, ResolvedAxiom],
    rules: AxiomRules,
) -> tuple[float, CalculationTrace, list[str]]:
    """
    Calculate gold_per_point for amplification axiom.

    Formula: base_axiom_gold_per_point * expected_base * 0.01

    Returns: (gold_per_point, trace, dependencies)
    """
    assert axiom.base_axiom is not None, "Amplification axiom missing base_axiom"
    assert axiom.expected_base_key is not None, "Amplification axiom missing expected_base_key"
    base_name = axiom.base_axiom
    expected_key = axiom.expected_base_key

    if base_name not in resolved_axioms:
        raise UnresolvedDependencyError(f"Base axiom '{base_name}' not yet resolved")

    base_value = resolved_axioms[base_name].gold_per_point
    # Look up expected base in settings (previously in expected_bases)
    expected_base = rules.settings.get(expected_key, 0)
    if expected_base == 0:
        expected_base = rules.expected_bases.get(expected_key, 0)

    if expected_base == 0:
        raise CalculationError(f"Expected base '{expected_key}' not found in settings")

    # 1% amplification = base_value * expected_base * 0.01
    gold_per_point = base_value * expected_base * 0.01

    base_display = resolved_axioms[base_name].display_name
    meta = getattr(rules, "settings_meta", None)
    expected_display = meta[expected_key].name if meta and expected_key in meta else expected_key
    trace = CalculationTrace(
        method="amplification_of",
        formula=f"{base_value:.2f} * {expected_base} * 0.01 = {gold_per_point:.2f}",
        formula_symbolic=f"{base_display}({base_value:.2f}g) × {expected_display}({expected_base:g}) × 0.01 = {gold_per_point:.2f}",
        base_axiom=base_name,
        base_value=base_value,
        expected_base=expected_base,
    )

    return gold_per_point, trace, [base_name]


def calculate_manual(axiom: Axiom) -> tuple[float, CalculationTrace, list[str]]:
    """
    Use manual gold_per_point value.

    Returns: (gold_per_point, trace, dependencies)
    """
    gold_per_point = axiom.gold_per_point or 0.0

    trace = CalculationTrace(
        method="manual",
        formula=f"manual value = {gold_per_point}",
    )

    return gold_per_point, trace, []


# =============================================================================
# Main Resolution Logic
# =============================================================================


def get_axiom_dependencies(axiom: Axiom, settings_keys: set[str] | None = None) -> set[str]:
    """Get all axiom names that this axiom depends on."""
    deps = set()

    if axiom.method == "formula":
        deps.update(get_formula_dependencies(axiom.formula or "", settings_keys))
    elif axiom.method == "amplification_of":
        if axiom.base_axiom:
            deps.add(axiom.base_axiom)
    elif axiom.method == "reference_item":
        # subtract_stats dependencies
        deps.update(axiom.subtract_stats or [])

    return deps


def calculate_axiom(
    axiom: Axiom,
    items_parsed: dict[str, Any],
    resolved_axioms: dict[str, ResolvedAxiom],
    rules: AxiomRules,
) -> ResolvedAxiom:
    """
    Calculate a single axiom's gold_per_point value.

    Raises UnresolvedDependencyError if dependencies not yet resolved.
    """
    method = axiom.method

    try:
        if method == "reference_item":
            gold_per_point, trace, deps = calculate_reference_item(
                axiom, items_parsed, resolved_axioms, rules
            )
        elif method == "formula":
            # Merge settings + expected_bases so formulas can reference both
            formula_vars = {**rules.settings, **rules.expected_bases}
            gold_per_point, trace, deps = calculate_formula(
                axiom, resolved_axioms, formula_vars, getattr(rules, "settings_meta", None)
            )
        elif method == "amplification_of":
            gold_per_point, trace, deps = calculate_amplification(axiom, resolved_axioms, rules)
        elif method == "manual":
            gold_per_point, trace, deps = calculate_manual(axiom)
        else:
            raise CalculationError(f"Unknown method: {method}")

        warning = None
        if axiom.status == "unknown":
            warning = f"status: unknown - using value {gold_per_point}"

        return ResolvedAxiom(
            name=axiom.name,
            gold_per_point=gold_per_point,
            display_name=axiom.display_name,
            category=axiom.category,
            comment=axiom.comment,
            calculation=trace,
            depends_on=deps,
            status=axiom.status,
            warning=warning,
            chance_stat=axiom.chance_stat,
        )

    except UnresolvedDependencyError:
        raise
    except Exception as e:
        raise CalculationError(f"Error calculating axiom '{axiom.name}': {e}")


def _make_error_axiom(
    name: str, axiom: Axiom, error_msg: str, method: str = "error"
) -> ResolvedAxiom:
    """Create a placeholder ResolvedAxiom for failed or unresolved calculations."""
    return ResolvedAxiom(
        name=name,
        gold_per_point=0.0,
        display_name=axiom.display_name,
        category=axiom.category,
        comment=axiom.comment,
        calculation=CalculationTrace(method=method, formula=error_msg),
        status=method,
        warning=error_msg,
    )


def _try_resolve(
    name: str,
    axiom: Axiom,
    items_parsed: dict[str, Any],
    resolved: dict[str, ResolvedAxiom],
    rules: AxiomRules,
    warnings: list[dict[str, Any]],
) -> ResolvedAxiom:
    """Try to calculate an axiom; on failure, record warning and return error placeholder."""
    try:
        return calculate_axiom(axiom, items_parsed, resolved, rules)
    except CalculationError as e:
        warnings.append({"axiom": name, "issue": str(e)})
        return _make_error_axiom(name, axiom, str(e))


def resolve_all_axioms(
    rules: AxiomRules,
    items_parsed: dict[str, Any],
    max_iterations: int = 10,
) -> tuple[dict[str, ResolvedAxiom], list[dict[str, Any]]]:
    """
    Resolve all axioms in dependency order.

    Returns:
        Tuple of (resolved_axioms, warnings)
    """
    resolved: dict[str, ResolvedAxiom] = {}
    warnings: list[dict[str, Any]] = []
    # Combine settings + expected_bases keys so they're not treated as axiom dependencies
    settings_keys = set(rules.settings.keys()) if rules.settings else set()
    settings_keys.update(rules.expected_bases.keys())

    # Separate axioms by dependency type
    independent = []  # manual, reference_item without subtract_stats
    dependent = []  # formula, amplification_of, reference_item with subtract_stats

    for name, axiom in rules.axioms.items():
        deps = get_axiom_dependencies(axiom, settings_keys)
        if not deps:
            independent.append(name)
        else:
            dependent.append(name)

    # Phase 1: Resolve independent axioms
    for name in independent:
        axiom = rules.axioms[name]
        resolved[name] = _try_resolve(name, axiom, items_parsed, resolved, rules, warnings)

    # Phase 2: Iteratively resolve dependent axioms
    for iteration in range(max_iterations):
        progress = False
        still_pending = []

        for name in dependent:
            if name in resolved:
                continue

            axiom = rules.axioms[name]
            deps = get_axiom_dependencies(axiom, settings_keys)

            # Check if all dependencies are resolved
            if all(d in resolved for d in deps):
                resolved[name] = _try_resolve(name, axiom, items_parsed, resolved, rules, warnings)
                progress = True
            else:
                still_pending.append(name)

        dependent = still_pending

        if not progress:
            break  # No more can be resolved

    # Phase 3: Report unresolved (circular or missing deps)
    for name in dependent:
        if name not in resolved:
            axiom = rules.axioms[name]
            deps = get_axiom_dependencies(axiom, settings_keys)
            missing = [d for d in deps if d not in resolved]
            error_msg = f"Missing dependencies: {missing}"

            warnings.append({"axiom": name, "issue": f"Unresolved - {error_msg}"})
            resolved[name] = _make_error_axiom(name, axiom, error_msg, method="unresolved")

    # Phase 4: Build used_by relationships
    for name, axiom_resolved in resolved.items():
        for dep in axiom_resolved.depends_on:
            if dep in resolved:
                resolved[dep].used_by.append(name)

    return resolved, warnings


# =============================================================================
# Output Generation
# =============================================================================


def resolved_to_dict(resolved: dict[str, ResolvedAxiom]) -> dict[str, Any]:
    """Convert resolved axioms to JSON-serializable dict."""
    result: dict[str, Any] = {}

    for name, axiom in resolved.items():
        calc = axiom.calculation
        calc_dict: dict[str, Any] = {
            "method": calc.method,
            "formula": calc.formula,
        }
        if calc.formula_symbolic:
            calc_dict["formula_symbolic"] = calc.formula_symbolic

        # Add method-specific fields
        if calc.reference_item:
            calc_dict["reference_item"] = calc.reference_item
            calc_dict["item_cost"] = calc.item_cost
            calc_dict["stat_value"] = calc.stat_value
        if calc.subtracted_value:
            calc_dict["subtracted_value"] = calc.subtracted_value
        if calc.uptime:
            calc_dict["uptime"] = calc.uptime
        if calc.base_axiom:
            calc_dict["base_axiom"] = calc.base_axiom
            calc_dict["base_value"] = calc.base_value
            calc_dict["expected_base"] = calc.expected_base

        entry: dict[str, Any] = {
            "gold_per_point": axiom.gold_per_point,
            "display_name": axiom.display_name,
            "category": axiom.category,
            "comment": axiom.comment,
            "status": axiom.status,
            "depends_on": axiom.depends_on,
            "used_by": axiom.used_by,
            "calculation": calc_dict,
        }

        if axiom.chance_stat:
            entry["chance_stat"] = axiom.chance_stat

        if axiom.warning:
            entry["warning"] = axiom.warning

        result[name] = entry

    return result


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    _logger = logging.getLogger(__name__)

    # Test calculation
    rules = load_axiom_rules()
    _logger.info("Loaded %d axioms", len(rules.axioms))

    # Load items_parsed.json
    items_path = Path(__file__).parent.parent.parent / "output" / "items_parsed.json"
    with open(items_path, "r", encoding="utf-8") as f:
        items_parsed = json.load(f)

    resolved, warnings = resolve_all_axioms(rules, items_parsed)

    _logger.info("\nResolved %d axioms", len(resolved))
    _logger.info("Warnings: %d", len(warnings))

    for w in warnings[:5]:
        _logger.info("  - %s: %s", w["axiom"], w["issue"])

    # Show some resolved values
    _logger.info("\nSample resolved values:")
    for name in ["bonus_strength", "bonus_health_regen", "hp_regen_amp", "spell_amp"]:
        if name in resolved:
            a = resolved[name]
            _logger.info("  %s: %.2f gold/point (%s)", name, a.gold_per_point, a.calculation.method)
