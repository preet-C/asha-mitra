# DECISIONS

> One line per late-binding decision. Add at the moment of decision. Format: `HH:MM | Decision | Reason`.

| Time | Decision | Reason |
|---|---|---|
| 18:37 | LLM bake-off result pending re-run | Previous run was interrupted (0 cases completed). See below. |
| 19:55 | **Active LLM: groq / openai/gpt-oss-120b** | Gemini 503 (server overload, hackathon day). Groq `openai/gpt-oss-120b` extracted all 5 fields correctly in first live demo: beneficiary_id, visit_type, NEWBORN, weight_kg=2.8, next_visit resolved to 2026-11-28. Fast (~400ms). D9 bake-off to be re-run when Gemini is available. |
| 19:55 | STT format: **codemix** (Gnani Prisma v3) | Hindi→Devanagari, Kannada→Kannada script, English terms stay Latin. Confirmed in P4 prompt design. |
| — | (D13 gate result goes here — event H13) | — |
