from fastapi.testclient import TestClient

from app.database import connect


def board(client: TestClient, board_id: int) -> dict:
    response = client.get(f"/api/boards/{board_id}")
    assert response.status_code == 200
    return response.json()


def test_board_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/boards").status_code == 401
    assert client.post("/api/boards", json={"title": "New"}).status_code == 401
    assert client.get("/api/boards/1").status_code == 401
    assert client.patch("/api/boards/1", json={"title": "New"}).status_code == 401
    assert client.delete("/api/boards/1").status_code == 401
    assert (
        client.patch("/api/boards/1/columns/1", json={"title": "Ideas"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/boards/1/cards",
            json={"column_id": 1, "title": "Card"},
        ).status_code
        == 401
    )
    assert (
        client.patch("/api/boards/1/cards/1", json={"title": "Edit"}).status_code
        == 401
    )
    assert client.delete("/api/boards/1/cards/1").status_code == 401
    assert (
        client.post(
            "/api/boards/1/cards/1/move", json={"column_id": 1, "position": 0}
        ).status_code
        == 401
    )


def test_reads_seeded_board(authenticated_client: TestClient, board_id: int) -> None:
    data = board(authenticated_client, board_id)

    assert data["title"] == "Kanban Studio"
    assert [column["title"] for column in data["columns"]] == [
        "Backlog",
        "Discovery",
        "In Progress",
        "Review",
        "Done",
    ]
    assert len(data["cards"]) == 8
    assert sum(len(column["cardIds"]) for column in data["columns"]) == 8


def test_lists_boards_for_the_current_user(
    authenticated_client: TestClient, board_id: int
) -> None:
    response = authenticated_client.get("/api/boards")

    assert response.status_code == 200
    summaries = response.json()
    assert len(summaries) == 1
    assert summaries[0]["id"] == str(board_id)
    assert summaries[0]["title"] == "Kanban Studio"
    assert "created_at" in summaries[0]
    assert "updated_at" in summaries[0]


def test_creates_a_second_board_with_default_columns(
    authenticated_client: TestClient, board_id: int
) -> None:
    response = authenticated_client.post("/api/boards", json={"title": "  Sprint 2  "})

    assert response.status_code == 201
    created = response.json()
    assert created["title"] == "Sprint 2"
    assert created["id"] != str(board_id)
    assert [column["title"] for column in created["columns"]] == [
        "Backlog",
        "Discovery",
        "In Progress",
        "Review",
        "Done",
    ]
    assert created["cards"] == {}

    listing = authenticated_client.get("/api/boards").json()
    assert {summary["id"] for summary in listing} == {str(board_id), created["id"]}
    assert len(listing) == 2


def test_rejects_a_blank_board_title(
    authenticated_client: TestClient, board_id: int
) -> None:
    assert (
        authenticated_client.post("/api/boards", json={"title": "   "}).status_code
        == 422
    )
    assert (
        authenticated_client.patch(
            f"/api/boards/{board_id}", json={"title": "   "}
        ).status_code
        == 422
    )


def test_renames_a_board(authenticated_client: TestClient, board_id: int) -> None:
    response = authenticated_client.patch(
        f"/api/boards/{board_id}", json={"title": "  Renamed  "}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert board(authenticated_client, board_id)["title"] == "Renamed"


def test_deletes_a_board_and_cascades(
    authenticated_client: TestClient, board_id: int
) -> None:
    response = authenticated_client.delete(f"/api/boards/{board_id}")

    assert response.status_code == 204
    assert authenticated_client.get(f"/api/boards/{board_id}").status_code == 404
    assert authenticated_client.get("/api/boards").json() == []
    with connect() as connection:
        column_count = connection.execute(
            "SELECT COUNT(*) FROM board_columns WHERE board_id = ?", (board_id,)
        ).fetchone()[0]
    assert column_count == 0


def test_missing_board_returns_404(authenticated_client: TestClient) -> None:
    assert authenticated_client.get("/api/boards/99999").status_code == 404
    assert (
        authenticated_client.patch(
            "/api/boards/99999", json={"title": "Ideas"}
        ).status_code
        == 404
    )
    assert authenticated_client.delete("/api/boards/99999").status_code == 404


def test_renames_a_column_and_persists_it(
    authenticated_client: TestClient, board_id: int
) -> None:
    column_id = board(authenticated_client, board_id)["columns"][0]["id"]

    response = authenticated_client.patch(
        f"/api/boards/{board_id}/columns/{column_id}", json={"title": "  Ideas  "}
    )

    assert response.status_code == 200
    assert response.json()["columns"][0]["title"] == "Ideas"
    assert board(authenticated_client, board_id)["columns"][0]["title"] == "Ideas"


def test_column_validation_and_ownership(
    authenticated_client: TestClient, board_id: int
) -> None:
    column_id = board(authenticated_client, board_id)["columns"][0]["id"]

    assert (
        authenticated_client.patch(
            f"/api/boards/{board_id}/columns/{column_id}", json={"title": "   "}
        ).status_code
        == 422
    )
    assert (
        authenticated_client.patch(
            f"/api/boards/{board_id}/columns/99999", json={"title": "Ideas"}
        ).status_code
        == 404
    )


def test_creates_and_edits_a_card(
    authenticated_client: TestClient, board_id: int
) -> None:
    column_id = board(authenticated_client, board_id)["columns"][0]["id"]

    created = authenticated_client.post(
        f"/api/boards/{board_id}/cards",
        json={
            "column_id": column_id,
            "title": "  New card  ",
            "details": "  Initial details  ",
        },
    )
    assert created.status_code == 201
    created_board = created.json()
    card_id = created_board["columns"][0]["cardIds"][-1]
    assert created_board["cards"][card_id]["title"] == "New card"
    assert created_board["cards"][card_id]["details"] == "Initial details"

    edited = authenticated_client.patch(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Updated", "details": "Changed"},
    )
    assert edited.status_code == 200
    assert edited.json()["cards"][card_id] == {
        "id": card_id,
        "title": "Updated",
        "details": "Changed",
    }
    assert board(authenticated_client, board_id)["cards"][card_id]["title"] == "Updated"


def test_card_validation_and_unknown_resources(
    authenticated_client: TestClient, board_id: int
) -> None:
    assert (
        authenticated_client.post(
            f"/api/boards/{board_id}/cards",
            json={"column_id": 99999, "title": "Card"},
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{board_id}/cards", json={"column_id": 1, "title": " "}
        ).status_code
        == 422
    )
    assert (
        authenticated_client.patch(
            f"/api/boards/{board_id}/cards/1", json={}
        ).status_code
        == 422
    )
    assert (
        authenticated_client.patch(
            f"/api/boards/{board_id}/cards/1", json={"title": " "}
        ).status_code
        == 422
    )
    assert (
        authenticated_client.patch(
            f"/api/boards/{board_id}/cards/99999", json={"title": "Missing"}
        ).status_code
        == 404
    )
    assert (
        authenticated_client.delete(f"/api/boards/{board_id}/cards/99999").status_code
        == 404
    )


def test_deletes_a_card_and_closes_the_position_gap(
    authenticated_client: TestClient, board_id: int
) -> None:
    initial = board(authenticated_client, board_id)
    column = initial["columns"][0]
    deleted_id = column["cardIds"][0]

    response = authenticated_client.delete(
        f"/api/boards/{board_id}/cards/{deleted_id}"
    )

    assert response.status_code == 200
    assert deleted_id not in response.json()["cards"]
    assert response.json()["columns"][0]["cardIds"] == column["cardIds"][1:]
    with connect() as connection:
        positions = [
            row["position"]
            for row in connection.execute(
                "SELECT position FROM cards WHERE column_id = ? ORDER BY position",
                (int(column["id"]),),
            )
        ]
    assert positions == list(range(len(positions)))


def test_reorders_a_card_within_its_column(
    authenticated_client: TestClient, board_id: int
) -> None:
    initial = board(authenticated_client, board_id)
    column = initial["columns"][0]
    moved_id = column["cardIds"][1]

    response = authenticated_client.post(
        f"/api/boards/{board_id}/cards/{moved_id}/move",
        json={"column_id": column["id"], "position": 0},
    )

    assert response.status_code == 200
    assert response.json()["columns"][0]["cardIds"] == [
        moved_id,
        column["cardIds"][0],
    ]


def test_moves_a_card_between_columns(
    authenticated_client: TestClient, board_id: int
) -> None:
    initial = board(authenticated_client, board_id)
    source = initial["columns"][0]
    target = initial["columns"][3]
    moved_id = source["cardIds"][0]

    response = authenticated_client.post(
        f"/api/boards/{board_id}/cards/{moved_id}/move",
        json={"column_id": target["id"], "position": 0},
    )

    assert response.status_code == 200
    result = response.json()
    assert moved_id not in result["columns"][0]["cardIds"]
    assert result["columns"][3]["cardIds"][0] == moved_id
    with connect() as connection:
        for column_id in (source["id"], target["id"]):
            positions = [
                row["position"]
                for row in connection.execute(
                    "SELECT position FROM cards WHERE column_id = ? ORDER BY position",
                    (int(column_id),),
                )
            ]
            assert positions == list(range(len(positions)))


def test_rejects_an_out_of_range_move(
    authenticated_client: TestClient, board_id: int
) -> None:
    initial = board(authenticated_client, board_id)
    card_id = initial["columns"][0]["cardIds"][0]

    response = authenticated_client.post(
        f"/api/boards/{board_id}/cards/{card_id}/move",
        json={"column_id": initial["columns"][0]["id"], "position": 99},
    )

    assert response.status_code == 422
    assert board(authenticated_client, board_id) == initial

    assert (
        authenticated_client.post(
            f"/api/boards/{board_id}/cards/{card_id}/move",
            json={"column_id": initial["columns"][0]["id"], "position": -1},
        ).status_code
        == 422
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{board_id}/cards/{card_id}/move",
            json={"column_id": 99999, "position": 0},
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{board_id}/cards/99999/move",
            json={"column_id": initial["columns"][0]["id"], "position": 0},
        ).status_code
        == 404
    )


def test_cannot_access_another_users_resources(
    authenticated_client: TestClient, board_id: int
) -> None:
    own_card_id = board(authenticated_client, board_id)["columns"][0]["cardIds"][0]
    with connect() as connection:
        other_user_id = connection.execute(
            "INSERT INTO users (username, password_hash) VALUES ('other', 'hash')"
        ).lastrowid
        other_board_id = connection.execute(
            "INSERT INTO boards (user_id, title) VALUES (?, 'Other')",
            (other_user_id,),
        ).lastrowid
        column_id = connection.execute(
            """
            INSERT INTO board_columns (board_id, title, position)
            VALUES (?, 'Private', 0)
            """,
            (other_board_id,),
        ).lastrowid
        card_id = connection.execute(
            """
            INSERT INTO cards (column_id, title, position)
            VALUES (?, 'Private card', 0)
            """,
            (column_id,),
        ).lastrowid

    assert authenticated_client.get(f"/api/boards/{other_board_id}").status_code == 404
    assert (
        authenticated_client.patch(
            f"/api/boards/{other_board_id}", json={"title": "Stolen"}
        ).status_code
        == 404
    )
    assert authenticated_client.delete(f"/api/boards/{other_board_id}").status_code == 404
    assert (
        authenticated_client.patch(
            f"/api/boards/{other_board_id}/columns/{column_id}",
            json={"title": "Stolen"},
        ).status_code
        == 404
    )
    assert (
        authenticated_client.patch(
            f"/api/boards/{other_board_id}/cards/{card_id}", json={"title": "Stolen"}
        ).status_code
        == 404
    )
    assert (
        authenticated_client.delete(
            f"/api/boards/{other_board_id}/cards/{card_id}"
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{other_board_id}/cards",
            json={"column_id": column_id, "title": "Stolen"},
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{other_board_id}/cards/{own_card_id}/move",
            json={"column_id": column_id, "position": 0},
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{board_id}/cards/{card_id}/move",
            json={"column_id": 1, "position": 0},
        ).status_code
        == 404
    )


def test_cannot_cross_reference_own_boards(
    authenticated_client: TestClient, board_id: int
) -> None:
    second_board = authenticated_client.post(
        "/api/boards", json={"title": "Second"}
    ).json()
    second_board_id = int(second_board["id"])
    own_column_id = board(authenticated_client, board_id)["columns"][0]["id"]

    assert (
        authenticated_client.patch(
            f"/api/boards/{second_board_id}/columns/{own_column_id}",
            json={"title": "Wrong board"},
        ).status_code
        == 404
    )
    assert (
        authenticated_client.post(
            f"/api/boards/{second_board_id}/cards",
            json={"column_id": own_column_id, "title": "Wrong board card"},
        ).status_code
        == 404
    )
