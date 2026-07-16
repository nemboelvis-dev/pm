import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import SCHEMA_VERSION, connect, initialize_database


def test_initialization_creates_schema_and_seed_data(client: TestClient) -> None:
    with connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        board_count = connection.execute("SELECT COUNT(*) FROM boards").fetchone()[0]
        column_count = connection.execute(
            "SELECT COUNT(*) FROM board_columns"
        ).fetchone()[0]
        card_count = connection.execute("SELECT COUNT(*) FROM cards").fetchone()[0]

    assert {"users", "boards", "board_columns", "cards", "chat_messages"} <= tables
    assert version == SCHEMA_VERSION
    assert (user_count, board_count, column_count, card_count) == (1, 1, 5, 8)


def test_initialization_is_idempotent(client: TestClient) -> None:
    initialize_database()
    initialize_database()

    with connect() as connection:
        counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("users", "boards", "board_columns", "cards")
        )

    assert counts == (1, 1, 5, 8)


def test_schema_supports_multiple_boards_per_user(
    client: TestClient,
) -> None:
    with connect() as connection:
        user_id = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES ('second', 'hash')"
        ).lastrowid
        connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, 'First board')",
            (user_id,),
        )
        connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, 'Second board')",
            (user_id,),
        )
        board_count = connection.execute(
            "SELECT COUNT(*) FROM boards WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

    assert board_count == 2


def test_migrates_a_v1_database_dropping_the_one_board_per_user_constraint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    legacy_connection = sqlite3.connect(db_path)
    legacy_connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE boards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE board_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 4),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (board_id, position)
        );
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_id INTEGER NOT NULL REFERENCES board_columns(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL CHECK (position >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (column_id, position)
        );
        CREATE TABLE chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    legacy_user_id = legacy_connection.execute(
        "INSERT INTO users (username, password_hash) VALUES ('legacy', 'hash')"
    ).lastrowid
    legacy_board_id = legacy_connection.execute(
        "INSERT INTO boards (user_id, title) VALUES (?, 'Legacy board')",
        (legacy_user_id,),
    ).lastrowid
    legacy_column_id = legacy_connection.execute(
        "INSERT INTO board_columns (board_id, title, position) VALUES (?, 'Backlog', 0)",
        (legacy_board_id,),
    ).lastrowid
    legacy_connection.execute(
        "INSERT INTO cards (column_id, title, position) VALUES (?, 'Legacy card', 0)",
        (legacy_column_id,),
    )
    legacy_connection.execute(
        "INSERT INTO chat_messages (board_id, role, content) VALUES (?, 'user', 'hi')",
        (legacy_board_id,),
    )
    legacy_connection.execute("PRAGMA user_version = 1")
    legacy_connection.commit()
    legacy_connection.close()

    initialize_database()

    with connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        preserved = connection.execute(
            "SELECT user_id, title FROM boards WHERE id = ?", (legacy_board_id,)
        ).fetchone()
        preserved_card = connection.execute(
            "SELECT title FROM cards WHERE column_id = ?", (legacy_column_id,)
        ).fetchone()
        preserved_message = connection.execute(
            "SELECT content FROM chat_messages WHERE board_id = ?", (legacy_board_id,)
        ).fetchone()
        connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, 'Second board')",
            (legacy_user_id,),
        )
        board_count = connection.execute(
            "SELECT COUNT(*) FROM boards WHERE user_id = ?", (legacy_user_id,)
        ).fetchone()[0]
        # Foreign keys must still resolve correctly for the pre-existing
        # child rows after boards is dropped and recreated during migration.
        connection.execute(
            "INSERT INTO board_columns (board_id, title, position) VALUES (?, 'Extra', 1)",
            (legacy_board_id,),
        )

    assert version == SCHEMA_VERSION
    assert preserved["user_id"] == legacy_user_id
    assert preserved["title"] == "Legacy board"
    assert preserved_card["title"] == "Legacy card"
    assert preserved_message["content"] == "hi"
    assert board_count == 2


def test_foreign_keys_cascade_owned_data(client: TestClient) -> None:
    with connect() as connection:
        user_id = connection.execute(
            "SELECT id FROM users WHERE username = 'user'"
        ).fetchone()["id"]
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))

        counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("boards", "board_columns", "cards")
        )

    assert counts == (0, 0, 0)
