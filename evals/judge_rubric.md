# Eval Judge Rubric

Use this rubric only for fuzzy constraint-adherence cases that cannot be scored
with deterministic rules.

- Score `1.0` when the itinerary clearly respects hard constraints.
- Score `0.5` when the itinerary is ambiguous but does not obviously violate a hard constraint.
- Score `0.0` when any stop directly conflicts with a hard constraint.
- Treat dietary restrictions and mobility notes as hard constraints, not preferences.
- Do not reward unsupported venue claims. The deterministic groundedness scorer owns place-id grounding.
