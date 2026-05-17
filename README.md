# ShiftLog

AI-powered document digitization and workflow management for manufacturing operations.

ShiftLog lets you upload handwritten or semi-structured operational documents, automatically extracts structured data using Google Gemini, validates it against business rules, and gives you a live dashboard of operational insights.

---

## Features

- **Document Upload** — supports images (JPG, PNG) and PDFs up to 10MB
- **AI Extraction** — Gemini reads handwritten fields and returns structured JSON with per-field confidence scores
- **Review Workflow** — extracted data is shown in an editable form; reviewers can correct any field before saving
- **Confidence Scoring** — fields below 60% confidence are highlighted for manual attention
- **Validation Engine** — catches missing mandatory fields, invalid shift values, suspicious quantities, duplicate work orders, and malformed machine codes
- **Dashboard & Analytics** — shift-wise summaries, machine output rankings, upload trends, validation failure rates
- **Search & Filter** — search records by work order, machine, employee number, or date range

---

## Tech Stack

- **Backend** — Django 6, SQLite
- **AI** — Google Gemini 2.0 Flash (`google-genai` SDK)
- **Frontend** — Bootstrap 5, Chart.js (CDN, no build step)
- **Static files** — WhiteNoise
- **Deployment** — Render (free tier)

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/SahilRpanjwani/shiftlog.git
cd shiftlog
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
GEMINI_API_KEY=your-gemini-api-key
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create the static folder (if not present)

```bash
mkdir static
```

### 7. Start the development server

```bash
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) — you'll land on the dashboard.

---

## Project Structure

```
shiftlog/
├── documents/          # Upload, extraction, review workflow
│   ├── models.py       # Document, ExtractedRecord, FieldConfidence
│   ├── services.py     # Gemini API call + validation logic
│   ├── views.py        # Upload, review, detail, delete, re-extract
│   └── urls.py
├── dashboard/          # Analytics and search
│   ├── views.py        # Dashboard KPIs, charts, record search
│   └── urls.py
├── templates/          # HTML templates
├── ShiftLog/           # Django project config
│   ├── settings.py
│   └── urls.py
├── requirements.txt
├── .env.example
├── README.md
└── AGENTS.md
```

---

## Deployment (Render)

1. Push repo to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set **Build Command**: `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
4. Set **Start Command**: `gunicorn ShiftLog.wsgi:application`
5. Add environment variables in the Render dashboard:
   - `SECRET_KEY`
   - `GEMINI_API_KEY`
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `your-app-name.onrender.com`

---

## Assumptions & Tradeoffs

- **Synchronous extraction** — Gemini is called directly in the upload request. Acceptable for a prototype; a production system would use Celery + Redis for async processing.
- **SQLite** — sufficient for the assignment scope. Swap to PostgreSQL for production by changing the `DATABASES` setting.
- **Machine code format** — validated against pattern `[A-Z]{1,4}-?\d{1,6}` (e.g. `MC-001`, `AB1234`). Assumed from dataset; adjust the regex in `services.py` if the actual format differs.
- **No authentication** — the assignment didn't require login. Adding Django's built-in auth would be straightforward if needed.
- **Confidence threshold** — fields below 0.6 are flagged as uncertain. This threshold was chosen empirically and can be tuned in `models.py`.