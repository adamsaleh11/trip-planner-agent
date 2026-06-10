# T4.3b — Metrics & evals dashboard UI

Repo: trip-journal-web (frontend) · System: Mac · Type: Next.js page
Skills: read-contract, frontend-tdd · Agent: CODEX (GPT 5.5, fullstack) · Depends on: T2.1 shell (dashboard stub route exists) · Mock-first: do NOT wait for 04-03a · Parallel with: 04-01 (Claude), 03-06 (Gemini)
Plan: ../trip-planner-agent/plans/trip-journal-pivot.md · Phase 4 · Wave 3

## Coordination rules
- You own ONLY the `/dashboard` route and its components this wave. Gemini owns trip pages, generation/whim UI, API client internals — do not edit shared files (`lib/api/types.ts`: append your types in one block at the end, never reorder).
- Build against the mocked endpoint shapes below; integrate live when 04-03a lands (config-only switch).

## Goal

The observability page: recent generations and whims with LLM-native metrics side by side (the two execution models contrasted), eval score history, and Cloud Trace link-outs — the FDE-rubric artifact rendered in-product.

## Responsibilities

- `/dashboard` (any signed-in user, demo-visibility by design): three sections.
- **Recent generations table**: trip name, status, latency (s), totalTokens, tokens/sec, estCostUsd, billingTier, started time, link-out to Cloud Trace (`https://console.cloud.google.com/traces/list?project=trip-agent-498919&tid={traceId}`). Mock shape (per 04-03a ticket): `GET /admin/generations/recent` → `[{tripId, tripName, status, latencyMs, totalTokens, tokensPerSecond, estCostUsd, billingTier, traceId, startedAt}]`.
- **Recent whims table**: same metric columns from `GET /admin/whims/recent` (same shape minus tripName, plus whimText excerpt). Place adjacent to generations — the latency contrast (seconds vs minutes) is the point; surface it visually (e.g., shared latency scale or explicit caption).
- **Eval runs**: `GET /admin/eval-runs` → `[{runId, timestamp, model, gitSha, aggregates: {schemaValidity, groundedness, constraintAdherence, suggestedFlagHonesty}}]` — render as compact score bars/sparkline over time; per-run detail on click.
- States per frontend-tdd: loading skeletons, empty ("no generations yet — run one"), error+retry. Dark-theme-consistent, mobile-acceptable (tables collapse to cards).
- Keep all fetch shapes in one `lib/api/adminTypes.ts` (new file, yours alone) so live integration is a base-URL/endpoint flip.

## Acceptance criteria

- [ ] Page renders all three sections from mock data with full state coverage (loading/empty/error tested).
- [ ] Trace links open the correct Cloud Trace URL format with the row's traceId.
- [ ] Generations vs whims latency contrast is visually evident.
- [ ] Zero edits to files owned by Gemini this wave (verify via git diff file list).
- [ ] Live integration after 04-03a is a one-commit config change.
