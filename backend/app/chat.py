import json
import sqlite3
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from app.auth import User, authenticated_user
from app.board import (
    Board,
    CreateCard,
    EditCard,
    MoveCard,
    board_id_for_user,
    create_card_record,
    edit_card_record,
    move_card_record,
    read_board,
)
from app.database import connect
from app.openrouter import (
    OpenRouterConfigurationError,
    OpenRouterRequestError,
    create_completion,
)


router = APIRouter(prefix="/api/chat", tags=["chat"])
PROMPT_HISTORY_LIMIT = 50

SYSTEM_PROMPT = """You are the board assistant for a project management app.
Use the current board IDs exactly as provided. Card and column IDs are numeric strings;
return them as integers in operations. You may create, edit, or move cards. You cannot
delete cards, rename columns, or invent IDs for existing resources. Positions are
zero-based. Return an empty operations array when no board change is needed."""


class SendMessage(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("Message must not be blank")
        return message


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class CardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["create", "edit", "move"] = Field(
        description="The card operation to apply."
    )
    card_id: int | None = Field(
        gt=0, description="Existing card ID for edit or move; otherwise null."
    )
    column_id: int | None = Field(
        gt=0, description="Target column ID for create or move; otherwise null."
    )
    position: int | None = Field(
        ge=0, description="Zero-based target position for move; otherwise null."
    )
    title: str | None = Field(
        description="Card title for create, changed title for edit, or null."
    )
    details: str | None = Field(
        description="Card details for create, changed details for edit, or null."
    )

    @model_validator(mode="after")
    def fields_match_operation(self) -> "CardOperation":
        if self.type == "create":
            valid = (
                self.card_id is None
                and self.column_id is not None
                and self.position is None
                and self.title is not None
                and bool(self.title.strip())
                and self.details is not None
            )
        elif self.type == "edit":
            valid = (
                self.card_id is not None
                and self.column_id is None
                and self.position is None
                and (self.title is not None or self.details is not None)
                and (self.title is None or bool(self.title.strip()))
            )
        else:
            valid = (
                self.card_id is not None
                and self.column_id is not None
                and self.position is not None
                and self.title is None
                and self.details is None
            )
        if not valid:
            raise ValueError(f"Fields do not match the {self.type} operation")
        return self


class AiBoardUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(description="A concise response to show the user.")
    operations: list[CardOperation] = Field(
        description="Card changes to apply in order."
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        message = value.strip()
        if not message:
            raise ValueError("Message must not be blank")
        return message


class ChatResponse(BaseModel):
    user_message: ChatMessage
    message: ChatMessage
    board: Board


AI_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "board_update",
        "strict": True,
        "schema": AiBoardUpdate.model_json_schema(),
    },
}


@router.get("", response_model=list[ChatMessage])
def history(user: User = Depends(authenticated_user)) -> list[ChatMessage]:
    with connect() as connection:
        return _read_messages(
            connection, board_id_for_user(connection, user.username)
        )


@router.post("", response_model=ChatResponse)
async def send_message(
    request: SendMessage,
    user: User = Depends(authenticated_user),
) -> ChatResponse:
    with connect() as connection:
        board = read_board(connection, user.username)
        previous_messages = _read_messages(
            connection,
            board_id_for_user(connection, user.username),
            limit=PROMPT_HISTORY_LIMIT,
        )

    messages = [
        {
            "role": "system",
            "content": (
                f"{SYSTEM_PROMPT}\n\nCurrent board JSON:\n"
                f"{json.dumps(board.model_dump(mode='json'), separators=(',', ':'))}"
            ),
        },
        *[
            {"role": message.role, "content": message.content}
            for message in previous_messages
        ],
        {"role": "user", "content": request.message},
    ]

    try:
        completion = await create_completion(
            messages,
            response_format=AI_RESPONSE_FORMAT,
            max_tokens=1000,
        )
        update = AiBoardUpdate.model_validate_json(completion)
    except OpenRouterConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except OpenRouterRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter returned an invalid board update",
        ) from error

    with connect() as connection:
        board_id = board_id_for_user(connection, user.username)
        user_message = _insert_message(
            connection, board_id, "user", request.message
        )
        try:
            for index, operation in enumerate(update.operations):
                _apply_operation(connection, board_id, operation)
        except HTTPException as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"AI operation {index + 1} is invalid: {error.detail}",
            ) from error
        assistant_message = _insert_message(
            connection, board_id, "assistant", update.message
        )
        refreshed_board = read_board(connection, user.username)

    return ChatResponse(
        user_message=user_message,
        message=assistant_message,
        board=refreshed_board,
    )


def _apply_operation(
    connection: sqlite3.Connection, board_id: int, operation: CardOperation
) -> None:
    if operation.type == "create":
        create_card_record(
            connection,
            board_id,
            CreateCard(
                column_id=cast(int, operation.column_id),
                title=cast(str, operation.title),
                details=cast(str, operation.details),
            ),
        )
    elif operation.type == "edit":
        edit_card_record(
            connection,
            board_id,
            cast(int, operation.card_id),
            EditCard(title=operation.title, details=operation.details),
        )
    else:
        move_card_record(
            connection,
            board_id,
            cast(int, operation.card_id),
            MoveCard(
                column_id=cast(int, operation.column_id),
                position=cast(int, operation.position),
            ),
        )


def _read_messages(
    connection: sqlite3.Connection,
    board_id: int,
    limit: int | None = None,
) -> list[ChatMessage]:
    if limit is None:
        rows = connection.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE board_id = ?
            ORDER BY id
            """,
            (board_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE board_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (board_id, limit),
        ).fetchall()
        rows.reverse()
    return [_row_to_message(row) for row in rows]


def _insert_message(
    connection: sqlite3.Connection,
    board_id: int,
    role: Literal["user", "assistant"],
    content: str,
) -> ChatMessage:
    message_id = connection.execute(
        "INSERT INTO chat_messages (board_id, role, content) VALUES (?, ?, ?)",
        (board_id, role, content),
    ).lastrowid
    row = connection.execute(
        """
        SELECT id, role, content, created_at
        FROM chat_messages
        WHERE id = ?
        """,
        (message_id,),
    ).fetchone()
    return _row_to_message(row)


def _row_to_message(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=str(row["id"]),
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
    )
