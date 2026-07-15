import json
from pathlib import Path
from typing import Any


PROFILE_PATH = (
    Path(__file__).resolve().parent.parent
    / "knowledge"
    / "profile.json"
)


def load_profile() -> dict[str, Any]:
    """读取并返回经过确认的个人资料。"""

    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as file:
            profile = json.load(file)

        return profile

    except FileNotFoundError as error:
        raise RuntimeError(
            f"找不到个人资料文件：{PROFILE_PATH}"
        ) from error

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"profile.json 格式错误："
            f"第 {error.lineno} 行，第 {error.colno} 列"
        ) from error
def get_profile_section(section: str) -> Any:
    """根据分类名称返回对应的个人资料。"""

    profile = load_profile()

    normalized_section = section.strip().lower()

    if normalized_section not in profile:
        available_sections = ", ".join(profile.keys())

        raise ValueError(
            f"不存在资料分类：{section}。"
            f"可查询分类：{available_sections}"
        )

    return profile[normalized_section]
def search_projects(keyword: str) -> list[dict[str, Any]]:
    """根据关键词搜索项目资料。"""

    normalized_keyword = keyword.strip().lower()

    if not normalized_keyword:
        return []

    projects = get_profile_section("projects")

    matched_projects = []

    for project in projects:
        searchable_text = json.dumps(
            project,
            ensure_ascii=False,
        ).lower()

        if normalized_keyword in searchable_text:
            matched_projects.append(project)

    return matched_projects