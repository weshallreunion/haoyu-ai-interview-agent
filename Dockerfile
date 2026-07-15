FROM python:3.12-slim

# 不生成 Python 缓存文件
ENV PYTHONDONTWRITEBYTECODE=1

# Python 日志立即输出到容器终端
ENV PYTHONUNBUFFERED=1

# 容器内部的工作目录
WORKDIR /app

# 先复制依赖清单，方便 Docker 利用构建缓存
COPY requirements.txt ./requirements.txt

# 安装 Python 依赖
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# 复制项目运行需要的文件
COPY app ./app
COPY frontend ./frontend
COPY knowledge ./knowledge

# 创建 SQLite 数据目录
RUN mkdir -p /app/data

# 声明应用端口
EXPOSE 8000

# 定期检查服务健康状态
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# 启动 FastAPI；该 JSON 数组必须保持为一条完整指令
CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]