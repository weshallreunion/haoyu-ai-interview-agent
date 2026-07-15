from pprint import pprint

from app.tools import get_verified_profile


print("工具名称：")
print(get_verified_profile.name)

print("\n工具说明：")
print(get_verified_profile.description)

print("\n参数规则：")
pprint(get_verified_profile.params_json_schema)