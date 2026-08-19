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

### Prompt 003 — grounded assistant boundary

> Build the AI question-answering layer so the model can interpret language but
> can never calculate, provide SQL, or introduce a numeric fact. It must support
> the three required questions, a contextual month follow-up, and an honest
> unsupported-question path without an API key.

**Outcome:** Common intents resolve locally; optional OpenAI-compatible model
output is constrained to `{intent, product, month}`. All answer values and
citations are generated from the governed analytics service.

**Verification:** Golden tests assert the category leader, June beef-poke
revenue, recent AOV direction, May follow-up, evidence processing run, and
zero-citation refusal path.

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

### A plausible hand-calculated AOV was rejected

The initial planning note recorded June average order value as approximately
¥34.95, but also carried an incorrect unrounded intermediate value. The
semantic golden test recomputed `13,244,000 cents / 3,789 orders` and failed on
the mismatch. The contract now asserts 3,495.38 cents internally, with ¥34.95
as the presentation-rounded value. This is why derived numbers are computed by
the governed metric service rather than copied from prose.

### A follow-up answer fixture contained an invented number

While writing the context test for “那五月呢？”, AI assistance proposed
¥13,692 as the expected May revenue for beef poke without first executing the
metric query. The grounding test failed: the governed semantic result is
¥13,020. The fixture was corrected to the tool result, and the test now proves
that follow-up context changes only the month while preserving the product.
This is the exact failure mode the product architecture is designed to stop.

## Human-owned decisions

| Decision kept human-owned | Why |
| --- | --- |
| Evidence-first product positioning and reusable platform boundary | This determines who the product serves and what trust promise it makes; it is not a code-completion choice |
| Repair versus quarantine policy | Imputation changes business truth. Missing amounts and conflicting IDs required an explicit risk decision |
| Revenue, order count, AOV, and refund definitions | Metric semantics are business contracts; AI may implement them but cannot choose them silently |
| LLM versus deterministic-computation boundary | Allowing free SQL or model-generated numbers would violate the assignment’s central correctness requirement |
| Visual hierarchy and proactive insight selection | The choice to foreground trust rate, evidence IDs, and growth decomposition reflects product judgment |
| Final acceptance and release | Automated checks provide evidence, but a human remains accountable for whether the evidence is sufficient |
