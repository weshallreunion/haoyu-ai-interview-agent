import json
from typing import Any, TypedDict

from app.chat_store import (
    create_connection,
    normalize_sources,
)


class FeedbackSummary(TypedDict):
    """反馈总体统计。"""

    total: int
    up_count: int
    down_count: int
    satisfaction_rate: float


class FeedbackRecord(TypedDict):
    """一条用于分析的回答反馈。"""

    message_id: int
    session_id: str
    question: str
    answer: str
    rating: str
    comment: str | None
    sources: list[str]
    created_at: str
    updated_at: str


def mask_session_id(
    session_id: str,
) -> str:
    """隐藏部分会话编号，避免后台直接展示完整标识。"""

    if len(session_id) <= 12:
        return session_id

    return (
        session_id[:8]
        + "..."
        + session_id[-4:]
    )


def get_feedback_summary() -> FeedbackSummary:
    """读取反馈总体统计。"""

    with create_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total,

                SUM(
                    CASE
                        WHEN rating = 'up'
                        THEN 1
                        ELSE 0
                    END
                ) AS up_count,

                SUM(
                    CASE
                        WHEN rating = 'down'
                        THEN 1
                        ELSE 0
                    END
                ) AS down_count

            FROM message_feedback
            """
        ).fetchone()

    total = int(row["total"] or 0)
    up_count = int(row["up_count"] or 0)
    down_count = int(
        row["down_count"] or 0
    )

    satisfaction_rate = (
        round(
            up_count / total * 100,
            2,
        )
        if total > 0
        else 0.0
    )

    return {
        "total": total,
        "up_count": up_count,
        "down_count": down_count,
        "satisfaction_rate":
            satisfaction_rate,
    }


def get_recent_feedback(
    limit: int = 20,
    rating: str | None = None,
) -> list[FeedbackRecord]:
    """读取最近反馈及对应的问题和回答。"""

    if limit <= 0:
        raise ValueError(
            "limit 必须大于0。"
        )

    safe_limit = min(limit, 100)

    if rating not in {
        None,
        "up",
        "down",
    }:
        raise ValueError(
            "rating 只能是 up、down 或 None。"
        )

    query = """
        SELECT
            feedback.message_id,
            feedback.session_id,
            feedback.rating,
            feedback.comment,
            feedback.created_at,
            feedback.updated_at,

            assistant_message.content
                AS answer,

            assistant_message.sources_json
                AS sources_json,

            COALESCE(
                (
                    SELECT
                        user_message.content

                    FROM chat_messages
                        AS user_message

                    WHERE
                        user_message.session_id
                            = assistant_message.session_id

                        AND user_message.role
                            = 'user'

                        AND user_message.id
                            < assistant_message.id

                    ORDER BY
                        user_message.id DESC

                    LIMIT 1
                ),
                ''
            ) AS question

        FROM message_feedback
            AS feedback

        INNER JOIN chat_messages
            AS assistant_message

            ON assistant_message.id
                = feedback.message_id

        WHERE
            assistant_message.role
                = 'assistant'
    """

    parameters: list[Any] = []

    if rating is not None:
        query += """
            AND feedback.rating = ?
        """

        parameters.append(rating)

    query += """
        ORDER BY
            feedback.updated_at DESC,
            feedback.message_id DESC

        LIMIT ?
    """

    parameters.append(safe_limit)

    with create_connection() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    records: list[FeedbackRecord] = []

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

        records.append(
            {
                "message_id": int(
                    row["message_id"]
                ),
                "session_id":
                    mask_session_id(
                        row["session_id"]
                    ),
                "question":
                    row["question"],
                "answer":
                    row["answer"],
                "rating":
                    row["rating"],
                "comment":
                    row["comment"],
                "sources":
                    sources,
                "created_at":
                    row["created_at"],
                "updated_at":
                    row["updated_at"],
            }
        )

    return records