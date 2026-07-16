# Database approach

The runtime database is SQLite, accessed through Python's standard `sqlite3` module. The machine-readable schema is in `database-schema.json`, and the implementation is in `backend/app/database.py`.

## Ownership model

| Parent | Child | Rule |
| --- | --- | --- |
| `users` | `boards` | Any number of boards per user (`boards.user_id`, indexed, not unique) |
| `boards` | `board_columns` | Exactly five positions, created once per board |
| `board_columns` | `cards` | Any number of cards with a unique position per column |
| `boards` | `chat_messages` | One ordered conversation history per board |

Foreign keys use `ON DELETE CASCADE`. Every query that reads or changes board, column, card, or chat data starts from the authenticated user's ID and the `board_id` in the URL path, so a request can't reach another user's board, or a board the same user owns but didn't ask for. The current signed authentication cookie remains stateless and does not require a sessions table.

Passwords (both the seeded MVP account and accounts created via `POST /api/auth/register`) are stored as a salted `scrypt` hash. Login looks up the submitted username and verifies its password against that hash; plaintext passwords are never stored in SQLite. Registration validates the username (3-32 characters, letters/numbers/underscore/dash) and password (8+ characters) before creating the user and a default board titled "My Board" with the same five empty columns as the demo board.

## Initialization

The database path comes from `DATABASE_PATH` and defaults to `data/project_management.db`. On application startup, the backend:

1. Create the parent directory and database file when absent.
2. Read `PRAGMA user_version`; if it is `1`, run the v1-to-v2 migration (below) before anything else.
3. enable foreign keys, WAL mode, and a five-second busy timeout;
4. execute `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` statements in one transaction;
5. set `PRAGMA user_version = 2`; and
6. insert the MVP user, its board, five columns, and existing demo cards only when they do not exist.

Running initialization repeatedly must not duplicate data.

### Schema migrations

`SCHEMA_VERSION` in `backend/app/database.py` is `2`. Version 1 enforced one board per user via a `UNIQUE` constraint on `boards.user_id`; version 2 drops that constraint so a user can own multiple boards. `_migrate_v1_to_v2` performs the migration by recreating the `boards` table (`RENAME` to `boards_v1`, `CREATE` the new shape, `INSERT ... SELECT`, `DROP boards_v1`) with both `foreign_keys` and `legacy_alter_table` pragmas explicitly managed.

The `legacy_alter_table` pragma matters here: without it, SQLite's `ALTER TABLE ... RENAME TO` silently rewrites foreign key clauses in *other* tables that reference the renamed table (`board_columns.board_id` and `chat_messages.board_id` would start pointing at `boards_v1`). Once `boards_v1` is dropped, those rewritten references dangle and every insert into `board_columns` or `chat_messages` fails with `no such table: main.boards_v1`. Setting `legacy_alter_table = ON` before the rename keeps those foreign key clauses referring to the literal name `"boards"`, so they resolve correctly once the replacement table is created under that name. `tests/test_database.py::test_migrates_a_v1_database_dropping_the_one_board_per_user_constraint` seeds a full legacy schema (including `board_columns`, `cards`, and `chat_messages`) specifically to catch this class of regression — a migration test that only covers the `users`/`boards` tables would not have caught it.

Any future schema change should increment `SCHEMA_VERSION` again and add a corresponding `_migrate_vN_to_vN+1` step.

## Ordering and updates

Column positions are fixed from 0 through 4. Cards use contiguous zero-based positions within each column. Create, delete, reorder, and cross-column move operations will rewrite affected positions inside one transaction so the unique `(column_id, position)` constraint is never left invalid.

The application updates `updated_at` whenever a board, column, or card changes. Timestamps use SQLite UTC `CURRENT_TIMESTAMP` text values.

## Transactions

Each API mutation uses a single connection and transaction. Connections always commit or roll back and then close. AI responses may contain multiple card operations; they commit together, or the entire update rolls back when any operation is invalid. Both chat messages and all AI-generated board changes are saved in that same transaction.
