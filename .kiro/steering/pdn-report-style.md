# PDN Report Writing Style

## When Writing PDN Calculation Reports or Responses About PDN Codes

### Code References
- When referring to PDN codes (E9, T12, A7, P10, etc.) — use **only the code itself**.
- Do NOT add trait descriptions in parentheses (e.g., don't write "E (מנהיג, ממוקד מטרה, החלטי)").
- Do NOT expand or explain what each letter means inline (e.g., don't write "T (שיטתי/זהיר)").
- The code is self-explanatory to the recipient. Keep it clean and concise.

### Examples

**Wrong:**
> הקוד E9 סביר, אבל מומלץ לוודא שהנבדק מזדהה עם מאפייני E (מנהיג, ממוקד מטרה, החלטי) ולא עם T (שיטתי, מתכנן, זהיר).

**Right:**
> הקוד E9 סביר, אבל מומלץ לוודא שהנבדק מזדהה יותר עם E ולא עם T. אם מתברר שהוא T, הקוד יהיה T12.

### General Tone
- Keep reports factual and concise.
- Focus on the numbers and the calculation flow.
- Let the codes speak for themselves.

### Emojis
- NEVER use emojis in reports, HTML files, or responses.
- Use plain text symbols or nothing at all.

### Dashes
- NEVER use em dash (—) in code, UI text, or reports.
- Use only a regular hyphen-minus (-) when a separator is needed.

### After Creating HTML Reports
- Always open the HTML file in the browser after creating it (`open <path>`).
- Do not ask the user if they want it opened — just do it.

## Excel Default Column Rule

**Every Excel file produced by the system MUST include:**
- Column A: `UID` - separate column, left-aligned
- Column B: `שם` (full name) - separate column

This applies to ALL sheets in ALL Excel files, no exceptions.
Never combine UID and name in the same cell.
This allows Pnina to use UID for anonymous analysis and name for quick identification.
