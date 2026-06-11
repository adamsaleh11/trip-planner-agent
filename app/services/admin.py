from __future__ import annotations

from typing import Any

from app.data.repository import Repository


DEFAULT_LIMIT = 20


def recent_generations(repo: Repository, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trip_id, trip in repo.list("trips"):
        trip_name = trip.get("name") or "Untitled trip"
        for _, generation in repo.list(f"trips/{trip_id}/generations"):
            metrics = generation.get("metrics") or {}
            rows.append(
                {
                    "tripId": trip_id,
                    "tripName": trip_name,
                    "status": generation.get("status", "unknown"),
                    "latencyMs": int(metrics.get("latencyMs") or 0),
                    "totalTokens": int(metrics.get("totalTokens") or 0),
                    "tokensPerSecond": float(metrics.get("tokensPerSecond") or 0.0),
                    "estCostUsd": float(metrics.get("estCostUsd") or 0.0),
                    "billingTier": metrics.get("billingTier") or "free",
                    "traceId": generation.get("traceId") or "",
                    "startedAt": generation.get("startedAt") or "",
                }
            )
    return _latest(rows, "startedAt", limit)


def recent_whims(repo: Repository, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for whim_id, whim in repo.list("whims"):
        metrics = whim.get("metrics") or {}
        rows.append(
            {
                "whimId": whim_id,
                "whimText": whim.get("whimText") or "",
                "latencyMs": int(metrics.get("latencyMs") or 0),
                "totalTokens": int(metrics.get("totalTokens") or 0),
                "tokensPerSecond": float(metrics.get("tokensPerSecond") or 0.0),
                "estCostUsd": float(metrics.get("estCostUsd") or 0.0),
                "billingTier": metrics.get("billingTier") or "free",
                "traceId": whim.get("traceId") or "",
                "createdAt": whim.get("createdAt") or "",
            }
        )
    return _latest(rows, "createdAt", limit)


def recent_eval_runs(repo: Repository, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    rows = [
        {
            "runId": run_id,
            "timestamp": run.get("timestamp") or "",
            "model": run.get("model") or "",
            "gitSha": run.get("gitSha") or "",
            "aggregates": run.get("aggregates") or {},
        }
        for run_id, run in repo.list("evalRuns")
    ]
    return _latest(rows, "timestamp", limit)


def _latest(rows: list[dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: row.get(key) or "", reverse=True)[:limit]
