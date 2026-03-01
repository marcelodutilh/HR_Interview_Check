# HR Interview Check

A Flask web app for managing job searches, candidates, and interview evaluations. Uses **Claude (Anthropic)** to analyse interview transcripts against a custom rubric and to answer follow-up questions.

## Features

- **Job searches** — Create and manage openings (title, description).
- **Evaluation rubric** — Define competencies per job (e.g. Communication, Problem solving) with Strong / Acceptable / Weak criteria.
- **Candidates** — Add candidates to each job search.
- **Interviews** — Log interview transcripts; optional **AI analysis** (recommendation, competency ratings, strengths, red flags, open questions).
- **Follow-up chat** — Ask questions about an interview; answers are grounded in the transcript and analysis.
- **Settings** — Enter your Anthropic API key in the app (or use the `ANTHROPIC_API_KEY` environment variable).
- Dark, minimal UI with breadcrumbs and back navigation.

## Requirements

- Python 3.9+
- Flask 3.1.0
- Anthropic Python SDK (for AI features)

## Quick start

1. **Clone or download** the repo and go to the app folder:

   ```bash
   cd HR_Interview_Check/JobSearch
   ```

2. **Create a virtual environment** (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional) API key** — Either:
   - Set in the app: run the server, open **Settings**, and paste your Anthropic API key, or
   - Set the env var: `export ANTHROPIC_API_KEY="sk-ant-..."`

5. **Run the app**:

   ```bash
   python app.py
   ```

   Open **http://127.0.0.1:5000** in your browser. The SQLite database (`jobsearch.db`) is created on first run.

## Project structure

```
HR_Interview_Check/
├── README.md
├── JobSearch/
│   ├── app.py          # Flask routes and logic
│   ├── ai.py            # Anthropic API (analysis + chat)
│   ├── database.py      # SQLite and settings
│   ├── requirements.txt
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── templates/       # Jinja2 HTML
```

## Production

- Set `SECRET_KEY` in the environment.
- Do not rely on the built-in Flask dev server for production; use a WSGI server (e.g. Gunicorn) behind a reverse proxy.
