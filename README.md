# Project Management MVP

## Run

Copy `.env.example` to `.env`, then set `OPENROUTER_API_KEY` in `.env`.

Windows:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```sh
cp .env.example .env
```

Windows:

```powershell
./scripts/start.ps1
```

macOS or Linux:

```sh
sh scripts/start.sh
```

Open <http://localhost:8000>. Use the matching `stop` script to stop the app.

Sign in with username `user` and password `password`.

SQLite data is stored in `data/project_management.db` and persists across container restarts.
The board assistant uses the server-side `OPENROUTER_API_KEY` from `.env` to create, edit, and move cards.

## Backend tests

```sh
cd backend
uv run pytest
```

The normal suite never calls OpenRouter. Run the opt-in live connectivity test from `backend/` only when needed:

```sh
uv run --env-file ../.env pytest -m live --run-openrouter-live
```

## Frontend checks

```sh
cd frontend
npm ci
npm run lint
npm run test:unit
npm run build
npm run test:e2e
```
