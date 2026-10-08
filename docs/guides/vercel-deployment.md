# Vercel deployment

The app uses two Vercel projects from this repository:

| Project | Root directory | Framework | Entry point |
| --- | --- | --- | --- |
| `document-copilot-web` | `frontend/` | Vite | Static SPA |
| `document-copilot-api` | `backend/` | FastAPI | `app.main:app` |

The backend is deployed as one Python serverless function. Vercel supports
streaming Python function responses; function duration limits still apply.
See [Vercel's FastAPI deployment guide](https://vercel.com/docs/frameworks/backend/fastapi)
and [streaming functions documentation](https://vercel.com/docs/functions/streaming-functions).

## Environment variables

Set these in each project's **Production** environment in the Vercel dashboard.
Set Preview and Development values separately if those environments are used.
Do not upload `.env` files or commit secrets.

Frontend:

- `VITE_API_BASE_URL` — the deployed backend project's HTTPS origin.
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Backend:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` — Supabase direct or session-mode PostgreSQL connection.
- `GEMINI_API_KEY` — Gemini API key created in Google AI Studio.
- `ALLOWED_EMAIL_DOMAINS` — comma-separated approved email domain(s). Adding
  `gmail.com` authorizes any authenticated Gmail account; use it only when that
  broad access is intentional.
- `ALLOWED_ORIGINS` — the exact HTTPS origin of the deployed frontend.

The backend model defaults are defined in `app/config.py`: chat uses
`gemini-2.5-flash`, and embeddings use `gemini-embedding-001` (768 dimensions).
Set `GEMINI_API_KEY` in local and Vercel environments. A different embedding
model or dimension requires a database migration. Gemini's free tier has
model-specific quotas; review Google's current pricing and data terms before
sending non-public content.

## Current production status

Migration `0005_huggingface_embeddings` sets the vector schema to 384
dimensions. Migration `0006_gemini_embeddings` changes vector storage and
search to 768 dimensions and refuses to run if chunks exist. Apply migrations
only after confirming the database target; existing chunks require a corpus
rebuild before switching embedding models.

## Supabase preparation

Confirm the production Supabase project before applying schema changes. From
`backend/`, use the private local environment with a direct or session-mode
database connection:

```sh
uv run alembic history
uv run alembic upgrade --sql head
uv run alembic upgrade head
```

Review the generated migration SQL and verify the database target before
running the final command. Then ingest the checked-in sample manifest. This
uses the configured Gemini API key and is subject to the model's free-tier quota:

```sh
uv run python -m app.ingestion.ingest
```

Confirm documents and chunks exist in the intended database before deploying
production traffic.

## Build and deploy

The directories are already linked to their separate Vercel projects. After
setting the backend variables (including the intended frontend origin), deploy
the backend first:

In the `document-copilot-api` Vercel project, set **Root Directory** to
`backend/` (Project Settings → Build and Deployment → Root Directory). The
backend's `pyproject.toml` sets Vercel's entrypoint to `app.main:app`, which is
resolved relative to that root. Do not deploy this project with the repository
root as its root directory; the backend package imports assume `backend/` is
the Python project root.

```sh
cd backend
vercel --prod
```

Copy the resulting backend HTTPS origin into the frontend's
`VITE_API_BASE_URL`, set the Supabase URL and anon key in the frontend project,
then deploy:

```sh
cd frontend
vercel --prod
```

If the frontend's assigned production origin differs from the value configured
in backend `ALLOWED_ORIGINS`, update the backend variable and redeploy the API.

## Production smoke test

1. Verify the backend `GET /health` endpoint returns `{"status":"ok"}`.
2. Open the frontend production URL and test an approved company email account.
3. Create a chat and verify history persists after a reload.
4. Ask a question answered by an ingested filing; verify streamed output,
   citations, and source excerpts.
5. Ask an unsupported question and verify the app reports insufficient evidence.
6. Verify a second user cannot read or mutate the first user's chats.

The local Vercel builds validate packaging only. They do not verify hosted
secrets, Supabase migrations, ingested data, Gemini inference calls, or
production authentication.
