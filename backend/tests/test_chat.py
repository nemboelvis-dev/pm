import json

import pytest
from fastapi.testclient import TestClient

from app import chat
from app.database import connect


def ai_response(message: str, operations: list[dict] | None = None) -> str:
    return json.dumps({"message": message, "operations": operations or []})


def test_chat_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/chat").status_code == 401
    assert client.post("/api/chat", json={"message": "Hello"}).status_code == 401


def test_chat_rejects_a_blank_message(authenticated_client: TestClient) -> None:
    response = authenticated_client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_sends_board_scoped_history_and_strict_schema(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with connect() as connection:
        board_id = connection.execute(
            """
            SELECT boards.id FROM boards
            JOIN users ON users.id = boards.user_id
            WHERE users.username = 'user'
            """
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO chat_messages (board_id, role, content) VALUES (?, 'user', ?)",
            (board_id, "Earlier question"),
        )
        connection.execute(
            """
            INSERT INTO chat_messages (board_id, role, content)
            VALUES (?, 'assistant', ?)
            """,
            (board_id, "Earlier answer"),
        )
        other_user_id = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES ('other', 'hash')"
        ).lastrowid
        other_board_id = connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, 'Private')",
            (other_user_id,),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO chat_messages (board_id, role, content)
            VALUES (?, 'user', 'Other user secret')
            """,
            (other_board_id,),
        )

    captured: dict[str, object] = {}

    async def fake_completion(
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, object],
        max_tokens: int,
    ) -> str:
        captured.update(
            messages=messages,
            response_format=response_format,
            max_tokens=max_tokens,
        )
        return ai_response("No changes needed.")

    monkeypatch.setattr(chat, "create_completion", fake_completion)
    board_before = authenticated_client.get("/api/board").json()

    response = authenticated_client.post(
        "/api/chat", json={"message": "What should I do next?"}
    )

    assert response.status_code == 200
    assert response.json()["user_message"]["content"] == "What should I do next?"
    assert response.json()["user_message"]["role"] == "user"
    assert response.json()["message"]["content"] == "No changes needed."
    assert response.json()["board"] == board_before

    messages = captured["messages"]
    assert isinstance(messages, list)
    assert [message["role"] for message in messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert [message["content"] for message in messages[1:]] == [
        "Earlier question",
        "Earlier answer",
        "What should I do next?",
    ]
    assert "Other user secret" not in json.dumps(messages)
    board_json = messages[0]["content"].split("Current board JSON:\n", 1)[1]
    assert json.loads(board_json) == board_before

    response_format = captured["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    json_schema = response_format["json_schema"]
    assert isinstance(json_schema, dict)
    assert json_schema["strict"] is True
    schema = json_schema["schema"]
    assert isinstance(schema, dict)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"message", "operations"}
    operation_schema = schema["$defs"]["CardOperation"]
    assert operation_schema["additionalProperties"] is False
    assert operation_schema["properties"]["type"]["enum"] == [
        "create",
        "edit",
        "move",
        "delete",
    ]
    assert set(operation_schema["required"]) == {
        "type",
        "card_id",
        "column_id",
        "position",
        "title",
        "details",
    }
    assert captured["max_tokens"] == 1000

    history = authenticated_client.get("/api/chat").json()
    assert [(message["role"], message["content"]) for message in history] == [
        ("user", "Earlier question"),
        ("assistant", "Earlier answer"),
        ("user", "What should I do next?"),
        ("assistant", "No changes needed."),
    ]


def test_chat_applies_multiple_card_operations_and_returns_the_board(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_before = authenticated_client.get("/api/board").json()
    first_column = board_before["columns"][0]
    target_column = board_before["columns"][1]
    card_id = int(first_column["cardIds"][0])

    async def fake_completion(*_: object, **__: object) -> str:
        return ai_response(
            "Created, edited, and moved the cards.",
            [
                {
                    "type": "create",
                    "card_id": None,
                    "column_id": int(first_column["id"]),
                    "position": None,
                    "title": "AI-created card",
                    "details": "Created from chat.",
                },
                {
                    "type": "edit",
                    "card_id": card_id,
                    "column_id": None,
                    "position": None,
                    "title": "AI-edited card",
                    "details": "Edited from chat.",
                },
                {
                    "type": "move",
                    "card_id": card_id,
                    "column_id": int(target_column["id"]),
                    "position": 0,
                    "title": None,
                    "details": None,
                },
            ],
        )

    monkeypatch.setattr(chat, "create_completion", fake_completion)

    response = authenticated_client.post(
        "/api/chat", json={"message": "Update my board"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"]["role"] == "assistant"
    assert data["user_message"]["content"] == "Update my board"
    assert data["message"]["content"] == "Created, edited, and moved the cards."
    assert data["board"]["cards"][str(card_id)] == {
        "id": str(card_id),
        "title": "AI-edited card",
        "details": "Edited from chat.",
    }
    assert data["board"]["columns"][1]["cardIds"][0] == str(card_id)
    assert any(
        card["title"] == "AI-created card"
        for card in data["board"]["cards"].values()
    )
    assert authenticated_client.get("/api/board").json() == data["board"]

    history = authenticated_client.get("/api/chat").json()
    assert [(message["role"], message["content"]) for message in history] == [
        ("user", "Update my board"),
        ("assistant", "Created, edited, and moved the cards."),
    ]


def test_chat_deletes_and_moves_cards_when_requested(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial_board = authenticated_client.get("/api/board").json()
    backlog = initial_board["columns"][0]
    create_response = authenticated_client.post(
        "/api/cards",
        json={
            "column_id": int(backlog["id"]),
            "title": "test",
            "details": "Delete through the assistant.",
        },
    )
    assert create_response.status_code == 201
    created_board = create_response.json()
    test_card_id = next(
        card_id
        for card_id, card in created_board["cards"].items()
        if card["title"] == "test"
    )

    board_before = created_board
    source_column = board_before["columns"][2]
    target_column = board_before["columns"][3]
    moved_card_id = next(
        card_id
        for card_id in source_column["cardIds"]
        if board_before["cards"][card_id]["title"] == "Design card layout"
    )
    moved_card = board_before["cards"][moved_card_id]

    async def fake_completion(*_: object, **__: object) -> str:
        return ai_response(
            "I deleted test and moved Design card layout to Review.",
            [
                {
                    "type": "delete",
                    "card_id": int(test_card_id),
                    "column_id": int(backlog["id"]),
                    "position": len(backlog["cardIds"]),
                    "title": "test",
                    "details": "Delete through the assistant.",
                },
                {
                    "type": "move",
                    "card_id": int(moved_card_id),
                    "column_id": int(target_column["id"]),
                    "position": len(target_column["cardIds"]),
                    "title": moved_card["title"],
                    "details": moved_card["details"],
                }
            ],
        )

    monkeypatch.setattr(chat, "create_completion", fake_completion)

    response = authenticated_client.post(
        "/api/chat",
        json={
            "message": (
                'Delete card "test" from Backlog. Move "Design card layout" '
                'from "In Progress" to "Review".'
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert test_card_id not in data["board"]["cards"]
    assert all(
        test_card_id not in column["cardIds"] for column in data["board"]["columns"]
    )
    assert moved_card_id not in data["board"]["columns"][2]["cardIds"]
    assert data["board"]["columns"][3]["cardIds"][-1] == moved_card_id
    assert data["board"]["cards"][moved_card_id] == moved_card


def test_invalid_ai_operation_rolls_back_all_changes_and_messages(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    board_before = authenticated_client.get("/api/board").json()
    column_id = int(board_before["columns"][0]["id"])

    async def fake_completion(*_: object, **__: object) -> str:
        return ai_response(
            "This must roll back.",
            [
                {
                    "type": "create",
                    "card_id": None,
                    "column_id": column_id,
                    "position": None,
                    "title": "Rolled-back card",
                    "details": "This should not persist.",
                },
                {
                    "type": "edit",
                    "card_id": 999999,
                    "column_id": None,
                    "position": None,
                    "title": "Missing",
                    "details": None,
                },
            ],
        )

    monkeypatch.setattr(chat, "create_completion", fake_completion)

    response = authenticated_client.post(
        "/api/chat", json={"message": "Apply an invalid update"}
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "AI operation 2 is invalid: Card not found"
    }
    assert authenticated_client.get("/api/board").json() == board_before
    assert authenticated_client.get("/api/chat").json() == []


def test_invalid_structured_response_is_rejected_without_saving_history(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_completion(*_: object, **__: object) -> str:
        return '{"message":"Missing operations"}'

    monkeypatch.setattr(chat, "create_completion", fake_completion)

    response = authenticated_client.post(
        "/api/chat", json={"message": "Invalid model response"}
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "OpenRouter returned an invalid board update"
    }
    assert authenticated_client.get("/api/chat").json() == []


def test_chat_reports_missing_openrouter_configuration(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    response = authenticated_client.post(
        "/api/chat", json={"message": "Help with the board"}
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "OPENROUTER_API_KEY is not configured on the server"
    }
    assert authenticated_client.get("/api/chat").json() == []


def test_chat_caps_history_sent_to_openrouter(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with connect() as connection:
        board_id = connection.execute("SELECT id FROM boards").fetchone()["id"]
        for index in range(55):
            connection.execute(
                """
                INSERT INTO chat_messages (board_id, role, content)
                VALUES (?, ?, ?)
                """,
                (
                    board_id,
                    "user" if index % 2 == 0 else "assistant",
                    f"History {index}",
                ),
            )

    captured_messages: list[dict[str, str]] = []

    async def fake_completion(
        messages: list[dict[str, str]], **_: object
    ) -> str:
        captured_messages.extend(messages)
        return ai_response("History was capped.")

    monkeypatch.setattr(chat, "create_completion", fake_completion)

    response = authenticated_client.post(
        "/api/chat", json={"message": "Newest request"}
    )

    assert response.status_code == 200
    assert len(captured_messages) == chat.PROMPT_HISTORY_LIMIT + 2
    assert captured_messages[1]["content"] == "History 5"
    assert captured_messages[-2]["content"] == "History 54"
    assert captured_messages[-1] == {"role": "user", "content": "Newest request"}
    assert len(authenticated_client.get("/api/chat").json()) == 57
