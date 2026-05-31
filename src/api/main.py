"""FastAPI 主应用"""

import uuid
import asyncio
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.models import (
    ManualRequest,
    ManualResponse,
    TaskStatus,
    LanguageCode,
    ProductData,
)
from src.scraper import AmazonScraper
from src.translator import Translator, TranslationProvider
import os

from src.pdf_generator import PDFGenerator

# 项目根目录（src/api/main.py -> src/api -> src -> root）
BASE_DIR = Path(__file__).parent.parent.parent


app = FastAPI(
    title="Product Manual Agent",
    description="跨境电商多语言产品说明书生成器",
    version="0.1.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任务存储
tasks: Dict[str, TaskStatus] = {}

# 模块实例
scraper = AmazonScraper(use_mock=True)  # Demo 模式使用 Mock 数据
translator = Translator(provider=TranslationProvider.MOCK)
pdf_generator = PDFGenerator(output_dir=str(BASE_DIR / "output"))


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回主页面"""
    # 使用绝对路径确保模板可被找到
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    html_path = os.path.join(base_dir, "src", "api", "templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Product Manual Agent</h1><p>请访问 /docs 查看 API 文档</p>"


@app.get("/api/languages")
async def get_languages():
    """获取支持的语言列表"""
    return {
        "supported": [lang.value for lang in LanguageCode]
    }


@app.post("/api/generate", response_model=ManualResponse)
async def generate_manual(request: ManualRequest, background_tasks: BackgroundTasks):
    """生成产品说明书"""
    task_id = str(uuid.uuid4())[:8]

    # 创建任务
    tasks[task_id] = TaskStatus(
        task_id=task_id,
        status="processing",
        progress=0,
        message="Starting...",
    )

    # 后台执行生成任务
    background_tasks.add_task(
        _process_generation,
        task_id=task_id,
        url=request.url,
        languages=request.languages,
    )

    return ManualResponse(
        task_id=task_id,
        status="processing",
        message="任务已提交，请稍候...",
    )


@app.get("/api/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return tasks[task_id]


@app.get("/api/download/{filename}")
async def download_pdf(filename: str):
    """下载生成的 PDF"""
    filepath = BASE_DIR / "output" / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf",
    )


@app.get("/api/files")
async def list_files():
    """列出所有生成的文件"""
    output_dir = BASE_DIR / "output"
    files = []
    if output_dir.exists():
        for f in output_dir.glob("*.pdf"):
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "created": f.stat().st_ctime,
            })
    return {"files": files}


async def _process_generation(
    task_id: str,
    url: str,
    languages: list[LanguageCode],
):
    """后台处理生成任务"""
    try:
        # 更新进度：抓取数据
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 10, "message": "正在抓取产品数据..."})
        product = await scraper.scrape(url)

        # 更新进度：翻译
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 40, "message": "正在翻译内容..."})
        translations = await translator.translate_product(product, languages)

        # 更新进度：生成 PDF
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 70, "message": "正在生成 PDF..."})
        pdf_path = pdf_generator.generate_manual(product, translations)

        # 完成
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 100, "status": "done", "message": "生成完成！", "pdf_path": pdf_path})

    except Exception as e:
        tasks[task_id] = tasks[task_id].model_copy(update={"status": "failed", "message": f"生成失败: {str(e)}"})


def start_app():
    """启动应用"""
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    start_app()
