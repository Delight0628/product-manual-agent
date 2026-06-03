"""FastAPI 主应用"""

import uuid
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from src.models import (
    ManualRequest,
    ManualResponse,
    TaskStatus,
    LanguageCode,
    ProductData,
    MaterialRequest,
    UploadResponse,
)
from src.scraper import AmazonScraper
from src.translator import Translator, TranslationProvider
import os

from src.pdf_generator import PDFGenerator

# 项目根目录（src/api/main.py -> src/api -> src -> root）
BASE_DIR = Path(__file__).parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 加载 .env
from dotenv import load_dotenv
_env_path = BASE_DIR / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# 上传文件映射 {file_id: file_path}
# 启动时从磁盘恢复，避免重启后丢失
uploaded_files: Dict[str, Path] = {}


def _restore_uploaded_files():
    """从 uploads 目录恢复文件映射（重启后仍可用）"""
    if not UPLOAD_DIR.exists():
        return
    for f in UPLOAD_DIR.iterdir():
        if f.is_file():
            # 文件名格式: {file_id}_{original_name}
            parts = f.name.split("_", 1)
            if len(parts) == 2:
                file_id = parts[0]
                uploaded_files[file_id] = f

_restore_uploaded_files()
if uploaded_files:
    logger.info(f"♻️ 从磁盘恢复了 {len(uploaded_files)} 个已上传文件")


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

# 思考过程存储 {task_id: [{"step": str, "content": str, "timestamp": float}]}
thinking_processes: Dict[str, List[Dict]] = defaultdict(list)

# SSE 客户端队列 {task_id: [asyncio.Queue, ...]}
sse_clients: Dict[str, List[asyncio.Queue]] = defaultdict(list)

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
    logger.info(f"📥 收到生成请求: task_id={task_id}, url={request.url}, languages={[l.value for l in request.languages]}")

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
    """列出所有生成的文件（PDF、TXT、JSON）"""
    output_dir = BASE_DIR / "output"
    files = []
    if output_dir.exists():
        # 列出所有文档类型（PDF优先，然后是TXT和JSON）
        for ext in ["*.pdf", "*.txt", "*.json"]:
            for f in output_dir.glob(ext):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "created": f.stat().st_ctime,
                    "type": ext.replace("*.", "").upper(),
                })
        # 按创建时间倒序排列（最新的在前）
        files.sort(key=lambda x: x["created"], reverse=True)
    return {"files": files}


def _emit_thinking(task_id: str, step: str, content: str):
    """发送思考过程到存储和 SSE 客户端"""
    import time
    entry = {
        "step": step,
        "content": content,
        "timestamp": time.time(),
    }
    thinking_processes[task_id].append(entry)
    logger.info(f"[{task_id}] 💭 {step}: {content}")

    # 广播到所有 SSE 客户端
    if task_id in sse_clients:
        for queue in sse_clients[task_id]:
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass  # 队列满则丢弃


@app.get("/api/tasks/{task_id}/stream")
async def stream_task_thinking(task_id: str):
    """SSE 端点：实时流式输出 Agent 思考过程"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_clients[task_id].append(queue)

    async def event_generator():
        try:
            # 先发送已有的思考过程
            for entry in thinking_processes.get(task_id, []):
                yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

            # 等待新的思考过程
            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"

                    # 如果任务完成，发送结束信号
                    task_status = tasks.get(task_id)
                    if task_status and task_status.status in ("done", "completed", "failed"):
                        yield f"data: {json.dumps({'step': 'done', 'content': task_status.status}, ensure_ascii=False)}\n\n"
                        break
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield f": heartbeat\n\n"
        finally:
            # 清理客户端
            if task_id in sse_clients:
                sse_clients[task_id] = [q for q in sse_clients[task_id] if q is not queue]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传素材文件"""
    logger.info(f"📤 收到上传文件: {file.filename} ({file.content_type})")

    # 验证文件大小（10MB）
    content = await file.read()
    max_size = 10 * 1024 * 1024
    if len(content) > max_size:
        logger.warning(f"❌ 文件过大: {file.filename} ({len(content)} bytes)")
        raise HTTPException(status_code=413, detail="文件大小超过 10MB 限制")

    # 验证文件类型
    allowed_exts = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json",
                    ".jpg", ".jpeg", ".png", ".gif", ".webp"}
    suffix = Path(file.filename or "unknown").suffix.lower()
    if suffix not in allowed_exts:
        logger.warning(f"❌ 不支持的文件类型: {suffix}")
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {suffix}")

    # 保存文件
    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(content)

    # 记录映射
    uploaded_files[file_id] = file_path

    logger.info(f"✅ 文件上传成功: {file.filename} -> file_id={file_id}, size={len(content)} bytes")

    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "unknown",
        size=len(content),
        content_type=file.content_type or "application/octet-stream",
    )


@app.post("/api/generate-material", response_model=ManualResponse)
async def generate_material(request: MaterialRequest, background_tasks: BackgroundTasks):
    """素材 + AI Agent 模式生成文档"""
    logger.info(f"📥 收到素材生成请求: prompt='{request.prompt[:50]}...', file_ids={request.file_ids}, format={request.output_format}")
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="提示词不能为空")

    # 解析 file_ids 对应的实际路径
    file_paths = []
    for fid in request.file_ids:
        if fid in uploaded_files:
            file_paths.append(str(uploaded_files[fid]))
        else:
            logger.warning(f"❌ file_id={fid} 不存在，当前已知: {list(uploaded_files.keys())}")
            raise HTTPException(status_code=400, detail=f"文件 ID 不存在: {fid}，请重新上传文件")

    task_id = str(uuid.uuid4())[:8]

    # 创建任务
    tasks[task_id] = TaskStatus(
        task_id=task_id,
        status="processing",
        progress=0,
        message="AI Agent 开始工作...",
    )

    # 后台执行
    background_tasks.add_task(
        _process_material_generation,
        task_id=task_id,
        prompt=request.prompt,
        file_paths=file_paths,
        output_format=request.output_format,
    )

    return ManualResponse(
        task_id=task_id,
        status="processing",
        message="AI Agent 已开始生成文档，请稍候...",
    )


async def _process_generation(
    task_id: str,
    url: str,
    languages: list[LanguageCode],
):
    """后台处理生成任务"""
    try:
        # 更新进度：抓取数据
        logger.info(f"[{task_id}] 🔍 正在抓取产品数据: {url}")
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 10, "message": "正在抓取产品数据..."})
        product = await scraper.scrape(url)

        # 更新进度：翻译
        logger.info(f"[{task_id}] 🌐 正在翻译内容到 {[l.value for l in languages]}...")
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 40, "message": "正在翻译内容..."})
        translations = await translator.translate_product(product, languages)

        # 更新进度：生成 PDF
        logger.info(f"[{task_id}] 📄 正在生成 PDF...")
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 70, "message": "正在生成 PDF..."})
        pdf_path = pdf_generator.generate_manual(product, translations)

        # 完成
        logger.info(f"[{task_id}] ✅ 生成完成: {pdf_path}")
        tasks[task_id] = tasks[task_id].model_copy(update={"progress": 100, "status": "done", "message": "生成完成！", "pdf_path": pdf_path})

    except Exception as e:
        logger.error(f"[{task_id}] ❌ 生成失败: {e}")
        tasks[task_id] = tasks[task_id].model_copy(update={"status": "failed", "message": f"生成失败: {str(e)}"})


async def _process_material_generation(
    task_id: str,
    prompt: str,
    file_paths: list[str],
    output_format: str,
):
    """后台处理素材模式生成任务（AI Agent）"""
    logger.info(f"[{task_id}] 🤖 AI Agent 开始工作: files={file_paths}, format={output_format}")

    try:
        from src.agent.graph import run_agent

        # 更新进度
        _emit_thinking(task_id, "初始化", "AI Agent 开始工作...")
        tasks[task_id] = tasks[task_id].model_copy(update={
            "progress": 10, "message": "AI Agent 分析素材中..."
        })

        # 定义思考过程回调
        def think_callback(step: str, content: str):
            _emit_thinking(task_id, step, content)
            # 同时更新任务进度消息
            try:
                tasks[task_id] = tasks[task_id].model_copy(update={
                    "message": f"[{step}] {content}",
                })
            except Exception:
                pass

        # 运行 Agent（同步调用，因为 LangGraph 的 invoke 是同步的）
        import asyncio
        loop = asyncio.get_event_loop()
        logger.info(f"[{task_id}] ⚙️ 调用 run_agent...")

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: run_agent(
                        user_prompt=prompt,
                        file_paths=file_paths,
                        output_format=output_format,
                        think_callback=think_callback,
                    ),
                ),
                timeout=180,  # 3 分钟超时
            )
        except asyncio.TimeoutError:
            logger.error(f"[{task_id}] ⏰ Agent 执行超时（180s）")
            _emit_thinking(task_id, "错误", "Agent 执行超时（180s）")
            tasks[task_id] = tasks[task_id].model_copy(update={
                "status": "failed",
                "message": "AI Agent 执行超时（3分钟），请稍后重试",
            })
            return

        logger.info(f"[{task_id}] ✅ Agent 执行完成")
        _emit_thinking(task_id, "完成", "AI Agent 执行完成")

        # 更新进度
        tasks[task_id] = tasks[task_id].model_copy(update={
            "progress": 100, "message": "AI 文档生成完成！"
        })

        output_path = result.get("output_path")
        if output_path and Path(output_path).exists():
            logger.info(f"[{task_id}] 📄 文档已生成: {output_path}")
            _emit_thinking(task_id, "完成", f"文档已生成: {Path(output_path).name}")
            tasks[task_id] = tasks[task_id].model_copy(update={
                "status": "done",
                "pdf_path": output_path,
            })
        else:
            logger.warning(f"[{task_id}] ⚠️ Agent 未能生成文件: {output_path}")
            _emit_thinking(task_id, "错误", f"Agent 未能生成文件")
            tasks[task_id] = tasks[task_id].model_copy(update={
                "status": "failed",
                "message": f"Agent 未能生成文件。输出: {output_path}",
            })

    except Exception as e:
        logger.error(f"[{task_id}] ❌ AI Agent 生成失败: {e}")
        _emit_thinking(task_id, "错误", f"AI Agent 生成失败: {str(e)}")
        tasks[task_id] = tasks[task_id].model_copy(update={
            "status": "failed",
            "message": f"AI Agent 生成失败: {str(e)}",
        })


def start_app():
    """启动应用"""
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    start_app()
