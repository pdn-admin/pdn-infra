#!/usr/bin/env python3
"""
PDN Questionnaire Load Test Tool

Simulates concurrent users filling out the questionnaire on production.
Tests login → user_info → answer questions → complete flow.

Usage:
    python tools/load_test_questionnaire.py --users 10
    python tools/load_test_questionnaire.py --users 50 --url https://pdn-chat.onrender.com
"""

import argparse
import asyncio
import random
import string
import time
from dataclasses import dataclass, field
from typing import List

import aiohttp

BASE_URL = "https://pdn-chat.onrender.com"
PASSWORD = "pdn"


@dataclass
class UserResult:
    user_id: int
    email: str
    login_ms: float = 0
    user_info_ms: float = 0
    answers_ms: float = 0
    complete_ms: float = 0
    total_ms: float = 0
    success: bool = False
    error: str = ""


def random_email():
    """Generate a unique test email."""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"loadtest_{suffix}@test.com"


async def simulate_user(session: aiohttp.ClientSession, user_id: int, base_url: str, fast: bool = False) -> UserResult:
    """Simulate one user completing the full questionnaire flow."""
    email = random_email()
    result = UserResult(user_id=user_id, email=email)
    start = time.time()

    try:
        # Step 1: Login
        t0 = time.time()
        async with session.post(f"{base_url}/pdn-diagnose/login", json={
            "email": email,
            "password": PASSWORD,
        }) as resp:
            if resp.status != 200:
                result.error = f"Login failed: {resp.status}"
                return result
        result.login_ms = (time.time() - t0) * 1000

        # Step 2: Submit user info
        t0 = time.time()
        async with session.post(f"{base_url}/pdn-diagnose/user_info", json={
            "email": email,
            "first_name": f"Test{user_id}",
            "last_name": "LoadTest",
            "phone": f"050{random.randint(1000000, 9999999)}",
            "gender": random.choice(["male", "female"]),
            "native_language": "hebrew",
            "education_level": "academic",
            "birth_year": str(random.randint(1970, 2000)),
        }) as resp:
            if resp.status != 200:
                result.error = f"User info failed: {resp.status} - {await resp.text()}"
                return result
        result.user_info_ms = (time.time() - t0) * 1000

        # Step 3: Answer 26 questions (Part A: 1-26) with realistic think time
        t0 = time.time()
        for q in range(1, 27):
            option = random.choice(["a", "b", "c", "d"])
            async with session.post(f"{base_url}/pdn-diagnose/answer", json={
                "question_number": q,
                "selected_option_code": option,
                "ranking": None,
            }) as resp:
                if resp.status != 200:
                    result.error = f"Answer Q{q} failed: {resp.status}"
                    return result
            # Simulate real user think time (5-10 seconds per question)
            if not fast:
                await asyncio.sleep(random.uniform(5, 10))
        result.answers_ms = (time.time() - t0) * 1000

        # Step 4: Complete questionnaire
        t0 = time.time()
        async with session.post(f"{base_url}/pdn-diagnose/complete_questionnaire") as resp:
            data = await resp.json()
            if resp.status != 200:
                result.error = f"Complete failed: {resp.status} - {data.get('error', '')}"
                return result
        result.complete_ms = (time.time() - t0) * 1000

        result.success = True
        result.total_ms = (time.time() - start) * 1000

    except Exception as e:
        result.error = str(e)
        result.total_ms = (time.time() - start) * 1000

    return result


async def run_load_test(num_users: int, base_url: str, fast: bool = False):
    """Run concurrent users through the questionnaire."""
    mode = "BURST (no think time)" if fast else "REALISTIC (5-10s per question)"
    print(f"\n{'='*60}")
    print(f"  PDN Questionnaire Load Test")
    print(f"  URL: {base_url}/pdn-diagnose")
    print(f"  Concurrent users: {num_users}")
    print(f"  Mode: {mode}")
    print(f"{'='*60}\n")

    # Use a cookie jar per user (separate sessions)
    connector = aiohttp.TCPConnector(limit=num_users + 10)

    results: List[UserResult] = []
    start = time.time()

    # Create separate sessions for each user (each with own cookies)
    tasks = []
    for i in range(num_users):
        jar = aiohttp.CookieJar()
        session = aiohttp.ClientSession(connector=connector, cookie_jar=jar)
        tasks.append((session, simulate_user(session, i + 1, base_url, fast=fast)))

    # Run all users concurrently
    print(f"Starting {num_users} concurrent users...")
    coros = [task for _, task in tasks]
    results = await asyncio.gather(*coros)

    # Close all sessions
    for session, _ in tasks:
        await session.close()
    await connector.close()

    elapsed = time.time() - start

    # Print results
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}\n")

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    print(f"  Total users:    {num_users}")
    print(f"  Successful:     {len(successes)} ✅")
    print(f"  Failed:         {len(failures)} ❌")
    print(f"  Total time:     {elapsed:.1f}s")
    print(f"  Throughput:     {len(successes) / elapsed:.1f} users/sec")

    if successes:
        login_times = [r.login_ms for r in successes]
        info_times = [r.user_info_ms for r in successes]
        answer_times = [r.answers_ms for r in successes]
        complete_times = [r.complete_ms for r in successes]
        total_times = [r.total_ms for r in successes]

        print(f"\n  Latency (ms):")
        print(f"  {'Step':<20} {'Avg':>8} {'P50':>8} {'P95':>8} {'Max':>8}")
        print(f"  {'-'*52}")

        for name, times in [
            ("Login", login_times),
            ("User Info", info_times),
            ("26 Answers", answer_times),
            ("Complete", complete_times),
            ("Total (end-to-end)", total_times),
        ]:
            times_sorted = sorted(times)
            avg = sum(times) / len(times)
            p50 = times_sorted[len(times) // 2]
            p95 = times_sorted[int(len(times) * 0.95)]
            mx = times_sorted[-1]
            print(f"  {name:<20} {avg:>7.0f} {p50:>7.0f} {p95:>7.0f} {mx:>7.0f}")

    if failures:
        print(f"\n  Failures:")
        for r in failures[:10]:
            print(f"    User {r.user_id}: {r.error}")
        if len(failures) > 10:
            print(f"    ... and {len(failures) - 10} more")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="PDN Questionnaire Load Test")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users (default: 10)")
    parser.add_argument("--url", type=str, default=BASE_URL, help="Base URL (default: production)")
    parser.add_argument("--fast", action="store_true", help="Burst mode — no think time between questions")
    args = parser.parse_args()

    asyncio.run(run_load_test(args.users, args.url, fast=args.fast))


if __name__ == "__main__":
    main()
