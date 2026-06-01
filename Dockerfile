FROM python:3.11-slim

WORKDIR /app

# 先装基础系统库
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
       libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
       libasound2 libpango-1.0-0 libcairo2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（包含 playwright）
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# 安装 Playwright 的系统依赖 + 浏览器
RUN playwright install-deps chromium \
    && playwright install chromium

# 复制源码
COPY . .

EXPOSE 8000

CMD uvicorn src.api.main:app --host 0.0.0.0 --port 8000
