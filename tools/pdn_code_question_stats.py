#!/usr/bin/env python3
"""
PDN Code x Question Statistics Matrix

Creates an HTML matrix report showing:
- Rows (X): Questions (number + description)
- Columns (Y): The 12 PDN codes (E1, E5, E9, A3, A7, A11, T4, T8, T12, P2, P6, P10)
- Values: Aggregate statistics of answers per PDN code group
"""

import csv
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SAVED_RESULTS_DIR = PROJECT_ROOT / "saved_results"
QUESTIONS_FILE = PROJECT_ROOT / "app" / "data" / "questions.json"
USER_METADATA_CSV = SAVED_RESULTS_DIR / "user_metadata.csv"

PDN_12_CODES = ["E1", "E5", "E9", "A3", "A7", "A11", "T4", "T8", "T12", "P2", "P6", "P10"]


def load_questions():
    """Load questions from questions.json, returning only PDN-relevant questions."""
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
                "options": q_data.get("options", []),
            }
    return questions


def load_users():
    """Load users from user_metadata.csv."""
    users = []
    with open(USER_METADATA_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdn_code = row.get("PDN Code", "").strip()
            if pdn_code in PDN_12_CODES:
                users.append({
                    "uid": row.get("User ID", ""),
                    "email": row.get("Email", ""),
                    "pdn_code": pdn_code,
                })
    return users


def get_user_dir(email):
    """Get user directory path from email."""
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
    """Extract the answer value (code) from answer data."""
    if answer_data is None:
        return None
    if isinstance(answer_data, dict):
        if "selected_option_code" in answer_data:
            return answer_data["selected_option_code"]
        if "ranking" in answer_data:
            ranking = answer_data["ranking"]
            if isinstance(ranking, dict):
                # Return the top-ranked code (rank 1)
                sorted_items = sorted(ranking.items(), key=lambda x: x[1])
                if sorted_items:
                    return sorted_items[0][0]
            return str(ranking)
    return None


def get_answer_text(answer_data):
    """Extract the answer text (the actual human-readable answer) from answer data."""
    if answer_data is None:
        return None
    if isinstance(answer_data, dict):
        if "selected_option_code" in answer_data:
            code = answer_data["selected_option_code"]
            # Find the matching option text
            for opt in answer_data.get("question_options", []):
                if opt.get("code") == code:
                    return opt.get("text", "").strip()
            return code
        if "ranking" in answer_data:
            ranking = answer_data["ranking"]
            if isinstance(ranking, dict):
                sorted_items = sorted(ranking.items(), key=lambda x: x[1])
                if sorted_items:
                    top_code = sorted_items[0][0]
                    # Find matching option text
                    for opt in answer_data.get("question_options", []):
                        if opt.get("code") == top_code:
                            return opt.get("text", "").strip()
                    return top_code
    return None


def compute_statistics(users, questions):
    """
    Compute answer statistics per question per PDN code.
    Returns: {q_num: {pdn_code: {answer_value: count, ...}, ...}, ...}
    Also returns answer text mapping: {q_num: {pdn_code: {code: text, ...}}}
    """
    # Group users by PDN code
    users_by_code = defaultdict(list)
    for user in users:
        users_by_code[user["pdn_code"]].append(user)

    # Load all answers
    all_answers = {}
    for user in users:
        answers = load_user_answers(user["email"])
        if answers:
            all_answers[user["email"]] = {k: v for k, v in answers.items() if k != "metadata"}

    # Compute stats: for each question, for each PDN code, count answer distributions
    stats = {}
    answer_texts = {}  # {q_num: {code: text}}
    for q_num in questions:
        stats[q_num] = {}
        if q_num not in answer_texts:
            answer_texts[q_num] = {}

        for pdn_code in PDN_12_CODES:
            answer_counts = defaultdict(int)
            total = 0
            for user in users_by_code.get(pdn_code, []):
                user_answers = all_answers.get(user["email"], {})
                answer = user_answers.get(str(q_num))
                if answer is not None:
                    val = format_answer(answer)
                    if val is not None:
                        answer_counts[val] += 1
                        total += 1
                        # Capture answer text mapping
                        if val not in answer_texts[q_num]:
                            txt = get_answer_text(answer)
                            if txt:
                                answer_texts[q_num][val] = txt
            stats[q_num][pdn_code] = {
                "counts": dict(answer_counts),
                "total": total,
            }

    return stats, users_by_code, answer_texts


def generate_html(questions, stats, users_by_code, answer_texts):
    """Generate the HTML matrix report."""
    def sort_key(q_num):
        try:
            return int(q_num)
        except ValueError:
            return 999

    sorted_q_nums = sorted(questions.keys(), key=sort_key)

    # Summary
    code_counts = {code: len(users) for code, users in users_by_code.items()}

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<title>PDN - סטטיסטיקת תשובות לפי קוד PDN</title>
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
    margin-bottom: 10px;
    font-size: 13px;
}}
.code-counts {{
    display: flex;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 15px;
}}
.code-badge {{
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
}}
.code-E {{ background: #d6eaf8; color: #1a5276; }}
.code-A {{ background: #d4efdf; color: #1e8449; }}
.code-T {{ background: #fdebd0; color: #935116; }}
.code-P {{ background: #fadbd8; color: #922b21; }}
.table-container {{
    overflow-x: auto;
    overflow-y: auto;
    max-height: 82vh;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    padding: 10px;
}}
table {{
    border-collapse: collapse;
    font-size: 11px;
    width: 100%;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 5px 6px;
    text-align: center;
    vertical-align: middle;
}}
thead th {{
    background: #34495e;
    color: white;
    position: sticky;
    top: 0;
    z-index: 10;
    font-size: 12px;
}}
th.q-col {{
    background: #2c3e50;
    position: sticky;
    right: 0;
    z-index: 20;
    text-align: right;
    min-width: 250px;
    max-width: 350px;
    white-space: normal;
    font-size: 11px;
}}
td.q-cell {{
    background: #f8f9fa;
    position: sticky;
    right: 0;
    z-index: 5;
    text-align: right;
    font-size: 10px;
    max-width: 350px;
    white-space: normal;
}}
td.stat-cell {{
    font-size: 10px;
    min-width: 70px;
    white-space: normal;
    line-height: 1.4;
}}
.stat-bar {{
    display: flex;
    height: 14px;
    border-radius: 3px;
    overflow: hidden;
    margin-top: 2px;
}}
.bar-segment {{
    height: 100%;
    min-width: 1px;
}}
.bar-ap {{ background: #27ae60; }}
.bar-et {{ background: #2980b9; }}
.bar-tp {{ background: #e67e22; }}
.bar-ae {{ background: #c0392b; }}
.bar-d {{ background: #8e44ad; }}
.bar-s {{ background: #16a085; }}
.bar-f {{ background: #f39c12; }}
.bar-other {{ background: #95a5a6; }}
.stat-label {{
    font-size: 9px;
    color: #666;
}}
.dominant {{
    font-weight: bold;
    font-size: 11px;
}}
.no-data {{
    color: #ccc;
}}
.phase-row td {{
    background: #7f8c8d;
    color: white;
    font-weight: bold;
    font-size: 12px;
    text-align: center;
}}
</style>
</head>
<body>
<h1>PDN - סטטיסטיקת תשובות לפי קוד</h1>
<div class="summary">
    נוצר: {datetime.now().strftime("%d/%m/%Y %H:%M")}
</div>
<div class="code-counts">
"""

    for code in PDN_12_CODES:
        css_class = f"code-{code[0]}"
        count = code_counts.get(code, 0)
        html += f'<span class="code-badge {css_class}">{code}: {count} משתמשים</span>\n'

    html += """</div>
<div class="table-container">
<table>
<thead>
<tr>
<th class="q-col">שאלה</th>
"""

    for code in PDN_12_CODES:
        html += f'<th>{code}</th>\n'

    html += "</tr>\n</thead>\n<tbody>\n"

    current_phase = None
    for q_num in sorted_q_nums:
        q = questions[q_num]

        # Phase separator row
        if q["phase"] != current_phase:
            current_phase = q["phase"]
            phase_label = {
                "PartA": "חלק א - בחירה בינארית (AP/ET, TP/AE)",
                "PartB": "חלק ב - דירוג (D/S/F)",
                "PartC": "חלק ג - סולם (A/T, P/E)",
                "PartD": "חלק ד - ילדות/בגרות (TP/AE, AP/TE)",
                "PartE": "חלק ה - דירוג 4 (E/P/T/A)",
                "PartF": "חלק ו - העדפות",
            }.get(current_phase, current_phase)
            html += f'<tr class="phase-row"><td colspan="{len(PDN_12_CODES) + 1}">{phase_label}</td></tr>\n'

        short_text = q["text"][:60] + ("..." if len(q["text"]) > 60 else "")
        html += f'<tr><td class="q-cell"><strong>Q{q_num}</strong> [{q["codes"]}]<br>{short_text}</td>\n'

        for pdn_code in PDN_12_CODES:
            stat = stats[q_num].get(pdn_code, {"counts": {}, "total": 0})
            total = stat["total"]
            counts = stat["counts"]

            if total == 0:
                html += '<td class="stat-cell no-data">-</td>\n'
                continue

            # Build cell content: show dominant answer and percentage
            sorted_answers = sorted(counts.items(), key=lambda x: -x[1])
            dominant = sorted_answers[0] if sorted_answers else ("", 0)
            dominant_pct = round(dominant[1] / total * 100) if total > 0 else 0

            cell_parts = []
            for ans, cnt in sorted_answers[:3]:
                pct = round(cnt / total * 100)
                is_dom = (ans == dominant[0])
                cls = "dominant" if is_dom else "stat-label"
                # Get answer text
                ans_text = answer_texts.get(q_num, {}).get(ans, "")
                display = f"{ans}:{pct}%"
                if ans_text and is_dom:
                    display = f"{ans}:{pct}% ({ans_text})"
                cell_parts.append(f'<span class="{cls}">{display}</span>')

            # Build mini bar
            bar_html = '<div class="stat-bar">'
            color_map = {
                "AP": "bar-ap", "ET": "bar-et", "TP": "bar-tp", "AE": "bar-ae",
                "D": "bar-d", "S": "bar-s", "F": "bar-f",
                "A": "bar-ap", "T": "bar-tp", "E": "bar-et", "P": "bar-ae",
            }
            for ans, cnt in sorted_answers:
                pct = cnt / total * 100
                bar_class = color_map.get(ans, "bar-other")
                bar_html += f'<div class="bar-segment {bar_class}" style="width:{pct}%"></div>'
            bar_html += '</div>'

            cell_content = " ".join(cell_parts) + bar_html
            html += f'<td class="stat-cell">{cell_content}</td>\n'

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

    print("Loading users with valid PDN codes...")
    users = load_users()
    print(f"  Found {len(users)} users with one of the 12 PDN codes")

    print("Computing statistics...")
    stats, users_by_code, answer_texts = compute_statistics(users, questions)

    print("Generating HTML report...")
    html = generate_html(questions, stats, users_by_code, answer_texts)

    output_path = PROJECT_ROOT / "docs" / "pdn_code_question_stats.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report saved to: {output_path}")
    return str(output_path)


if __name__ == "__main__":
    output = main()
    print(f"\nDone! Opening report...")
    os.system(f"open '{output}'")
