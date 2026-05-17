# AGENTS.md — AI Workflow

Quick breakdown of how I used AI tools while building ShiftLog.

---

## Tools Used

| Tool | What I used it for |
|---|---|
| Claude (Anthropic) | Main assistant throughout — planning, code, debugging |
| DeepSeek | Tried during the OCR phase when I hit Claude's context limit |
| Qodo | Same — used alongside DeepSeek to debug Tesseract/EasyOCR |
| Google Gemini Flash | The actual extraction engine at runtime |

---

## How I worked with Claude

I didn't just dump the whole assignment and ask for a complete app. I went file by file — models first, then services, then views, then urls, then templates. Each file got reviewed and tested before moving to the next. When something broke I'd paste the error and debug from there.

Claude handled the heavy lifting on:
- The model schema (Document, ExtractedRecord, FieldConfidence)
- The Gemini integration in services.py
- All the Django views
- Dashboard aggregation queries — the ORM stuff for shift summaries, machine rankings etc would have taken me much longer solo
- Templates — basic but functional

I made the actual decisions though. What to build, what to skip, what the data model should look like, when to stop over-engineering something.

---

## The Gemini situation

This took longer than expected. The first few models I tried (gemini-2.0-flash-lite, gemini-2.0-flash) had zero quota on my account — turned out to be a regional restriction. At first it looked like rate limiting so I kept switching keys and models thinking that was the problem.

Eventually wrote a standalone test script outside Django to isolate the issue. Ran it with gemini-flash-latest and it worked immediately — extracted all 3 rows from the test image correctly in one call. That's when I knew it was a model availability issue, not a key or rate limit issue.

---

## The OCR detour

While debugging Gemini I hit Claude's context limit and switched to DeepSeek and Qodo to try EasyOCR and Tesseract as local fallbacks.

Short version: neither worked. EasyOCR was reading characters so badly it was unusable (confidence 0.06-0.42, misreading "BT4685" as "GLybss"). Tesseract was merging entire rows into single blobs. Spent a few hours on preprocessing — upscaling, adaptive thresholding, noise reduction — helped a bit but not enough.

Once Gemini was working again it was obvious why: Gemini read the exact same image perfectly in 11 seconds. Some problems just need the right tool.

---

## Multi-row extraction

The sample dataset had log sheets with multiple rows per page, not single-record forms. The original design assumed one record per document.

Had to rethink the whole thing — changed the model relationship from OneToOneField to ForeignKey, updated the extraction to return a list of rows, rewrote the review UI to let you navigate between records (1 of 3, 2 of 3 etc). The save button auto-advances to the next record. Small detail but makes the review flow actually usable.

---

## Deployment

Render free tier works fine for a demo but has two annoying limitations:
- Uploaded files get wiped on every redeploy (no persistent disk)
- Workers time out on long requests — had to increase gunicorn timeout to 120s for Gemini calls

For production you'd swap SQLite for PostgreSQL and use S3 or Cloudinary for file storage.

---

## Honest take

The whole backend — models, services, views, urls, settings — got built in one session that would've taken me days solo. The parts that needed human judgment were the architecture decisions upfront and the debugging when things didn't work as expected.

The OCR detour was the biggest time sink and probably the most useful learning. Knowing why something doesn't work is as useful as knowing what does.

Shipped within 48 hours despite a regional API block, an OCR dead end, a context limit mid-session, and the usual deployment surprises.