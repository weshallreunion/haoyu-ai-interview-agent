import json
import sqlite3
from pathlib import Path
from typing import (
    Any,
    Literal,
    TypedDict,
    cast,
)


MessageRole = Literal[
    "user",
    "assistant",
]

FeedbackRating = Literal[
    "up",
    "down",
]


class StoredMessage(TypedDict):
    """网页中需要显示的一条聊天消息。"""

    message_id: int
    role: MessageRole
    content: str
    sources: list[str]
    feedback: FeedbackRating | None


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CHAT_HISTORY_PATH = (
    DATA_DIR / "chat_history.db"
)


def create_connection() -> sqlite3.Connection:
    """创建网页聊天记录数据库连接。"""

    DATA_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(
        CHAT_HISTORY_PATH,
        timeout=10,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA busy_timeout = 5000"
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialize_database() -> None:
    """创建聊天记录表和回答反馈表。"""

    with create_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            chat_messages (
                id INTEGER
                    PRIMARY KEY AUTOINCREMENT,

                session_id TEXT
                    NOT NULL,

                role TEXT
                    NOT NULL
                    CHECK (
                        role IN (
                            'user',
                            'assistant'
                        )
                    ),

                content TEXT
                    NOT NULL,

                sources_json TEXT
                    NOT NULL
                    DEFAULT '[]',

                created_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        columns = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    chat_messages
                )
                """
            ).fetchall()
        }

        if "sources_json" not in columns:
            connection.execute(
                """
                ALTER TABLE chat_messages
                ADD COLUMN sources_json TEXT
                NOT NULL DEFAULT '[]'
                """
            )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_chat_messages_session
            ON chat_messages (
                session_id,
                id
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS
            message_feedback (
                message_id INTEGER
                    PRIMARY KEY,

                session_id TEXT
                    NOT NULL,

                rating TEXT
                    NOT NULL
                    CHECK (
                        rating IN (
                            'up',
                            'down'
                        )
                    ),

                comment TEXT,

                created_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (
                    message_id
                )
                REFERENCES chat_messages (
                    id
                )
                ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_message_feedback_session
            ON message_feedback (
                session_id
            )
            """
        )


def normalize_sources(
    sources: list[Any] | None,
) -> list[str]:
    """清理来源标签并去除重复项。"""

    normalized_sources: list[str] = []

    for source in sources or []:
        if not isinstance(source, str):
            continue

        normalized_source = source.strip()

        if (
            normalized_source
            and normalized_source
            not in normalized_sources
        ):
            normalized_sources.append(
                normalized_source
            )

    return normalized_sources


def append_message(
    session_id: str,
    role: MessageRole,
    content: str,
    sources: list[str] | None = None,
) -> int:
    """保存一条消息，并返回消息编号。"""

    normalized_content = content.strip()

    if not normalized_content:
        raise ValueError(
            "消息内容不能为空。"
        )

    normalized_sources = normalize_sources(
        sources
    )

    sources_json = json.dumps(
        normalized_sources,
        ensure_ascii=False,
    )

    with create_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO chat_messages (
                session_id,
                role,
                content,
                sources_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                normalized_content,
                sources_json,
            ),
        )

        message_id = cursor.lastrowid

    if message_id is None:
        raise RuntimeError(
            "保存消息后没有获得消息编号。"
        )

    return int(message_id)


def append_messages(
    session_id: str,
    messages: list[StoredMessage],
) -> list[int]:
    """一次保存多条旧消息，并返回消息编号。"""

    message_ids: list[int] = []

    for message in messages:
        content = message["content"].strip()

        if not content:
            continue

        message_id = append_message(
            session_id=session_id,
            role=message["role"],
            content=content,
            sources=message.get(
                "sources",
                [],
            ),
        )

        message_ids.append(message_id)

    return message_ids


def get_messages(
    session_id: str,
) -> list[StoredMessage]:
    """读取指定会话的消息和反馈状态。"""

    with create_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                chat_messages.id,
                chat_messages.role,
                chat_messages.content,
                chat_messages.sources_json,
                message_feedback.rating
            FROM chat_messages

            LEFT JOIN message_feedback
                ON message_feedback.message_id
                = chat_messages.id

            WHERE chat_messages.session_id = ?

            ORDER BY chat_messages.id ASC
            """,
            (session_id,),
        ).fetchall()

    messages: list[StoredMessage] = []

    for row in rows:
        try:
            raw_sources = json.loads(
                row["sources_json"]
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            raw_sources = []

        sources = (
            normalize_sources(raw_sources)
            if isinstance(raw_sources, list)
            else []
        )

        role = cast(
            MessageRole,
            row["role"],
        )

        raw_feedback = row["rating"]

        feedback: FeedbackRating | None

        if raw_feedback in {
            "up",
            "down",
        }:
            feedback = cast(
                FeedbackRating,
                raw_feedback,
            )
        else:
            feedback = None

        messages.append(
            {
                "message_id": int(
                    row["id"]
                ),
                "role": role,
                "content": row["content"],
                "sources": sources,
                "feedback": feedback,
            }
        )

    return messages


def save_feedback(
    session_id: str,
    message_id: int,
    rating: FeedbackRating,
    comment: str | None = None,
) -> bool:
    """保存或更新一条助手回答的反馈。"""

    if rating not in {
        "up",
        "down",
    }:
        raise ValueError(
            "rating 只能是 up 或 down。"
        )

    normalized_comment = (
        comment.strip()
        if isinstance(comment, str)
        and comment.strip()
        else None
    )

    with create_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO message_feedback (
                message_id,
                session_id,
                rating,
                comment
            )

            SELECT
                id,
                session_id,
                ?,
                ?

            FROM chat_messages

            WHERE
                id = ?
                AND session_id = ?
                AND role = 'assistant'

            ON CONFLICT(message_id)
            DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                rating,
                normalized_comment,
                message_id,
                session_id,
            ),
        )

        return cursor.rowcount > 0


def clear_messages(
    session_id: str,
) -> None:
    """清空会话消息，关联反馈会自动删除。"""

    with create_connection() as connection:
        connection.execute(
            """
            DELETE FROM chat_messages
            WHERE session_id = ?
            """,
            (session_id,),
        )


initialize_database()