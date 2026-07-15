from pprint import pprint

from app.persona_store import get_persona_section


print("后端学习动机：")
pprint(
    get_persona_section(
        "backend_motivation"
    )
)

print("\n解决问题方式：")
pprint(
    get_persona_section(
        "problem_solving_method"
    )
)

print("\n目前不足：")
pprint(
    get_persona_section(
        "growth_areas"
    )
)