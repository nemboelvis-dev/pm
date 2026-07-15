# Project Management MVP execution plan

Complete one part at a time and wait for explicit user approval before starting the next part. The database design is documented as JSON, while SQLite is the runtime database. Login sessions must survive browser refreshes and restarts.

## Part 1: Plan and repository understanding

- [x] Review the root instructions and existing frontend.
- [x] Document the frontend in `frontend/AGENTS.md`.
- [x] Define implementation steps, tests, and success criteria.
- [x] Receive user approval before starting Part 2.

Tests and success criteria:

- The plan covers every business requirement and technical decision.
- Each implementation part has explicit verification criteria.
- `frontend/AGENTS.md` accurately describes the existing frontend code and tests.
- The user has reviewed and approved the plan.

## Part 2: Scaffolding

- [x] Add a uv-managed FastAPI project in `backend/` with automated API tests.
- [x] Add Docker infrastructure that runs one FastAPI process.
- [x] Serve a small example HTML page at `/` that calls an example `/api/hello` endpoint.
- [x] Add Docker Compose configuration with `.env` loading.
- [x] Add PowerShell scripts for Windows and shell scripts shared by macOS and Linux.
- [x] Document the scaffold in `backend/AGENTS.md` and keep the root README concise.
- [x] Build and smoke-test the container while the Docker engine is running.
- [x] Receive user approval before starting Part 3.

Tests and success criteria:

- `uv lock --check` confirms a valid lockfile.
- Backend tests prove that `/`, `/api/hello`, and `/api/health` work.
- The container builds and starts with the documented scripts.
- Opening `/` shows the example page and its successful API response.

## Part 3: Static frontend integration

- [x] Configure Next.js for static export.
- [x] Preserve the existing Kanban layout and color scheme.
- [x] Replace the example page by copying the static export into the FastAPI runtime image.
- [x] Make FastAPI serve the exported frontend at `/` while keeping `/api/*` available.
- [x] Add comprehensive frontend unit and browser integration coverage.
- [x] Update the minimal project README with run and test commands.
- [x] Receive user approval before starting Part 4.

Tests and success criteria:

- `npm run build` produces `frontend/out/` without a Node server.
- FastAPI serves the exported `index.html` at `/`.
- Frontend lint, unit tests, browser tests, and the production container check pass.

## Part 4: Persistent dummy authentication

- [x] Validate the hardcoded user `user` with password `password` in FastAPI.
- [x] Implement login, session lookup, and logout APIs.
- [x] Sign a 30-day HttpOnly cookie so login survives refreshes and browser restarts.
- [x] Show the board only after successful authentication and provide logout.
- [x] Receive user approval before starting Part 5.

Tests and success criteria:

- Invalid credentials return HTTP 401.
- Valid credentials set a persistent cookie and return the user.
- The cookie authenticates a new request and survives browser restarts.
- Logout clears the cookie and protects the board again.
- The session endpoint returns HTTP 401 and the frontend hides the board when unauthenticated.

## Part 5: Database modelling

- [x] Save the proposed schema in `docs/database-schema.json`.
- [x] Document initialization, ownership, ordering, and transaction behavior.
- [x] Model multiple users and one board per user.
- [x] Keep the board columns fixed while allowing their titles to change.
- [x] Receive user approval before starting Part 6.

Tests and success criteria:

- The proposal defines automatic, idempotent initialization for Part 6.
- Foreign keys and uniqueness constraints define ownership and one board per user.
- The JSON document accurately describes the SQLite schema.
- No runtime database code is introduced before schema approval.

## Part 6: Persistent backend APIs

- [x] Implement board read, column rename, card create/edit/delete, and card move APIs.
- [x] Return a stable JSON board representation from every mutation.
- [x] Validate ownership and update card positions atomically.
- [x] Update `backend/AGENTS.md` with the finished architecture.
- [x] Receive user approval before starting Part 7.

Tests and success criteria:

- API tests cover every endpoint, validation failure, and authentication boundary.
- Card ordering remains contiguous after create, move, and delete operations.
- Data written by one authenticated request is visible in a later request.
- A user cannot access another user's board data.

## Part 7: Frontend and backend integration

- [x] Load the board from the authenticated API.
- [x] Persist column renames and all card operations.
- [x] Add card editing to the existing add/delete/drag behavior.
- [x] Display loading and actionable error states.
- [x] Receive user approval before starting Part 8.

Tests and success criteria:

- Component tests verify API-backed login and board workflows.
- Browser tests verify login, refresh persistence, card creation/editing, and logout.
- A page refresh shows the last persisted board state.
- Dragging within and between columns persists the resulting order.

## Part 8: OpenRouter connectivity

- [x] Add an OpenRouter client using `OPENROUTER_API_KEY`.
- [x] Use the `openai/gpt-oss-120b` model.
- [x] Add a deliberately opt-in live connectivity test for the `2+2` prompt.
- [x] Receive user approval before starting Part 9.

Tests and success criteria:

- The normal test suite never spends API credits.
- The live test can be run explicitly and confirms the configured model responds.
- Missing configuration produces a clear server response without exposing secrets.

## Part 9: Structured AI board updates

- [x] Include the current board, saved conversation history, and new user message in each call.
- [x] Require a strict JSON Schema response with an assistant message and card operations.
- [x] Validate and apply create, edit, and move operations in one SQLite transaction.
- [x] Save both user and assistant chat messages.
- [x] Receive user approval before starting Part 10.

Tests and success criteria:

- Mocked OpenRouter tests inspect the complete prompt and structured-output schema.
- Invalid or inapplicable operations roll back the entire board update.
- A successful response returns both the assistant message and refreshed board.
- Chat history is scoped to the authenticated user.

## Part 10: AI chat sidebar and final verification

- [x] Add a responsive chat sidebar with history, sending, and error states.
- [x] Refresh the board immediately from the AI response when operations are applied.
- [x] Run backend, frontend, integration, static-build, and container checks.
- [x] Mark completed plan items and report any environment-only limitation.

Tests and success criteria:

- Chat UI tests cover history, sending, failure, and board refresh behavior.
- The full automated suite passes.
- The production container serves the login, board, API, and chat from one local port.
- No API key or generated database is committed.
