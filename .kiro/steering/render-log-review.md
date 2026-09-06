---
inclusion: manual
---

# Render Log Review — PDN Chat

## How to Run
When the user asks to review Render logs, follow this procedure:

## Steps

1. **Set workspace** — Call `mcp_render_list_workspaces` first (auto-selects if only one)

2. **Fetch error/warning logs** — Use:
   ```
   mcp_render_list_logs(
     resource: ["srv-d0r0fsndiees73bngn3g"],
     level: ["error", "warn"],
     limit: 50,
     startTime: <48 hours ago in RFC3339>
   )
   ```

3. **Summarize findings** in a table:
   - Error message (deduplicated)
   - Count
   - Time range (first → last occurrence)
   - Severity assessment (🔴 critical / 🟡 recurring / ⚪ ignorable)

4. **Known ignorable errors:**
   - `pip dependency conflicts` — build warning, not runtime
   - `Session verification failed: ??? Unknown Error: None` — bot/scanner hitting admin endpoint without token

5. **Actionable errors to flag:**
   - Any new error type not seen before
   - 500 status codes from user-facing endpoints
   - Database/file errors
   - Email sending failures
   - Memory or timeout errors

## Service Info
- **Service ID**: `srv-d0r0fsndiees73bngn3g`
- **Name**: pdn_chat
- **URL**: https://pdn-chat.onrender.com
- **Region**: Frankfurt
- **Runtime**: Python (gunicorn)
