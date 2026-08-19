from datetime import date

import pytest

from app.workspace_adapters.moneki.normalization import (
    normalize_identifier,
    parse_date,
    parse_integer,
    parse_money_to_cents,
)


@pytest.mark.parametrize(
    ("raw", "expected", "repair_reason"),
    [
        ("2026-05-07", date(2026, 5, 7), None),
        ("2026/05/07", date(2026, 5, 7), "date_format_normalized"),
        ("07-05-2026", date(2026, 5, 7), "date_format_normalized"),
        ("2026-02-30", None, None),
        ("05-07-26", None, None),
        ("", None, None),
    ],
)
def test_parse_date_routes_each_supported_format_explicitly(
    raw: str, expected: date | None, repair_reason: str | None
) -> None:
    result = parse_date(raw)

    assert result.value == expected
    assert result.repair_reason == repair_reason


@pytest.mark.parametrize(
    ("raw", "expected", "repair_reason"),
    [
        ("32", 3_200, None),
        ("-32.50", -3_250, None),
        ("¥ 1,234.50", 123_450, "currency_symbol_removed"),
        ("10.001", None, None),
        ("not-money", None, None),
        (None, None, None),
    ],
)
def test_money_is_parsed_to_integer_cents_without_rounding(
    raw: str | None, expected: int | None, repair_reason: str | None
) -> None:
    result = parse_money_to_cents(raw)

    assert result.value == expected
    assert result.repair_reason == repair_reason


def test_identifier_repair_is_visible() -> None:
    assert normalize_identifier(" s01 ").value == "S01"
    assert normalize_identifier(" s01 ").repair_reason == "identifier_normalized"


@pytest.mark.parametrize(("raw", "expected"), [("2", 2), ("-1", -1), ("2.0", None)])
def test_quantity_requires_an_integer_literal(raw: str, expected: int | None) -> None:
    assert parse_integer(raw).value == expected
