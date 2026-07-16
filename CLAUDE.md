# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Project Management MVP: a Kanban board app with a NextJS frontend, Python FastAPI backend, SQLite database, and an AI chat sidebar (via OpenRouter, `openai/gpt-oss-120b`) that can create/edit/move/delete cards. Single hardcoded user (`user`/`password`), one board per user, runs locally via Docker. See `README.md` for business requirements and `docs/PLAN.md` / `docs/DATABASE.md` for design details.

## Commands

### Run the app (Docker)

```sh
cp .env.example .env   # set OPENROUTER_API_KEY
./scripts/start.ps1    # Windows
sh scripts/start.sh    # macOS/Linux
```

App runs at http://localhost:8000. Stop with the matching `stop` script. These scripts are thin `docker compose` wrappers around the root `compose.yaml`.

### Backend (`backend/`, uv-managed)

```sh
uv run pytest                                              # run all tests
uv run pytest tests/test_board.py::test_name                # run a single test
uv run --env-file ../.env pytest -m live --run-openrouter-live   # opt-in live OpenRouter test
uv lock --check                                             # verify lockfile matches pyproject.toml
```

Tests must pass with warnings treated as errors and never call OpenRouter except the explicit live test above.

### Frontend (`frontend/`)

```sh
npm run lint
npm run test:unit       # vitest
npm run build           # required before test:e2e (static export)
npm run test:e2e        # playwright, runs against the static build
npm run test:all        # unit + e2e
```

Run lint, test:unit, build, and test:e2e whenever frontend behavior changes.

## Architecture

The frontend is statically exported (`next.config.ts` sets static export) and has no Node server in production — FastAPI serves the exported files from `STATIC_DIRECTORY` (`frontend/out` locally) and mounts them at `/` after the `/api` routes. All app APIs live under `/api`.

Backend modules in `backend/app/` (each owns one responsibility):
- `auth.py` — validates MVP credentials and issues a signed 30-day HttpOnly session cookie (no sessions table; the cookie is stateless).
- `database.py` — SQLite schema, connection/transaction lifecycle, schema version (`PRAGMA user_version`), idempotent demo data init. Runs at startup via `main.py`'s lifespan.
- `board.py` — authenticated board reads and column/card mutations. Every query is scoped through the signed-in username; ownership chain is `users -> boards -> board_columns -> cards` with `ON DELETE CASCADE`.
- `openrouter.py` — the OpenRouter HTTP client; reads `OPENROUTER_API_KEY` server-side only, uses `openai/gpt-oss-120b`, enforces strict structured output, sanitizes upstream failures.
- `chat.py` — builds each AI request from the current board + saved history (last 50 messages sent to OpenRouter, though full history is retrievable) + new message; validates the strict response and applies create/edit/move/delete operations. One retry on retryable OpenRouter failures.

Key invariants:
- Column positions are fixed 0-4; card positions are contiguous zero-based per column. Reorders/moves rewrite affected positions inside one transaction.
- Board mutations and chat operations are each atomic: an invalid AI operation rolls back all operations *and* both chat messages in that turn.
- The board API returns IDs as strings and cards as a record keyed by ID (matches frontend `BoardData`); every mutation returns the full refreshed board.

Frontend structure (`frontend/src/`):
- `app/page.tsx` — session check, switches between loading/login/board states.
- `components/KanbanBoard.tsx` — loads/mutates the board, optimistic drag-and-drop (dnd-kit) with rollback, accepts AI-refreshed boards.
- `components/ChatSidebar.tsx` — chat history, sending/error states, hands successful board updates to `KanbanBoard`.
- `lib/api.ts` — typed same-origin API client (auth, board, chat).
- `lib/kanban.ts` — board types, demo data (used by tests), ID generation, pure card-movement logic.
- Unit tests live beside source (Vitest/Testing Library/jsdom); e2e tests are in `tests/` (Playwright, against the static build served by FastAPI).

State stays same-origin and backend-owned: no client state library, no browser storage for durable state — all board/chat state is persisted through `/api` and SQLite so it survives reloads and restarts.

## Coding standards

- Use latest/idiomatic library versions.
- Keep it simple: no over-engineering, no unnecessary defensive programming, no speculative features.
- No emojis, anywhere.
- When debugging, find the root cause with evidence before fixing — don't guess.
- Do not bypass the auth dependency or query board data without the user-ownership scoping in `board.py`.

## Project color scheme (`frontend/src/app/globals.css`)

- Accent Yellow `#ecad0a` — accent lines, highlights
- Blue Primary `#209dd7` — links, key sections
- Purple Secondary `#753991` — submit buttons, important actions
- Dark Navy `#032147` — main headings
- Gray Text `#888888` — supporting text, labels
