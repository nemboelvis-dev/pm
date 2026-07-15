# Code Review

## Remediation update

The concrete MVP-safe actions from this review have now been applied:

- login verifies the stored `scrypt` password hash;
- frontend API errors tolerate non-JSON bodies and retain the HTTP status;
- missing static frontend assets generate a startup warning;
- Python dependencies have compatible version bounds;
- OpenRouter uses one bounded retry and honors numeric `Retry-After` values;
- only the latest 50 chat messages are sent to the model;
- duplicated chat-row mapping was removed;
- Playwright output is ignored and the tracked run-state file is removed from the index;
- `.env.example`, clearer startup errors, a Compose health check, and CI were added; and
- regression tests cover the new behavior.

The production-only authentication cluster and formal migration framework remain deferred because this is explicitly a local MVP. The suggested extra drag payload assertion was not added: the existing pure movement tests, backend position tests, and real persistence browser test already cover the behavior at more stable boundaries.

Scope: full repository (`backend/`, `frontend/`, `docs/`, Docker/Compose, scripts). This is an
independent review; `review.md` already contains the author's own five-point self-review
(production-hardening priorities) and is a useful cross-check, not a duplicate of this document.
Findings below are new or more granular unless explicitly marked "confirms review.md".

Overall assessment: the codebase is small, consistent, and well tested for its stated MVP scope
(see `AGENTS.md`). Ownership checks, transactional writes, and structured AI output validation are
implemented correctly and are backed by strong test coverage on both sides. The issues below are
mostly polish, a few real edge-case bugs, and some housekeeping items — nothing that blocks the
stated MVP goal, but worth fixing before this evolves toward anything beyond a local demo.

---

## 1. Correctness issues

### 1.1 `password_hash` is computed and stored but never checked (dead/misleading code)
**File:** `backend/app/database.py:199-202`, `backend/app/auth.py:74-92`

`_seed_mvp_board` hashes the seed password with `scrypt` and stores it in `users.password_hash`,
which strongly implies login is verified against the database. In reality, `auth.login()` compares
the submitted credentials against the hardcoded module constants `USERNAME`/`PASSWORD`
(`auth.py:13-14, 76-77`) and never reads `users.password_hash` at all. The column and the hashing
logic are vestigial — no code path uses them.

**Risk:** a future contributor (or an AI agent) who wants to add a second user or a password-change
feature will reasonably assume the hash column is already wired into login, and will be surprised
when it isn't. It's a trap disguised as an implemented feature.

**Remedial action:** either (a) actually verify against `password_hash` for the seeded user (small,
consistent change, and a real step toward the multi-user future the schema already supports), or
(b) remove the hashing/column entirely and note in `docs/DATABASE.md` that credential storage is
deferred until real auth is built. Given the schema is explicitly designed to "support multiple
users for future" (`AGENTS.md:14`), option (a) is the smaller, more forward-compatible fix.

### 1.2 Frontend `request()` helper can throw an unhandled `SyntaxError` on non-JSON error bodies
**File:** `frontend/src/lib/api.ts:34-37`

```ts
if (!response.ok) {
  const body = (await response.json()) as { detail?: string };
  throw new ApiError(body.detail ?? "Request failed", response.status);
}
```

If a non-2xx response has no JSON body (e.g. a raw 502/504 from a proxy in front of the container,
or any unexpected plain-text/HTML error page), `response.json()` throws a `SyntaxError` instead of
producing an `ApiError`. Callers all branch on `error instanceof ApiError` and fall back to a
generic message otherwise (`KanbanBoard.tsx:264-267`, `ChatSidebar.tsx:187-188`, `page.tsx:38-42`),
so today this "only" degrades to a slightly less specific error message rather than crashing the
UI — but it silently loses the HTTP status code, and any *new* caller that assumes `catch` always
yields an `ApiError` will break.

**Remedial action:** guard the parse, e.g.:
```ts
if (!response.ok) {
  const detail = await response.json().then((b) => b?.detail, () => undefined);
  throw new ApiError(detail ?? "Request failed", response.status);
}
```

### 1.3 `StaticFiles` mount uses `check_dir=False`, hiding a misconfigured `STATIC_DIRECTORY`
**File:** `backend/app/main.py:32-50`

`check_dir=False` lets the app start even if `STATIC_DIRECTORY` doesn't exist. That's needed so
backend tests can run without a frontend build present, but it means a production misconfiguration
(wrong path, frontend build step skipped) fails silently at startup and only surfaces as 404s on
every page request at runtime, with no log line pointing at the cause.

**Remedial action:** low priority for the MVP, but consider logging a warning at startup if
`static_directory` doesn't exist (rather than changing `check_dir`, which would break the test
setup), so a bad deploy is visible in `docker compose logs` immediately.

---

## 2. Security (mostly confirms/extends `review.md` §1 with specifics)

These are already called out at a high level in `review.md`; the notes below add the concrete
locations and a couple of items not in that list.

- **Hardcoded credentials and fallback session secret are intentional for the MVP**
  (`backend/app/auth.py:13-14, 106`), per `AGENTS.md:14`. Not a bug, but flag explicitly: the
  `SESSION_SECRET` fallback (`"local-project-management-secret"`) is a real secret if this ever
  runs anywhere non-local, since it's committed in source and is trivial to forge a session with.
  There's no startup check that fails loudly if `SESSION_SECRET` is unset in a non-dev environment.
- **No rate limiting on `/api/auth/login`** (`auth.py:74`). Combined with a fixed, publicly-known
  password, this is only benign because the app is local-only by design — flag it here so it isn't
  forgotten if the app is ever exposed on a network.
- **No CSRF token; relies solely on `SameSite=Lax`** (`auth.py:90`). Adequate for today's
  same-origin, GET/POST-from-JS-only usage, but worth a one-line note in `backend/AGENTS.md` so the
  assumption is explicit if a future change adds cross-site or `<form>`-based POSTs.
- **Cookie is not `Secure`** (`auth.py:84-91`). Correct for local HTTP-only usage; would need to
  change if the container is ever served over HTTPS behind a reverse proxy.

None of these need action for the current local-only MVP; they're recorded so they aren't
rediscovered from scratch later. `review.md` §1 already prioritizes fixing this cluster before any
production move — this section just pins down file/line references for that work.

---

## 3. Maintainability / design

### 3.1 Unbounded chat history is resent on every request
**File:** `backend/app/chat.py:157-181`

`send_message` loads *all* prior chat messages for the board (`_read_messages`, unbounded) and puts
every one into the OpenRouter request body. There's no cap, truncation, or summarization. For an
MVP with one board and a demo session this is invisible, but the cost and context-window risk grow
linearly and silently with conversation length. `review.md` §3 already flags this as a reliability
item; concretely, the fix point is `_read_messages` in `chat.py:257-276` — e.g. cap to the last N
messages or introduce a rolling summary before this needs to handle real usage.

### 3.2 No version constraints in `backend/pyproject.toml`
**File:** `backend/pyproject.toml:6-10`

```toml
dependencies = [
    "fastapi",
    "httpx",
    "uvicorn[standard]",
]
```

`uv.lock` pins exact resolved versions for reproducible installs today, which covers the immediate
risk. But the `pyproject.toml` itself has no lower/upper bounds, so the first `uv lock --upgrade` (or
any workflow that regenerates the lock file) can silently jump major versions of FastAPI/httpx/
uvicorn with no guardrail. Consider at least a minimum version per the coding standard "use latest
versions... as of today" (`AGENTS.md:45`), e.g. `"fastapi>=0.115"`, so an upgrade can't
accidentally regress below a known-good baseline.

### 3.3 Duplicated `ChatMessage` construction
**File:** `backend/app/chat.py:257-302`

`_read_messages` and `_insert_message` both build a `ChatMessage` from a `sqlite3.Row` with
identical field mapping. Minor duplication; a small `_row_to_message(row)` helper would remove the
repetition. Not worth doing in isolation, but worth folding in next time either function changes.

---

## 4. Testing

Backend and frontend test coverage is genuinely strong: auth (valid/invalid/tampered/expired
tokens), ownership isolation across users, position-contiguity after create/move/delete, AI
operation rollback, and mocked OpenRouter request shape are all directly tested
(`backend/tests/test_board.py`, `test_chat.py`, `test_auth`-equivalent tests in `test_main.py`).
Frontend has matching unit tests (Vitest/Testing Library) and Playwright e2e coverage for the same
flows. A few gaps:

- **No test exercises the `request()` non-JSON-error-body path** described in §1.2 — understandable
  since it doesn't come up in mocked fetch responses, but worth one regression test once fixed.
- **No frontend test for the drag-and-drop position math end-to-end against the API** (the
  Playwright drag test asserts the card lands in the target column, but doesn't check the numeric
  `position` sent matches backend expectations the way `kanban.test.ts` unit-tests `moveCard` in
  isolation). Low priority given the backend already tests position math directly
  (`test_reorders_a_card_within_its_column`, `test_moves_a_card_between_columns`).
- **No CI workflow** (`.github/workflows/` is absent). `review.md` §5 already calls this out as the
  top gap; nothing to add beyond confirming it.

---

## 5. Infrastructure / repo hygiene

### 5.1 `frontend/test-results/.last-run.json` is committed to git
**Confirmed via `git ls-files frontend/test-results`.**

This is a Playwright-generated run-state file, not source. It's tracked in the repository (likely
from a `git add .` at some point) even though `frontend/.gitignore` doesn't exclude
`test-results/`. It'll churn on every local test run and creates noisy diffs for anyone who runs
`npm run test:e2e`.

**Remedial action:** add `test-results/` and `playwright-report/` to `frontend/.gitignore`, then
`git rm --cached frontend/test-results/.last-run.json`.

### 5.2 No `.env.example`
**Files:** `README.md:21-22`, `AGENTS.md:26`, `tutorial.md:184-190`

Three separate docs tell the reader to create a `.env` with `OPENROUTER_API_KEY` (and implicitly
`SESSION_SECRET` for anything beyond local use), but there's no checked-in `.env.example` template.
Trivial to add and removes one manual step / one way to typo the variable name.

**Remedial action:** add a root `.env.example` with `OPENROUTER_API_KEY=` (and optionally a comment
about `SESSION_SECRET`), referenced from the README.

### 5.3 `compose.yaml` hard-requires `.env` to exist
**File:** `compose.yaml:6-7`

`env_file: [.env]` makes `docker compose up` fail immediately if `.env` is missing, with a message
that doesn't point a new contributor at the README section that explains why. Combined with §5.2,
a first-time clone-and-run will hit this. Low priority, but pairing the `.env.example` fix with a
one-line README callout ("copy `.env.example` to `.env` before running the start script") would
close the loop.

---

## 6. Summary of remedial actions (priority order)

| # | Action | File(s) | Priority |
| - | --- | --- | --- |
| 1 | Wire `password_hash` into login or drop it, and update `docs/DATABASE.md` accordingly | `backend/app/database.py`, `backend/app/auth.py` | Medium — misleading dead code |
| 2 | Guard `response.json()` on the error path in the API client | `frontend/src/lib/api.ts` | Medium — real edge-case bug |
| 3 | Add `test-results/`/`playwright-report/` to `.gitignore`; untrack `frontend/test-results/.last-run.json` | `frontend/.gitignore` | Low — repo hygiene |
| 4 | Add root `.env.example`; add a copy-the-template note to `README.md` | new file, `README.md` | Low — onboarding friction |
| 5 | Add minimum version bounds in `backend/pyproject.toml` | `backend/pyproject.toml` | Low — future-proofing |
| 6 | Cap/summarize chat history sent to OpenRouter (confirms `review.md` §3) | `backend/app/chat.py` | Low for MVP, higher before real usage |
| 7 | Add a CI workflow running backend + frontend checks (confirms `review.md` §5) | new `.github/workflows/*.yml` | Low for MVP, higher before real usage |
| 8 | Production-hardening cluster: real auth, `SESSION_SECRET` enforcement, rate limiting, CSRF, `Secure` cookies (confirms `review.md` §1) | `backend/app/auth.py` | Deferred by design; revisit before any non-local deployment |

No code was modified as part of this review, per instructions.
