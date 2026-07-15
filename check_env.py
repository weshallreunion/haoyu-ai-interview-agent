import os

from dotenv import load_dotenv


load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("OPENAI_DEFAULT_MODEL")

if not api_key:
    raise RuntimeError(
        "没有读取到 OPENAI_API_KEY，请检查 .env 文件。"
    )

print("API Key 已成功读取：", bool(api_key))
print("当前模型：", model)