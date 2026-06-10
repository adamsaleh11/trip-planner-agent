# Scale Notes

## Generation Jobs

The MVP generation endpoints use FastAPI `BackgroundTasks` for per-category jobs and coordinator jobs. This is acceptable for local development and early demos because job state is persisted to Firestore and clients observe Firestore progress directly.

Production should move these jobs to Cloud Tasks:

- Enqueue one task for `POST /trips/{tripId}/categories/{category}/generate`.
- Enqueue one coordinator task for `POST /trips/{tripId}/generate`.
- Make each task idempotent against the Firestore job document status and trace id.
- Keep Firestore as the progress source of truth so the frontend listener contract does not change.
- Preserve the same stale/running cutoffs and duplicate POST behavior at the HTTP edge.

Cloud Tasks gives durable retry, survives process restarts, and avoids tying long ADK runs to the lifecycle of a single FastAPI worker.
