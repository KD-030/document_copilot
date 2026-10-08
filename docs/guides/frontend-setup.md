# Frontend setup

This project uses a Vite + React SPA because the frontend is an internal tool that mainly needs fast iteration, authenticated app flows, and a clean connection to the FastAPI backend. We do not need the extra server-rendering, SEO, or full-stack routing features that Next.js is optimized for.

## Init (from empty `frontend/`)

```bash
cd frontend
pnpm create vite . --template react-ts
pnpm install
pnpm add react-router-dom @supabase/supabase-js
pnpm add -D tailwindcss @tailwindcss/vite
```

The shadcn configuration is already checked in at `frontend/components.json`, so
you do not need to run `init` again. Run component commands from `frontend/`,
where the Vite app lives—not from the repository root:

```bash
cd frontend
pnpm dlx shadcn@latest add button
```

## Run

```bash
cd frontend
cp .env.example .env
pnpm install
pnpm dev
```

Set `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and
`VITE_SUPABASE_ANON_KEY` in `frontend/.env`. The anon key is intended for
browser use; never put the Supabase service-role key in frontend configuration.

## Check

```bash
pnpm tsc --noEmit
pnpm lint
```
