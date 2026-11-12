import pytest

from app.agent.tool_schemas import tool_definitions
from app.domain.quantity_unit import QuantityUnit
from app.tools.shared import ValidationError, _quantity_unit


def test_piece_is_a_known_unit():
    assert QuantityUnit.from_database_value("piece") is QuantityUnit.PIECE
    assert _quantity_unit("piece", 10) == "piece"


def test_piece_requires_a_quantity():
    with pytest.raises(ValidationError):
        _quantity_unit("piece", None)


def test_tool_schema_offers_piece_and_migration_allows_it():
    apply = next(t for t in tool_definitions() if t["function"]["name"] == "apply_journal_actions")
    unit = apply["function"]["parameters"]["properties"]["actions"]["items"]["properties"]["unit"]
    assert "piece" in unit["enum"]
    import pathlib
    assert "'piece'" in pathlib.Path("alembic/versions/f1a2b3c4d5e6_piece_quantity_unit.py").read_text()
