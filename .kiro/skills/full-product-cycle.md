---
inclusion: manual
---
# Full Product Cycle Workflow

When asked to run a full product lifecycle review, execute all personas sequentially.

## Skill: kiro.workflow.full_product_cycle

Execute full product lifecycle using all personas.

## Steps

Execute in this exact order, passing each output as input to the next:

1. **Senior Product Manager** — use `kiro.product.senior_pm.google_level`
   - Input: the user's product idea, code, and any constraints
   - Output: Score (0-5), executive summary, PM analysis

2. **System Architect** — use `kiro.architect.staff.meta_amazon`
   - Input: PM output + code as product requirements
   - Output: Score (0-5), executive summary, architecture design

3. **Product Designer** — use `kiro.design.principal.ux_ui`
   - Input: PM output + code as product flow
   - Output: Score (0-5), executive summary, UX/DX review

4. **Technical Writer** — use `kiro.docs.technical_writer.senior`
   - Input: PM output + architect output + code + existing docs
   - Output: Score (0-5), executive summary, documentation assessment

5. **QA Analyst** — use `kiro.qa.analyst.full_coverage`
   - Input: PM output + architect output + code
   - Output: Score (0-5), executive summary, test plan

6. **Code Reviewer** — use `kiro.code_review.principal.google`
   - Input: architect output + code (must read actual source files)
   - Output: Score (0-5), executive summary, code review

7. **Security Engineer** — use `kiro.security.engineer.senior`
   - Input: architect output + code reviewer output + code
   - Output: Score (0-5), executive summary, threat model

8. **DevOps / SRE** — use `kiro.ops.devops_sre.senior`
   - Input: architect output + code + deployment context
   - Output: Score (0-5), executive summary, operational readiness

9. **Coordinator** — use `kiro.coordinator.execution_orchestrator` **(MANDATORY — NEVER SKIP)**
   - Input: all eight outputs above (scores, summaries, and full analysis)
   - Output: Scorecard, weighted score with formula, executive summary, alignment issues, decisions, MVP scope, risks, prioritized recommendations, Go/No-Go
   - **This step MUST always run and MUST always appear as Section 9 in the HTML report**

## Output Format

**CRITICAL: Do NOT output persona analysis to the Kiro chat console.** All analysis content goes exclusively into the HTML report file. The only chat output should be brief progress updates (e.g., "Running Product Manager analysis..." → "Running Architect analysis..." → etc.) and a final one-liner like "Report saved to {filename}. Opening in browser."

After all personas have completed, produce a single HTML report file and save it to the workspace root. The filename should be `{feature-name}-product-cycle-report.html`. If a report with that name already exists, append `-v2`, `-v3`, etc.

After saving the file, automatically open it in the browser.

### Consistent Report Structure (always follow this exact layout)

The HTML report must always use this exact structure, in this order, every time:

1. **Go/No-Go Banner** — colored banner at the very top:
   - Green (#22c55e) = GO
   - Yellow (#eab308) = CONDITIONAL GO
   - Red (#ef4444) = NO-GO
   - Contains: one-line verdict, overall score, short explanation
2. **Meta Line** — feature name, generation date, persona count, version
3. **Scorecard** — horizontal bar chart showing all 8 persona scores (0-5):
   - Color-coded bars: green (≥4), yellow (≥3), orange (≥2), red (<2)
   - Overall weighted average as a large number below
   - Weighted formula shown in small monospace text
4. **Executive Summary** — one paragraph synthesizing all persona findings
5. **Table of Contents** — numbered list linking to each persona section, with scores inline
6. **Persona Sections (1-8)** — each section follows this exact internal layout:
   - Section heading: number + persona name
   - Score badge (colored) + executive summary blurb (italic)
   - Sub-sections with detailed analysis using tables, lists, code blocks
7. **Coordinator Section (9)** — MANDATORY, always the last persona section:
   - Scorecard table with all 8 personas, weights, weighted scores, summaries
   - Weighted score calculation with formula and actual numbers
   - Executive summary (3-5 sentences)
   - Alignment issues table
   - Decisions (paragraph per conflict)
   - Final MVP scope (checklist)
   - Consolidated risks table
   - Prioritized recommendations (3 tables: blockers / fast-follows / future)
   - Go/No-Go verdict in colored box with launch conditions and timelines

### HTML Styling Rules

- Self-contained, inline CSS — no external dependencies
- Clean, professional design with consistent spacing and max-width 1100px
- Color scheme: green (#22c55e), yellow (#eab308), orange (#f97316), red (#ef4444)
- Score bars: gradient fills matching severity colors
- Score badges: green (≥4), yellow (≥3), orange (≥2), red (<2)
- Tables: full-width, collapsed borders, alternating row colors for readability
- Code blocks: dark background (#1f2937), light text, rounded corners
- Severity labels: Critical (red bold), High (orange bold), Medium (yellow bold), Low (blue)
- Viewable by opening the file directly in a browser

## Rules

- Execute sequentially — each step depends on previous outputs
- Pass outputs between steps — don't lose context
- Read the actual source code — personas that take code input must read the real files
- Do not skip steps — every persona adds value
- **NEVER skip the Coordinator (step 9)** — without it the report has no verdict, no scorecard, and no recommendations
- Coordinator produces the final answer — it's the single source of truth
- The scorecard in the report header uses the Coordinator's weighted score calculation
- Do NOT print persona analysis to the chat — only brief progress lines
- The final deliverable is the HTML report file — always generate it
- Always follow the exact report structure above — users should recognize the format instantly
- Always open the HTML report in the browser after generating it
- If the user only wants specific personas, run just those (but warn about gaps in the Coordinator section)
