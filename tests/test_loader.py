"""
Tests for axioms/loader.py - YAML loading and validation.
"""

from pathlib import Path

import pytest

from axioms.loader import (
    VALID_ABILITY_TYPES,
    VALID_METHODS,
    Ability,
    AxiomRules,
    CustomStatConfig,
    IgnoredStatConfig,
    SchemaValidationError,
    SwitchableStatConfig,
    UptimeStatConfig,
    YAMLSyntaxError,
    get_all_ignored_stats,
    get_axiom_by_stat,
    is_item_excluded,
    load_axiom_rules,
    load_raw_yaml,
    normalize_stat_name,
    validate_abilities,
    validate_axiom,
    validate_rules,
)


class TestLoadAxiomRules:
    """Tests for loading axiom_rules.yaml."""

    def test_load_default_file(self, rules: AxiomRules):
        """Test loading the actual axiom_rules.yaml file."""
        assert rules is not None
        assert rules.version == "1.0"
        assert rules.patch == "7.41b"

    def test_has_required_sections(self, rules: AxiomRules):
        """Test that all required sections exist."""
        assert len(rules.axioms) > 0
        assert len(rules.settings) > 0

        assert len(rules.stat_normalization) > 0
        assert len(rules.ignored_stats) > 0

    def test_axiom_count(self, rules: AxiomRules):
        """Test expected number of axioms."""
        assert len(rules.axioms) >= 64, f"Expected at least 64 axioms, got {len(rules.axioms)}"

    def test_technical_yaml_loaded(self, rules: AxiomRules):
        """Test that technical config (from axiom_technical.yaml) is merged."""
        # stat_normalization should have entries from axiom_technical.yaml
        assert "bonus_str" in rules.stat_normalization
        assert rules.stat_normalization["bonus_str"] == "bonus_strength"
        # excluded_items should have patterns
        assert "patterns" in rules.excluded_items
        assert len(rules.excluded_items["patterns"]) > 0
        # ignored_stats should have global category
        assert "global" in rules.ignored_stats
        assert len(rules.ignored_stats["global"]) > 0

    def test_file_not_found(self, tmp_path: Path):
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_axiom_rules(tmp_path / "nonexistent.yaml")


class TestValidation:
    """Tests for axiom validation."""

    def test_validate_reference_item(self):
        """Test validation of reference_item axiom."""
        valid = {
            "method": "reference_item",
            "reference_item": "item_ogre_axe",
            "stat": "bonus_strength",
        }
        errors = validate_axiom("test", valid)
        assert len(errors) == 0

    def test_validate_reference_item_missing_stat(self):
        """Test validation fails when stat is missing."""
        invalid = {
            "method": "reference_item",
            "reference_item": "item_ogre_axe",
            # missing 'stat'
        }
        errors = validate_axiom("test", invalid)
        assert len(errors) == 1
        assert "stat" in errors[0]

    def test_validate_manual(self):
        """Test validation of manual axiom."""
        valid = {
            "method": "manual",
            "gold_per_point": 100,
        }
        errors = validate_axiom("test", valid)
        assert len(errors) == 0

    def test_validate_formula(self):
        """Test validation of formula axiom."""
        valid = {
            "method": "formula",
            "formula": "bonus_strength * 2",
        }
        errors = validate_axiom("test", valid)
        assert len(errors) == 0

    def test_validate_unknown_method(self):
        """Test validation fails for unknown method."""
        invalid = {
            "method": "unknown_method",
        }
        errors = validate_axiom("test", invalid)
        assert len(errors) == 1
        assert "unknown method" in errors[0].lower()

    def test_validate_missing_method(self):
        """Test validation fails when method is missing."""
        invalid = {
            "gold_per_point": 100,
        }
        errors = validate_axiom("test", invalid)
        assert len(errors) == 1
        assert "method" in errors[0]


class TestStatNormalization:
    """Tests for stat name normalization."""

    def test_normalize_known_stat(self, rules: AxiomRules):
        """Test normalizing a known stat alias."""
        # Check some common mappings exist
        assert "bonus_str" in rules.stat_normalization
        result = normalize_stat_name("bonus_str", rules)
        assert result == "bonus_strength"

    def test_normalize_unknown_stat(self, rules: AxiomRules):
        """Test that unknown stats pass through unchanged."""
        result = normalize_stat_name("completely_unknown_stat", rules)
        assert result == "completely_unknown_stat"


class TestIgnoredStats:
    """Tests for ignored stats handling."""

    def test_get_all_ignored_stats(self, rules: AxiomRules):
        """Test getting flat set of all ignored stats."""
        ignored = get_all_ignored_stats(rules)
        assert isinstance(ignored, set)
        assert len(ignored) >= 15, f"Expected at least 15 global ignored stats, got {len(ignored)}"

    def test_ignored_stats_have_reasons(self, rules: AxiomRules):
        """Test that all ignored stats have reasons."""
        for category, stats in rules.ignored_stats.items():
            for stat_name, stat_obj in stats.items():
                assert stat_obj.reason, f"Ignored stat {category}.{stat_name} has no reason"


class TestExcludedItems:
    """Tests for item exclusion logic."""

    def test_recipe_excluded_by_pattern(self, rules: AxiomRules):
        """Test that recipe items are excluded by pattern."""
        excluded, reason = is_item_excluded("item_recipe_blink", {}, rules)
        assert excluded
        assert "recipe" in reason.lower()

    def test_specific_item_excluded(self, rules: AxiomRules):
        """Test that specific items are excluded."""
        excluded, reason = is_item_excluded("item_tango", {}, rules)
        assert excluded

    def test_normal_item_not_excluded(self, rules: AxiomRules):
        """Test that normal items are not excluded."""
        excluded, reason = is_item_excluded("item_blink", {}, rules)
        assert not excluded


class TestAxiomLookup:
    """Tests for axiom lookup functions."""

    def test_get_axiom_by_stat_direct(self, rules: AxiomRules):
        """Test finding axiom by direct stat name."""
        axiom = get_axiom_by_stat("bonus_strength", rules)
        assert axiom is not None
        assert axiom.name == "bonus_strength"

    def test_get_axiom_by_stat_normalized(self, rules: AxiomRules):
        """Test finding axiom by normalized stat name."""
        axiom = get_axiom_by_stat("bonus_str", rules)
        assert axiom is not None
        assert axiom.name == "bonus_strength"

    def test_get_axiom_unknown_stat(self, rules: AxiomRules):
        """Test that unknown stat returns None."""
        axiom = get_axiom_by_stat("completely_unknown_stat", rules)
        assert axiom is None


class TestAxiomStructure:
    """Tests for axiom structure and completeness."""

    def test_all_axioms_have_method(self, rules: AxiomRules):
        """Test that all axioms have a method field."""
        for name, axiom in rules.axioms.items():
            assert axiom.method in VALID_METHODS, f"Axiom {name} has invalid method: {axiom.method}"

    def test_all_axioms_have_display_name(self, rules: AxiomRules):
        """Test that all axioms have display_name."""
        for name, axiom in rules.axioms.items():
            assert axiom.display_name, f"Axiom {name} has no display_name"

    def test_all_axioms_have_category(self, rules: AxiomRules):
        """Test that all axioms have category."""
        for name, axiom in rules.axioms.items():
            assert axiom.category, f"Axiom {name} has no category"

    def test_reference_items_have_stat(self, rules: AxiomRules):
        """Test that reference_item axioms have stat field."""
        for name, axiom in rules.axioms.items():
            if axiom.method == "reference_item":
                assert axiom.reference_item, f"Axiom {name} missing reference_item"
                assert axiom.stat, f"Axiom {name} missing stat"


class TestAbilities:
    """Tests for abilities key in item overrides."""

    def test_item_without_abilities(self, rules: AxiomRules):
        """Test that items without abilities key have empty list."""
        # Find any item that we know has no abilities key
        for item_id, override in rules.item_overrides.items():
            if not override.abilities:
                assert override.abilities == []
                break

    def test_items_with_abilities_have_valid_types(self, rules: AxiomRules):
        """Test that all abilities have valid types."""
        for item_id, override in rules.item_overrides.items():
            for ab in override.abilities:
                assert (
                    ab.type in VALID_ABILITY_TYPES
                ), f"{item_id} ability '{ab.name}' has invalid type: {ab.type}"

    def test_abilities_have_names(self, rules: AxiomRules):
        """Test that all abilities have names."""
        for item_id, override in rules.item_overrides.items():
            for ab in override.abilities:
                assert ab.name, f"{item_id} has ability with empty name"

    def test_abilities_stats_are_lists(self, rules: AxiomRules):
        """Test that all ability stats are lists."""
        for item_id, override in rules.item_overrides.items():
            for ab in override.abilities:
                assert isinstance(
                    ab.stats, list
                ), f"{item_id} ability '{ab.name}' stats is not a list"

    def test_validate_abilities_invalid_type(self):
        """Test validation catches invalid ability type."""
        abilities = [{"name": "Test", "type": "invalid", "stats": []}]
        errors = validate_abilities("test_item", abilities)
        assert len(errors) == 1
        assert "invalid type" in errors[0].lower()

    def test_validate_abilities_missing_name(self):
        """Test validation catches missing name."""
        abilities = [{"type": "active", "stats": []}]
        errors = validate_abilities("test_item", abilities)
        assert len(errors) == 1
        assert "name" in errors[0].lower()

    def test_validate_abilities_duplicate_stats(self):
        """Test validation catches duplicate stats across abilities."""
        abilities = [
            {"name": "Ability1", "type": "active", "stats": ["stat_a"]},
            {"name": "Ability2", "type": "aura", "stats": ["stat_a"]},
        ]
        errors = validate_abilities("test_item", abilities)
        assert len(errors) == 1
        assert "already claimed" in errors[0].lower()

    def test_validate_abilities_valid(self):
        """Test validation passes for valid abilities."""
        abilities = [
            {"name": "Endurance", "type": "active", "stats": ["bonus_attack_speed_pct"]},
            {"name": "Swiftness Aura", "type": "aura", "stats": ["aura_movement_speed"]},
        ]
        errors = validate_abilities("test_item", abilities)
        assert len(errors) == 0

    def test_item_override_display_name_field(self, rules: AxiomRules):
        """Test that ItemOverride has display_name field."""
        for item_id, override in rules.item_overrides.items():
            assert hasattr(override, "display_name"), f"{item_id} missing display_name field"
            assert isinstance(
                override.display_name, str
            ), f"{item_id} display_name should be string"


class TestFormulaValidation:
    """Tests for formula and reference validation in validate_rules()."""

    def _make_rules_data(self, **overrides):
        """Create minimal valid rules data with overrides."""
        data = {
            "version": "1.0",
            "patch": "test",
            "settings": {"cooldown_efficiency": 0.75},
            "axioms": {
                "bonus_strength": {
                    "method": "reference_item",
                    "reference_item": "item_ogre_axe",
                    "stat": "bonus_strength",
                },
            },
        }
        data.update(overrides)
        return data

    def test_bad_formula_reference(self):
        """Formula referencing non-existent axiom/setting raises error."""
        data = self._make_rules_data(
            axioms={
                "bonus_strength": {
                    "method": "reference_item",
                    "reference_item": "item_ogre_axe",
                    "stat": "bonus_strength",
                },
                "test_formula": {
                    "method": "formula",
                    "formula": "bonus_strength * nonexistent_thing",
                },
            }
        )
        errors = validate_rules(data)
        assert any("nonexistent_thing" in e for e in errors)

    def test_valid_formula_reference(self):
        """Formula referencing known axioms and settings passes."""
        data = self._make_rules_data(
            axioms={
                "bonus_strength": {
                    "method": "reference_item",
                    "reference_item": "item_ogre_axe",
                    "stat": "bonus_strength",
                },
                "test_formula": {
                    "method": "formula",
                    "formula": "bonus_strength * cooldown_efficiency",
                },
            }
        )
        errors = validate_rules(data)
        assert not any("formula" in e for e in errors)

    def test_formula_sqrt_allowed(self):
        """sqrt is allowed in formulas."""
        data = self._make_rules_data(
            axioms={
                "bonus_strength": {
                    "method": "reference_item",
                    "reference_item": "item_ogre_axe",
                    "stat": "bonus_strength",
                },
                "test_formula": {
                    "method": "formula",
                    "formula": "sqrt(bonus_strength)",
                },
            }
        )
        errors = validate_rules(data)
        assert not any("sqrt" in e for e in errors)

    def test_bad_subtract_stats_reference(self):
        """subtract_stats referencing non-existent axiom raises error."""
        data = self._make_rules_data(
            axioms={
                "bonus_strength": {
                    "method": "reference_item",
                    "reference_item": "item_ogre_axe",
                    "stat": "bonus_strength",
                    "subtract_stats": ["nonexistent_axiom"],
                },
            }
        )
        errors = validate_rules(data)
        assert any("nonexistent_axiom" in e for e in errors)

    def test_valid_subtract_stats_reference(self):
        """subtract_stats referencing existing axiom passes."""
        data = self._make_rules_data(
            axioms={
                "bonus_strength": {
                    "method": "reference_item",
                    "reference_item": "item_ogre_axe",
                    "stat": "bonus_strength",
                },
                "bonus_hp": {
                    "method": "reference_item",
                    "reference_item": "item_vitality_booster",
                    "stat": "bonus_health",
                    "subtract_stats": ["bonus_strength"],
                },
            }
        )
        errors = validate_rules(data)
        assert not any("subtract_stats" in e for e in errors)

    def test_uptime_stats_missing_all_fields(self):
        """uptime_stats without any timing or stat_as field raises error."""
        data = self._make_rules_data(
            item_overrides={
                "item_test": {
                    "uptime_stats": {
                        "some_stat": {"reason": "just a reason"},
                    }
                }
            }
        )
        errors = validate_rules(data)
        assert any("uptime_stats" in e and "item_test" in e for e in errors)

    def test_uptime_stats_with_cooldown_stat(self):
        """uptime_stats with cooldown_stat passes."""
        data = self._make_rules_data(
            item_overrides={
                "item_test": {
                    "uptime_stats": {
                        "some_stat": {"cooldown_stat": "cd", "duration_stat": "dur"},
                    }
                }
            }
        )
        errors = validate_rules(data)
        assert not any("uptime_stats" in e for e in errors)

    def test_uptime_stats_with_manual_uptime(self):
        """uptime_stats with manual_uptime passes."""
        data = self._make_rules_data(
            item_overrides={
                "item_test": {
                    "uptime_stats": {
                        "some_stat": {"manual_uptime": 0.5},
                    }
                }
            }
        )
        errors = validate_rules(data)
        assert not any("uptime_stats" in e for e in errors)

    def test_custom_stats_missing_formula(self):
        """custom_stats without formula raises error."""
        data = self._make_rules_data(
            item_overrides={
                "item_test": {
                    "custom_stats": {
                        "crit_damage": {"comment": "no formula"},
                    }
                }
            }
        )
        errors = validate_rules(data)
        assert any("formula" in e for e in errors)

    def test_custom_stats_with_formula(self):
        """custom_stats with formula passes."""
        data = self._make_rules_data(
            item_overrides={
                "item_test": {
                    "custom_stats": {
                        "crit_damage": {"formula": "bonus_damage * 2"},
                    }
                }
            }
        )
        errors = validate_rules(data)
        assert not any("custom_stats" in e for e in errors)

    def test_switchable_stats_non_numeric_multiplier(self):
        """switchable_stats with non-numeric multiplier raises error."""
        data = self._make_rules_data(
            item_overrides={
                "item_test": {
                    "switchable_stats": {
                        "some_stat": {"multiplier": "not_a_number"},
                    }
                }
            }
        )
        errors = validate_rules(data)
        assert any("multiplier" in e and "numeric" in e for e in errors)


class TestTypedOverrideConfigs:
    """Tests for typed dataclass fields on ItemOverride."""

    def test_uptime_stats_are_typed(self, rules: AxiomRules):
        """uptime_stats values are UptimeStatConfig instances."""
        for item_id, override in rules.item_overrides.items():
            for stat_name, cfg in override.uptime_stats.items():
                assert isinstance(cfg, UptimeStatConfig), (
                    f"{item_id}.uptime_stats.{stat_name} is {type(cfg).__name__}, "
                    "expected UptimeStatConfig"
                )

    def test_custom_stats_are_typed(self, rules: AxiomRules):
        """custom_stats values are CustomStatConfig instances."""
        for item_id, override in rules.item_overrides.items():
            for stat_name, cfg in override.custom_stats.items():
                assert isinstance(cfg, CustomStatConfig), (
                    f"{item_id}.custom_stats.{stat_name} is {type(cfg).__name__}, "
                    "expected CustomStatConfig"
                )

    def test_switchable_stats_are_typed(self, rules: AxiomRules):
        """switchable_stats values are SwitchableStatConfig instances."""
        for item_id, override in rules.item_overrides.items():
            for stat_name, cfg in override.switchable_stats.items():
                assert isinstance(cfg, SwitchableStatConfig), (
                    f"{item_id}.switchable_stats.{stat_name} is {type(cfg).__name__}, "
                    "expected SwitchableStatConfig"
                )

    def test_ignored_stats_are_typed(self, rules: AxiomRules):
        """ignored_stats values are IgnoredStatConfig instances."""
        for item_id, override in rules.item_overrides.items():
            for stat_name, cfg in override.ignored_stats.items():
                assert isinstance(cfg, IgnoredStatConfig), (
                    f"{item_id}.ignored_stats.{stat_name} is {type(cfg).__name__}, "
                    "expected IgnoredStatConfig"
                )

    def test_uptime_stat_attributes_accessible(self, rules: AxiomRules):
        """UptimeStatConfig attributes are accessible (integration test)."""
        for item_id, override in rules.item_overrides.items():
            for stat_name, cfg in override.uptime_stats.items():
                # These should not raise AttributeError
                _ = cfg.cooldown_stat
                _ = cfg.duration_stat
                _ = cfg.stat_as
                _ = cfg.manual_uptime
                _ = cfg.reason

    def test_custom_stat_attributes_accessible(self, rules: AxiomRules):
        """CustomStatConfig attributes are accessible (integration test)."""
        for item_id, override in rules.item_overrides.items():
            for stat_name, cfg in override.custom_stats.items():
                _ = cfg.formula
                _ = cfg.axiom
                _ = cfg.comment
                _ = cfg.reason
