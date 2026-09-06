---
inclusion: manual
---

# PDN Health Report

## When to Use
When the user asks for a health report, system status, or production check.

## Steps

1. **Set workspace** — Call `mcp_render_list_workspaces` (auto-selects)

2. **Get service info:**
   ```
   mcp_render_get_service(serviceId: "srv-d0r0fsndiees73bngn3g")
   ```

3. **Get metrics (last 8 hours, 1h resolution):**
   ```
   mcp_render_get_metrics(
     resourceId: "srv-d0r0fsndiees73bngn3g",
     metricTypes: ["cpu_usage", "memory_usage", "cpu_limit", "memory_limit", "bandwidth_usage", "instance_count"],
     resolution: 3600,
     startTime: <8 hours ago in RFC3339>
   )
   ```

4. **Get error logs (last 48h):**
   ```
   mcp_render_list_logs(
     resource: ["srv-d0r0fsndiees73bngn3g"],
     level: ["error", "warn"],
     limit: 30,
     startTime: <48 hours ago in RFC3339>
   )
   ```

5. **Get latest deploy:**
   ```
   mcp_render_list_deploys(serviceId: "srv-d0r0fsndiees73bngn3g", limit: 1)
   ```

6. **Generate HTML report** at `docs/pdn_health_report.html` with:
   - Overall status (green/yellow/red)
   - CPU usage vs limit (%)
   - Memory usage vs limit (%)
   - Bandwidth per hour
   - Instance count and stability
   - Error summary (deduplicated)
   - Last deploy info
   - Storage info (1GB disk at /pdn)

7. **Open the report** in browser

## Service Info
- **Service ID**: `srv-d0r0fsndiees73bngn3g`
- **Name**: pdn_chat
- **URL**: https://pdn-chat.onrender.com
- **Region**: Frankfurt
- **Plan**: Starter (0.5 CPU, 512MB RAM, 1GB disk)
- **Runtime**: Python (gunicorn)

## Thresholds
- CPU > 70% → 🟡 Warning
- CPU > 90% → 🔴 Critical
- Memory > 80% → 🟡 Warning
- Memory > 95% → 🔴 Critical
- Errors > 0 new types → 🟡 Investigate
- Instance restarts → 🟡 Investigate

## Known Ignorable Errors
- `Session verification failed: ??? Unknown Error: None` — bot scanning
- `pip dependency conflicts` — build warning only
