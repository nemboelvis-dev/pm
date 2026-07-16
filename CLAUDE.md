# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Project Management app: a Kanban board app with a NextJS frontend, Python FastAPI backend, SQLite database, and an AI chat sidebar (via OpenRouter, `openai/gpt-oss-120b`) that can create/edit/move/delete cards. Accounts are created via `POST /api/auth/register` (plus a seeded demo account, `user`/`password`); each user can own any number of boards, switchable from the board tabs in the header. Runs locally via Docker. See `README.md` for business requirements and `docs/PLAN.md` / `docs/DATABASE.md` for design details.

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
uv run pytest --cov=app --cov-report=term-missing            # run tests with coverage
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
- `auth.py` — validates credentials and registration (username 3-32 chars alnum/`_`/`-`, password 8+ chars), issues a signed 30-day HttpOnly session cookie (no sessions table; the cookie is stateless). Registration creates the user and a default board in one transaction.
- `database.py` — SQLite schema, connection/transaction lifecycle, schema version (`PRAGMA user_version`, currently `2`), idempotent demo data init, and the `_migrate_v1_to_v2` schema migration. Runs at startup via `main.py`'s lifespan.
- `board.py` — authenticated board-list and board CRUD (`GET/POST /api/boards`, `GET/PATCH/DELETE /api/boards/{board_id}`) plus column/card mutations nested under `/api/boards/{board_id}/...`. Every query is scoped through the signed-in username *and* the `board_id` in the path; ownership chain is `users -> boards -> board_columns -> cards` with `ON DELETE CASCADE`. `owned_board` is the shared ownership check `chat.py` also uses.
- `openrouter.py` — the OpenRouter HTTP client; reads `OPENROUTER_API_KEY` server-side only, uses `openai/gpt-oss-120b`, enforces strict structured output, sanitizes upstream failures. Accepts optional `frequency_penalty`/`presence_penalty` (chat.py sends 0.4/0.4 to curb repetition-loop degeneration in board updates).
- `chat.py` — nested under `/api/boards/{board_id}/chat`; builds each AI request from that board + saved history (last 50 messages sent to OpenRouter, though full history is retrievable) + new message; validates the strict response and applies create/edit/move/delete operations. Up to 2 retries (3 attempts total) on an invalid structured response, logging the raw completion if all attempts fail.

Key invariants:
- A user can own any number of boards (schema v2; v1 enforced one board per user via a `UNIQUE` constraint, dropped by the migration — see `docs/DATABASE.md` for why the migration needs `PRAGMA legacy_alter_table = ON`).
- Column positions are fixed 0-4; card positions are contiguous zero-based per column. Reorders/moves rewrite affected positions inside one transaction.
- Board mutations and chat operations are each atomic: an invalid AI operation rolls back all operations *and* both chat messages in that turn.
- The board API returns IDs as strings and cards as a record keyed by ID (matches frontend `BoardData`); every mutation returns the full refreshed board.

Frontend structure (`frontend/src/`):
- `app/page.tsx` — session check, switches between loading/login/register/board states.
- `components/LoginForm.tsx` / `components/RegisterForm.tsx` — sign-in and account-creation forms with a toggle link between them.
- `components/KanbanBoard.tsx` — owns board-list state (fetches `listBoards`, tracks `activeBoardId`), loads/mutates the active board, optimistic drag-and-drop (dnd-kit) with rollback, accepts AI-refreshed boards, renders an inline "create your first board" prompt when the account has none yet.
- `components/BoardSwitcher.tsx` — board tabs (switch/create/delete) rendered in the board header.
- `components/ChatSidebar.tsx` — chat history, sending/error states for the active board (keyed by `boardId` in the parent so switching boards remounts it), hands successful board updates to `KanbanBoard`.
- `lib/api.ts` — typed same-origin API client (auth, register, board list/CRUD, board-scoped column/card/chat calls).
- `lib/kanban.ts` — board types, demo data (used by tests), ID generation, pure card-movement logic.
- Unit tests live beside source (Vitest/Testing Library/jsdom); e2e tests are in `tests/` (Playwright, against the static build served by FastAPI).

State stays same-origin and backend-owned: no client state library, no browser storage for durable state — all board/chat state is persisted through `/api` and SQLite so it survives reloads and restarts. Which board is "active" is plain React state seeded from `GET /api/boards` (ordered by `updated_at DESC`), not a separate persisted field.

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
