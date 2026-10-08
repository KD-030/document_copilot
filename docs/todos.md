# Project implementation checklist

> The Vercel frontend and backend are deployed, and the hosted Supabase schema is
> migrated through `0004_persist_chat_turn`. The backend now targets Gemini for
> chat and embeddings; migration `0006_gemini_embeddings` and a `GEMINI_API_KEY`
> are required before corpus ingestion and grounded chat validation. The most
> recent ingestion attempt stopped on Hugging Face HTTP 402 before creating
> documents or chunks. See the deployment guide for the handoff.

## Recommended execution order

Start with the backend and data layer first, then retrieval, then the frontend. The reason is simple: the client brief is built around trusted answers, citations, and grounded research. The UI can only be polished once the backend contract, auth, ingestion pipeline, and retrieval quality are stable.

Suggested order:

1. Backend foundation
2. Database + Supabase setup
3. SEC ingestion + chunking + embeddings
4. Retrieval + grounding
5. Chat orchestration + API endpoints
6. Frontend auth + chat UX
7. History, citations, and polish
8. QA, pilot readiness, deployment

---

## Phase 0 — project setup and environment

- [x] Confirm repo structure is in place (`backend/`, `frontend/`, `docs/`, `data/`)
- [x] Install local prerequisites: Python 3.12+, uv, Node 20+, pnpm
- [x] Create a shared environment checklist for all required keys and config values
- [x] Create `.env.example` or environment templates for backend and frontend
- [x] Verify workspace can run backend and frontend locally without code changes

## Phase 1 — backend foundation

- [x] Set up FastAPI app entrypoint and health check endpoint
- [x] Create central settings module (`backend/app/config.py`) for required env vars
- [x] Configure logging, startup validation, and app lifecycle
- [x] Add dependency injection patterns for DB/auth/services
- [x] Set up Supabase client wrapper and auth verification helpers
- [x] Define user/session models and authentication flow for the configured Driftwood email allow-list (`driftwood.com`)
- [x] Set up Alembic project and confirm migration workflow

## Phase 2 — database schema and Supabase setup

- [x] Create Supabase Postgres project and required tables
- [x] Add users table linked to Supabase Auth user IDs
- [x] Add chats table for conversation metadata
- [x] Add messages table for turn history and role/content payloads
- [x] Add documents table for source metadata
- [x] Add chunks table with content, metadata, embedding, and source pointer
- [x] Add indexes for query performance and retrieval support
- [x] Enable pgvector extension if not already enabled
- [x] Define full-text search support for keyword retrieval
- [x] Add migration files for all schema changes and review them

## Phase 3 — SEC corpus ingestion pipeline

- [x] Review the sample SEC 10-K corpus structure in `data/`
- [x] Build or finalize downloader script for SEC filings
- [x] Define manifest format for documents, titles, filing dates, and metadata
- [x] Parse source filings into clean text and extraction metadata
- [x] Normalise company/filing metadata for consistent querying
- [x] Chunk documents into passages suitable for retrieval
- [ ] Store source page references, document IDs, and chunk metadata
- [x] Generate embeddings for chunks via the configured Gemini embedding model (pipeline implemented; not run against live services)
- [x] Write ingestion pipeline to insert documents + chunks into Supabase/Postgres
- [ ] Validate a sample filing can be retrieved by document ID and chunk ID
- [x] Build a repeatable ingestion script for future filing batches

## Phase 4 — retrieval and grounding

- [x] Implement vector search against pgvector embeddings
- [x] Implement keyword/full-text search against Postgres
- [x] Define hybrid retrieval strategy using vector + keyword results
- [x] Implement Reciprocal Rank Fusion (RRF) or equivalent reranking logic
- [x] Add source-passage retrieval and ranking results for answer grounding
- [x] Build citation mapping from passages back to filing/page references
- [x] Ensure the system can return exact source snippets for evidence
- [x] Add safeguards so the model must answer only from retrieved evidence
- [x] Add a "not enough evidence" response path for empty retrieval context and validate answer citations
- [ ] Validate retrieval quality on realistic analyst questions

## Phase 5 — chat orchestration and backend answers

- [x] Define request/response schemas for chat sessions and messages
- [x] Build chat API routes: start chat, list chats, get chat history, send message
- [x] Add user auth guard and secure chat access by user
- [x] Create answer-generation workflow using retrieved context
- [x] Build prompt templates that instruct the model to cite sources and refuse unsupported claims
- [x] Add grounding checks before final answer is returned
- [x] Implement final answer formatting with cited filings and passages
- [x] Add error states for retrieval failures, upstream LLM failures, and empty context
- [x] Ensure outputs remain auditable and transparent for analyst use
- [x] Stream draft answer text and return the persisted, citation-validated turn

## Phase 6 — frontend shell and app structure

- [x] Set up Vite + React + TypeScript app
- [x] Configure Tailwind, shadcn, router, and global theme/token setup
- [x] Create `src/lib/env.ts` for frontend env configuration
- [x] Create `src/lib/api.ts` client wrapper for backend requests
- [x] Build app shell with authenticated layout and route structure
- [x] Build sign-in shell for the configured email allow-list
- [x] Build chat page and conversation list page
- [x] Build message composer and loading states
- [x] Add answer rendering with citations and source references
- [x] Add source snippet / filing expand details panel
- [x] Add empty states and error handling for no-results / auth failures

## Phase 7 — user experience and analyst workflow

- [x] Add chat history persistence on the backend
- [x] Display previous conversations by user
- [x] Display source company, filing dates, and available page references clearly
- [x] Add a way to inspect the underlying passages used for an answer
- [x] Build a clean research workflow for analyst questions
- [x] Ensure the UI maps directly to the product brief: plain-English Q&A, citations, and trustworthiness
- [x] Add responsive layout for browser-only use
- [ ] Review UX against the Driftwood workflow and remove unnecessary complexity

## Phase 8 — validation, QA, and production readiness

- [x] Run backend tests for retrieval, ingestion, and grounding logic
- [x] Run frontend type checks and lint checks
- [ ] Test realistic analyst prompts against the sample SEC corpus
- [ ] Verify citation accuracy for all key answer flows
- [ ] Verify unsupported or missing-evidence requests fail gracefully
- [ ] Confirm user authentication works with Driftwood email policy
- [ ] Confirm app works in a local browser workflow end-to-end
- [ ] Review security and secrets handling before deployment
- [x] Prepare deployment configuration for Vercel backend and frontend
- [ ] Pilot with 5 analysts and collect feedback against the 3-hour savings target

## Phase 9 — launch prep

- [ ] Finalize production env variables and secrets
- [ ] Review RLS, access control, and user isolation against the hosted database
- [ ] Validate DB performance on real corpus size and expected query volume
- [x] Prepare backend and frontend health checks
- [ ] Prepare release notes and support plan for pilot users
- [ ] Track pilot metrics: answer quality, adoption, and analyst time saved

---

## Most logical implementation order in one sentence

Backend + database + ingestion + retrieval first, then chat orchestration, then frontend UI, then final QA and pilot.

This is the correct order because Document Copilot's product value is not the interface; it is the trustworthiness of grounded answers from SEC filings. The architecture must be proven before the client-facing shell is polished.
