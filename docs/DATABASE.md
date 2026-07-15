# Database approach

The runtime database is SQLite, accessed through Python's standard `sqlite3` module. The machine-readable schema is in `database-schema.json`, and the implementation is in `backend/app/database.py`.

## Ownership model

| Parent | Child | Rule |
| --- | --- | --- |
| `users` | `boards` | One board per user, enforced by unique `boards.user_id` |
| `boards` | `board_columns` | Exactly five positions, created once by the application |
| `board_columns` | `cards` | Any number of cards with a unique position per column |
| `boards` | `chat_messages` | One ordered conversation history per board |

Foreign keys use `ON DELETE CASCADE`. Every query that reads or changes board data will start from the authenticated user's ID, preventing cross-user access. The current signed authentication cookie remains stateless and does not require a sessions table.

The seeded MVP password is stored as a salted `scrypt` hash. Login looks up the submitted username and verifies its password against that hash; plaintext passwords are never stored in SQLite.

## Initialization

The database path comes from `DATABASE_PATH` and defaults to `data/project_management.db`. On application startup, the backend:

1. Create the parent directory and database file when absent.
2. enable foreign keys, WAL mode, and a five-second busy timeout;
3. execute `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` statements in one transaction;
4. set `PRAGMA user_version = 1`; and
5. insert the MVP user, its board, five columns, and existing demo cards only when they do not exist.

Running initialization repeatedly must not duplicate data. A future schema change will increment `user_version` and use an explicit migration.

## Ordering and updates

Column positions are fixed from 0 through 4. Cards use contiguous zero-based positions within each column. Create, delete, reorder, and cross-column move operations will rewrite affected positions inside one transaction so the unique `(column_id, position)` constraint is never left invalid.

The application updates `updated_at` whenever a board, column, or card changes. Timestamps use SQLite UTC `CURRENT_TIMESTAMP` text values.

## Transactions

Each API mutation uses a single connection and transaction. Connections always commit or roll back and then close. AI responses may contain multiple card operations; they commit together, or the entire update rolls back when any operation is invalid. Both chat messages and all AI-generated board changes are saved in that same transaction.
