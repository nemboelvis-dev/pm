import hashlib
import hmac
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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

    with connect() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _seed_mvp_board(connection)


def _seed_mvp_board(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
        ("user", _password_hash("password")),
    )
    user_id = connection.execute(
        "SELECT id FROM users WHERE username = ?", ("user",)
    ).fetchone()["id"]

    connection.execute(
        "INSERT OR IGNORE INTO boards (user_id, title) VALUES (?, ?)",
        (user_id, "Kanban Studio"),
    )
    board_id = connection.execute(
        "SELECT id FROM boards WHERE user_id = ?", (user_id,)
    ).fetchone()["id"]

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


def _password_hash(password: str) -> str:
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
