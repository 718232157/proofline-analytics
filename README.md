# Proofline Analytics

**Evidence-first analytics for questions that cannot afford invented numbers.**

Proofline is a reusable analytics platform for relational CSV and database
workspaces. It combines data-quality auditing, a governed metric layer, an
operator dashboard, and natural-language analysis whose answers remain tied to
deterministic query results.

The restaurant assignment is implemented as the first complete workspace,
`moneki`; it is a production-shaped example rather than hard-coded product
logic.

> Current milestone: evidence-linked operator dashboard. Each milestone is
> committed as a runnable, reviewable increment.

## Why this is not a generic chat-with-CSV demo

1. **Evidence before eloquence** — every AI number must originate from a
   validated metric tool and include its scope.
2. **Raw data is immutable** — repairs and exclusions are recorded instead of
   silently rewriting source files.
3. **One semantic contract** — dashboard, API, AI tools, and tests share metric
   and dimension definitions.
4. **Workspace-driven** — new domains provide manifests, joins, cleaning rules,
   metrics, and labels without changing the platform core.
5. **Useful failure** — unsupported questions explain the data boundary and
   never guess.

## Planned Moneki experience

- Daily revenue, order count, average order value, and refund visibility
- Revenue trend and Top 10 product analysis with store/date filters
- Natural-language questions backed by governed analytics tools
- Evidence cards showing filters, metric definitions, and query results
- Follow-up questions and one-click synchronization from chat to dashboard
- A visible ledger for repaired, deduplicated, and quarantined records

The current dashboard already delivers shared date filtering, governed KPI
cards, daily revenue trend, Top 10 product ranking, store-category contribution,
and an auditable quality summary. Charts are loaded as a separate bundle so the
application shell remains fast on first load.

## Repository layout

```text
backend/          Generic ingestion, semantic metrics, AI tools, and API
frontend/         Metadata-driven React analytics experience
workspaces/       Domain manifests and workspace-specific policy
data/             Assignment-provided, immutable Moneki POS exports
docs/             Architecture decisions and original assignment brief
AI_USAGE.md       Transparent AI-assisted development log
DEMO.md           Evidence-backed written product demonstration
```

## Local development

The final submission will provide a three-step startup path. During the
foundation milestone, applications can be started independently:

```bash
# Backend (Python 3.12+)
cd backend
python -m venv .venv
# Activate the environment, then:
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (Node 24+, pnpm 11+)
cd frontend
pnpm install
pnpm dev
```

Backend health check: `GET http://localhost:8000/api/health`

Governed analytics are exposed through one contract rather than dashboard-only
queries:

```http
POST /api/workspaces/moneki/analytics/query
Content-Type: application/json

{
  "metric": "revenue",
  "filters": {"product": ["牛肉poke"]},
  "date_from": "2026-06-01",
  "date_to": "2026-06-30"
}
```

The response includes values in integer minor currency units plus a stable
evidence ID, processing-run ID, metric definition, and human-readable scope.

### Grounded assistant

`POST /api/workspaces/moneki/assistant/chat` accepts a question and optional
prior `context`. The assistant follows a strict two-stage contract:

1. A deterministic resolver handles the required operational intents. When an
   `LLM_API_KEY` is configured, an OpenAI-compatible model may map long-tail
   phrasing into the same closed intent schema; it is explicitly forbidden from
   calculating numbers.
2. The governed analytics service executes the metric query. Only its returned
   values can enter the answer and evidence citations.

Without a key, this is still a real tool chain—not canned numeric text. The
intent resolver creates a semantic query at runtime, and tests compare every
answer citation with the canonical database result. Unsupported questions
return a scoped refusal.

Raw workspace ingestion is deliberately separate from cleaning:

```bash
cd backend
python -m app.cli ingest --workspace moneki
python -m app.cli process --workspace moneki
```

The first command validates `workspaces/moneki/workspace.toml`, imports all
12,156 source rows with provenance, and replaces the previous raw run
atomically. The second applies the deterministic repair/quarantine policy and
writes a row-level quality ledger. See [the data-quality contract](docs/DATA_QUALITY.md).

## Delivery contract

- [ ] Public GitHub repository with meaningful development history
- [ ] Three-step startup and architecture diagram in this README
- [x] Auditable data policy and golden metric tests
- [ ] AI answers whose numbers match database results
- [ ] `AI_USAGE.md` with real prompts, failures, and human-owned decisions
- [ ] `DEMO.md` with required questions and verifiable evidence

## Source and attribution

The `moneki` workspace implements the public
[Moneki full-stack assignment](https://github.com/MorrisPRC/moneki-fullstack-assignment).
Its anonymized CSV files are retained as the immutable source layer.

## License

MIT. See [LICENSE](LICENSE).
