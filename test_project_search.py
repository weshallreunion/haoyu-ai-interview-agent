from pprint import pprint

from app.profile_store import search_projects


keywords = [
    "Haoyu AI",
    "FastAPI",
    "SQLite",
    "React",
]

for keyword in keywords:
    print(f"\n搜索关键词：{keyword}")
    pprint(search_projects(keyword))