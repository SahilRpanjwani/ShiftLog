# ShiftLog

AI-powered document digitization and workflow management for manufacturing operations.

ShiftLog lets you upload handwritten or semi-structured operational documents, automatically extracts structured data using Google Gemini, validates it against business rules, and gives you a live dashboard of operational insights.

**Live Demo:** https://shiftlog-zqmo.onrender.com
> Hosted on Render free tier — first load after inactivity may take 30-60 seconds to spin up.

---

## Features

- **Document Upload** — supports images (JPG, PNG) and PDFs up to 10MB
- **AI Extraction** — Gemini reads handwritten log sheets and extracts all rows as structured data with confidence scores
- **Multi-row Support** — single document can contain multiple records; each row is extracted and reviewed individually
- **Review Workflow** — extracted data shown in an editable form with prev/next navigation between records
- **Confidence Scoring** — fields with low confidence highlighted for manual attention
- **Validation Engine** — catches missing mandatory fields, invalid shift values, suspicious quantities, duplicate work orders, and malformed machine codes
- **Dashboard & Analytics** — shift-wise summaries, machine output rankings, upload trends, validation failure rates
- **Search & Filter** — search records by work order, machine, employee number, date range

---

## Tech Stack

- **Backend** — Django 6, SQLite
- **AI** — Google Gemini Flash (`gemini-flash-latest` via `google-genai` SDK)
- **Frontend** — Bootstrap 5, Chart.js (CDN, no build step)
- **Static files** — WhiteNoise
- **Deployment** — Render (free tier)

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/SahilRpanjwani/ShiftLog.git
cd ShiftLog
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
Use model `gemini-flash-latest` — other models may have regional quota restrictions.

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
ShiftLog/
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
3. Set **Build Command:** `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
4. Set **Start Command:** `gunicorn ShiftLog.wsgi:application --workers 1 --timeout 120`
5. Add environment variables:
   - `SECRET_KEY`
   - `GEMINI_API_KEY`
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `your-app-name.onrender.com`

**Note:** Render free tier has no persistent disk — uploaded media files are wiped on redeploy. For production, replace local file storage with AWS S3 or Cloudinary.

---

## Assumptions & Tradeoffs

- **Synchronous extraction** — Gemini is called directly in the upload request. Fine for a prototype; production would use Celery + Redis for async processing.
- **SQLite** — sufficient for assignment scope. Swap to PostgreSQL for production.
- **Machine code format** — validated against `[A-Z]{1,4}-?\d{1,6}` (e.g. `MC-001`). Assumed from dataset; adjust regex in `services.py` if format differs.
- **No authentication** — not required by the assignment. Django's built-in auth can be added straightforwardly.
- **Confidence scoring** — Gemini-extracted fields default to 0.9 confidence. Fields with null values get 0.0 and trigger validation errors directing reviewer attention.
- **Gemini model** — `gemini-flash-latest` was used after discovering other models had zero free-tier quota due to regional restrictions. See AGENTS.md for full context.