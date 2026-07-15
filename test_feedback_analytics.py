from uuid import uuid4

from app.chat_store import (
    append_message,
    clear_messages,
    save_feedback,
)
from app.feedback_analytics import (
    get_feedback_summary,
    get_recent_feedback,
)


def main() -> None:
    session_id = (
        "analytics_test_"
        + uuid4().hex[:12]
    )

    before_summary = (
        get_feedback_summary()
    )

    try:
        append_message(
            session_id=session_id,
            role="user",
            content=(
                "你为什么做 Haoyu AI？"
            ),
            sources=[],
        )

        assistant_message_id = (
            append_message(
                session_id=session_id,
                role="assistant",
                content=(
                    "我希望通过这个项目实践 "
                    "AI Agent 的开发。"
                ),
                sources=[
                    "本人确认的表达资料"
                ],
            )
        )

        saved = save_feedback(
            session_id=session_id,
            message_id=(
                assistant_message_id
            ),
            rating="down",
            comment="回答还可以更具体。",
        )

        assert saved is True

        after_summary = (
            get_feedback_summary()
        )

        assert (
            after_summary["total"]
            == before_summary["total"] + 1
        )

        assert (
            after_summary["down_count"]
            == before_summary["down_count"]
            + 1
        )

        print(
            "[PASS] 反馈总体统计"
        )

        records = get_recent_feedback(
            limit=100,
            rating="down",
        )

        target_record = next(
            (
                record
                for record in records
                if record["message_id"]
                == assistant_message_id
            ),
            None,
        )

        assert target_record is not None

        assert (
            target_record["question"]
            == "你为什么做 Haoyu AI？"
        )

        assert (
            target_record["rating"]
            == "down"
        )

        assert (
            target_record["comment"]
            == "回答还可以更具体。"
        )

        assert (
            "本人确认的表达资料"
            in target_record["sources"]
        )

        print(
            "[PASS] 问题和回答正确关联"
        )

        assert (
            "..."
            in target_record["session_id"]
        )

        print(
            "[PASS] 会话编号脱敏"
        )

        only_positive = (
            get_recent_feedback(
                limit=100,
                rating="up",
            )
        )

        assert all(
            record["rating"] == "up"
            for record in only_positive
        )

        print(
            "[PASS] 按反馈类型筛选"
        )

    finally:
        clear_messages(session_id)

    final_summary = get_feedback_summary()

    assert (
        final_summary["total"]
        == before_summary["total"]
    )

    print(
        "[PASS] 清理测试数据"
    )

    print(
        "\n反馈分析模块全部测试通过。"
    )


if __name__ == "__main__":
    main()