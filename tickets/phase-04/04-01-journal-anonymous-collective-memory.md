# T4.1 — Journal + anonymous collective trip memory (RAG)

Repo: trip-planner-agent (backend) · System: Mac · Type: FastAPI + Vertex AI Vector Search
Skill: tdd · Agent: CLAUDE CODE (backend) · Depends on: T3.2 · Parallel with: T3.3 then T4.2 (Codex)
Plan: plans/trip-journal-pivot.md · Phase 4

## Goal

Close the product loop: completed trips become journal entries; members opt in to sharing anonymized tips into a collective memory index that makes every future group's itinerary smarter — with privacy enforced structurally, not by policy.

## Responsibilities

- `POST /trips/{id}/complete` (admin): trip status → `completed`; seeds `journalEntries` stubs per itinerary stop (placeId, name, category) ready for rating.
- Journal API: `PUT /trips/{id}/journal/{placeId}` per member `{rating 1-5, note (max 1000 chars), shareAnonymously: bool (default FALSE)}`; `GET /trips/{id}/journal` (members only — private by default, period).
- Share pipeline (on save with shareAnonymously=true, re-run on edit):
  1. **PII scrub**: strip person names/handles/emails from the note via one flash call with a strict rewrite prompt ("remove names and identifying references, keep the tip") + regex pass for emails/phones/@handles.
  2. **Embed** scrubbed text + venue context with `text-embedding-005`.
  3. **Upsert** to Vector Search with deterministic opaque ID = HMAC-SHA256(server secret, uid:tripId:placeId) — edits overwrite, ID is unlinkable without the secret. Restricts/filters: destination (city-level token), category. Payload (hydration doc in a PUBLICLY-UNLINKABLE Firestore collection `collectiveMemory/{opaqueId}`): destination, category, placeId, venueName, rating, scrubbedText, groupSizeBucket (solo/small/large), monthVisited. **NO uid, tripId, names, exact dates.**
  4. **Deletion map**: `collectiveMemoryShares/{uid}/items/{opaqueId}` (private, uid-scoped) enabling `DELETE /me/shares/{opaqueId}` → removes datapoint + hydration doc (right-to-erasure).
- Unshare on toggle-off (same deletion path). Index check: verify the existing Vector Search index supports STREAM_UPDATE; if batch-only, create a new streaming index and point config at it (document the steps taken).
- `search_collective_memory(destination, category, query)` tool: embed query → search with destination+category restricts → hydrate from `collectiveMemory` docs → return tips. Wire into T3.1 category agents (replacing the stub): agents receive "tips from past travelers (anonymized)" context; coordinator may cite them in whyItFits as "travelers tip". Also replace the stub in the T3.4 whim agent so Right Now suggestions can carry a `travelersTip`.
- Whim → journal tie-in: `POST /trips/{id}/journal/from-whim/{whimId}` (member, whim owner only) creates a journal entry from a saved whim suggestion — spontaneous outings become part of the trip's story (and, if shared, of collective memory). Enables the "Save to journal" action in T3.5.
- Seed script: ~15 clearly-synthetic entries across 2–3 fictional-but-real destinations (e.g., Lisbon, Mexico City) marked `synthetic: true`. **No real user or Rio trip data — ever.**

## ADK patterns

- RAG as a tool, not a pipeline stage: agents decide when to call; retrieval results are context, never authority (Places remains ground truth for venue existence).

## Model routing

- Scrub: flash. Embeddings: text-embedding-005. Config-driven.

## Cost rules

- Max 1 collective-memory retrieval per category agent per generation (top-5 neighbors). Scrub = 1 flash call per shared note (write-time, not read-time). Embedding at write-time only.

## Acceptance criteria

- [ ] Privacy proof in tests: the retrievable payload for a shared note contains zero of: uid, email, trip id, member names; a note containing "Adam loved this place" comes back scrubbed.
- [ ] Cross-account proof: account B's generation for the same destination retrieves account A's shared (synthetic-style) tip; A's UNSHARED notes are never retrievable.
- [ ] Deletion proof: retrieval before/after `DELETE /me/shares/{id}` shows the entry gone from results and hydration collection.
- [ ] Edits overwrite (no ghost duplicates) — deterministic-ID test.
- [ ] A live generation's whyItFits can carry a travelers-tip citation sourced from seed data; journal entries remain members-only via API tests.

## Updates (2026-06-10 — free-tier switch: NO hosted Vector Search)

- **Retrieval backend changed to $0 mode**: keep the `search_collective_memory(destination, category, query)` interface exactly as specced, but implement it as in-process exact nearest-neighbor (cosine similarity) over `collectiveMemory/{opaqueId}` Firestore docs, which now also store the embedding vector. No index creation, no endpoint deploy, no hourly billing. At this corpus size results are identical to ANN.
- **Embedding model**: `gemini-embedding-001` via the AI Studio key (3072 dims; free tier) — replaces `text-embedding-005`. Keep the model name + dims in config.
- **Vector Search becomes the documented scale path**: implement retrieval behind a small `MemoryRetriever` interface so a `VertexVectorSearchRetriever` is a drop-in class; the handoff doc explains the swap trigger (corpus size / latency) — "right-sized retrieval, swappable backend" is the interview line. The optional demo-day deploy steps move to the handoff doc.
- Everything else stands: opt-in default-false, PII scrub (flash), HMAC opaque IDs (`SERVER_HMAC_SECRET`), deletion map + endpoint, whim→journal endpoint, synthetic-only seed.
- Group-size bucket counts PARTICIPANTS, not just account members.
- Drop the "verify streaming index" task — obsolete in $0 mode.
