# Backend setup

This project uses a separate Python + FastAPI backend because the server is responsible for AI and document-processing work, not just basic web CRUD. Python gives us the strongest ecosystem for ingestion, chunking, embeddings, retrieval, evaluation, and LLM workflows. Keeping this logic behind a dedicated API also keeps the frontend focused on the user experience while the backend owns data access, orchestration, and grounding.

## Init (from empty `backend/`)

```bash
cd backend
uv sync
uv add fastapi uvicorn pydantic pydantic-settings httpx structlog openai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector
uv add --dev pytest ruff
```

## Request authentication

Protected FastAPI routes should depend on
`app.auth.dependencies.get_current_user`. It verifies the bearer token with
Supabase Auth, upserts the verified user's ID and email into `users`, and yields
the identity with a request-scoped Supabase client carrying that user's JWT.
The dependency closes the client when the request finishes. Use
`current_user.id` to scope application queries; never accept an owner ID from
the request body. The service-role key is used only by the backend when
provisioning the verified user row.

## Database migrations

Alembic owns database schema changes for this project. SQLAlchemy models describe the app tables, and Alembic migrations apply those changes to Supabase Postgres.

Initialize Alembic once from `backend/`:

```bash
uv run alembic init alembic
```

Configure `alembic/env.py` to import the app's SQLAlchemy metadata and read the direct database URL from `app.config.settings`. Use the direct/session Supabase database connection, not the transaction pooler URL, for migrations.

Create a migration after changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "add document tables"
```

Always review the generated migration. Add explicit operations for Supabase/Postgres features that autogenerate cannot reliably infer:

- `create extension if not exists vector`
- `vector(1536)` columns
- generated `tsvector` columns
- HNSW and GIN indexes
- RLS enablement and policies

Apply migrations:

```bash
uv run alembic upgrade head
```

## Run

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Imports (`from app...`)

`backend/app` is installed as an editable package by `uv sync`, so `from app...` imports work from uvicorn, direct Python execution, tests, and Jupyter kernels that use the backend venv.

The `[build-system]` and `[tool.hatch.build.targets.wheel]` sections in `backend/pyproject.toml` tell uv how to install the local `app/` package. Without that package install, imports depend on the current working directory or a manually configured `PYTHONPATH`, which is fragile in notebooks and IDE run buttons.

Preferred API server command:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Direct file execution also works:

```bash
cd backend
uv run python app/main.py
```

For Jupyter, install and select the backend kernel:

```bash
cd backend
uv run python -m ipykernel install --user --name document-copilot-backend --display-name "Document Copilot Backend"
```

Then notebooks can import backend modules:

```python
from app.config import settings
```

## Sample SEC data

From the repo root (stdlib-only script, no backend env needed):

```bash
uv run data/download.py
```

The downloader preserves existing files under `data/downloads/`. The ingestion
command reads its manifest, parses filings, creates embeddings, and writes
documents and chunks to Postgres:

```bash
cd backend
uv run python -m app.ingestion.ingest
```

Ingestion requires a configured `DATABASE_URL` and `HF_TOKEN`. SEC filing
HTML does not provide reliable printed page numbers, so citations use filing
metadata, section title, source URL, and exact passage text.
