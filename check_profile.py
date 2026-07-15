from pprint import pprint

from app.profile_store import get_profile_section


print("教育背景：")
pprint(get_profile_section("education"))

print("\n技能信息：")
pprint(get_profile_section("skills"))

print("\n项目经历：")
pprint(get_profile_section("projects"))