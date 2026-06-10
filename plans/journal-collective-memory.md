# Plan: Journal Collective Memory

> Source PRD: T4.1 -- Journal + anonymous collective trip memory (RAG), with 2026-06-10 free-tier retrieval pivot.

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: `POST /trips/{id}/complete`, `GET /trips/{id}/journal`, `PUT /trips/{id}/journal/{placeId}`, `POST /trips/{id}/journal/from-whim/{whimId}`, `GET /me/shares`, and `DELETE /me/shares/{opaqueId}`.
- **Schema**: Journal entries are trip-scoped and venue-centric. Each journal stop stores public-to-trip stop metadata plus private per-member contribution state. Shared collective-memory docs store only anonymized retrieval payloads plus embeddings.
- **Key models**: `journalEntries`, `collectiveMemory`, and private owner-scoped `collectiveMemoryShares/{uid}/items/{opaqueId}` deletion map.
- **Auth**: Completing a trip is admin-only. Journal reads and writes are trip-member-only. Per-member note content remains private to its author. Whim-to-journal requires the whim owner to still be a trip member.
- **External services**: PII scrub and embedding are dependency-injected boundaries. The default retrieval backend is exact cosine scan over Firestore docs; hosted Vector Search remains the documented scale path behind the same retriever interface.
- **Privacy**: Shared payloads never store uid, tripId, member names, emails, handles, phone numbers, or exact dates. Opaque IDs are deterministic HMACs using a server secret so edits overwrite and users can delete their own shared datapoints.

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

## Phase 2: Member Journal Save And Privacy

**User stories**: Members rate/write notes per place; notes are private by default; non-members cannot read or write.

### What to build

Member journal editing through the trip journal API. A member can update rating, note, and share preference for a journaled place. Journal reads return stop metadata and the current user's own contribution only.

### Acceptance criteria

- [ ] Members can save rating 1-5 and a note up to 1000 characters.
- [ ] Missing `shareAnonymously` defaults to false.
- [ ] A member cannot see another member's private note through `GET /trips/{id}/journal`.
- [ ] Non-members cannot read or write journal entries.

---

## Phase 3: Opt-In Anonymous Share Pipeline

**User stories**: Member opts into sharing; note is scrubbed, embedded, stored with opaque HMAC ID and anonymized hydration payload.

### What to build

When a member saves a journal contribution with `shareAnonymously=true`, the system scrubs identifying text, embeds the anonymized tip, and writes a deterministic collective-memory document plus a private deletion-map item. Edits overwrite the same shared item.

### Acceptance criteria

- [ ] Shared payload includes destination, category, placeId, venueName, rating, scrubbedText, groupSizeBucket, monthVisited, embedding, and optional synthetic marker.
- [ ] Shared payload excludes uid, tripId, member names, emails, handles, phones, and exact dates.
- [ ] A note containing a member name plus email/handle/phone is retrievable only after scrubbing.
- [ ] Editing a shared entry overwrites the same opaque ID with no duplicate memory docs.

---

## Phase 4: Search And Deletion Loop

**User stories**: Another account can retrieve shared tips for the same destination/category; unshared notes are never retrievable; delete/unshare removes the shared memory.

### What to build

Exact cosine retrieval over shared memory docs, filtered by normalized destination and category, plus user-visible share listing and deletion. Toggle-off uses the same deletion path.

### Acceptance criteria

- [ ] `search_collective_memory(destination, category, query)` returns top matching anonymized tips for the same destination/category.
- [ ] A different account's generation path can retrieve another user's shared tip, while unshared notes are absent.
- [ ] `DELETE /me/shares/{opaqueId}` removes both the public memory doc and private deletion-map item.
- [ ] Retrieval before and after deletion proves the entry is gone.

---

## Phase 5: Agent And Whim Memory Integration

**User stories**: Category agents can use anonymous traveler tips; generated itinerary `whyItFits` can cite "travelers tip"; Right Now suggestions can include `travelersTip`.

### What to build

Replace the existing collective-memory stub with the real retriever while keeping retrieval as a tool. Update category-agent instructions so traveler tips are context, never authority. Enrich trip-context whim suggestions with a matching anonymous traveler tip when available.

### Acceptance criteria

- [ ] Category agents may call collective memory at most once per generation and receive top-5 anonymized tips.
- [ ] Memory-inspired recommendations remain marked `suggested=true` unless directly grounded in current-trip preferences.
- [ ] A live itinerary stop can include a "travelers tip" citation in `whyItFits`.
- [ ] Trip-context whim responses can include `travelersTip` from collective memory.

---

## Phase 6: Whim To Journal And Synthetic Seed Data

**User stories**: A trip-context whim can be saved into the journal by its owner; synthetic collective memory entries support demos without real user data.

### What to build

Allow a member to save their own trip-context whim suggestion into the trip journal using the same journal entry and sharing pipeline as itinerary stops. Add a repeatable seed script that creates clearly synthetic collective-memory docs for demo destinations.

### Acceptance criteria

- [ ] Whim owner can save a trip-context suggestion into that trip's journal.
- [ ] Non-owners and non-members cannot save a whim into the journal.
- [ ] A saved whim can be shared anonymously and retrieved like any other journal entry.
- [ ] Seed script creates about 15 clearly synthetic entries across 2-3 real destinations and never uses real user/trip data.
