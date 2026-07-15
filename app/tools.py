import json
from typing import Any

from agents import function_tool

from app.profile_store import (
    get_profile_section,
    search_projects,
)

from app.persona_store import get_persona_section

GENERAL_PROFILE_SECTIONS = {
    "basic",
    "education",
    "skills",
    "awards",
    "availability",
}


@function_tool
def get_verified_profile(section: str) -> str:
    """查询钱浩宇的非项目类个人资料。

    这个工具用于查询基本信息、教育背景、技术能力、
    获奖情况和实习安排，不用于查询项目。

    Args:
        section: 可选值为 basic、education、skills、
            awards、availability。
    """

    normalized_section = section.strip().lower()

    print(
        f"[Tool] 正在查询资料分类："
        f"{normalized_section}"
    )

    if normalized_section not in GENERAL_PROFILE_SECTIONS:
        return json.dumps(
            {
                "error": "不支持该资料分类。",
                "available_sections": sorted(
                    GENERAL_PROFILE_SECTIONS
                ),
                "hint": (
                    "项目相关问题应使用项目查询工具。"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    try:
        section_data: Any = get_profile_section(
            normalized_section
        )
    except ValueError as error:
        return str(error)

    return json.dumps(
        section_data,
        ensure_ascii=False,
        indent=2,
    )


@function_tool
def get_all_verified_projects() -> str:
    """查询钱浩宇经过确认的全部项目经历。

    仅在用户询问全部项目、整体项目经历或做过哪些项目时使用。
    """

    print("[Tool] 正在查询全部项目")

    projects = get_profile_section("projects")

    return json.dumps(
        {
            "project_count": len(projects),
            "projects": projects,
        },
        ensure_ascii=False,
        indent=2,
    )


@function_tool
def search_verified_projects(keyword: str) -> str:
    """根据关键词精准搜索钱浩宇的项目资料。

    当用户询问某项技术、项目名称或具体功能对应哪个项目时，
    应优先使用本工具，不要读取全部项目。

    Args:
        keyword: 搜索关键词，例如 Go、Gin、MySQL、
            Docker、Library、借阅或 Mini Program。
    """

    normalized_keyword = keyword.strip()

    print(
        f"[Tool] 正在搜索项目关键词："
        f"{normalized_keyword}"
    )

    matched_projects = search_projects(
        normalized_keyword
    )

    if not matched_projects:
        return json.dumps(
            {
                "keyword": normalized_keyword,
                "match_count": 0,
                "matches": [],
                "message": "现有资料中没有找到匹配项目。",
            },
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        {
            "keyword": normalized_keyword,
            "match_count": len(matched_projects),
            "matches": matched_projects,
        },
        ensure_ascii=False,
        indent=2,
    )

@function_tool
def get_verified_persona(section: str) -> str:
    """查询钱浩宇本人确认的动机、想法和个人表达。

    适用于“为什么选择某个方向”“如何解决问题”
    “目前有哪些不足”“希望从实习中获得什么”等问题。

    Args:
        section: 要查询的表达分类。可选值包括
            backend_motivation、
            ai_agent_motivation、
            preferred_project、
            problem_solving_method、
            growth_areas、
            internship_expectation、
            communication_style。
    """

    normalized_section = section.strip().lower()

    print(
        f"[Tool] 正在查询个人表达分类："
        f"{normalized_section}"
    )

    try:
        persona_data = get_persona_section(
            normalized_section
        )
    except ValueError as error:
        return json.dumps(
            {
                "error": str(error),
                "hint": (
                    "请根据可用分类重新选择。"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        persona_data,
        ensure_ascii=False,
        indent=2,
    )