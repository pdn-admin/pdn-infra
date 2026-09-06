# PDN Chat - Backlog

## Open Items

---

### [BACKLOG-001] Store questionnaire completion time (`completed_at`)

**Priority:** Medium
**Area:** `app/utils/answer_storage.py`, `app/pdn_diagnose/diagnosis_routes.py`

**Background:**
Currently, `save_user_metadata()` saves a `timestamp` field when the user submits the personal info form (start of questionnaire). There is no `completed_at` field saved when the user finishes.

From Render logs, typical fresh completion takes 25-30 minutes, but this cannot be reliably computed per-user from logs alone (no user identity in log lines, multiple concurrent sessions, 30-day log retention limit).

**What to implement:**
- In `complete_questionnaire()` in `diagnosis_routes.py`, after a successful PDN code calculation, write a `completed_at` timestamp to the user's `{email}_answers.json` file under the `metadata` key.
- Format: same as `timestamp` - `YYYY_MM_DD_HH_MM`, or ISO format for easier parsing.
- This allows computing exact fill duration: `completed_at - metadata.timestamp`.

**Acceptance criteria:**
- `completed_at` appears in the answers JSON after questionnaire completion.
- Duration can be derived from `metadata.timestamp` and `metadata.completed_at`.
- No change to existing flows or data.

---

### [BACKLOG-002] Questionnaire timeout - 2 hours

**Priority:** Medium
**Area:** `app/pdn_diagnose/diagnosis_routes.py`

**Background:**
There is currently no time limit on filling the questionnaire. A user who starts but does not finish occupies a session indefinitely. The desired behavior is to enforce a 2-hour window from the time the user submits their personal info (`metadata.timestamp`).

**What to implement:**
- On every request to the questionnaire endpoints (`/answer`, `/questionnaire/<n>`, `/complete_questionnaire`), check `metadata.timestamp` from the user's answers JSON.
- If more than 120 minutes have elapsed since `metadata.timestamp`, return an appropriate error response (e.g., HTTP 403 with a user-friendly message in Hebrew).
- The frontend should handle this response and display a timeout message, prompting the user to restart.
- Timeout threshold should be configurable (e.g., via `config.py` or an env var `QUESTIONNAIRE_TIMEOUT_MINUTES`, defaulting to 120).

**Acceptance criteria:**
- Requests to questionnaire endpoints more than 2 hours after `metadata.timestamp` are rejected with a clear message.
- Timeout threshold is configurable without code changes.
- Users who have not yet submitted their personal info (no `metadata.timestamp`) are not affected.
- Existing completed questionnaires are not affected.

---

## Done

*(nothing yet)*
