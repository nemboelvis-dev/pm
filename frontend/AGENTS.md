# Frontend

This directory contains the Kanban frontend built with the Next.js App Router, React, strict TypeScript, and Tailwind CSS. `next.config.ts` enables static export, so the production build has no Node.js server and is served by FastAPI. Authentication uses same-origin `/api/auth` requests and a backend-owned HttpOnly cookie. The authenticated board is loaded and mutated through the same-origin API, so board changes survive page reloads and browser restarts.

## Structure

- `src/app/page.tsx` checks the persistent session and switches between loading, login, and authenticated board states.
- `src/app/layout.tsx` provides metadata and fonts, while `globals.css` defines the project color variables and global styles.
- `src/components/LoginForm.tsx` contains the accessible MVP sign-in form.
- `src/components/KanbanBoard.tsx` loads the board, coordinates API-backed mutations, keeps drag-and-drop responsive with optimistic updates and rollback, and accepts refreshed boards from AI responses.
- `src/components/ChatSidebar.tsx` loads saved conversation history, sends user requests, displays sending/error states, and passes successful board updates to `KanbanBoard`.
- `KanbanColumn.tsx`, `KanbanCard.tsx`, `KanbanCardPreview.tsx`, and `NewCardForm.tsx` contain the board UI.
- `src/lib/api.ts` is the typed same-origin client for authentication, board operations, and chat.
- `src/lib/kanban.ts` defines the board types, demo data used by tests, ID generation, and the pure card movement function.
- Tests beside the source use Vitest, Testing Library, and jsdom. Tests in `tests/` use Playwright against the static build served by FastAPI.

## Existing behavior

The user must sign in with `user` / `password` before seeing the board and can log out. The board has five fixed columns. A user can rename them; add, edit, or remove cards; reorder cards; and drag cards between columns. The responsive AI sidebar can create, edit, move, or delete one or more cards through natural-language requests and refreshes the board immediately. Board changes and chat history are persisted by FastAPI and SQLite. The UI includes loading, retry, sending, and failure states. It uses dnd-kit for pointer-based sorting and the project color scheme from `globals.css`.

## Development rules

Preserve the established visual language and accessibility labels. Keep components and state flow direct; do not introduce a client state library. Use same-origin `/api` requests and keep durable state in the backend rather than browser storage.

Run `npm run lint`, `npm run test:unit`, `npm run build`, and `npm run test:e2e` when frontend behavior changes.
