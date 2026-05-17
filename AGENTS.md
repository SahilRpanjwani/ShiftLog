# AGENTS.md — AI-Assisted Engineering Workflow

This document describes how AI tools were used during the development of ShiftLog.

---

## Tools Used

| Tool | Role |
|---|---|
| Claude (Anthropic) | Primary development assistant — architecture, code generation, debugging |
| Google Gemini 2.0 Flash | Runtime AI — OCR and structured data extraction from uploaded documents |

---

## How Claude Was Used

### Architecture & Planning
The overall project structure (2-app Django design, model schema, services layer separation) was planned collaboratively with Claude before writing any code. I described the assignment requirements and we reasoned through the tradeoffs — for example, keeping extraction synchronous rather than adding Celery, and using SQLite over PostgreSQL for prototype scope.

### Code Generation
Claude generated the initial versions of:
- `models.py` — `Document`, `ExtractedRecord`, `FieldConfidence` schema
- `services.py` — Gemini API integration, JSON parsing, field extraction helpers
- `views.py` — all seven views across the documents app
- `dashboard/views.py` — ORM aggregation queries for KPIs and chart data
- `settings.py` — with WhiteNoise, environment variable loading, media configuration

Each generated file was reviewed, placed into the project, and tested before moving to the next. Files were not blindly copy-pasted — errors and mismatches were debugged iteratively.

### Debugging
When `makemigrations` threw a `ModuleNotFoundError: No module named 'shiftlog'`, Claude identified the root cause immediately — a casing mismatch between the actual folder name `ShiftLog` and the lowercase references in `ROOT_URLCONF` and `WSGI_APPLICATION`. Fix took under a minute.

When `google.generativeai` threw a deprecation warning, Claude caught that the package had been fully deprecated in favor of `google-genai` and rewrote `services.py` to use the new SDK (`google.genai.Client`, `types.Part.from_bytes`) before it became a runtime failure.

### Prompting Strategy
Rather than prompting for the entire project at once, I worked file by file — models first, then services, then views, then urls. This kept context tight and made errors easier to isolate. For the Gemini extraction prompt inside `services.py`, I iterated on the JSON schema definition to ensure Gemini returned per-field confidence scores alongside values rather than a flat extraction.

---

## Gemini's Role at Runtime

The extraction prompt instructs Gemini 2.0 Flash to:
1. Read the uploaded document image or PDF
2. Extract 8 operational fields (date, shift, employee number, etc.)
3. Return a structured JSON object with a `value` and `confidence` score per field
4. Flag completely illegible documents with confidence 0.1 across all fields

The confidence scores drive two downstream behaviors:
- Fields below 0.6 are flagged as uncertain and highlighted in the review UI
- The overall confidence score is stored on the record and displayed in the document list

---

## Where AI Helped Most

- **Speed** — the entire backend (models, services, views, urls, settings) was produced and debugged in a single focused session rather than over days
- **ORM aggregation queries** — the dashboard queries (shift-wise summaries, machine rankings, upload trends) would have taken significant trial and error to write from scratch; Claude produced correct Django ORM syntax directly
- **SDK migration** — catching the `google.generativeai` deprecation before it caused a production failure saved meaningful debugging time

---

## Where Manual Intervention Was Needed

- **Folder casing** — Django project was created as `ShiftLog` (capitalized) on Windows, but generated config referenced `shiftlog` (lowercase). Required manual correction in `settings.py`.
- **Templates** — HTML templates were written manually. AI-generated templates tend to produce bloated or generic markup; writing them by hand gave better control over the review UX and confidence score highlighting.
- **Environment setup** — virtual environment creation, package installation, and `.env` configuration were done manually.
- **Gemini extraction quality** — the extraction prompt required a few iterations to get Gemini to reliably return `null` for missing fields rather than hallucinating plausible values.
- **Gemini model selection** — initial models (gemini-2.0-flash-lite, gemini-2.0-flash) 
  had zero free-tier quota on the account due to regional restrictions. Spent significant 
  time debugging what appeared to be rate limit errors before discovering `gemini-flash-latest` 
  was the correct model for this account. EasyOCR and Tesseract were evaluated as fallbacks 
  during this period — both failed on this handwriting style, confirming Gemini Vision was 
  the right approach
---

## Reflection

AI-assisted development on this project wasn't about generating code blindly — it was about compressing the time between design decision and working implementation. The architecture decisions (what models to create, how to structure validation, what the dashboard should aggregate) were made by reasoning through the problem, with Claude acting as a fast implementation layer once the design was clear.

The result is a prototype that would have taken 3-4 days to build solo, completed within the 48-hour window.