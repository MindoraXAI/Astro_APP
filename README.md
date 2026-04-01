# Astro Intelligence System

Astro Intelligence System is a hybrid astrology platform that combines a deterministic chart engine, a rule-based interpretation layer, a human-readable reading generator, and a mobile-ready web experience.

The current product focus is:

- precise chart computation with Swiss Ephemeris
- rule-based Vedic astrology signals and timing logic
- plain-language personal readings for traits, past, present, and future
- follow-up chart chat grounded in the computed reading
- a progressive web app frontend designed for mobile deployment

## What Is Included

This repository contains:

- a `FastAPI` backend for chart computation and prediction APIs
- a `Three.js` + `pretext` frontend served from `/app`
- deterministic rule engines for chart interpretation
- seeded astrology reference corpora used for retrieval
- local dataset files used during experimentation and curation

## Repository Layout

```text
Astro APP/
|-- backend/
|   |-- app/
|   |   |-- alm/          # orchestration, human reading, prompts, rules
|   |   |-- api/          # FastAPI routes
|   |   |-- core/         # settings and Pydantic models
|   |   |-- ephemeris/    # Swiss Ephemeris, dashas, strengths
|   |   |-- rag/          # retrieval and seed data
|   |   |-- services/     # helpers such as location resolution
|   |   `-- symbolic/     # yoga and aspect logic
|   |-- data/             # curated and raw reference text corpora
|   |-- db/               # SQL bootstrap files
|   |-- tests/            # backend test suite
|   |-- .env.example      # safe environment template
|   `-- requirements.txt  # Python dependencies
|-- frontend/             # installable web app UI
|-- DataSet/              # local research dataset files
|-- docker-compose.yml    # Weaviate, PostgreSQL, Redis
`-- start.ps1             # local startup helper
```

## Product Architecture

```text
Birth details
  -> location resolution
  -> Swiss Ephemeris chart computation
  -> yoga and rule evaluation
  -> structured predictions
  -> human reading generation
  -> optional retrieval and LLM synthesis
  -> personal reading UI + follow-up chat
```

## Core Features

### Deterministic astrology engine

- resolves birth place into coordinates and timezone
- computes natal chart state with Swiss Ephemeris
- evaluates house, sign, dasha, transit, and yoga signals
- produces auditable structured prediction objects

### Human reading layer

- converts technical chart output into plain-language sections
- renders personality traits, emotional nature, relationships, career, past patterns, present phase, future guidance, strengths, and watch-outs
- powers the follow-up chat with section-aware answers instead of repeating a single summary

### Mobile-ready frontend

- two-screen reading flow
- animated cosmic background built with `Three.js`
- display typography laid out with `pretext`
- progressive web app shell with manifest and service worker

## Local Setup

### 1. Create environment variables

Copy the backend template:

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

Fill in the values you need, especially:

- `NVIDIA_CHAT_API_KEY`
- `NVIDIA_EMBED_API_KEY`
- `ENABLE_LLM_SYNTHESIS`

### 2. Start local services and the API

```powershell
.\start.ps1
```

That script will:

- start Docker services from `docker-compose.yml`
- create `backend/.venv` if needed
- install Python dependencies
- launch the FastAPI app

### 3. Open the app

- frontend: `http://127.0.0.1:8000/app`
- docs: `http://127.0.0.1:8000/docs`
- health: `http://127.0.0.1:8000/health`

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | system health check |
| `POST` | `/api/chart/compute` | compute the natal chart |
| `POST` | `/api/chart/yogas` | evaluate yoga rules |
| `POST` | `/api/predict` | generate the full personal reading |
| `POST` | `/api/predict/seed` | seed retrieval data |
| `GET` | `/docs` | interactive API documentation |

## Example Request

```json
{
  "birth_data": {
    "full_name": "Aarav Sharma",
    "date": "1990-01-15",
    "time": "06:30:00",
    "birth_place": "New Delhi, India",
    "time_confidence": "approximate"
  },
  "query": "Tell me about my career and future",
  "life_domain": "general",
  "tradition": "vedic",
  "time_horizon": "1year",
  "query_type": "general",
  "known_facts": []
}
```

## Development Notes

### Run tests

```powershell
cd backend
python -m pytest tests -v
```

### Compile-check the backend

```powershell
python -m compileall .\backend\app
```

## Data Notes

- `backend/data/raw` stores source text files used to seed or curate astrology knowledge.
- `backend/data/curated` stores processed corpora used by retrieval logic.
- `DataSet/archive` stores experimental research CSV files used during project exploration.

## Security Notes

- Do not commit `backend/.env`.
- Keep API keys in local environment files or deployment secrets only.
- The repository intentionally tracks only `backend/.env.example` as a template.

## Current Status

This repository is a working application codebase, not a finished scientific validation program. Astronomical calculations are deterministic, while astrological interpretation remains a rule-based product layer built from the current logic in the repo.
