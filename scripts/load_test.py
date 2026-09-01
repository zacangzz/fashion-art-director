#!/usr/bin/env python3
"""
Fashion Art Director Studio - Cloud Run Load & Resiliency Test
Validates latency, concurrency, and error rates against deployed service.
"""

import sys
import time
import urllib.request
import urllib.error
import concurrent.futures

SERVICE_URL = "https://ai-art-director-prod.web.app"
HEALTH_URL = f"{SERVICE_URL}/health"
CONFIG_URL = f"{SERVICE_URL}/api/models/config"

TOTAL_REQUESTS = 20
CONCURRENCY = 5


def fetch_url(url: str) -> dict:
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LoadTester/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            return {
                "url": url,
                "status": resp.status,
                "latency_ms": elapsed_ms,
                "error": None,
            }
    except Exception as err:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return {
            "url": url,
            "status": getattr(err, "code", 500),
            "latency_ms": elapsed_ms,
            "error": str(err),
        }


def main():
    print(f"[*] Starting Resiliency & Concurrency Test against: {SERVICE_URL}")
    print(f"[*] Concurrency: {CONCURRENCY} workers | Total Requests: {TOTAL_REQUESTS}")

    urls = [HEALTH_URL if i % 2 == 0 else CONFIG_URL for i in range(TOTAL_REQUESTS)]
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(fetch_url, u) for u in urls]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    successes = [r for r in results if r["status"] == 200]
    latencies = [r["latency_ms"] for r in successes]

    print("\n--- Summary Results ---")
    print(f"Total Requests: {len(results)}")
    print(f"Success Rate:   {len(successes)}/{len(results)} ({len(successes)/len(results)*100:.1f}%)")

    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        min_lat = min(latencies)
        max_lat = max(latencies)
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)]
        print(f"Min Latency:    {min_lat:.1f}ms")
        print(f"Avg Latency:    {avg_lat:.1f}ms")
        print(f"P95 Latency:    {p95_lat:.1f}ms")
        print(f"Max Latency:    {max_lat:.1f}ms")

    if len(successes) == len(results):
        print("\n[✔] ALL CONCURRENT REQUESTS PASSED HEALTH & RESILIENCY CHECKS.")
        sys.exit(0)
    else:
        print("\n[x] SOME REQUESTS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
