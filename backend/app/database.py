import hashlib
import hmac
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS boards_user_id ON boards(user_id);

CREATE TABLE IF NOT EXISTS board_columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 4),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_id INTEGER NOT NULL REFERENCES board_columns(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL CHECK (position >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (column_id, position)
);

CREATE INDEX IF NOT EXISTS cards_column_id ON cards(column_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS chat_messages_board_id_id
ON chat_messages(board_id, id);
"""

COLUMNS = ["Backlog", "Discovery", "In Progress", "Review", "Done"]

CARDS = [
    (
        0,
        "Align roadmap themes",
        "Draft quarterly themes with impact statements and metrics.",
    ),
    (
        0,
        "Gather customer signals",
        "Review support tags, sales notes, and churn feedback.",
    ),
    (
        1,
        "Prototype analytics view",
        "Sketch initial dashboard layout and key drill-downs.",
    ),
    (
        2,
        "Refine status language",
        "Standardize column labels and tone across the board.",
    ),
    (
        2,
        "Design card layout",
        "Add hierarchy and spacing for scanning dense lists.",
    ),
    (
        3,
        "QA micro-interactions",
        "Verify hover, focus, and loading states.",
    ),
    (
        4,
        "Ship marketing page",
        "Final copy approved and asset pack delivered.",
    ),
    (
        4,
        "Close onboarding sprint",
        "Document release notes and share internally.",
    ),
]


def database_path() -> Path:
    default = Path(__file__).resolve().parents[2] / "data" / "project_management.db"
    return Path(os.getenv("DATABASE_PATH", default))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 1:
            _migrate_v1_to_v2(connection)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _seed_mvp_board(connection)
        connection.commit()
    finally:
        connection.close()


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    """Drop the one-board-per-user UNIQUE constraint on boards.user_id.

    `ALTER TABLE ... RENAME TO` rewrites foreign key clauses in *other*
    tables that reference the renamed table (e.g. board_columns.board_id
    would start pointing at "boards_v1"). legacy_alter_table suppresses
    that rewrite so those clauses keep referring to "boards" and resolve
    correctly once the replacement table is created under that name.
    """
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("PRAGMA legacy_alter_table = ON")
    connection.executescript(
        """
        ALTER TABLE boards RENAME TO boards_v1;

        CREATE TABLE boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO boards (id, user_id, title, created_at, updated_at)
        SELECT id, user_id, title, created_at, updated_at FROM boards_v1;

        DROP TABLE boards_v1;
        """
    )
    connection.execute("PRAGMA legacy_alter_table = OFF")
    connection.execute("PRAGMA foreign_keys = ON")


def _seed_mvp_board(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
        ("user", hash_password("password")),
    )
    user_id = connection.execute(
        "SELECT id FROM users WHERE username = ?", ("user",)
    ).fetchone()["id"]

    existing_board = connection.execute(
        "SELECT id FROM boards WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)
    ).fetchone()
    if existing_board:
        board_id = existing_board["id"]
    else:
        board_id = connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, ?)",
            (user_id, "Kanban Studio"),
        ).lastrowid

    for position, title in enumerate(COLUMNS):
        connection.execute(
            """
            INSERT OR IGNORE INTO board_columns (board_id, title, position)
            VALUES (?, ?, ?)
            """,
            (board_id, title, position),
        )

    card_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM cards
        JOIN board_columns ON board_columns.id = cards.column_id
        WHERE board_columns.board_id = ?
        """,
        (board_id,),
    ).fetchone()["count"]
    if card_count:
        return

    card_positions: dict[int, int] = {}
    for column_position, title, details in CARDS:
        column_id = connection.execute(
            """
            SELECT id FROM board_columns
            WHERE board_id = ? AND position = ?
            """,
            (board_id, column_position),
        ).fetchone()["id"]
        position = card_positions.get(column_position, 0)
        connection.execute(
            """
            INSERT INTO cards (column_id, title, details, position)
            VALUES (?, ?, ?, ?)
            """,
            (column_id, title, details, position),
        )
        card_positions[column_position] = position + 1


def create_board_with_default_columns(
    connection: sqlite3.Connection, user_id: int, title: str
) -> int:
    board_id = connection.execute(
        "INSERT INTO boards (user_id, title) VALUES (?, ?)",
        (user_id, title),
    ).lastrowid
    for position, column_title in enumerate(COLUMNS):
        connection.execute(
            """
            INSERT INTO board_columns (board_id, title, position)
            VALUES (?, ?, ?)
            """,
            (board_id, column_title, position),
        )
    return board_id


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, salt_value, digest_value = encoded_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_value),
            n=16384,
            r=8,
            p=1,
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_value)
