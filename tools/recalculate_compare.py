#!/usr/bin/env python3
"""
Recalculate all user PDN codes and compare with stored results.
Flags all cases where the new calculation differs from the stored code.

Usage:
    python tools/recalculate_compare.py
"""

import sys
import os
import csv
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.pdn_calculator import calculate_pdn_code
from app.utils.pdn_file_path import PDNFilePath
from app.utils.answer_storage import load_answers


def load_all_users_from_csv():
    """Load all user emails and current PDN codes from CSV."""
    csv_path = Path(os.getenv('SAVED_RESULTS_DIR', 'saved_results')) / 'user_metadata.csv'
    
    if not csv_path.exists():
        print(f"ERROR: CSV file not found at {csv_path}")
        return []
    
    users = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("Email") or "").strip()
            if not email:
                continue
            users.append({
                "email": email,
                "stored_pdn_code": (row.get("PDN Code") or "").strip(),
                "date": (row.get("Date") or "").strip(),
                "diagnose_pdn_code": (row.get("Diagnose PDN Code") or "").strip(),
            })
    
    return users


def recalculate_user(email):
    """Recalculate PDN code for a user and return detailed result."""
    answers = load_answers(email)
    if not answers:
        return None, "NO_ANSWERS"
    
    # Count answered questions
    digit_keys = [k for k in answers.keys() if k.isdigit()]
    answer_count = len(digit_keys)
    
    result = calculate_pdn_code(answers, return_details=True)
    
    if isinstance(result, dict):
        return {
            "pdn_code": result.get("pdn_code", "NA"),
            "needs_verification": result.get("needs_verification", False),
            "stage_e_override": result.get("stage_e_override", False),
            "missing_stage_e": result.get("missing_stage_e", False),
            "answer_count": answer_count,
            "calculation_details": result.get("calculation_details", []),
        }, None
    else:
        return {
            "pdn_code": result,
            "needs_verification": False,
            "stage_e_override": False,
            "missing_stage_e": False,
            "answer_count": answer_count,
            "calculation_details": [],
        }, None


def main():
    print("=" * 70)
    print("PDN RECALCULATION COMPARISON REPORT")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()
    
    users = load_all_users_from_csv()
    print(f"Total users in CSV: {len(users)}")
    print()
    
    # Results tracking
    differences = []
    missing_stage_e_cases = []
    needs_verification_cases = []
    stage_e_override_cases = []
    no_answers_cases = []
    unchanged = []
    
    for user in users:
        email = user["email"]
        stored_code = user["stored_pdn_code"]
        
        calc_result, error = recalculate_user(email)
        
        if error == "NO_ANSWERS":
            no_answers_cases.append(user)
            continue
        
        new_code = calc_result["pdn_code"]
        
        # Track differences
        if stored_code and new_code != stored_code:
            differences.append({
                "email": email,
                "stored_code": stored_code,
                "new_code": new_code,
                "date": user["date"],
                "diagnose_code": user["diagnose_pdn_code"],
                "needs_verification": calc_result["needs_verification"],
                "stage_e_override": calc_result["stage_e_override"],
                "missing_stage_e": calc_result["missing_stage_e"],
                "answer_count": calc_result["answer_count"],
            })
        else:
            unchanged.append(email)
        
        # Track flags
        if calc_result["missing_stage_e"]:
            missing_stage_e_cases.append({
                "email": email,
                "pdn_code": new_code,
                "answer_count": calc_result["answer_count"],
            })
        
        if calc_result["needs_verification"]:
            needs_verification_cases.append({
                "email": email,
                "pdn_code": new_code,
                "stored_code": stored_code,
            })
        
        if calc_result["stage_e_override"]:
            stage_e_override_cases.append({
                "email": email,
                "pdn_code": new_code,
                "stored_code": stored_code,
            })
    
    # Print results
    print("-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"  Unchanged codes:          {len(unchanged)}")
    print(f"  DIFFERENT codes:          {len(differences)}")
    print(f"  No answers (skipped):     {len(no_answers_cases)}")
    print(f"  Missing Stage E (part 5): {len(missing_stage_e_cases)}")
    print(f"  Needs verification:       {len(needs_verification_cases)}")
    print(f"  Stage E override:         {len(stage_e_override_cases)}")
    print()
    
    if differences:
        print("=" * 70)
        print("DIFFERENCES FOUND - Code changed after recalculation")
        print("=" * 70)
        for i, diff in enumerate(differences, 1):
            print(f"\n  [{i}] {diff['email']}")
            print(f"      Stored code:    {diff['stored_code']}")
            print(f"      New code:       {diff['new_code']}")
            print(f"      Diagnose code:  {diff['diagnose_code'] or '(none)'}")
            print(f"      Date:           {diff['date']}")
            print(f"      Answers:        {diff['answer_count']}")
            flags = []
            if diff['needs_verification']:
                flags.append("NEEDS_VERIFICATION")
            if diff['stage_e_override']:
                flags.append("STAGE_E_OVERRIDE")
            if diff['missing_stage_e']:
                flags.append("MISSING_STAGE_E")
            if flags:
                print(f"      Flags:          {', '.join(flags)}")
        print()
    
    if missing_stage_e_cases:
        print("=" * 70)
        print("MISSING STAGE E (Part 5) - No self-scoring answers")
        print("=" * 70)
        for case in missing_stage_e_cases:
            print(f"  {case['email']} | code: {case['pdn_code']} | answers: {case['answer_count']}")
        print()
    
    if no_answers_cases:
        print("=" * 70)
        print("NO ANSWERS FOUND")
        print("=" * 70)
        for case in no_answers_cases:
            print(f"  {case['email']} | stored code: {case['stored_pdn_code']}")
        print()
    
    # Save full report as JSON
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_users": len(users),
            "unchanged": len(unchanged),
            "differences": len(differences),
            "no_answers": len(no_answers_cases),
            "missing_stage_e": len(missing_stage_e_cases),
            "needs_verification": len(needs_verification_cases),
            "stage_e_override": len(stage_e_override_cases),
        },
        "differences": differences,
        "missing_stage_e": missing_stage_e_cases,
        "no_answers": [u["email"] for u in no_answers_cases],
        "needs_verification": needs_verification_cases,
        "stage_e_override": stage_e_override_cases,
    }
    
    report_path = Path("saved_results") / "recalculation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"Full report saved to: {report_path}")
    print()
    
    if differences:
        print(f"*** {len(differences)} USERS HAVE DIFFERENT CODES AFTER RECALCULATION ***")
    else:
        print("All codes unchanged - no differences found.")
    
    return len(differences)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(1 if exit_code > 0 else 0)
