from uuid import uuid4

from app.chat_store import (
    append_message,
    clear_messages,
    get_messages,
    save_feedback,
)


def main() -> None:
    session_id = (
        "feedback_test_"
        + uuid4().hex[:12]
    )

    try:
        user_message_id = append_message(
            session_id=session_id,
            role="user",
            content="你做过哪些项目？",
            sources=[],
        )

        assistant_message_id = (
            append_message(
                session_id=session_id,
                role="assistant",
                content=(
                    "我目前主要做过 "
                    "Haoyu AI 等项目。"
                ),
                sources=[
                    "全部项目资料"
                ],
            )
        )

        assert user_message_id > 0
        assert assistant_message_id > 0

        print(
            "[PASS] 消息编号生成"
        )

        saved = save_feedback(
            session_id=session_id,
            message_id=assistant_message_id,
            rating="up",
        )

        assert saved is True

        print(
            "[PASS] 保存正面反馈"
        )

        messages = get_messages(
            session_id
        )

        assistant_message = next(
            message
            for message in messages
            if message["message_id"]
            == assistant_message_id
        )

        assert (
            assistant_message["feedback"]
            == "up"
        )

        print(
            "[PASS] 读取反馈状态"
        )

        updated = save_feedback(
            session_id=session_id,
            message_id=assistant_message_id,
            rating="down",
            comment="回答可以更简洁。",
        )

        assert updated is True

        updated_messages = get_messages(
            session_id
        )

        updated_assistant = next(
            message
            for message in updated_messages
            if message["message_id"]
            == assistant_message_id
        )

        assert (
            updated_assistant["feedback"]
            == "down"
        )

        print(
            "[PASS] 更新反馈状态"
        )

        invalid_feedback = save_feedback(
            session_id=session_id,
            message_id=user_message_id,
            rating="up",
        )

        assert invalid_feedback is False

        print(
            "[PASS] 禁止评价用户消息"
        )

    finally:
        clear_messages(session_id)

    remaining_messages = get_messages(
        session_id
    )

    assert remaining_messages == []

    print(
        "[PASS] 清理测试数据"
    )

    print(
        "\n回答反馈存储模块全部测试通过。"
    )


if __name__ == "__main__":
    main()