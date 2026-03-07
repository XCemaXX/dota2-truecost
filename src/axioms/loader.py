"""
Axiom Rules Loader

Loads and validates axiom_rules.yaml, returning typed structures.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# Exceptions
# =============================================================================


class AxiomRulesError(Exception):
    """Base exception for axiom rules errors."""

    pass


class YAMLSyntaxError(AxiomRulesError):
    """YAML syntax error with line number."""

    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"YAML syntax error{f' at line {line}' if line else ''}: {message}")


class SchemaValidationError(AxiomRulesError):
    """Schema validation error."""

    def __init__(self, message: str, path: str | None = None):
        self.path = path
        prefix = f"Validation error at '{path}': " if path else "Validation error: "
        super().__init__(prefix + message)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class UptimeConfig:
    """Uptime modifier configuration."""

    duration_stat: str
    cooldown_stat: str


@dataclass
class Axiom:
    """Single axiom definition."""

    name: str
    method: str  # reference_item, manual, formula, amplification_of
    display_name: str = ""
    category: str = "other"
    comment: str = ""

    # reference_item method
    reference_item: str | None = None
    stat: str | None = None
    subtract_stats: list[str] = field(default_factory=list)
    uptime: UptimeConfig | None = None

    # manual method
    gold_per_point: float | None = None

    # formula method
    formula: str | None = None

    # chance_stat: another stat that modifies this one as probability
    chance_stat: str | None = None

    # amplification_of method
    base_axiom: str | None = None
    expected_base_key: str | None = None

    # status tracking
    status: str = "active"  # active, unknown, situational
    question: str | None = None


@dataclass
class IgnoredStat:
    """Single ignored stat definition."""

    name: str
    category: str
    reason: str


@dataclass
class ExcludedItem:
    """Single excluded item definition."""

    item_id: str
    reason: str


@dataclass
class ExcludedPattern:
    """Pattern for excluding items."""

    pattern: str
    reason: str


@dataclass
class UptimeStatConfig:
    """Uptime stat configuration for an item override."""

    cooldown_stat: str = ""
    duration_stat: str = ""
    stat_as: str | None = None
    manual_uptime: float | None = None
    reason: str = ""


@dataclass
class CustomStatConfig:
    """Custom stat configuration for an item override."""

    formula: str = ""
    axiom: str | None = None
    comment: str = ""
    reason: str = ""


@dataclass
class SwitchableStatConfig:
    """Switchable stat configuration for an item override."""

    multiplier: float = 1.0
    reason: str = ""


@dataclass
class IgnoredStatConfig:
    """Ignored stat configuration for an item override."""

    reason: str = ""


@dataclass
class Ability:
    """Single ability definition for an item."""

    name: str  # Human-readable ability name (e.g., "Endurance")
    type: str  # "active", "aura", or "passive"
    stats: list[str]  # Stat names belonging to this ability


@dataclass
class ItemOverride:
    """Per-item override configuration."""

    item_id: str
    ability_value: float | None = None  # Direct gold value
    ability_value_ref: str | None = None  # Reference to item cost, e.g. "item_blink"
    ability_value_formula: str | None = (
        None  # Formula, e.g. "push_length * displacement_gold_per_unit"
    )
    comment: str = ""
    display_name: str = ""
    ignored_stats: dict[str, IgnoredStatConfig] = field(default_factory=dict)
    switchable_stats: dict[str, SwitchableStatConfig] = field(default_factory=dict)
    uptime_stats: dict[str, UptimeStatConfig] = field(default_factory=dict)
    custom_stats: dict[str, CustomStatConfig] = field(default_factory=dict)
    excluded: bool = False
    ability_not_evaluated: bool = False
    abilities: list[Ability] = field(default_factory=list)


@dataclass
class SettingMeta:
    """Metadata for a setting constant."""

    value: float | int
    name: str
    comment: str = ""


@dataclass
class AxiomRules:
    """Complete axiom rules structure."""

    version: str
    patch: str
    settings: dict[str, Any]
    settings_meta: dict[str, SettingMeta]
    expected_bases: dict[str, float]
    axioms: dict[str, Axiom]
    stat_normalization: dict[str, str]
    ignored_stats: dict[str, dict[str, IgnoredStat]]
    excluded_items: dict[str, Any]
    item_overrides: dict[str, ItemOverride]


# =============================================================================
# Validation
# =============================================================================

VALID_METHODS = {"reference_item", "manual", "formula", "amplification_of"}
VALID_ABILITY_TYPES = {"active", "aura", "passive"}

REQUIRED_FIELDS_BY_METHOD = {
    "reference_item": ["reference_item", "stat"],
    "manual": ["gold_per_point"],
    "formula": ["formula"],
    "amplification_of": ["base_axiom", "expected_base_key"],
}


def validate_axiom(name: str, data: dict[str, Any]) -> list[str]:
    """Validate a single axiom definition. Returns list of errors."""
    errors = []

    # Check method field
    method = data.get("method")
    if not method:
        errors.append(f"axioms.{name}: missing required field 'method'")
        return errors

    if method not in VALID_METHODS:
        valid = ", ".join(VALID_METHODS)
        errors.append(f"axioms.{name}: unknown method '{method}'. Valid options: {valid}")
        return errors

    # Check required fields for method
    required = REQUIRED_FIELDS_BY_METHOD.get(method, [])
    for field_name in required:
        if field_name not in data or data[field_name] is None:
            errors.append(f"axioms.{name}: method '{method}' requires field '{field_name}'")

    return errors


def validate_abilities(item_id: str, abilities: list) -> list[str]:
    """Validate abilities list for an item override. Returns list of errors."""
    errors = []
    if not isinstance(abilities, list):
        errors.append(
            f"item_overrides.{item_id}.abilities: expected list, got {type(abilities).__name__}"
        )
        return errors

    all_stats = set()
    for i, ab in enumerate(abilities):
        if not isinstance(ab, dict):
            errors.append(f"item_overrides.{item_id}.abilities[{i}]: expected dict")
            continue
        if not ab.get("name"):
            errors.append(f"item_overrides.{item_id}.abilities[{i}]: missing required field 'name'")
        ab_type = ab.get("type", "")
        if ab_type not in VALID_ABILITY_TYPES:
            errors.append(
                f"item_overrides.{item_id}.abilities[{i}]: invalid type '{ab_type}'. Valid: {VALID_ABILITY_TYPES}"
            )
        stats = ab.get("stats", [])
        if not isinstance(stats, list):
            errors.append(f"item_overrides.{item_id}.abilities[{i}].stats: expected list")
        else:
            # Check for duplicate stats across abilities
            for s in stats:
                if s in all_stats:
                    errors.append(
                        f"item_overrides.{item_id}.abilities[{i}]: stat '{s}' already claimed by another ability"
                    )
                all_stats.add(s)
    return errors


def validate_rules(data: dict[str, Any]) -> list[str]:
    """Validate the complete rules structure. Returns list of errors."""
    errors = []

    # Check top-level required fields
    for field in ["version", "patch", "settings", "axioms"]:
        if field not in data:
            errors.append(f"Missing required top-level field: '{field}'")

    # Validate axioms
    axioms = data.get("axioms", {})
    if isinstance(axioms, dict):
        for name, axiom_data in axioms.items():
            if isinstance(axiom_data, dict):
                errors.extend(validate_axiom(name, axiom_data))
            else:
                errors.append(f"axioms.{name}: expected dict, got {type(axiom_data).__name__}")

    # Validate formula references and subtract_stats
    settings = data.get("settings", {})
    if isinstance(axioms, dict):
        axiom_keys = set(axioms.keys())
        settings_keys = set(settings.keys()) if isinstance(settings, dict) else set()
        known_identifiers = axiom_keys | settings_keys | {"sqrt"}

        for name, axiom_data in axioms.items():
            if not isinstance(axiom_data, dict):
                continue

            # 5a: Formula references
            if axiom_data.get("method") == "formula" and axiom_data.get("formula"):
                formula = axiom_data["formula"]
                tokens = re.findall(r"[a-zA-Z_]\w*", formula)
                for token in tokens:
                    if token not in known_identifiers:
                        errors.append(
                            f"axioms.{name}: formula references unknown identifier '{token}'"
                        )

            # 5b: subtract_stats references
            for sub_stat in axiom_data.get("subtract_stats", []) or []:
                if sub_stat not in axiom_keys:
                    errors.append(
                        f"axioms.{name}: subtract_stats references unknown axiom '{sub_stat}'"
                    )

    # Validate item_overrides
    overrides = data.get("item_overrides", {})
    if isinstance(overrides, dict):
        for item_id, override_data in overrides.items():
            if not isinstance(override_data, dict):
                continue

            if "abilities" in override_data:
                errors.extend(validate_abilities(item_id, override_data["abilities"]))

            # 5c: uptime_stats validation
            for stat_name, cfg in (override_data.get("uptime_stats") or {}).items():
                if isinstance(cfg, dict):
                    has_cooldown = bool(cfg.get("cooldown_stat"))
                    has_manual = cfg.get("manual_uptime") is not None
                    has_duration = bool(cfg.get("duration_stat"))
                    has_stat_as = bool(cfg.get("stat_as"))
                    if not (has_cooldown or has_manual or has_duration or has_stat_as):
                        errors.append(
                            f"item_overrides.{item_id}.uptime_stats.{stat_name}: "
                            "must have at least one of 'cooldown_stat', 'manual_uptime', "
                            "'duration_stat', or 'stat_as'"
                        )

            # 5d: custom_stats validation
            for stat_name, cfg in (override_data.get("custom_stats") or {}).items():
                if isinstance(cfg, dict):
                    if not cfg.get("formula"):
                        errors.append(
                            f"item_overrides.{item_id}.custom_stats.{stat_name}: "
                            "must have non-empty 'formula'"
                        )

            # 5e: switchable_stats validation
            for stat_name, cfg in (override_data.get("switchable_stats") or {}).items():
                if isinstance(cfg, dict):
                    mult = cfg.get("multiplier")
                    if mult is not None and not isinstance(mult, (int, float)):
                        errors.append(
                            f"item_overrides.{item_id}.switchable_stats.{stat_name}: "
                            "'multiplier' must be numeric"
                        )

    return errors


# =============================================================================
# Parsing
# =============================================================================


def parse_uptime(data: dict[str, Any] | None) -> UptimeConfig | None:
    """Parse uptime configuration."""
    if not data:
        return None
    return UptimeConfig(
        duration_stat=data.get("duration_stat", ""),
        cooldown_stat=data.get("cooldown_stat", ""),
    )


def parse_axiom(name: str, data: dict[str, Any]) -> Axiom:
    """Parse a single axiom from raw dict."""
    return Axiom(
        name=name,
        method=data.get("method", ""),
        display_name=data.get("display_name", ""),
        category=data.get("category", "other"),
        comment=data.get("comment", "").strip() if data.get("comment") else "",
        reference_item=data.get("reference_item"),
        stat=data.get("stat"),
        subtract_stats=data.get("subtract_stats", []) or [],
        chance_stat=data.get("chance_stat"),
        uptime=parse_uptime(data.get("uptime")),
        gold_per_point=data.get("gold_per_point"),
        formula=data.get("formula"),
        base_axiom=data.get("base_axiom"),
        expected_base_key=data.get("expected_base_key"),
        status=data.get("status", "active"),
        question=data.get("question"),
    )


def parse_ignored_stats(data: dict[str, Any] | None) -> dict[str, dict[str, IgnoredStat]]:
    """Parse ignored stats by category."""
    if not data:
        return {}

    result: dict[str, dict[str, IgnoredStat]] = {}
    for category, stats in data.items():
        if not isinstance(stats, dict):
            continue
        result[category] = {}
        for stat_name, stat_data in stats.items():
            if isinstance(stat_data, dict):
                result[category][stat_name] = IgnoredStat(
                    name=stat_name,
                    category=category,
                    reason=stat_data.get("reason", ""),
                )
    return result


def parse_excluded_items(data: dict[str, Any] | None) -> dict[str, Any]:
    """Parse excluded items section."""
    if not data:
        return {"patterns": [], "flags": {}, "items": {}}
    return data


def parse_item_overrides(data: dict[str, Any] | None) -> dict[str, ItemOverride]:
    """Parse item overrides section."""
    if not data:
        return {}

    result = {}
    for item_id, override_data in data.items():
        if isinstance(override_data, dict):
            # Parse abilities list
            abilities = []
            for ab_data in override_data.get("abilities", []):
                if isinstance(ab_data, dict):
                    abilities.append(
                        Ability(
                            name=ab_data.get("name", ""),
                            type=ab_data.get("type", ""),
                            stats=ab_data.get("stats", []),
                        )
                    )

            # Parse ability_value: can be a number, "item_cost:<item_id>",
            # "formula:<expr>", or absent
            raw_ability_value = override_data.get("ability_value")
            ability_value = None
            ability_value_ref = None
            ability_value_formula = None
            if isinstance(raw_ability_value, str) and raw_ability_value.startswith("item_cost:"):
                ability_value_ref = raw_ability_value.split(":", 1)[1]
            elif isinstance(raw_ability_value, str) and raw_ability_value.startswith("formula:"):
                ability_value_formula = raw_ability_value.split(":", 1)[1].strip()
            elif raw_ability_value is not None:
                ability_value = float(raw_ability_value)

            # Parse typed nested configs
            ignored_stats = {
                k: IgnoredStatConfig(**v) if isinstance(v, dict) else IgnoredStatConfig()
                for k, v in override_data.get("ignored_stats", {}).items()
            }
            switchable_stats = {
                k: SwitchableStatConfig(**v) if isinstance(v, dict) else SwitchableStatConfig()
                for k, v in override_data.get("switchable_stats", {}).items()
            }
            uptime_stats = {
                k: UptimeStatConfig(**v) if isinstance(v, dict) else UptimeStatConfig()
                for k, v in override_data.get("uptime_stats", {}).items()
            }
            custom_stats = {
                k: CustomStatConfig(**v) if isinstance(v, dict) else CustomStatConfig()
                for k, v in override_data.get("custom_stats", {}).items()
            }

            result[item_id] = ItemOverride(
                item_id=item_id,
                ability_value=ability_value,
                ability_value_ref=ability_value_ref,
                ability_value_formula=ability_value_formula,
                comment=override_data.get("comment", ""),
                display_name=override_data.get("display_name", ""),
                ignored_stats=ignored_stats,
                switchable_stats=switchable_stats,
                uptime_stats=uptime_stats,
                custom_stats=custom_stats,
                excluded=override_data.get("excluded", False),
                ability_not_evaluated=override_data.get("ability_not_evaluated", False),
                abilities=abilities,
            )
    return result


def parse_settings(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, SettingMeta]]:
    """Parse settings: supports both plain values and {value, name, comment} dicts."""
    values: dict[str, Any] = {}
    meta: dict[str, SettingMeta] = {}
    for key, val in raw.items():
        if isinstance(val, dict) and "value" in val:
            values[key] = val["value"]
            meta[key] = SettingMeta(
                value=val["value"],
                name=val.get("name", key),
                comment=val.get("comment", ""),
            )
        else:
            values[key] = val
            meta[key] = SettingMeta(value=val, name=key)
    return values, meta


def parse_rules(data: dict[str, Any]) -> AxiomRules:
    """Parse raw dict into AxiomRules dataclass."""
    # Parse settings
    settings_values, settings_meta = parse_settings(data.get("settings", {}))

    # Parse axioms
    axioms = {}
    for name, axiom_data in data.get("axioms", {}).items():
        if isinstance(axiom_data, dict):
            axioms[name] = parse_axiom(name, axiom_data)

    return AxiomRules(
        version=data.get("version", ""),
        patch=data.get("patch", ""),
        settings=settings_values,
        settings_meta=settings_meta,
        expected_bases=data.get("expected_bases", {}),
        axioms=axioms,
        stat_normalization=data.get("stat_normalization", {}),
        ignored_stats=parse_ignored_stats(data.get("ignored_stats")),
        excluded_items=parse_excluded_items(data.get("excluded_items")),
        item_overrides=parse_item_overrides(data.get("item_overrides")),
    )


# =============================================================================
# Main Loader Function
# =============================================================================


def get_default_rules_path() -> Path:
    """Get the default path to axiom_rules.yaml."""
    return Path(__file__).parent / "axiom_rules.yaml"


def get_default_technical_path() -> Path:
    """Get the default path to axiom_technical.yaml."""
    return Path(__file__).parent / "axiom_technical.yaml"


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a single YAML file and return parsed dict."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        line = getattr(e, "problem_mark", None)
        line_num = line.line + 1 if line else None
        raise YAMLSyntaxError(str(e), line_num) from e
    if not isinstance(data, dict):
        raise SchemaValidationError(f"Root element must be a mapping/dict in {path}")
    return data


def load_axiom_rules(path: str | Path | None = None, validate: bool = True) -> AxiomRules:
    """
    Load and parse axiom rules from YAML files.

    Loads axiom_rules.yaml (game design config) and merges with
    axiom_technical.yaml (stat normalization, ignored stats, excluded items).

    Args:
        path: Path to main YAML file. If None, uses default location.
        validate: If True, validate schema and raise on errors.

    Returns:
        AxiomRules dataclass with all parsed data.

    Raises:
        YAMLSyntaxError: If YAML syntax is invalid.
        SchemaValidationError: If schema validation fails.
        FileNotFoundError: If file doesn't exist.
    """
    if path is None:
        path = get_default_rules_path()
    else:
        path = Path(path)

    data = _load_yaml_file(path)

    # Load technical config from sibling file
    technical_path = path.parent / "axiom_technical.yaml"
    if technical_path.exists():
        technical_data = _load_yaml_file(technical_path)
        # Merge technical sections into main data (technical sections don't overlap)
        for key in ("stat_normalization", "ignored_stats", "excluded_items"):
            if key in technical_data:
                data[key] = technical_data[key]

    # Validate
    if validate:
        errors = validate_rules(data)
        if errors:
            raise SchemaValidationError("\n".join(errors))

    # Parse
    return parse_rules(data)


def load_raw_yaml(path: str | Path | None = None) -> dict[str, Any]:
    """
    Load axiom rules as raw dict without parsing into dataclasses.
    Useful for tools that need to modify the YAML.
    """
    if path is None:
        path = get_default_rules_path()
    else:
        path = Path(path)

    with open(path, "r", encoding="utf-8") as f:
        return dict(yaml.safe_load(f))


# =============================================================================
# Utility Functions
# =============================================================================


def get_all_ignored_stats(rules: AxiomRules) -> set[str]:
    """Get a flat set of all ignored stat names across all categories."""
    result: set[str] = set()
    for category_stats in rules.ignored_stats.values():
        result.update(category_stats.keys())
    return result


def normalize_stat_name(stat_name: str, rules: AxiomRules) -> str:
    """Normalize a stat name using the rules' stat_normalization mapping."""
    return rules.stat_normalization.get(stat_name, stat_name)


def get_axiom_by_stat(stat_name: str, rules: AxiomRules) -> Axiom | None:
    """Find axiom for a given stat name (after normalization)."""
    normalized = normalize_stat_name(stat_name, rules)

    # Direct match
    if normalized in rules.axioms:
        return rules.axioms[normalized]

    # Check if any axiom has this as its stat key
    for axiom in rules.axioms.values():
        if axiom.stat == normalized:
            return axiom

    return None


def is_item_excluded(
    item_id: str, item_data: dict[str, Any], rules: AxiomRules
) -> tuple[bool, str]:
    """
    Check if an item should be excluded from analysis.

    Returns:
        Tuple of (is_excluded, reason)
    """
    import re

    excluded = rules.excluded_items

    # Check patterns
    for pattern_data in excluded.get("patterns", []):
        pattern = pattern_data.get("pattern", "")
        if pattern and re.match(pattern, item_id):
            return True, pattern_data.get("reason", "Matches exclusion pattern")

    # Check flags
    flags = excluded.get("flags", {})
    for flag_name, flag_data in flags.items():
        # Parse flag name like "ItemCost_0" -> field="ItemCost", value="0"
        parts = flag_name.rsplit("_", 1)
        if len(parts) == 2:
            field, expected = parts
            if str(item_data.get(field, "")) == expected:
                return True, flag_data.get("reason", f"Has {flag_name}")

    # Check specific items
    items = excluded.get("items", {})
    if item_id in items:
        return True, items[item_id].get("reason", "Explicitly excluded")

    return False, ""


def get_items_path() -> str:
    """Read items file path from data/latest.txt.

    Falls back to data/items.txt if latest.txt doesn't exist.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data"
    latest_path = data_dir / "latest.txt"
    if latest_path.exists():
        filename = latest_path.read_text().strip()
        return str(data_dir / filename)
    return str(data_dir / "items.txt")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    _logger = logging.getLogger(__name__)

    # Test loading
    rules = load_axiom_rules()
    _logger.info("Loaded axiom rules v%s for patch %s", rules.version, rules.patch)
    _logger.info("  Axioms: %d", len(rules.axioms))
    _logger.info("  Stat normalizations: %d", len(rules.stat_normalization))
    _logger.info("  Item overrides: %d", len(rules.item_overrides))

    # Count ignored stats
    total_ignored = sum(len(stats) for stats in rules.ignored_stats.values())
    _logger.info(
        "  Ignored stats: %d across %d categories", total_ignored, len(rules.ignored_stats)
    )
