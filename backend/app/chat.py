import json
import logging
import sqlite3
from typing import Annotated, Literal

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
    delete_card_record,
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
MAX_BOARD_UPDATE_ATTEMPTS = 3

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the board assistant for a project management app.
Use the current board IDs exactly as provided. Card and column IDs are numeric strings;
return them as integers in operations. You may create, edit, move, or delete cards. You
cannot rename columns or invent IDs for existing resources. Explain unsupported requests
without returning an operation for them, and still perform any supported parts of the
request. Use only the fields defined for each operation. Positions are zero-based. Return
an empty operations array when no board change is needed."""

RESPONSE_CORRECTION_PROMPT = """Your previous response did not match the required JSON
schema. Return only a corrected board update. Use exactly the fields defined for each
operation type and preserve the user's requested changes."""


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


class OperationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateOperation(OperationBase):
    type: Literal["create"] = Field(description="Create a card.")
    column_id: int = Field(gt=0, description="Target column ID.")
    title: str = Field(description="New card title.")
    details: str = Field(description="New card details; use an empty string if absent.")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be blank")
        return value


class EditOperation(OperationBase):
    type: Literal["edit"] = Field(description="Edit a card.")
    card_id: int = Field(gt=0, description="Existing card ID.")
    title: str | None = Field(description="Changed title, or null if unchanged.")
    details: str | None = Field(description="Changed details, or null if unchanged.")

    @model_validator(mode="after")
    def at_least_one_changed_field(self) -> "EditOperation":
        if self.title is None and self.details is None:
            raise ValueError("At least one changed field is required")
        if self.title is not None and not self.title.strip():
            raise ValueError("Title must not be blank")
        return self


class MoveOperation(OperationBase):
    type: Literal["move"] = Field(description="Move a card.")
    card_id: int = Field(gt=0, description="Existing card ID.")
    column_id: int = Field(gt=0, description="Target column ID.")
    position: int = Field(ge=0, description="Zero-based target position.")


class DeleteOperation(OperationBase):
    type: Literal["delete"] = Field(description="Delete a card.")
    card_id: int = Field(gt=0, description="Existing card ID.")


CardOperation = Annotated[
    CreateOperation | EditOperation | MoveOperation | DeleteOperation,
    Field(discriminator="type"),
]


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
        update = await _request_board_update(messages)
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


async def _request_board_update(
    messages: list[dict[str, str]],
) -> AiBoardUpdate:
    request_messages = list(messages)
    for attempt in range(MAX_BOARD_UPDATE_ATTEMPTS):
        completion = await create_completion(
            request_messages,
            response_format=AI_RESPONSE_FORMAT,
            max_tokens=1000,
            frequency_penalty=0.4,
            presence_penalty=0.4,
        )
        try:
            return AiBoardUpdate.model_validate_json(completion)
        except ValidationError:
            if attempt + 1 == MAX_BOARD_UPDATE_ATTEMPTS:
                logger.error(
                    "OpenRouter board update failed validation after %d attempts; "
                    "last raw completion: %s",
                    MAX_BOARD_UPDATE_ATTEMPTS,
                    completion,
                )
                raise
            logger.warning("Retrying OpenRouter after an invalid board update")
            request_messages.extend(
                [
                    {"role": "assistant", "content": completion},
                    {"role": "user", "content": RESPONSE_CORRECTION_PROMPT},
                ]
            )

    raise RuntimeError("Unreachable")


def _apply_operation(
    connection: sqlite3.Connection, board_id: int, operation: CardOperation
) -> None:
    if operation.type == "create":
        create_card_record(
            connection,
            board_id,
            CreateCard(
                column_id=operation.column_id,
                title=operation.title,
                details=operation.details,
            ),
        )
    elif operation.type == "edit":
        edit_card_record(
            connection,
            board_id,
            operation.card_id,
            EditCard(title=operation.title, details=operation.details),
        )
    elif operation.type == "move":
        move_card_record(
            connection,
            board_id,
            operation.card_id,
            MoveCard(
                column_id=operation.column_id,
                position=operation.position,
            ),
        )
    else:
        delete_card_record(
            connection,
            board_id,
            operation.card_id,
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
