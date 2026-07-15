import json
from pathlib import Path
from typing import Any


PERSONA_PATH = (
    Path(__file__).resolve().parent.parent
    / "knowledge"
    / "persona.json"
)


def load_persona() -> dict[str, Any]:
    """读取并返回经过本人确认的个人表达资料。"""

    try:
        with PERSONA_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            persona = json.load(file)

        return persona

    except FileNotFoundError as error:
        raise RuntimeError(
            f"找不到个人表达资料文件：{PERSONA_PATH}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "persona.json 格式错误："
            f"第 {error.lineno} 行，"
            f"第 {error.colno} 列"
        ) from error


def get_persona_section(section: str) -> Any:
    """根据分类名称查询个人表达资料。"""

    persona = load_persona()

    normalized_section = section.strip().lower()

    if normalized_section not in persona:
        available_sections = ", ".join(
            persona.keys()
        )

        raise ValueError(
            f"不存在个人表达分类：{section}。"
            f"可查询分类：{available_sections}"
        )

    return persona[normalized_section]