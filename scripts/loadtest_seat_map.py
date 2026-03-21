#!/usr/bin/env python3
"""
Fire concurrent GET /api/v1/flights/{id}/seats and print latency p50 / p95 / p99 (ms).

Requires: pip install httpx
Run with API up, e.g.:
  python scripts/loadtest_seat_map.py --base-url http://127.0.0.1:8000 --flight-id 1 -n 200 -c 50
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import sys
import time


def _pct(sorted_ms: list[float], p: float) -> float:
    if not sorted_ms:
        return 0.0
    k = max(0, min(len(sorted_ms) - 1, math.ceil(p * len(sorted_ms)) - 1))
    return sorted_ms[k]


async def _run(args: argparse.Namespace) -> int:
    try:
        import httpx
    except ImportError:
        print("Install httpx: pip install httpx", file=sys.stderr)
        return 1

    url = f"{args.base_url.rstrip('/')}/api/v1/flights/{args.flight_id}/seats"
    sem = asyncio.Semaphore(args.concurrency)
    latencies: list[float] = []
    errors = 0

    async def one(client: httpx.AsyncClient) -> None:
        nonlocal errors
        async with sem:
            t0 = time.perf_counter()
            try:
                r = await client.get(url)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                if r.status_code >= 400:
                    errors += 1
                else:
                    latencies.append(dt_ms)
            except Exception:
                errors += 1

    async with httpx.AsyncClient(timeout=30.0) as client:
        await asyncio.gather(*[one(client) for _ in range(args.requests)])

    latencies.sort()
    print(f"URL: {url}")
    print(f"OK: {len(latencies)}  errors: {errors}  concurrency: {args.concurrency}")
    if latencies:
        print(
            f"ms — min: {latencies[0]:.1f}  p50: {_pct(latencies, 0.50):.1f}  "
            f"p95: {_pct(latencies, 0.95):.1f}  p99: {_pct(latencies, 0.99):.1f}  "
            f"max: {latencies[-1]:.1f}  mean: {statistics.mean(latencies):.1f}"
        )
        if _pct(latencies, 0.95) >= 1000:
            print("Note: p95 >= 1000 ms — tune DB/Redis/pool or reduce load for the assignment target.")
    return 0 if errors == 0 else 2


def main() -> None:
    p = argparse.ArgumentParser(description="Seat map load / latency smoke test")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--flight-id", type=int, default=1)
    p.add_argument("-n", "--requests", type=int, default=200, help="total GET requests")
    p.add_argument("-c", "--concurrency", type=int, default=50)
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
