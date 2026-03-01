"""Unit tests for extracted helper functions in 03_calculate_costs.py."""

import importlib
import math

import pytest

from axioms.loader import CustomStatConfig, SwitchableStatConfig, UptimeStatConfig

cc = importlib.import_module("pipeline.03_calculate_costs")


class TestApplyCustomStats:
    """Tests for _apply_custom_stats()."""

    def test_no_override_returns_same_stats(self):
        stats = {"bonus_damage": 10.0}
        item = {"stats": stats, "raw_data": {}}
        result = cc._apply_custom_stats(stats, item, None, _mock_rules())
        assert result is stats  # same object, not copied

    def test_formula_adds_synthetic_stat(self):
        stats = {"bonus_damage": 50.0}
        item = {"stats": stats, "raw_data": {}}
        override = _mock_override(
            custom_stats={"effective_dps": CustomStatConfig(formula="bonus_damage * 2")}
        )
        result = cc._apply_custom_stats(stats, item, override, _mock_rules())
        assert result["effective_dps"] == 100.0
        assert result["bonus_damage"] == 50.0

    def test_formula_uses_raw_data(self):
        stats = {"bonus_damage": 10.0}
        item = {"stats": stats, "raw_data": {"AbilityCooldown": "12"}}
        override = _mock_override(
            custom_stats={"dps": CustomStatConfig(formula="bonus_damage / AbilityCooldown")}
        )
        result = cc._apply_custom_stats(stats, item, override, _mock_rules())
        assert abs(result["dps"] - 10.0 / 12.0) < 0.001

    def test_formula_uses_settings(self):
        stats = {"bonus_damage": 10.0}
        item = {"stats": stats, "raw_data": {}}
        override = _mock_override(
            custom_stats={"scaled": CustomStatConfig(formula="bonus_damage * aura_avg_targets")}
        )
        rules = _mock_rules(settings={"aura_avg_targets": 3.0})
        result = cc._apply_custom_stats(stats, item, override, rules)
        assert result["scaled"] == 30.0

    def test_does_not_mutate_original(self):
        stats = {"bonus_damage": 10.0}
        item = {"stats": stats, "raw_data": {}}
        override = _mock_override(
            custom_stats={"extra": CustomStatConfig(formula="bonus_damage + 5")}
        )
        cc._apply_custom_stats(stats, item, override, _mock_rules())
        assert "extra" not in stats

    def test_sqrt_available_in_formula(self):
        stats = {"bonus_damage": 16.0}
        item = {"stats": stats, "raw_data": {}}
        override = _mock_override(
            custom_stats={"root": CustomStatConfig(formula="sqrt(bonus_damage)")}
        )
        result = cc._apply_custom_stats(stats, item, override, _mock_rules())
        assert result["root"] == 4.0


class TestApplySwitchableMultiplier:
    """Tests for _apply_switchable_multiplier()."""

    def test_no_override_returns_unchanged(self):
        gv, note = cc._apply_switchable_multiplier(100.0, "base", None, "stat", None)
        assert gv == 100.0
        assert note == "base"

    def test_applies_multiplier(self):
        override = _mock_override(
            switchable_stats={
                "bonus_damage": SwitchableStatConfig(multiplier=0.5, reason="dual mode")
            }
        )
        breakdown = {"amount": 10, "gold_per_point": 10.0, "total_value": 100.0}
        gv, note = cc._apply_switchable_multiplier(
            100.0, "base", breakdown, "bonus_damage", override
        )
        assert gv == 50.0
        assert "switchable" in note
        assert breakdown["multiplier"] == 0.5
        assert breakdown["total_value"] == 50.0

    def test_ignores_unrelated_stat(self):
        override = _mock_override(
            switchable_stats={"bonus_damage": SwitchableStatConfig(multiplier=0.5)}
        )
        gv, note = cc._apply_switchable_multiplier(100.0, "base", None, "armor", override)
        assert gv == 100.0


class TestApplyUptimeFactor:
    """Tests for _apply_uptime_factor()."""

    def test_no_override_returns_unchanged(self):
        item = {"stats": {}, "raw_data": {}}
        gv, note = cc._apply_uptime_factor(100.0, "base", None, "stat", item, None, _mock_rules())
        assert gv == 100.0

    def test_duration_over_cooldown(self):
        item = {"stats": {}, "raw_data": {"cd": "10", "dur": "5"}}
        override = _mock_override(
            uptime_stats={"bonus_damage": UptimeStatConfig(cooldown_stat="cd", duration_stat="dur")}
        )
        breakdown = {"amount": 10, "gold_per_point": 10.0, "total_value": 100.0}
        gv, note = cc._apply_uptime_factor(
            100.0, "base", breakdown, "bonus_damage", item, override, _mock_rules()
        )
        # factor = 5/10 * 1.0 = 0.5
        assert gv == 50.0
        assert "uptime" in note

    def test_instant_effect_no_duration(self):
        item = {"stats": {}, "raw_data": {"cd": "20"}}
        override = _mock_override(
            uptime_stats={"bonus_damage": UptimeStatConfig(cooldown_stat="cd")}
        )
        breakdown = {"amount": 10, "gold_per_point": 10.0, "total_value": 100.0}
        gv, note = cc._apply_uptime_factor(
            100.0, "base", breakdown, "bonus_damage", item, override, _mock_rules()
        )
        # factor = 1/20 * 1.0 = 0.05
        assert abs(gv - 5.0) < 0.001

    def test_duration_only_no_cooldown(self):
        item = {"stats": {}, "raw_data": {"dur": "3"}}
        override = _mock_override(
            uptime_stats={"bonus_damage": UptimeStatConfig(duration_stat="dur")}
        )
        breakdown = {"amount": 10, "gold_per_point": 10.0, "total_value": 100.0}
        gv, note = cc._apply_uptime_factor(
            100.0, "base", breakdown, "bonus_damage", item, override, _mock_rules()
        )
        # multiply by duration directly
        assert gv == 300.0

    def test_manual_uptime(self):
        item = {"stats": {}, "raw_data": {}}
        override = _mock_override(
            uptime_stats={"bonus_damage": UptimeStatConfig(manual_uptime=0.7, reason="toggle")}
        )
        breakdown = {"amount": 10, "gold_per_point": 10.0, "total_value": 100.0}
        gv, note = cc._apply_uptime_factor(
            100.0, "base", breakdown, "bonus_damage", item, override, _mock_rules()
        )
        assert abs(gv - 70.0) < 0.001
        assert "manual uptime" in note

    def test_cooldown_efficiency_setting(self):
        item = {"stats": {}, "raw_data": {"cd": "10", "dur": "5"}}
        override = _mock_override(
            uptime_stats={"bonus_damage": UptimeStatConfig(cooldown_stat="cd", duration_stat="dur")}
        )
        rules = _mock_rules(settings={"cooldown_efficiency": 0.8})
        breakdown = {"amount": 10, "gold_per_point": 10.0, "total_value": 100.0}
        gv, note = cc._apply_uptime_factor(
            100.0, "base", breakdown, "bonus_damage", item, override, rules
        )
        # factor = 5/10 * 0.8 = 0.4
        assert abs(gv - 40.0) < 0.001


# --- Test helpers ---


class _MockRules:
    def __init__(self, settings=None):
        self.settings = settings or {}


class _MockOverride:
    def __init__(self, custom_stats=None, switchable_stats=None, uptime_stats=None):
        self.custom_stats = custom_stats or {}
        self.switchable_stats = switchable_stats or {}
        self.uptime_stats = uptime_stats or {}


def _mock_rules(settings=None):
    return _MockRules(settings)


def _mock_override(**kwargs):
    return _MockOverride(**kwargs)
