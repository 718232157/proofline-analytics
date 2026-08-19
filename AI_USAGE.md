# AI Usage Report

This file is an evidence log, not a retrospective marketing summary. It is
updated alongside implementation commits so reviewers can see where AI helped,
where it failed, and which decisions remained human-owned.

## Tools used

| Tool | Role | Guardrail |
| --- | --- | --- |
| OpenAI Codex | Repository analysis, implementation assistance, test review, and documentation | Every generated change is inspected and verified against executable tests or source data |

## Task decomposition

1. Inspect the assignment and profile every raw CSV row.
2. Separate reusable trust primitives from the Moneki domain configuration.
3. Define a documented data-quality and metric contract.
4. Build deterministic ingestion and analytics before adding an LLM.
5. Expose only validated semantic tools to the LLM.
6. Prove answer-to-database consistency with golden tests.
7. Build product interactions around evidence, not a generic chat box.

## Prompt log

### Prompt 001 — repository orientation

> Analyze the assignment, identify the actual scoring bottleneck, inspect the
> dirty data, and propose a high-quality implementation and commit plan. Do not
> start by producing a generic dashboard.

**Outcome:** The highest-risk requirement is numerical grounding. The initial
design used a shared metric contract and restricted analytics tools.

**Verification:** Findings were checked against all source CSV rows. They will
be locked by automated data-profile and golden-metric tests.

### Prompt 002 — reusable product boundary

> Do not build only for the assignment. Make it capable of producing real value
> as a general product.

**Outcome:** The architecture was split into a reusable platform and a
configuration-driven Moneki workspace before the foundation commit was made.
Workspace manifests own domain labels and metric policy; ingestion, evidence,
query validation, AI orchestration, and UI primitives remain generic.

**Verification:** No restaurant-specific module is permitted in the platform
core. A later architecture test will load the Moneki workspace through the same
registry interface intended for additional workspaces.

## AI failures and corrections

### Mixed date parsing produced plausible but wrong months

**Incorrect approach:** During exploratory profiling, AI-generated analysis
used a global `dayfirst=True` parser for a column containing ISO dates and
day-first dates. That interpretation moved valid ISO values into unexpected
months.

**How it was detected:** The resulting date range and month distribution did
not match the source contract (May through July 2026). We inspected the raw
string patterns instead of accepting the plausible aggregate.

**Correction:** The production parser now routes the three accepted formats by
regular expression before parsing: `%Y-%m-%d`, `%Y/%m/%d`, and `%d-%m-%Y`.
Unit tests cover each format and invalid calendar dates; the full-dataset test
locks all three monthly totals.

### Why missing amounts are not filled from unit price

An inferred repair (`quantity × unit_price`) would make the dataset look more
complete, but the source has no discount field and contains legitimate negative
refunds. The human-owned decision is therefore to quarantine missing amounts,
retain the raw row, and expose the exclusion in the quality ledger.

## Human-owned decisions

- Evidence-first product positioning and reusable platform boundary
- Data repair versus quarantine policy
- Definitions of revenue, order count, average order value, and refunds
- The boundary between LLM interpretation and deterministic computation
- Final visual hierarchy, acceptance criteria, and release decisions
