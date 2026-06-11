# Plan: Observability And Evals Backend

> Source PRD: T4.3a observability/evals backend ticket and grill-me decisions from 2026-06-10

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `GET /admin/generations/recent`, `GET /admin/whims/recent`, and `GET /admin/eval-runs` expose dashboard-ready backend read models. The dashboard UI remains owned by 04-03b.
- **Schema**: generation docs remain under `trips/{tripId}/generations/{generationId}`; whim docs remain top-level under `whims/{whimId}`; eval run docs live at top-level `evalRuns/{runId}`.
- **Key models**: generation and whim rows expose status/text identifiers, trace id, timestamps, latency, token counts, tokens per second, estimated cost, and billing tier. Eval run summaries expose model, git SHA, timestamp, and aggregate scores.
- **Auth**: admin metrics endpoints require a signed-in user only for demo visibility. They do not introduce a global admin role.
- **External services**: OpenTelemetry exports to Google Cloud Trace when configured. Local tests and unconfigured development runs use no-op/in-memory tracing behavior.
- **Trace correlation**: stored `traceId` values are 32-character hex trace IDs and should match the Cloud Trace trace id. Full generations, standalone category runs, and whims each get root spans.
- **Privacy**: span attributes may include trip ids, categories, model names, status, token counts, latency, and tool names. Preference free-text, whim text, prompts, addresses, and raw tool payloads stay out of span attributes.
- **Eval execution**: evals run sequentially by default on the AI Studio free tier, support case subsets, retry transient 503s, and write a reviewable `evalRuns/{runId}` result.

---

## Phase 1: Admin Metrics Read Model

**User stories**: dashboard can read recent generations, recent whims, and eval run summaries from backend contracts.

### What to build

Expose the three backend-only admin endpoints using signed-in demo visibility. The endpoints should return the exact shapes expected by the dashboard ticket and derive rows from existing Firestore document locations without changing generation or whim write paths.

### Acceptance criteria

- [ ] Signed-in users can read recent generation rows with trip name, status, metrics, trace id, and start time.
- [ ] Signed-in users can read recent whim rows with whim text excerpt, metrics, trace id, and creation time.
- [ ] Signed-in users can read recent eval run summaries with aggregate scores.
- [ ] Unauthenticated requests are rejected by the existing auth dependency.

---

## Phase 2: Trace Correlation Baseline

**User stories**: real generation/whim has a Cloud Trace trace id matching the stored doc `traceId`; spans avoid preference free-text.

### What to build

Configure OpenTelemetry once at application startup and wrap generation, standalone category, and whim execution in root spans that reuse the already persisted trace ids. Add child spans for category/coordinator/whim runner work and cache-skip activity, with PII-light attributes only.

### Acceptance criteria

- [ ] A full generation creates a root span using the generation document trace id.
- [ ] Standalone category generation and whim requests create root spans using their stored trace ids.
- [ ] Cached category reuse is visible as child span activity without forcing a re-run.
- [ ] Tests prove preference free-text and whim text are not copied into span attributes.

---

## Phase 3: Metric Constants And Cost Honesty

**User stories**: dashboard sees latency, tokens/sec, estimated cost, billing tier; free-tier still reports scale cost.

### What to build

Make cost estimation model-aware and explicit, while keeping `billingTier` separate from estimated scale cost. Preserve the existing metrics contract for generations and whims.

### Acceptance criteria

- [ ] Cost estimation uses named pricing constants for configured Flash models.
- [ ] Generation metrics include token counts, latency, estimated cost, LLM/tool call counts, tokens per second, and billing tier.
- [ ] Free-tier runs still compute nonzero estimated cost when token usage is nonzero.
- [ ] Tests verify current default Flash-Lite pricing math.

---

## Phase 4: Eval Scorer Core

**User stories**: schema validity, groundedness, constraint adherence, and suggested-flag honesty are deterministic and test-covered where possible.

### What to build

Add reusable scorer logic for itinerary schema validity, stop grounding, hard-constraint checks, and suggested flag honesty. Keep scorers independent from live LLM execution so they can be tested against fixtures.

### Acceptance criteria

- [ ] Schema validity accepts valid itinerary payloads and rejects invalid ones.
- [ ] Groundedness scores deliberately ungrounded stops below 100%.
- [ ] Constraint checks catch rule-detectable hard-constraint violations.
- [ ] Empty-category cases fail when generated stops are not marked `suggested: true`.

---

## Phase 5: Golden Set And Eval Runner

**User stories**: `python -m evals.run` runs synthetic trips live on Flash, supports case subsets, handles free-tier backoff, prints aggregates.

### What to build

Create the golden set, judge rubric, and plain Python eval runner. The runner should execute cases sequentially, score each result, print aggregate scores, and write an `evalRuns/{runId}` document with model, git SHA, per-case results, and aggregates.

### Acceptance criteria

- [ ] Golden set covers filled preferences, empty categories, dietary constraints, conflicting preferences, single-day, 14-day, and an admin-filled unclaimed participant.
- [ ] Runner supports `--cases` to run a subset.
- [ ] Runner retries transient 503/high-demand failures with backoff.
- [ ] Runner writes `evalRuns/{runId}` and pretty-prints aggregate scores.

---

## Phase 6: Evidence And End-To-End Verification

**User stories**: one committed full eval run exists as evidence; real trace can be found from stored trace id; backend contract is ready for 04-03b UI.

### What to build

Record one full eval run artifact safe for review, document smoke verification for Cloud Trace, and ensure endpoint shapes match the dashboard contract.

### Acceptance criteria

- [ ] A reviewable eval result artifact exists without secrets or raw prompts.
- [ ] Smoke steps document how to verify a Cloud Trace trace from a stored `traceId`.
- [ ] Backend endpoint responses match the 04-03b mocked shapes.
- [ ] Relevant tests pass locally without live Firestore, Cloud Trace, or LLM credentials.
