# T4.3 — Observability (OTel → Cloud Trace) + eval runner + dashboard

Repo: trip-planner-agent (backend) + trip-journal-web (dashboard page) · System: Mac · Type: OpenTelemetry + eval pipeline
Skill: tdd · Agent: Claude (backend) with Codex assist on the dashboard page if free · Depends on: T3.2 · Parallel with: T4.2 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 4

## Goal

Make the agent system observable and evaluated — distributed traces per generation in Cloud Trace, LLM-native metrics surfaced in-app, and a golden-set eval pipeline proving itinerary quality — the FDE interview rubric, working.

## Responsibilities

- **Tracing**: enable ADK's built-in OpenTelemetry instrumentation; export to Cloud Trace via `opentelemetry-exporter-gcp-trace`. One root span per generation (traceId stored on the generation doc since T3.2 — make them the SAME id so doc ↔ trace correlate); child spans per agent and per tool call. Span attributes: trip-scoped but PII-light (tripId, category, model, tokens — no preference text in span attributes).
- **Metrics already on generation docs** (T3.2): add derived `tokensPerSecond` and confirm estCostUsd math against current flash pricing constant.
- **Eval golden set**: `evals/golden_set.json` — ~10 synthetic trip configs spanning: all-categories-filled, all-empty (pure inference), dietary hard constraints, conflicting preferences (one wants clubs, one wants chill), single-day trip, 14-day trip.
- **Eval runner** (`python -m evals.run`): executes generation per case (live, flash) and scores:
  - *Schema validity*: itinerary parses against the Pydantic schema (binary).
  - *Groundedness*: % of stops whose placeId appeared in tool outputs captured during the run (target 100%).
  - *Constraint adherence*: hard constraints respected (e.g., no steakhouse-only stop for a vegetarian-constrained group) — checked by rules where possible + one flash judge call with rubric for the fuzzy cases (judge prompt included in repo).
  - *Suggested-flag honesty*: empty-category cases must have suggested:true on those categories' stops (binary).
- Results written to Firestore `evalRuns/{runId}` {timestamp, perCase scores, aggregates, model, gitSha}; also pretty-printed to console.
- **Dashboard page** (`/dashboard` in frontend, admin-visible to any signed-in user for demo purposes): recent generations table (trip, latency, tokens, est cost, tokens/sec, status, link to Cloud Trace via trace URL), recent whims table (same metric columns — the latency contrast between the two execution models is the point), eval runs over time (aggregate score per run — simple sparkline/bars), current model + pricing constants display.
- Whim requests get the same OTel treatment (one span tree per whim) — cheap, since T3.4 already records the identical metrics shape.

## Tools / Interfaces

- opentelemetry-sdk + GCP trace exporter; eval runner is plain Python (no framework). Dashboard reads `evalRuns` + recent generations via two new API endpoints (`GET /admin/generations/recent`, `GET /admin/eval-runs`).

## Patterns

- Evals are code-reviewable artifacts: golden set + judge rubric live in the repo; runner is deterministic in structure (LLM variance acknowledged in scoring notes).
- tdd on the scorers themselves: groundedness/constraint scorers unit-tested against fixture itineraries before any live run.

## Model routing

- Generation under eval: flash. LLM judge: flash. Config-driven.

## Cost rules

- Full eval run = 10 generations + ≤10 judge calls ≈ well under $1 on flash; runner prints projected cost before executing and supports `--cases` subset flag.

## Acceptance criteria

- [ ] A real generation produces a Cloud Trace trace (root + agent + tool spans) findable by the traceId shown on the generation doc/dashboard.
- [ ] Scorers pass unit tests on fixtures (including a deliberately-ungrounded itinerary scoring < 100%).
- [ ] `python -m evals.run` completes the golden set, writes evalRuns doc, prints aggregates; at least one full run committed as evidence.
- [ ] Dashboard page renders recent generations with metrics + trace link-outs and eval history.
- [ ] No preference free-text appears in span attributes (privacy check in tests).

## Updates (2026-06-10 — free-tier switch)

- Eval runner runs on the AI Studio free tier: pace cases sequentially and retry 503s with backoff; the rate limits, not cost, are the constraint now. `--cases` subset flag matters more.
- Keep estCostUsd in metrics computed from pricing constants (it answers "what would this cost at scale" even when the bill is $0); add a `billingTier: free|vertex` field on generation metrics so the dashboard is honest.
- Eval cases assemble preferences across PARTICIPANTS (claimed + unclaimed) — include one golden case where an admin filled an unclaimed participant's preferences.
