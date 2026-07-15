import sqlite3

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


def test_schema_supports_multiple_users_but_one_board_each(
    client: TestClient,
) -> None:
    with connect() as connection:
        user_id = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES ('second', 'hash')"
        ).lastrowid
        connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, 'Second board')",
            (user_id,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO boards (user_id, title) VALUES (?, 'Duplicate')",
                (user_id,),
            )


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
