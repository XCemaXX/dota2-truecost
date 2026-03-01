"""
Pytest fixtures for 2parser tests.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from axioms.loader import AxiomRules, load_axiom_rules


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def rules(project_root: Path) -> AxiomRules:
    """Load actual axiom rules from YAML."""
    return load_axiom_rules(project_root / "src" / "axioms" / "axiom_rules.yaml")


@pytest.fixture(scope="session")
def items_parsed(project_root: Path) -> dict:
    """Load parsed items from JSON."""
    items_path = project_root / "output" / "items_parsed.json"
    with open(items_path, "r", encoding="utf-8") as f:
        items_list = json.load(f)
    # Convert list to dict by id
    return {item["id"]: item for item in items_list}


@pytest.fixture(scope="session")
def calculated_axioms(project_root: Path) -> dict:
    """Load calculated axioms from JSON."""
    axioms_path = project_root / "output" / "calculated_axioms.json"
    with open(axioms_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def effective_costs(project_root: Path) -> list:
    """Load effective costs from JSON."""
    costs_path = project_root / "output" / "effective_costs.json"
    with open(costs_path, "r", encoding="utf-8") as f:
        return json.load(f)
