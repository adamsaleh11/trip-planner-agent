# Plan: Journal Collective Memory

> Source PRD: T4.1 -- Journal + anonymous collective trip memory (RAG), with 2026-06-10 free-tier retrieval pivot and grill-session decisions.

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `POST /trips/{id}/complete`, `GET /trips/{id}/journal`, `PUT /trips/{id}/journal/{placeId}`, `POST /trips/{id}/journal/from-whim/{whimId}`, `GET /me/shares`, and `DELETE /me/shares/{opaqueId}`.
- **Schema**: Journal entries are trip-scoped and venue-centric. Each journal stop stores public-to-trip stop metadata plus private per-member contribution state. Shared collective-memory docs store only anonymized retrieval payloads plus embeddings.
- **Key models**: `journalEntries`, `collectiveMemory`, and private owner-scoped `collectiveMemoryShares/{uid}/items/{opaqueId}` deletion map.
- **Auth**: Completing a trip is admin-only. Journal reads and writes are trip-member-only. Per-member note content remains private to its author. Whim-to-journal requires the whim owner to still be a trip member.
- **External services**: Production sharing uses regex pre-scrub, Gemini Flash scrub, regex post-scrub, and `gemini-embedding-001` embeddings. Tests and local fallback use dependency-injected fakes.
- **Retrieval**: The default backend is exact cosine scan over Firestore docs behind a `MemoryRetriever` interface. Hosted Vertex Vector Search is the documented scale path, not deployed for the free-tier MVP.
- **Privacy**: Shared payloads never store uid, tripId, member names, emails, handles, phone numbers, or exact dates. Destination is normalized below full raw trip text. Opaque IDs are deterministic HMACs using a server secret so edits overwrite and users can delete their own shared datapoints.
- **Failure behavior**: If scrub or embedding fails during opt-in share, the private journal contribution is still saved, but no public memory doc is created.

---

## Phase 1: Complete Trip Seeds Private Journal

**User stories**: Admin completes a generated trip; itinerary stops and scheduled manual plans become journal-ready private stubs.

### What to build

Complete-trip behavior that marks the trip completed and creates missing journal stubs from the latest generated itinerary. The operation is idempotent and preserves any existing member notes. Only concrete itinerary stops with real `placeId` values become journal entries, including scheduled manual-plan stops.

### Acceptance criteria

- [ ] Admin can complete a generated trip and the trip status becomes `completed`.
- [ ] Completion creates one journal stub per unique itinerary place with place ID, name, category, address, coordinates, source, and manual-plan reference when present.
- [ ] Running completion again does not erase existing ratings or notes and does not duplicate stubs.
- [ ] Members can read the journal stubs; non-members cannot.

---

## Phase 2: Member Journal Save And Private Reads

**User stories**: Members rate/write notes per place; notes are private by default; non-members cannot read or write.

### What to build

Member journal editing through the trip journal API. A member can update rating, note, and share preference for a journaled place. Journal reads return stop metadata and the current user's own contribution only.

### Acceptance criteria

- [ ] Members can save rating 1-5 and a note up to 1000 characters.
- [ ] Missing `shareAnonymously` defaults to false.
- [ ] A member cannot see another member's private note through `GET /trips/{id}/journal`.
- [ ] Non-members cannot read or write journal entries.

---

## Phase 3: Production Anonymous Share Pipeline

**User stories**: Member opts into sharing; note is scrubbed, embedded, stored with opaque HMAC ID and anonymized hydration payload.

### What to build

When a member saves a journal contribution with `shareAnonymously=true`, the system requires a rating, regex-scrubs obvious PII before model exposure, asks Gemini Flash to remove identifying references while preserving the travel tip, regex-scrubs again, embeds the anonymized venue-context text, and writes a deterministic collective-memory document plus a private deletion-map item. If the scrub or embed boundary fails, the contribution is saved privately and the public share is skipped.

### Acceptance criteria

- [ ] Shared payload includes destination, category, placeId, venueName, rating, scrubbedText, groupSizeBucket, monthVisited, embedding, and optional synthetic marker.
- [ ] Shared payload excludes uid, tripId, member names, participant names, emails, handles, phones, and exact dates.
- [ ] A note containing a member name plus email/handle/phone is retrievable only after scrubbing.
- [ ] Editing a shared entry overwrites the same opaque ID with no duplicate memory docs.
- [ ] A failed scrub or embedding call leaves the journal note private and creates no collective-memory doc.
- [ ] Sharing requires a rating, while private journal saves may omit one.

---

## Phase 4: Exact Memory Retrieval And Deletion

**User stories**: Another account can retrieve shared tips for the same destination/category; unshared notes are never retrievable; delete/unshare removes the shared memory.

### What to build

Exact cosine retrieval over shared memory docs, filtered by normalized destination and category, plus user-visible share listing and deletion. Toggle-off uses the same deletion path and only succeeds for shares owned by the caller's private deletion map.

### Acceptance criteria

- [ ] `search_collective_memory(destination, category, query)` returns top matching anonymized tips for the same destination/category.
- [ ] Destination matching avoids raw trip text and distinguishes common city/country variants when the input includes them.
- [ ] A different account's generation path can retrieve another user's shared tip, while unshared notes are absent.
- [ ] `DELETE /me/shares/{opaqueId}` removes both the public memory doc and private deletion-map item.
- [ ] Retrieval before and after deletion proves the entry is gone.

---

## Phase 5: Retriever Abstraction And Scale Path

**User stories**: The MVP stays on a free exact retriever, while the production architecture has a clear swap path for larger corpora.

### What to build

Keep the public `search_collective_memory(destination, category, query)` interface stable while routing retrieval through a small retriever abstraction. The Firestore exact-cosine retriever is the default. The handoff docs describe when to swap to Vertex Vector Search and which fields become restricts/filters.

### Acceptance criteria

- [ ] Retrieval behavior is exercised through the stable tool interface, not a hosted index.
- [ ] The default retriever stores and reads embeddings from `collectiveMemory`.
- [ ] A future Vertex retriever can be introduced without changing journal writes or agent tool callers.
- [ ] Documentation explains the corpus-size or latency trigger for switching backends.

---

## Phase 6: Agent Citation Integration

**User stories**: Category agents can use anonymous traveler tips; generated itinerary `whyItFits` can cite "travelers tip".

### What to build

Category agents may call memory once per category and receive up to five anonymized tips as context. Memory-inspired suggestions remain grounded through Places and can carry an explicit `travelersTip` field as well as a "travelers tip" citation inside explanatory text.

### Acceptance criteria

- [ ] Category agents may call collective memory at most once per generation and receive top-5 anonymized tips.
- [ ] Category results can expose optional `travelersTip` without breaking existing clients.
- [ ] Memory-inspired recommendations remain marked `suggested=true` unless directly grounded in current-trip preferences.
- [ ] A live itinerary stop can include a "travelers tip" citation in `whyItFits`.

---

## Phase 7: Whim Memory And Journal Tie-In

**User stories**: Right Now suggestions can include `travelersTip`; a trip-context whim can be saved into the journal by its owner.

### What to build

Trip-context whim responses attach a matching anonymous traveler tip when available. A member can save their own trip-context whim suggestion into that trip's journal, where it behaves like any other journal entry and can later be rated, edited, or explicitly shared.

### Acceptance criteria

- [ ] Trip-context whim responses can include `travelersTip` from collective memory.
- [ ] Whim owner can save a trip-context suggestion into that trip's journal.
- [ ] Non-owners and non-members cannot save a whim into the journal.
- [ ] A saved whim can be shared anonymously and retrieved like any other journal entry.

---

## Phase 8: Synthetic Seed And Demo Proof

**User stories**: Synthetic collective memory entries support demos without real user data.

### What to build

Add a repeatable seed script that creates clearly synthetic collective-memory docs for demo destinations using the same embedding boundary as production. Seed data must never read from users, trips, journal entries, or private collections.

### Acceptance criteria

- [ ] Seed script creates about 15 clearly synthetic entries across 2-3 real destinations.
- [ ] Seed entries are marked `synthetic: true`.
- [ ] Seed entries use embeddings compatible with production query embeddings.
- [ ] No real user, real trip, or Rio trip data is read or written.
