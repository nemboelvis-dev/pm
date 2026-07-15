# Backend

This directory contains the uv-managed FastAPI backend. `app/main.py` assembles the API routers, initializes SQLite during application startup, and mounts the exported Next.js frontend after `/api` routes. The container supplies the frontend through `STATIC_DIRECTORY`; local development defaults to `frontend/out`.

## Modules

- `app/auth.py` validates the MVP credentials (`user` / `password`) and owns the signed 30-day HttpOnly session cookie.
- `app/database.py` owns the SQLite schema, connection/transaction lifecycle, schema version, and idempotent demo data initialization.
- `app/board.py` owns authenticated board reads and reusable column/card mutation functions. Every query is scoped through the signed-in username.
- `app/openrouter.py` owns the OpenRouter HTTP client and authenticated connectivity endpoint. It reads `OPENROUTER_API_KEY` only on the server, uses `openai/gpt-oss-120b`, forwards strict structured-output requirements, and sanitizes upstream failures.
- `app/chat.py` builds each AI request from the current board, that board's saved history, and the new user message. It validates the strict response, applies create/edit/move operations, and saves both messages atomically.

The board API returns IDs as strings and cards as a record keyed by ID, matching the frontend's existing `BoardData` shape. Every mutation returns the complete refreshed board. Card ordering changes and ownership checks occur inside one transaction. The chat API returns both saved messages and the refreshed board; any invalid AI operation rolls back all operations and both messages. All history remains available through the chat API, while only the latest 50 messages are sent to OpenRouter. Retryable OpenRouter failures receive one bounded retry.

Dependencies and Python compatibility are declared in `pyproject.toml`; `uv.lock` must be committed. Run tests from this directory with `uv run pytest`. Tests use a separate temporary database per test and must pass with warnings treated as errors. The live OpenRouter test is always skipped unless pytest receives `--run-openrouter-live`; run it explicitly with `uv run --env-file ../.env pytest -m live --run-openrouter-live`.

Keep application APIs under `/api`. Add separate modules only for distinct responsibilities. Do not bypass the authentication dependency or perform board queries without user ownership constraints.

Authentication is intentionally scoped to local MVP use. The signed cookie uses a committed fallback secret, `SameSite=Lax`, and no `Secure` flag so local HTTP works. Before any non-local deployment, require a strong external session secret, HTTPS with secure cookies, CSRF protection, and login rate limiting.
