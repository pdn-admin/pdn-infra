#!/usr/bin/env python3
"""
User Answers Matrix Report Generator

Creates an HTML matrix report showing:
- Rows (X): Users with their UID (מזהה מערכת) and PDN Code
- Columns (Y): Questions (number, description, PDN code options)
- Values: The answer the user selected (selected_option_code or ranking)
"""

import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SAVED_RESULTS_DIR = PROJECT_ROOT / "saved_results"
QUESTIONS_FILE = PROJECT_ROOT / "app" / "data" / "questions.json"
USER_METADATA_CSV = SAVED_RESULTS_DIR / "user_metadata.csv"


def load_questions():
    """Load questions from questions.json, returning only PDN-relevant questions (PartA-PartF)."""
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = {}
    for phase_name, phase_data in data.get("phases", {}).items():
        if phase_name == "PersonalDetails":
            continue
        for q_num, q_data in phase_data.get("questions", {}).items():
            codes = set()
            for opt in q_data.get("options", []):
                if opt.get("code"):
                    codes.add(opt["code"])
            codes_str = "/".join(sorted(codes)) if codes else "-"
            questions[q_num] = {
                "text": q_data.get("text", ""),
                "codes": codes_str,
                "phase": phase_name,
            }
    return questions


def load_users():
    """Load users from user_metadata.csv."""
    users = []
    with open(USER_METADATA_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append({
                "uid": row.get("User ID", ""),
                "email": row.get("Email", ""),
                "pdn_code": row.get("PDN Code", ""),
                "date": row.get("Date", ""),
            })
    return users


def get_user_dir(email):
    """Get user directory path from email (same logic as pdn_file_path.py)."""
    safe_username = "".join(c for c in email if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_username = safe_username.replace(' ', '_')
    return SAVED_RESULTS_DIR / safe_username


def load_user_answers(email):
    """Load answers JSON for a user."""
    user_dir = get_user_dir(email)
    answers_file = user_dir / f"{email}_answers.json"
    if not answers_file.exists():
        return None
    try:
        with open(answers_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def format_answer(answer_data):
    """Format an answer value for display in the matrix cell."""
    if answer_data is None:
        return ""
    if isinstance(answer_data, dict):
        # Binary choice questions (PartA, PartB selected)
        if "selected_option_code" in answer_data:
            return answer_data["selected_option_code"]
        # Ranking questions (PartB, PartC, PartD, PartE)
        if "ranking" in answer_data:
            ranking = answer_data["ranking"]
            if isinstance(ranking, dict):
                # Show as code:rank pairs sorted by rank
                sorted_items = sorted(ranking.items(), key=lambda x: x[1])
                return " ".join(f"{k}:{v}" for k, v in sorted_items)
            return str(ranking)
    return str(answer_data)


def generate_html_report(users, questions, user_answers_map):
    """Generate the HTML matrix report."""
    # Sort questions by phase and number
    def sort_key(q_num):
        try:
            return int(q_num)
        except ValueError:
            return 999

    sorted_q_nums = sorted(questions.keys(), key=sort_key)

    # Count users with answers
    users_with_answers = [u for u in users if u["email"] in user_answers_map and user_answers_map[u["email"]]]
    total_users = len(users)
    answered_users = len(users_with_answers)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<title>PDN - מטריצת תשובות משתמשים</title>
<style>
body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 20px;
    background: #f5f5f5;
    direction: rtl;
}}
h1 {{
    color: #2c3e50;
    text-align: center;
    margin-bottom: 5px;
}}
.summary {{
    text-align: center;
    color: #555;
    margin-bottom: 20px;
    font-size: 14px;
}}
.table-container {{
    overflow-x: auto;
    overflow-y: auto;
    max-height: 85vh;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    padding: 10px;
}}
table {{
    border-collapse: collapse;
    font-size: 11px;
    white-space: nowrap;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 4px 6px;
    text-align: center;
}}
th {{
    background: #34495e;
    color: white;
    position: sticky;
    top: 0;
    z-index: 10;
}}
th.user-header {{
    background: #2c3e50;
    position: sticky;
    right: 0;
    z-index: 20;
    text-align: right;
    min-width: 180px;
}}
td.user-cell {{
    background: #ecf0f1;
    position: sticky;
    right: 0;
    z-index: 5;
    text-align: right;
    font-weight: bold;
    font-size: 10px;
}}
th.q-header {{
    writing-mode: vertical-rl;
    text-orientation: mixed;
    max-width: 30px;
    height: 180px;
    font-size: 9px;
    padding: 4px 2px;
}}
td.answer-cell {{
    font-size: 10px;
    min-width: 30px;
}}
td.answer-ap {{ background: #d4efdf; color: #1e8449; }}
td.answer-et {{ background: #d6eaf8; color: #1a5276; }}
td.answer-tp {{ background: #fdebd0; color: #935116; }}
td.answer-ae {{ background: #fadbd8; color: #922b21; }}
td.answer-ranking {{ background: #f9f9f9; color: #333; font-size: 9px; }}
td.answer-pref {{ background: #e8daef; color: #4a235a; font-size: 9px; }}
td.empty {{ background: #f8f8f8; color: #ccc; }}
.pdn-code {{
    display: inline-block;
    padding: 1px 4px;
    border-radius: 3px;
    font-weight: bold;
    font-size: 10px;
    margin-right: 4px;
}}
.pdn-E {{ background: #d6eaf8; color: #1a5276; }}
.pdn-A {{ background: #d4efdf; color: #1e8449; }}
.pdn-T {{ background: #fdebd0; color: #935116; }}
.pdn-P {{ background: #fadbd8; color: #922b21; }}
.pdn-NA {{ background: #eee; color: #999; }}
.phase-header {{
    background: #7f8c8d;
    color: white;
    font-weight: bold;
    font-size: 10px;
}}
</style>
</head>
<body>
<h1>PDN - מטריצת תשובות משתמשים</h1>
<div class="summary">
    סה"כ משתמשים: {total_users} | משתמשים עם תשובות: {answered_users} | שאלות: {len(sorted_q_nums)}<br>
    נוצר: {datetime.now().strftime("%d/%m/%Y %H:%M")}
</div>
<div class="table-container">
<table>
<thead>
<tr>
<th class="user-header">משתמש (מזהה מערכת / PDN)</th>
"""

    # Column headers - question numbers with description
    current_phase = None
    for q_num in sorted_q_nums:
        q = questions[q_num]
        phase = q["phase"]
        short_text = q["text"][:40] + ("..." if len(q["text"]) > 40 else "")
        codes = q["codes"]
        html += f'<th class="q-header" title="Q{q_num}: {q["text"]} [{codes}]">Q{q_num} [{codes}]</th>\n'

    html += "</tr>\n</thead>\n<tbody>\n"

    # Rows - each user
    for user in users:
        email = user["email"]
        uid = user["uid"]
        pdn = user["pdn_code"] or "NA"
        pdn_class = f"pdn-{pdn[0]}" if pdn and pdn[0] in "EATP" else "pdn-NA"

        answers = user_answers_map.get(email, {})
        if not answers:
            continue  # Skip users without answers

        html += f'<tr><td class="user-cell">'
        html += f'<span class="pdn-code {pdn_class}">{pdn}</span> '
        html += f'{uid}</td>\n'

        for q_num in sorted_q_nums:
            answer = answers.get(str(q_num))
            if answer is None or answer == "":
                # Check if stored differently
                answer = answers.get(q_num)

            if answer is None or (isinstance(answer, dict) and "question_text" not in answer and "selected_option_code" not in answer and "ranking" not in answer):
                html += '<td class="answer-cell empty">-</td>\n'
                continue

            formatted = format_answer(answer)
            if not formatted:
                html += '<td class="answer-cell empty">-</td>\n'
                continue

            # Determine cell class based on answer
            cell_class = "answer-cell"
            if formatted in ("AP", "A"):
                cell_class += " answer-ap"
            elif formatted in ("ET", "E"):
                cell_class += " answer-et"
            elif formatted in ("TP", "T"):
                cell_class += " answer-tp"
            elif formatted in ("AE", "P"):
                cell_class += " answer-ae"
            elif ":" in formatted:
                cell_class += " answer-ranking"
            elif formatted not in ("AP", "ET", "TP", "AE"):
                cell_class += " answer-pref"

            html += f'<td class="{cell_class}" title="Q{q_num}: {formatted}">{formatted}</td>\n'

        html += "</tr>\n"

    html += """</tbody>
</table>
</div>
</body>
</html>"""
    return html


def main():
    print("Loading questions...")
    questions = load_questions()
    print(f"  Loaded {len(questions)} questions")

    print("Loading users...")
    users = load_users()
    print(f"  Loaded {len(users)} users")

    print("Loading user answers...")
    user_answers_map = {}
    for user in users:
        email = user["email"]
        answers = load_user_answers(email)
        if answers:
            # Remove metadata key
            answers_only = {k: v for k, v in answers.items() if k != "metadata"}
            user_answers_map[email] = answers_only

    answered_count = sum(1 for v in user_answers_map.values() if v)
    print(f"  Found answers for {answered_count} users")

    print("Generating HTML report...")
    html = generate_html_report(users, questions, user_answers_map)

    output_path = PROJECT_ROOT / "docs" / "user_answers_matrix.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report saved to: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    output = main()
    print(f"\nDone! Opening report...")
    os.system(f"open '{output}'")
