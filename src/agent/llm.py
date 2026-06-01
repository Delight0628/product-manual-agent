"""LLM 连接封装 — 统一使用 OpenAI 兼容接口"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env
from pathlib import Path
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def get_llm(temperature: float = 0.3):
    """获取 LLM 实例（OpenAI 兼容接口）"""
    from langchain_openai import ChatOpenAI

    base_url = os.getenv("LLM_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "mimo-v2.5")

    if not api_key:
        raise ValueError(
            "LLM_API_KEY 未设置。请在 .env 文件中配置：\n"
            "LLM_API_KEY=your_api_key_here"
        )

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=60,
        max_retries=2,
    )


def get_llm_safe(temperature: float = 0.3):
    """安全获取 LLM，失败时返回 None 而不是抛异常"""
    try:
        return get_llm(temperature)
    except Exception as e:
        print(f"[Agent] LLM 初始化失败: {e}")
        return None
