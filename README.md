# A Locally Deployed AI Assistant Platform for SMEs

A privacy-first AI assistant for hospitality SMEs. Customer-data inference runs locally
on a single Apple Silicon Mac across two end-to-end use cases:

- **UC1 — Voice Reservation:** call audio → voice activity detection → bilingual speech
  recognition → structured extraction → human review → booking → optional Google Calendar mirror.
- **UC2 — Marketing Support:** review text → sentiment classification, and venue photo →
  popularity score + pixel attributes → grounded, prioritised photography suggestions.

The project follows the CM3070 template **“Orchestrating AI models to achieve a goal.”** Its core
constraint is useful local inference on an Apple M1 with 16 GB unified memory and no discrete GPU.
PostgreSQL and Redis run in Docker; inference runs on the host. Ollama uses Apple Metal,
while faster-whisper uses CTranslate2 on the CPU.

## Product surfaces

| Page            | Purpose                                                                                                                                                         |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/`             | Redirects to `/reservations`                                                                                                                                    |
| `/reservations` | Upload call audio; review the transcript and AI fields; approve, edit and approve, or reject; view confirmed bookings and retry failed Calendar sync            |
| `/reviews`      | Classify pasted reviews, confirm or correct the AI label, and inspect the positive/neutral/negative history tally (corrected labels take priority in the tally) |
| `/marketing`    | Upload a venue photo and poll for its score, attributes and grounded suggestions                                                                                |
| `/settings`     | Read-only database and Calendar status; secrets remain in `backend/.env`                                                                                        |

API documentation is available at `http://localhost:8000/docs` while the backend is running.

## Architecture

```text
┌────────────────────────── Host: Apple Silicon, 16 GB ──────────────────────────┐
│  Next.js :3000 ──► FastAPI :8000                                               │
│                         ├─ synchronous mBERT review sentiment                  │
│                         └─ Redis queue ─► Celery worker (concurrency = 1)       │
│                                             │                                  │
│                          ┌──────────────────┴──────────────────┐               │
│                          │ UC1                                 │ UC2 photo      │
│                          │ Silero VAD → faster-whisper         │ ResNet50       │
│                          │ → Qwen2.5 7B extraction             │ + OpenCV       │
│                          │                                     │ → Qwen2.5-VL   │
│                          └──────────────────┬──────────────────┘               │
│                                             │                                  │
│                         PostgreSQL + local uploaded-media storage              │
└─────────────────────────────────────────────┼──────────────────────────────────┘
                                              │ optional, async, retrying
                                              ▼
                                      Google Calendar API
```

Heavy inference tasks share one Celery worker with `worker_concurrency=1`. Whisper is unloaded
before the extraction LLM runs; the photo pipeline scores the image before asking the VLM for
suggestions. Upload requests enqueue work, and the frontend polls the saved result. If the VLM
fails, the photo score and attributes remain available as a partial result. Review sentiment is
served synchronously by FastAPI with a guarded classifier cache.

Google Calendar is the production system's only optional online integration. It is disabled by
default, runs outside the booking request path, retries failures and performs idempotent upserts.
The local database remains the source of truth.

## Technology stack

- **Backend:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, PostgreSQL 16
- **Orchestration:** Celery 5.4 and Redis 7
- **UC1:** Silero VAD 5.1, faster-whisper 1.1 (`small`, CPU int8), Ollama with
  `qwen2.5:7b-instruct-q4_K_M`
- **UC2:** fine-tuned `bert-base-multilingual-cased`, pretrained ResNet50 intrinsic image
  popularity model, OpenCV attributes, Ollama with `qwen2.5vl:7b`
- **Frontend:** Next.js 15.1, React 19, TypeScript 5.7, Tailwind CSS 3.4
- **Tests:** pytest

## Requirements

### Full application

- macOS on Apple Silicon (M1 or newer recommended)
- 16 GB or more unified memory
- approximately 10 GB free disk for dependencies and model weights
- Docker Desktop, Python 3.12+, Node.js 22+ and Ollama

The code can fall back to CPU on other platforms, but the full pipelines were designed and
measured on Apple Silicon and may be impractically slow elsewhere. A network is needed for initial
downloads. Normal inference is local; Calendar sync uses a network only when explicitly enabled.

### Tests only

Backend tests need Python 3.12+ and the packages in `backend/requirements.txt`. They do not
require Docker, Redis, PostgreSQL, Ollama, or downloaded model weights.

## Quick start

`make up` automates the complete project-level setup, but it does not install
operating-system tools. Before running it, install Docker Desktop, Python 3.12+,
Node.js 22+, and Ollama. On macOS, Ollama can be installed with Homebrew:

```bash
brew install ollama
make up
```

On its first successful run, `make up` automatically:

- starts Docker Desktop when it is installed but not running;
- starts PostgreSQL and Redis containers;
- creates the backend virtual environment and `backend/.env`;
- installs and synchronises Python and npm dependencies;
- downloads and verifies the pinned faster-whisper, sentiment, and image-popularity weights;
- starts Ollama and pulls the text and vision-language models;
- starts FastAPI, the single-concurrency Celery worker, and Next.js; and
- waits for the application services to become ready before reporting success.

Remote model revisions and checksums are pinned. Later runs skip dependencies and models that are
already current, so local fine-tuning is not required. Ports 3000 and 8000 must be available; if
another process uses either port, `make up` stops with an explanatory error instead of reporting a
false successful start.

Google Calendar credentials are needed only when Calendar sync is enabled. Normal application
use does not require an external LLM API key.

- Frontend: http://localhost:3000
- Health check: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs

```bash
make status   # host processes and Docker containers
make logs     # tail .dev/logs/*.log
make restart  # restart the full stack
make down     # stop everything; preserve the PostgreSQL volume
```

The first run downloads several gigabytes and can take a while. Model artifacts are gitignored.
The sentiment weights come from
[`AtsushiHatake/ai-agent-sme-sentiment-mbert`](https://huggingface.co/AtsushiHatake/ai-agent-sme-sentiment-mbert),
so local fine-tuning is not required. `backend/scripts/train_sentiment.py` remains available
for retraining from the included `data/testset/sentiment_train.json`.

## Manual start

Use this when debugging individual services:

```bash
# Terminal 1
docker compose up -d

# Terminal 2: API
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # only if backend/.env does not exist
uvicorn app.main:app --reload --port 8000

# Terminal 3: worker
cd backend
source .venv/bin/activate
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo --concurrency=1

# Terminal 4: frontend
cd frontend
npm ci
npm run dev

# Separate terminal, if Ollama is not already running
ollama serve
```

The manual path also needs the three model assets and two Ollama models. From the repository
root, run `backend/.venv/bin/python scripts/bootstrap_models.py`, then
`ollama pull qwen2.5:7b-instruct-q4_K_M` and `ollama pull qwen2.5vl:7b` before processing
recordings or photos. `make up` performs these steps automatically.

The API is intended for one operator on the local machine. Do not expose it publicly: it has no
remote-user authentication layer.

## Existing-database migrations

FastAPI calls SQLAlchemy `create_all` at startup, which creates missing tables but does not alter
existing ones. Fresh databases need no manual schema step. For a database created by an older
revision, apply the idempotent migrations from the repository root:

```bash
psql "postgresql://sme:sme_dev_pw@localhost:5432/sme" \
  -f backend/scripts/migrate_add_booking_columns.sql
psql "postgresql://sme:sme_dev_pw@localhost:5432/sme" \
  -f backend/scripts/migrate_add_review_sentiment.sql
psql "postgresql://sme:sme_dev_pw@localhost:5432/sme" \
  -f backend/scripts/migrate_add_sentiment_feedback.sql
```

Back up important data before applying schema changes.

## Google Calendar mirror

Calendar sync is optional and off by default. To enable it:

1. Create a Google Cloud project and enable the Google Calendar API.
2. Create a service account and save its JSON key under a gitignored path such as
   `backend/secrets/service-account.json`.
3. Share the target calendar with the service-account email using **Make changes to events**.
4. Set these values in `backend/.env` and restart:

```dotenv
CALENDAR_SYNC_ENABLED=true
GOOGLE_CALENDAR_ID=your-calendar-id
GOOGLE_CREDENTIALS_PATH=./secrets/service-account.json
CALENDAR_TIMEZONE=Asia/Tokyo
```

When disabled or temporarily unavailable, bookings continue locally. Failed syncs retain an
explicit status and can be retried from the reservation screen.

## Testing

Run the backend suite:

```bash
cd backend
source .venv/bin/activate
pytest -q
```

Build the frontend with Node 22+:

```bash
cd frontend
npm run build
```

Evaluation results are under `data/testset/` and `data/eval_photos/venue_likert/`. The one-off
report scripts used to produce them are no longer included. Photo sources and licences are recorded in
[`ATTRIBUTION.md`](data/eval_photos/venue_likert/ATTRIBUTION.md).

## Sample inputs

- UC1: `data/audio/sample_ja.wav`, `sample_en.wav`, `sample_en_noisy.wav`
- UC2 photos: `data/eval_photos/venue_likert/photo_01.jpg` through `photo_18.jpg`
- UC2 reviews: paste Japanese or English text into `/reviews`

Never commit real customer calls, reviews, credentials or identifying usability-study records.
Runtime uploads, `.env`, service-account keys, model weights and local databases are gitignored.

## Repository layout

```text
backend/
  app/
    ai/                    VAD, ASR, extraction, sentiment, popularity and VLM wrappers
    api/                   UC1, sentiment, photo-evaluation and settings routes
    pipelines/             Celery UC1, Calendar and UC2 photo pipelines
    services/              booking, Calendar, image attributes and upload handling
  scripts/                 sentiment training and SQL migrations
  tests/                   isolated pytest suite with external services mocked
frontend/
  app/                     reservations, reviews, marketing and settings
  components/              shared application shell and UI components
  lib/api.ts               typed API client
data/                      sample inputs and evaluation data/results
docker-compose.yml         PostgreSQL and Redis only
scripts/                   local startup and pinned model downloads
```

## Known limitations

- The target is a local, single-tenant operator machine, not a public multi-user service.
- UC1 accuracy is measured mainly on synthetic speech and additive noise; authentic restaurant
  phone audio remains an external-validity gap.
- The date resolver was evaluated on the set that exposed its failure modes; an unseen-phrasing
  set is still needed to establish generalisation.
- Popularity calibration uses stock photos, and the PDIP result uses the model's training-domain
  family; neither is a restaurant-domain guarantee.
- The sentiment dataset is bespoke and synthetic. Its score does not establish universal or
  aspect-level sentiment accuracy.
- In the five-rater suggestion study, local advice averaged 3.62/5 versus 1.99/5 for generic
  tips; GPT-4o averaged 3.92/5. The repeated ratings do not establish population-level
  significance, so these differences are descriptive within this sample.
- The five-participant usability study is formative, contains missing and internally inconsistent
  task records, and does not establish usability for the wider target population.

## Licence and third-party assets

This repository does not currently declare a project-wide software licence. Third-party models,
datasets and photos remain subject to their respective licences. The upstream Intrinsic Image
Popularity repository describes its code as MIT but does not ship a standalone licence file;
treat its checkpoint as a research prototype asset and verify redistribution terms before
commercial use. Photo-specific attribution is preserved alongside the evaluation set.
