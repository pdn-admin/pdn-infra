#!/usr/bin/env python3
"""
Compare pre-deploy snapshot against current recalculation results.
Flags any differences between the production export and the new algorithm.

Usage:
    python tools/compare_snapshot.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.pdn_calculator import calculate_pdn_code
from app.utils.answer_storage import load_answers


def main():
    snapshot_path = Path("saved_results/pre_deploy_snapshot.json")
    if not snapshot_path.exists():
        print("ERROR: pre_deploy_snapshot.json not found")
        return 1

    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    users = snapshot["users"]
    print("=" * 70)
    print("SNAPSHOT vs RECALCULATION COMPARISON")
    print(f"Snapshot: {snapshot['description']}")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total users in snapshot: {len(users)}")
    print("=" * 70)
    print()

    differences = []
    no_answers = []
    same = []
    new_verifications = []

    for user in users:
        email = user["email"]
        stored_code = user["pdn_code"]

        answers = load_answers(email)
        if not answers:
            no_answers.append(user)
            continue

        result = calculate_pdn_code(answers, return_details=True)

        if isinstance(result, dict):
            new_code = result.get("pdn_code", "NA")
            needs_verification = result.get("needs_verification", False)
            missing_stage_e = result.get("missing_stage_e", False)
        else:
            new_code = result
            needs_verification = False
            missing_stage_e = False

        # Compare codes
        if stored_code and new_code != stored_code:
            differences.append({
                "email": email,
                "name": user["name"],
                "stored_code": stored_code,
                "new_code": new_code,
                "stored_status": user["status"],
                "needs_verification": needs_verification,
                "missing_stage_e": missing_stage_e,
            })
        else:
            same.append(email)

        # Track new verifications (was OK before, now flagged)
        if user["status"] == "תקין" and needs_verification:
            new_verifications.append({
                "email": email,
                "name": user["name"],
                "code": new_code,
                "missing_stage_e": missing_stage_e,
            })

    # Print results
    print("-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"  Same code:              {len(same)}")
    print(f"  DIFFERENT code:         {len(differences)}")
    print(f"  No answers (skipped):   {len(no_answers)}")
    print(f"  New verifications:      {len(new_verifications)}")
    print()

    if differences:
        print("=" * 70)
        print("DIFFERENCES - Code changed after new algorithm")
        print("=" * 70)
        for i, d in enumerate(differences, 1):
            print(f"\n  [{i}] {d['name']} ({d['email']})")
            print(f"      Production code:  {d['stored_code']}")
            print(f"      New calc code:    {d['new_code']}")
            print(f"      Was status:       {d['stored_status']}")
            flags = []
            if d['needs_verification']:
                flags.append("NEEDS_VERIFICATION")
            if d['missing_stage_e']:
                flags.append("MISSING_STAGE_E")
            if flags:
                print(f"      Flags:            {', '.join(flags)}")
        print()
    else:
        print("  >>> NO DIFFERENCES FOUND - All codes match production <<<")
        print()

    if new_verifications:
        print("=" * 70)
        print("NEW VERIFICATIONS - Previously OK, now flagged")
        print("=" * 70)
        for v in new_verifications:
            reason = "missing Stage E" if v["missing_stage_e"] else "close scores"
            print(f"  {v['name']} ({v['email']}) | code: {v['code']} | reason: {reason}")
        print()

    if no_answers:
        print(f"  ({len(no_answers)} users skipped - no answer files found)")
        print()

    return len(differences)


if __name__ == "__main__":
    diff_count = main()
    sys.exit(1 if diff_count > 0 else 0)
