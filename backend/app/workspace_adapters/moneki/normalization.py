import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class NormalizedValue[T]:
    value: T | None
    repair_reason: str | None = None


def normalize_identifier(raw: str | None) -> NormalizedValue[str]:
    if raw is None:
        return NormalizedValue(None)
    normalized = raw.strip().upper()
    if not normalized:
        return NormalizedValue(None)
    reason = "identifier_normalized" if normalized != raw else None
    return NormalizedValue(normalized, reason)


def normalize_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = raw.strip()
    return normalized or None


def parse_date(raw: str | None) -> NormalizedValue[date]:
    value = normalize_text(raw)
    if value is None:
        return NormalizedValue(None)

    formats = (
        (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d", None),
        (r"\d{4}/\d{2}/\d{2}", "%Y/%m/%d", "date_format_normalized"),
        (r"\d{2}-\d{2}-\d{4}", "%d-%m-%Y", "date_format_normalized"),
    )
    for pattern, date_format, repair_reason in formats:
        if re.fullmatch(pattern, value):
            try:
                return NormalizedValue(
                    datetime.strptime(value, date_format).date(),
                    repair_reason,
                )
            except ValueError:
                return NormalizedValue(None)
    return NormalizedValue(None)


def parse_integer(raw: str | None) -> NormalizedValue[int]:
    value = normalize_text(raw)
    if value is None or not re.fullmatch(r"-?\d+", value):
        return NormalizedValue(None)
    return NormalizedValue(int(value))


def parse_money_to_cents(raw: str | None) -> NormalizedValue[int]:
    value = normalize_text(raw)
    if value is None:
        return NormalizedValue(None)

    repair_reason = None
    if value.startswith("¥"):
        value = value.removeprefix("¥").strip()
        repair_reason = "currency_symbol_removed"
    value = value.replace(",", "")

    try:
        amount = Decimal(value)
    except InvalidOperation:
        return NormalizedValue(None)

    cents = amount * 100
    if cents != cents.to_integral_value():
        return NormalizedValue(None)
    return NormalizedValue(int(cents), repair_reason)
