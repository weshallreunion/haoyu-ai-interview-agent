from app.agent import haoyu_agent


print("Agent名称：")
print(haoyu_agent.name)

print("\nAgent类型：")
print(type(haoyu_agent).__name__)

print("\nAgent规则：")
print(haoyu_agent.instructions)

print("\n可用工具：")
for tool in haoyu_agent.tools:
    print("-", tool.name)