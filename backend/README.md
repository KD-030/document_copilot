# Backend

FastAPI service for Document Copilot. Run commands below from this directory.

## Run locally

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; interactive docs are at `/docs`.
The health check is at `/health`.

## Configuration

Copy `.env.example` to `.env` and fill in the required Supabase, database, and
Gemini values. Create a Gemini API key in Google AI Studio and set
`GEMINI_API_KEY`. Settings are validated at startup in `app/config.py`. Keep
`.env` private; never commit credentials.
`ALLOWED_EMAIL_DOMAINS` is a comma-separated, server-enforced allow-list. The
example uses `driftwood.com`; confirm the organization's verified email domain
before production sign-in. Adding `gmail.com` allows any authenticated Gmail
account, so use it only when that broad access is intentional.

## Database models

SQLAlchemy models live in `app/database/models/`, with one file per model.
Import `app.database.models` to register all models with `Base.metadata`.
User IDs use the corresponding Supabase Auth UUID. Chunk embeddings use the
768-dimensional `gemini-embedding-001` model. Chat uses `gemini-2.5-flash`
through Gemini's OpenAI-compatible endpoint. Keep
`GEMINI_EMBEDDING_DIMENSIONS=768` aligned with the embedding model and Alembic
migration `0006_gemini_embeddings`.

The models describe the schema; they do not create or update Supabase tables.
Use reviewed Alembic migrations for schema changes.

## Database migrations

Alembic configuration and revisions live in `alembic.ini` and `alembic/`.
`DATABASE_URL` must be a valid PostgreSQL URL using Supabase's direct or
session-mode connection; URL-encode reserved characters in the credentials.
Do not use the Supabase transaction pooler for migrations. An exported
`DATABASE_URL` environment variable overrides the value in `.env`; if it points
to SQLite or another database, unset it or replace it with the PostgreSQL URL.

From this directory, inspect revisions or render SQL without connecting:

```bash
uv run alembic history
uv run alembic upgrade --sql head
```

`uv run alembic upgrade head` applies migrations to the configured database.
Review the rendered SQL and confirm the target database before running it.

## Dependencies and checks

Add a package with `uv add <package>` and a development package with
`uv add --dev <package>`. Run the fast test suite with:

```bash
uv run pytest -m "not integration"
```

## Ingesting the local SEC corpus

The downloader stores raw SEC HTML filings and a manifest under `data/downloads/`.
It preserves existing downloads when refreshed. Set `DATABASE_URL` and
`GEMINI_API_KEY` in the backend environment, then run from `backend/`:

```bash
uv run python -m app.ingestion.ingest
```

Ingestion parses visible filing text, assigns section-aware overlapping chunks,
creates embeddings, and inserts each filing in a transaction. Existing accession
numbers are skipped, so the command can be rerun safely after an API or database
failure. Documents and chunks commit together, and the final count reports only
filings created by that run. SEC HTML filings do not
carry reliable printed page numbers; chunks retain their filing section and source
URL instead of inventing page references. Gemini's free tier has model-specific
rate limits; its free-tier data use terms differ from its paid tier, so review
Google's current [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
and [data use terms](https://ai.google.dev/gemini-api/docs/billing) before sending
non-public material.

After ingestion reports a nonzero created count, ask a question answered by a
sample filing in the app. Confirm citations include the filing, section, and
supporting excerpt. An all-skipped run creates no new data; check that documents
and chunks exist before treating it as a successful first ingestion.
