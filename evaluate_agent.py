import asyncio
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv


load_dotenv()


from agents import Runner  # noqa: E402

from app.agent import haoyu_agent  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent

CASES_PATH = (
    BASE_DIR
    / "evaluation"
    / "cases.json"
)

REPORTS_DIR = (
    BASE_DIR
    / "evaluation"
    / "reports"
)


def load_cases() -> list[dict[str, Any]]:
    """读取自动评测用例。"""

    try:
        with CASES_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            cases = json.load(file)

    except FileNotFoundError as error:
        raise RuntimeError(
            f"找不到评测文件：{CASES_PATH}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "cases.json 格式错误："
            f"第 {error.lineno} 行，"
            f"第 {error.colno} 列"
        ) from error

    if not isinstance(cases, list):
        raise RuntimeError(
            "cases.json 最外层必须是数组。"
        )

    return cases


def extract_tool_name(
    item: Any,
) -> str | None:
    """从不同结构的RunItem中提取工具名称。"""

    direct_name = getattr(
        item,
        "tool_name",
        None,
    )

    if isinstance(direct_name, str):
        normalized_name = direct_name.strip()

        if normalized_name:
            return normalized_name

    raw_item = getattr(
        item,
        "raw_item",
        None,
    )

    if isinstance(raw_item, dict):
        raw_name = (
            raw_item.get("name")
            or raw_item.get("tool_name")
        )

        if isinstance(raw_name, str):
            normalized_name = raw_name.strip()

            if normalized_name:
                return normalized_name

        return None

    raw_name = (
        getattr(raw_item, "name", None)
        or getattr(
            raw_item,
            "tool_name",
            None,
        )
    )

    if isinstance(raw_name, str):
        normalized_name = raw_name.strip()

        if normalized_name:
            return normalized_name

    return None


def collect_used_tools(
    items: list[Any],
) -> list[str]:
    """收集一次Agent运行实际使用的工具。"""

    used_tools: list[str] = []

    for item in items:
        tool_name = extract_tool_name(item)

        if (
            tool_name
            and tool_name not in used_tools
        ):
            used_tools.append(tool_name)

    return used_tools


def contains_any(
    answer: str,
    terms: list[str],
) -> bool:
    """判断回答是否包含至少一个目标词。"""

    if not terms:
        return True

    normalized_answer = answer.lower()

    return any(
        term.lower() in normalized_answer
        for term in terms
    )


def find_forbidden_terms(
    answer: str,
    terms: list[str],
) -> list[str]:
    """返回回答中出现的禁止表达。"""

    normalized_answer = answer.lower()

    return [
        term
        for term in terms
        if term.lower() in normalized_answer
    ]


async def evaluate_case(
    case: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    """执行并检查单个评测用例。"""

    name = str(
        case.get(
            "name",
            f"用例{index}",
        )
    )

    question = str(
        case.get("question", "")
    ).strip()

    expected_tools = case.get(
        "expected_tools",
        [],
    )
    allowed_tools = case.get(
    "allowed_tools"
)

    required_any = case.get(
        "required_any",
        [],
    )

    forbidden = case.get(
        "forbidden",
        [],
    )

    if not question:
        return {
            "name": name,
            "passed": False,
            "error": "评测问题为空。",
        }

    started_at = time.perf_counter()

    try:
        result = await Runner.run(
            haoyu_agent,
            question,
            max_turns=5,
        )

        answer = str(
            result.final_output or ""
        ).strip()

        used_tools = collect_used_tools(
            result.new_items
        )

        missing_tools = [
            tool
            for tool in expected_tools
            if tool not in used_tools
        ]
        unexpected_tools = []

        if isinstance(allowed_tools, list):
            unexpected_tools = [
                tool
                for tool in used_tools
                if tool not in allowed_tools
            ]

        required_check = contains_any(
            answer,
            required_any,
        )

        found_forbidden = (
            find_forbidden_terms(
                answer,
                forbidden,
            )
        )

        answer_check = bool(answer)

        passed = (
            not missing_tools
            and not unexpected_tools
            and required_check
            and not found_forbidden
            and answer_check
        )

        duration_seconds = round(
            time.perf_counter()
            - started_at,
            2,
        )

        return {
            "name": name,
            "question": question,
            "passed": passed,
            "duration_seconds": (
                duration_seconds
            ),
            "expected_tools": (
                expected_tools
            ),
            "used_tools": used_tools,
            "missing_tools": (
                missing_tools
            ),
            "required_any": (
                required_any
            ),
            "required_check": (
                required_check
            ),
            "found_forbidden": (
                found_forbidden
            ),
            "answer": answer,
            "allowed_tools": allowed_tools,
            "unexpected_tools": unexpected_tools,
        }

    except Exception as error:
        duration_seconds = round(
            time.perf_counter()
            - started_at,
            2,
        )

        return {
            "name": name,
            "question": question,
            "passed": False,
            "duration_seconds": (
                duration_seconds
            ),
            "error": (
                f"{type(error).__name__}: "
                f"{error}"
            ),
        }


def print_case_result(
    result: dict[str, Any],
    index: int,
) -> None:
    """在终端显示单个用例结果。"""

    status = (
        "PASS"
        if result.get("passed")
        else "FAIL"
    )

    print(
        "\n"
        + "=" * 68
    )

    print(
        f"[{status}] "
        f"{index}. "
        f"{result.get('name')}"
    )

    print(
        f"问题："
        f"{result.get('question', '')}"
    )

    if "error" in result:
        print(
            f"错误："
            f"{result['error']}"
        )

        return

    print(
        "实际工具："
        f"{result.get('used_tools', [])}"
    )

    missing_tools = result.get(
        "missing_tools",
        [],
    )

    if missing_tools:
        print(
            "缺少工具："
            f"{missing_tools}"
        )
    unexpected_tools = result.get(
    "unexpected_tools",
    [],
)

    if unexpected_tools:
        print(
            "调用了多余工具："
            f"{unexpected_tools}"
        )

    if not result.get(
        "required_check",
        True,
    ):
        print(
            "未包含任一关键表达："
            f"{result.get('required_any', [])}"
        )

    forbidden_terms = result.get(
        "found_forbidden",
        [],
    )

    if forbidden_terms:
        print(
            "出现禁止表达："
            f"{forbidden_terms}"
        )

    print(
        "回答："
        f"{result.get('answer', '')}"
    )

    print(
        "耗时："
        f"{result.get('duration_seconds')}秒"
    )


async def main() -> None:
    """运行全部评测用例并生成报告。"""

    cases = load_cases()

    print(
        f"共加载 {len(cases)} 个评测用例。"
    )

    print(
        "注意：本次评测会调用大模型API。"
    )

    results: list[dict[str, Any]] = []

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print(
            f"\n正在执行 "
            f"{index}/{len(cases)}："
            f"{case.get('name', '未命名用例')}"
        )

        result = await evaluate_case(
            case,
            index,
        )

        results.append(result)

        print_case_result(
            result,
            index,
        )

    passed_count = sum(
        1
        for result in results
        if result.get("passed")
    )

    failed_count = (
        len(results)
        - passed_count
    )

    report = {
        "report_id": uuid4().hex,
        "total": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate": round(
            passed_count
            / len(results)
            * 100,
            2,
        )
        if results
        else 0,
        "results": results,
    }

    REPORTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path = (
        REPORTS_DIR
        / "latest_report.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "\n"
        + "=" * 68
    )

    print("评测完成")

    print(
        f"通过："
        f"{passed_count}"
    )

    print(
        f"失败："
        f"{failed_count}"
    )

    print(
        f"通过率："
        f"{report['pass_rate']}%"
    )

    print(
        f"报告位置："
        f"{report_path}"
    )


if __name__ == "__main__":
    asyncio.run(main())