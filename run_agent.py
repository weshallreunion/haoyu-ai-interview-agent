from dotenv import load_dotenv
from agents import Runner

from app.agent import haoyu_agent


load_dotenv()


def main() -> None:
    """运行一次 Haoyu Agent 问答。"""

    question = (
        "请介绍钱浩宇做过的后端项目，"
        "并明确说明哪些功能已经完成，哪些尚未完成。"
    )

    print("Recruiter:")
    print(question)

    try:
        result = Runner.run_sync(
            haoyu_agent,
            question,
            max_turns=5,
        )
    except Exception as error:
        print("\nAgent 调用失败：")
        print(f"{type(error).__name__}: {error}")
        return

    print("\nHaoyu AI:")
    print(result.final_output)


if __name__ == "__main__":
    main()