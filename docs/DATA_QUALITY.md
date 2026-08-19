# Data quality contract

Proofline treats cleaning as a governed transformation, not an invisible CSV
rewrite. The source rows remain immutable in `raw_records`; every repair,
deduplication, quarantine, and business classification is written to
`quality_events` with its source row and record key.

## Moneki policy

The processor applies rules in a fixed order so a row is counted once in the
most actionable quarantine category.

| Stage | Policy | Why it is safe |
| --- | --- | --- |
| Parse | Route `YYYY-MM-DD`, `YYYY/MM/DD`, and `DD-MM-YYYY` explicitly | Avoids ambiguous global date inference |
| Normalize | Trim and uppercase identifiers | Repairs casing/whitespace without changing identity |
| Money | Remove a leading `¥`; parse exact decimal values into integer cents | Avoids floating-point drift and preserves sign |
| Deduplicate | Compare the complete canonical row signature | Catches duplicates that differ only in repairable formatting |
| Conflict | Quarantine every surviving row when one order ID has different canonical payloads | Never chooses an arbitrary version of a disputed transaction |
| Referential integrity | Quarantine unknown stores/products | Prevents silent attribution to the wrong dimension |
| Quantity | Require a strictly positive integer | Zero/negative quantities are not treated as sales |
| Amount | Require an explicit amount matching `quantity × unit price` in absolute value | Missing amounts are not imputed because discounts are not represented in the source contract |
| Refund | Preserve a valid negative amount and classify it as a refund | Revenue remains net of supported refunds |

No source file is modified. Quarantined rows remain queryable through their raw
payload and quality event, so a future source correction can be reprocessed.

## Reproducible baseline

For the assignment dataset, the executable contract in
`backend/tests/test_moneki_processing.py` asserts:

| Outcome | Count |
| --- | ---: |
| Raw sales rows | 12,131 |
| Accepted canonical sales | 11,869 |
| Canonical duplicates removed | 78 |
| Rows quarantined | 184 |
| Repairs recorded | 203 |
| Valid refunds preserved | 49 |

Quarantine reasons are mutually exclusive under the precedence above: 4
conflicting-order rows, 7 unknown-store rows, 30 unknown-product rows, 24
invalid-quantity rows, and 119 missing/invalid-amount rows.

The same test locks the monthly net revenue and order totals:

| Month | Net revenue | Orders |
| --- | ---: | ---: |
| 2026-05 | ¥139,446.00 | 3,836 |
| 2026-06 | ¥132,440.00 | 3,789 |
| 2026-07 | ¥151,527.00 | 4,244 |

The derived monthly average order values are ¥36.35, ¥34.95, and ¥35.70 after
display rounding. Internally, the semantic layer retains two decimal places in
minor currency units before presentation (for example, June is 3,495.38 cents).

If a future code change alters any count or total, CI fails and requires an
explicit policy review rather than silently changing dashboard numbers.
