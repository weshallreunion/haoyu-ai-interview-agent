from pathlib import Path

from dotenv import load_dotenv
from agents import Runner, SQLiteSession

from app.agent import haoyu_agent


load_dotenv()


DATA_DIR = Path(__file__).parent / "data"
DATABASE_PATH = DATA_DIR / "conversations.db"
SESSION_ID = "local_recruiter_demo"


def main() -> None:
    """在终端中运行支持多轮记忆的招聘问答。"""

    DATA_DIR.mkdir(exist_ok=True)

    session = SQLiteSession(
        SESSION_ID,
        str(DATABASE_PATH),
    )

    print("=" * 55)
    print("Haoyu AI Interview Agent")
    print("可以询问教育、技能、项目、奖项和实习安排")
    print("输入 exit 退出")
    print("=" * 55)

    while True:
        question = input("\nRecruiter: ").strip()

        if question.lower() in {"exit", "quit"}:
            print("\nHaoyu AI: 感谢交流，再见。")
            break

        if not question:
            print("请输入问题。")
            continue

        try:
            result = Runner.run_sync(
                haoyu_agent,
                question,
                session=session,
                max_turns=5,
            )
        except Exception as error:
            print("\nAgent 调用失败：")
            print(f"{type(error).__name__}: {error}")
            continue

        print("\nHaoyu AI:")
        print(result.final_output)


if __name__ == "__main__":
    main()