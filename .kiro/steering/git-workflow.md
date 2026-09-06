# Git Workflow Rules

## Testing Before Commits

**NEVER commit before tests pass.** Before creating any git commit, you MUST:

1. Run the relevant test suite based on changed files (see mapping below)
2. Verify 0 failures
3. If tests fail, fix them BEFORE committing
4. Only after all tests pass, proceed with `git add` and `git commit`

**Test mapping:**
- `app/pdn_admin/*` → `tests/test_admin_routes_coverage.py tests/test_coupon_admin_routes.py tests/test_coupon_email.py tests/test_metrics_and_report.py`
- `app/pdn_diagnose/*` → `tests/test_diagnosis_routes_coverage.py tests/test_app.py tests/test_conversation_history.py`
- `app/pdn_chat_ai/*` → `tests/test_chat_routes.py tests/test_pdn_agent.py tests/test_pdn_agent_history.py`
- `app/pdn_relationships/*` → `tests/test_relationship_routes.py tests/test_relationship_agent.py tests/test_property_relationship_routes.py`
- `app/utils/pdn_calculator*` → `tests/test_pdn_calculator.py`
- `app/utils/user_manager*` → `tests/test_user_manager.py tests/test_unified_login.py`
- If unsure, run: `source venv/bin/activate && arch -arm64 python3 -m pytest tests/ -q --ignore=tests/test_admin_dashboard.py --ignore=tests/test_chat_improvements.py --ignore=tests/test_pdn_agent_refactored.py --ignore=tests/test_voice_recording.py`

**Ignored test files** (broken imports, do not run): `test_admin_dashboard.py`, `test_chat_improvements.py`, `test_pdn_agent_refactored.py`, `test_voice_recording.py`

This is a hard rule — no exceptions, no `--no-verify`, no "commit now fix later".

## Playwright E2E Tests

E2E tests live in `e2e/` and require the Flask server to be running on port 8001.

**When to run E2E tests:**
- After any change to HTML templates (`app/**/templates/*.html`)
- After any change to frontend JS (`app/static/js/*.js`)
- After adding or changing routes that the UI calls

**How to run:**
```bash
# 1. Start the Flask server in one terminal
source venv/bin/activate && python run.py

# 2. In another terminal, run the E2E tests
npm test
# or specific file:
npx playwright test e2e/admin.spec.js
```

**Test files and what they cover:**
- `e2e/admin.spec.js` — Admin login, dashboard tabs, version modal, logo click, status filters
- `e2e/diagnose.spec.js` — Questionnaire login, user_info form, answer API, progress
- `e2e/binat.spec.js` — Binat chat login, chat page render, logout
- `e2e/relationships.spec.js` — Relationships login API (all 12 PDN codes, all 3 relationship types), chat page

**Credentials used in E2E tests:**
- Admin: `jclazvbdn` (config.py default)
- Binat/Relationships: `tomergur@gmail.com` / `pdn`
- Diagnose: `e2etest@playwright.com` / `e2etest` (local part = password)

## Preventing Local/Production Drift

**NEVER push frontend changes (JS/HTML) that reference backend routes without also committing the backend code in the same commit or earlier.**

Before committing frontend changes that call new endpoints:
1. Run `git diff --name-only -- '*.py'` to check for uncommitted Python changes
2. If there are uncommitted Python files that define routes referenced by the frontend, include them in the commit
3. The pre-push hook will block pushes if uncommitted .py files exist

## Commit Discipline

- Always commit backend + frontend together when they depend on each other
- Never leave route handlers as uncommitted local changes
- If you add a JS `fetch('/pdn-admin/new_endpoint')`, the Python route MUST be in the same commit
