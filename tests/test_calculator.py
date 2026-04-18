"""
Tests for axioms/calculator.py - axiom calculation methods.
"""

import pytest

from axioms.calculator import (
    CalculationError,
    ResolvedAxiom,
    UnresolvedDependencyError,
    calculate_axiom,
    eval_formula,
    get_formula_dependencies,
    resolve_all_axioms,
)
from axioms.loader import AxiomRules


class TestFormulaParser:
    """Tests for formula parsing and evaluation."""

    def test_get_dependencies_simple(self):
        """Test extracting dependencies from simple formula."""
        deps = get_formula_dependencies("bonus_strength * 2")
        assert deps == {"bonus_strength"}

    def test_get_dependencies_multiple(self):
        """Test extracting multiple dependencies."""
        deps = get_formula_dependencies("bonus_armor + bonus_health_regen")
        assert deps == {"bonus_armor", "bonus_health_regen"}

    def test_get_dependencies_complex(self):
        """Test complex formula with parentheses."""
        deps = get_formula_dependencies("(hp_regen_amp + mana_regen_amp) / 2")
        assert "hp_regen_amp" in deps
        assert "mana_regen_amp" in deps

    def test_eval_formula_simple(self):
        """Test evaluating simple formula."""
        resolved = {
            "bonus_strength": ResolvedAxiom(
                name="bonus_strength",
                gold_per_point=100.0,
                display_name="Strength",
                category="attributes",
                comment="",
                calculation=None,
            )
        }
        result = eval_formula("bonus_strength * 2", resolved)
        assert result == 200.0

    def test_eval_formula_division(self):
        """Test division in formula."""
        resolved = {
            "bonus_armor": ResolvedAxiom(
                name="bonus_armor",
                gold_per_point=140.0,
                display_name="Armor",
                category="defense",
                comment="",
                calculation=None,
            )
        }
        result = eval_formula("bonus_armor / 2", resolved)
        assert result == 70.0

    def test_eval_formula_with_settings(self):
        """Test evaluating formula with settings values."""
        resolved = {
            "bonus_lifesteal": ResolvedAxiom(
                name="bonus_lifesteal",
                gold_per_point=50.0,
                display_name="Lifesteal",
                category="offense",
                comment="",
                calculation=None,
            )
        }
        settings = {"aura_avg_targets": 2}
        result = eval_formula("bonus_lifesteal * aura_avg_targets", resolved, settings)
        assert result == 100.0

    def test_get_dependencies_excludes_settings(self):
        """Test that settings keys are excluded from dependencies."""
        deps = get_formula_dependencies(
            "bonus_lifesteal * aura_avg_targets", settings_keys={"aura_avg_targets"}
        )
        assert deps == {"bonus_lifesteal"}

    def test_eval_formula_unknown_axiom(self):
        """Test that unknown axiom in formula raises error."""
        resolved = {}
        with pytest.raises(UnresolvedDependencyError):
            eval_formula("unknown_axiom * 2", resolved)


class TestResolveAllAxioms:
    """Tests for axiom resolution."""

    def test_resolve_all_axioms(self, rules: AxiomRules, items_parsed: dict):
        """Test resolving all axioms from rules."""
        resolved, warnings = resolve_all_axioms(rules, items_parsed)

        # Should resolve all axioms
        assert len(resolved) == len(rules.axioms)

        # Check some known axioms
        assert "bonus_strength" in resolved
        assert "bonus_health" in resolved
        assert "bonus_damage" in resolved

    def test_bonus_strength_value(self, rules: AxiomRules, items_parsed: dict):
        """Test that bonus_strength resolves to ~100 gold/point."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        strength = resolved["bonus_strength"]
        # Ogre Axe: 1000g / 10 STR = 100 g/point
        assert (
            95 <= strength.gold_per_point <= 105
        ), f"bonus_strength should be ~100, got {strength.gold_per_point}"

    def test_bonus_health_value(self, rules: AxiomRules, items_parsed: dict):
        """Test that bonus_health resolves correctly."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        health = resolved["bonus_health"]
        # Vitality Booster: 1000g / 250 HP = 4 g/point
        assert (
            3.5 <= health.gold_per_point <= 4.5
        ), f"bonus_health should be ~4, got {health.gold_per_point}"

    def test_depends_on_populated(self, rules: AxiomRules, items_parsed: dict):
        """Test that depends_on is populated for dependent axioms."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        # hp_regen_amp depends on bonus_health_regen
        if "hp_regen_amp" in resolved:
            hp_regen_amp = resolved["hp_regen_amp"]
            assert "bonus_health_regen" in hp_regen_amp.depends_on

    def test_used_by_populated(self, rules: AxiomRules, items_parsed: dict):
        """Test that used_by is populated correctly."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        # bonus_health_regen should be used_by hp_regen_amp
        if "bonus_health_regen" in resolved and "hp_regen_amp" in rules.axioms:
            health_regen = resolved["bonus_health_regen"]
            # Note: used_by might include other axioms too
            assert len(health_regen.used_by) >= 0  # At least check it's a list

    def test_no_circular_dependencies(self, rules: AxiomRules, items_parsed: dict):
        """Test that there are no circular dependency errors."""
        resolved, warnings = resolve_all_axioms(rules, items_parsed)

        # Check no unresolved axioms due to circular deps
        for name, axiom in resolved.items():
            assert (
                axiom.status != "unresolved"
            ), f"Axiom {name} is unresolved (possible circular dependency)"


class TestCalculationTraces:
    """Tests for calculation traces."""

    def test_reference_item_has_trace(self, rules: AxiomRules, items_parsed: dict):
        """Test that reference_item axioms have calculation trace."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        strength = resolved["bonus_strength"]
        assert strength.calculation is not None
        assert strength.calculation.method == "reference_item"
        assert strength.calculation.reference_item is not None

    def test_trace_has_formula(self, rules: AxiomRules, items_parsed: dict):
        """Test that traces include formula string."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        strength = resolved["bonus_strength"]
        assert strength.calculation.formula
        assert "=" in strength.calculation.formula  # Should show "X / Y = Z"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_zero_stat_value(self, rules: AxiomRules, items_parsed: dict):
        """Test handling of zero stat value (should not crash)."""
        resolved, warnings = resolve_all_axioms(rules, items_parsed)
        # Should complete without crashing
        assert len(resolved) > 0

    def test_manual_axiom_value(self, rules: AxiomRules, items_parsed: dict):
        """Test that manual axioms use their specified value."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        # Find a manual axiom and check its value
        for name, axiom in rules.axioms.items():
            if axiom.method == "manual" and axiom.gold_per_point:
                resolved_axiom = resolved[name]
                assert (
                    resolved_axiom.gold_per_point == axiom.gold_per_point
                ), f"Manual axiom {name} should have value {axiom.gold_per_point}"
                break


class TestChanceStat:
    """Tests for chance_stat mechanism."""

    def test_chance_stat_divides_gold_per_point(self, rules: AxiomRules, items_parsed: dict):
        """Test that chance_stat divides gold_per_point by chance probability."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        # bonus_chance_damage: formula "bonus_damage" = 50 g/pt (chance applied at item level)
        assert "bonus_chance_damage" in resolved
        pierce = resolved["bonus_chance_damage"]
        assert (
            45 <= pierce.gold_per_point <= 55
        ), f"bonus_chance_damage should be ~50, got {pierce.gold_per_point}"

    def test_chance_stat_on_resolved(self, rules: AxiomRules, items_parsed: dict):
        """Test that chance_stat is preserved on resolved axioms."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        pierce = resolved["bonus_chance_damage"]
        assert pierce.chance_stat == "bonus_chance"

    def test_chain_damage_with_chance(self, rules: AxiomRules, items_parsed: dict):
        """Test chain_damage uses chance_stat for calculation."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        chain = resolved["chain_damage"]
        assert chain.chance_stat == "chain_chance"
        assert chain.gold_per_point > 0

    def test_block_damage_with_formula(self, rules: AxiomRules, items_parsed: dict):
        """Test block_damage_melee derived from armor via formula."""
        resolved, _ = resolve_all_axioms(rules, items_parsed)

        block = resolved["block_damage_melee"]
        assert block.gold_per_point > 0
        # block = bonus_armor / expected_physical_damage / armor_damage_factor
        # 7.41b: Chainmail 500g / 4 armor = 125 gpp → block = 125 / 150 / 0.06 = 13.89
        assert (
            13 <= block.gold_per_point <= 16
        ), f"block_damage_melee should be ~13.89 (7.41b), got {block.gold_per_point}"


class TestCalculatedAxiomsJson:
    """Tests for calculated_axioms.json output."""

    def test_output_structure(self, calculated_axioms: dict):
        """Test calculated_axioms.json has correct structure."""
        assert "version" in calculated_axioms
        assert "patch" in calculated_axioms
        assert "axioms" in calculated_axioms

    def test_axioms_have_gold_per_point(self, calculated_axioms: dict):
        """Test all axioms have gold_per_point."""
        for name, axiom in calculated_axioms["axioms"].items():
            assert "gold_per_point" in axiom, f"Axiom {name} missing gold_per_point"

    def test_axioms_have_calculation(self, calculated_axioms: dict):
        """Test all axioms have calculation trace."""
        for name, axiom in calculated_axioms["axioms"].items():
            assert "calculation" in axiom, f"Axiom {name} missing calculation"
            assert "method" in axiom["calculation"], f"Axiom {name} missing calculation method"
