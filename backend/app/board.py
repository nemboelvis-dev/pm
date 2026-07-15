import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth import User, authenticated_user
from app.database import connect


router = APIRouter(prefix="/api", tags=["board"])


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cardIds: list[str]


class Board(BaseModel):
    id: str
    title: str
    columns: list[Column]
    cards: dict[str, Card]


class RenameColumn(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title must not be blank")
        return title


class CreateCard(BaseModel):
    column_id: int
    title: str
    details: str = ""

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Title must not be blank")
        return title

    @field_validator("details")
    @classmethod
    def trim_details(cls, value: str) -> str:
        return value.strip()


class EditCard(BaseModel):
    title: str | None = None
    details: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title:
            raise ValueError("Title must not be blank")
        return title

    @field_validator("details")
    @classmethod
    def trim_details(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "EditCard":
        if self.title is None and self.details is None:
            raise ValueError("At least one field is required")
        return self


class MoveCard(BaseModel):
    column_id: int
    position: int = Field(ge=0)


@router.get("/board", response_model=Board)
def get_board(user: User = Depends(authenticated_user)) -> Board:
    with connect() as connection:
        return read_board(connection, user.username)


@router.patch("/columns/{column_id}", response_model=Board)
def rename_column(
    column_id: int,
    update: RenameColumn,
    user: User = Depends(authenticated_user),
) -> Board:
    with connect() as connection:
        board_id = board_id_for_user(connection, user.username)
        result = connection.execute(
            """
            UPDATE board_columns
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND board_id = ?
            """,
            (update.title, column_id, board_id),
        )
        if not result.rowcount:
            _not_found("Column")
        _touch_board(connection, board_id)
        return read_board(connection, user.username)


@router.post("/cards", response_model=Board, status_code=status.HTTP_201_CREATED)
def create_card(
    card: CreateCard,
    user: User = Depends(authenticated_user),
) -> Board:
    with connect() as connection:
        board_id = board_id_for_user(connection, user.username)
        create_card_record(connection, board_id, card)
        return read_board(connection, user.username)


@router.patch("/cards/{card_id}", response_model=Board)
def edit_card(
    card_id: int,
    update: EditCard,
    user: User = Depends(authenticated_user),
) -> Board:
    with connect() as connection:
        board_id = board_id_for_user(connection, user.username)
        edit_card_record(connection, board_id, card_id, update)
        return read_board(connection, user.username)


@router.delete("/cards/{card_id}", response_model=Board)
def delete_card(
    card_id: int,
    user: User = Depends(authenticated_user),
) -> Board:
    with connect() as connection:
        board_id = board_id_for_user(connection, user.username)
        card = _owned_card(connection, board_id, card_id)
        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        remaining_ids = _card_ids(connection, card["column_id"])
        _rewrite_positions(connection, card["column_id"], remaining_ids)
        _touch_board(connection, board_id)
        return read_board(connection, user.username)


@router.post("/cards/{card_id}/move", response_model=Board)
def move_card(
    card_id: int,
    move: MoveCard,
    user: User = Depends(authenticated_user),
) -> Board:
    with connect() as connection:
        board_id = board_id_for_user(connection, user.username)
        move_card_record(connection, board_id, card_id, move)
        return read_board(connection, user.username)


def create_card_record(
    connection: sqlite3.Connection, board_id: int, card: CreateCard
) -> None:
    _owned_column(connection, board_id, card.column_id)
    position = connection.execute(
        "SELECT COUNT(*) AS count FROM cards WHERE column_id = ?",
        (card.column_id,),
    ).fetchone()["count"]
    connection.execute(
        """
        INSERT INTO cards (column_id, title, details, position)
        VALUES (?, ?, ?, ?)
        """,
        (card.column_id, card.title, card.details, position),
    )
    _touch_board(connection, board_id)


def edit_card_record(
    connection: sqlite3.Connection,
    board_id: int,
    card_id: int,
    update: EditCard,
) -> None:
    _owned_card(connection, board_id, card_id)
    fields: list[str] = []
    values: list[str | int] = []
    if update.title is not None:
        fields.append("title = ?")
        values.append(update.title)
    if update.details is not None:
        fields.append("details = ?")
        values.append(update.details)
    values.append(card_id)
    connection.execute(
        f"""
        UPDATE cards
        SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        values,
    )
    _touch_board(connection, board_id)


def move_card_record(
    connection: sqlite3.Connection,
    board_id: int,
    card_id: int,
    move: MoveCard,
) -> None:
    card = _owned_card(connection, board_id, card_id)
    _owned_column(connection, board_id, move.column_id)
    source_column_id = card["column_id"]

    if source_column_id == move.column_id:
        card_ids = [
            item for item in _card_ids(connection, source_column_id) if item != card_id
        ]
        _validate_position(move.position, len(card_ids))
        card_ids.insert(move.position, card_id)
        _rewrite_positions(connection, source_column_id, card_ids)
    else:
        source_ids = [
            item for item in _card_ids(connection, source_column_id) if item != card_id
        ]
        target_ids = _card_ids(connection, move.column_id)
        _validate_position(move.position, len(target_ids))
        target_ids.insert(move.position, card_id)

        temporary_position = len(target_ids) - 1
        connection.execute(
            "UPDATE cards SET column_id = ?, position = ? WHERE id = ?",
            (move.column_id, temporary_position, card_id),
        )
        _rewrite_positions(connection, source_column_id, source_ids)
        _rewrite_positions(connection, move.column_id, target_ids)

    _touch_board(connection, board_id)


def read_board(connection: sqlite3.Connection, username: str) -> Board:
    board = connection.execute(
        """
        SELECT boards.id, boards.title
        FROM boards
        JOIN users ON users.id = boards.user_id
        WHERE users.username = ?
        """,
        (username,),
    ).fetchone()
    if not board:
        _not_found("Board")

    columns: list[Column] = []
    cards: dict[str, Card] = {}
    for column in connection.execute(
        """
        SELECT id, title FROM board_columns
        WHERE board_id = ?
        ORDER BY position
        """,
        (board["id"],),
    ):
        card_ids: list[str] = []
        for card in connection.execute(
            """
            SELECT id, title, details FROM cards
            WHERE column_id = ?
            ORDER BY position
            """,
            (column["id"],),
        ):
            card_id = str(card["id"])
            card_ids.append(card_id)
            cards[card_id] = Card(
                id=card_id,
                title=card["title"],
                details=card["details"],
            )
        columns.append(
            Column(id=str(column["id"]), title=column["title"], cardIds=card_ids)
        )

    return Board(
        id=str(board["id"]),
        title=board["title"],
        columns=columns,
        cards=cards,
    )


def board_id_for_user(connection: sqlite3.Connection, username: str) -> int:
    row = connection.execute(
        """
        SELECT boards.id FROM boards
        JOIN users ON users.id = boards.user_id
        WHERE users.username = ?
        """,
        (username,),
    ).fetchone()
    if not row:
        _not_found("Board")
    return row["id"]


def _owned_column(
    connection: sqlite3.Connection, board_id: int, column_id: int
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM board_columns WHERE id = ? AND board_id = ?",
        (column_id, board_id),
    ).fetchone()
    if not row:
        _not_found("Column")
    return row


def _owned_card(
    connection: sqlite3.Connection, board_id: int, card_id: int
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT cards.* FROM cards
        JOIN board_columns ON board_columns.id = cards.column_id
        WHERE cards.id = ? AND board_columns.board_id = ?
        """,
        (card_id, board_id),
    ).fetchone()
    if not row:
        _not_found("Card")
    return row


def _card_ids(connection: sqlite3.Connection, column_id: int) -> list[int]:
    return [
        row["id"]
        for row in connection.execute(
            "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
            (column_id,),
        )
    ]


def _rewrite_positions(
    connection: sqlite3.Connection, column_id: int, card_ids: list[int]
) -> None:
    row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) AS maximum FROM cards WHERE column_id = ?",
        (column_id,),
    ).fetchone()
    offset = row["maximum"] + 1
    if card_ids:
        connection.execute(
            """
            UPDATE cards
            SET position = position + ?, updated_at = CURRENT_TIMESTAMP
            WHERE column_id = ?
            """,
            (offset, column_id),
        )
        for position, card_id in enumerate(card_ids):
            connection.execute(
                """
                UPDATE cards
                SET position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (position, card_id),
            )


def _touch_board(connection: sqlite3.Connection, board_id: int) -> None:
    connection.execute(
        "UPDATE boards SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (board_id,)
    )


def _validate_position(position: int, maximum: int) -> None:
    if position > maximum:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Position must be between 0 and {maximum}",
        )


def _not_found(resource: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found",
    )
