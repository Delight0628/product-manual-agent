"""LangGraph Agent 状态图 — 智能文档生成工作流"""

import json
from pathlib import Path
from typing import Literal, Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, END

from src.agent.schemas import AgentState
from src.agent.prompts import SYSTEM_PROMPT, ANALYZE_PROMPT, PLAN_PROMPT
from src.agent.tools import (
    extract_text_from_file,
    analyze_image,
    generate_html,
    render_to_pdf,
    render_to_docx,
    search_furniture_glossary,
)

# Agent 所有工具
TOOLS = [
    extract_text_from_file,
    analyze_image,
    generate_html,
    render_to_pdf,
    render_to_docx,
    search_furniture_glossary,
]

MAX_STEPS = 10  # 防止 Agent 死循环

# 全局思考过程回调（用于 SSE 流式输出）
_think_callback: Optional[Callable[[str, str], None]] = None


def set_think_callback(callback: Callable[[str, str], None]):
    """设置思考过程回调函数，用于实时流式输出

    Args:
        callback: 回调函数，接收 (step_name, content) 两个参数
    """
    global _think_callback
    _think_callback = callback


def _emit_think(step: str, content: str):
    """发送思考过程到回调"""
    if _think_callback:
        try:
            _think_callback(step, content)
        except Exception:
            pass  # 回调失败不影响主流程


def _call_llm(state: AgentState, prompt: str, max_retries: int = 2) -> str:
    """调用 LLM 的通用方法（带重试）"""
    import time
    from src.agent.llm import get_llm_safe
    llm = get_llm_safe(temperature=0.3)
    if not llm:
        print("[Agent] LLM 不可用，跳过", flush=True)
        return ""
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state.get("messages", []) + [
        HumanMessage(content=prompt)
    ]
    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            print(f"[Agent] LLM 调用失败 (attempt {attempt+1}/{max_retries+1}): {e}", flush=True)
            if attempt < max_retries:
                time.sleep(2)
    print("[Agent] LLM 调用全部失败", flush=True)
    return ""


# === 节点函数 ===

def analyze_input(state: AgentState) -> dict:
    """分析用户输入，判断文件类型和需要提取的内容"""
    file_paths = state.get("file_paths", [])
    user_prompt = state.get("user_prompt", "")

    _emit_think("分析素材", f"正在分析 {len(file_paths)} 个文件...")

    contents = []
    for fp in file_paths:
        path = Path(fp)
        _emit_think("分析素材", f"处理文件: {path.name}")
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            # 图片文件：用 LLM 分析
            _emit_think("分析素材", f"使用多模态 LLM 分析图片: {path.name}")
            desc = analyze_image.invoke({"image_path": fp})
            contents.append(f"[图片 {path.name}]\n{desc}")
            _emit_think("分析素材", f"✓ 图片分析完成: {path.name}")
        else:
            # 文本文件：直接提取
            _emit_think("分析素材", f"提取文本内容: {path.name}")
            text = extract_text_from_file.invoke({"file_path": fp})
            contents.append(f"[文件 {path.name}]\n{text[:3000]}")  # 限制长度
            _emit_think("分析素材", f"✓ 文本提取完成: {path.name} ({len(text)} 字符)")

    _emit_think("分析素材", f"✓ 共提取 {len(contents)} 个文件内容")

    return {
        "extracted_contents": contents,
        "messages": [AIMessage(content=f"已分析 {len(file_paths)} 个文件，提取了内容。")],
    }


def plan_layout(state: AgentState) -> dict:
    """LLM 规划文档结构"""
    extracted = "\n\n".join(state.get("extracted_contents", []))
    user_prompt = state.get("user_prompt", "")

    _emit_think("规划结构", "正在根据素材和用户要求规划文档结构...")
    _emit_think("规划结构", f"用户指令: {user_prompt[:100]}")

    prompt = PLAN_PROMPT.format(
        user_prompt=user_prompt,
        extracted_contents=extracted[:5000],
    )

    _emit_think("规划结构", "调用 LLM 进行文档结构规划...")
    plan = _call_llm(state, prompt)
    _emit_think("规划结构", f"✓ 文档结构规划完成")

    return {
        "document_plan": plan,
        "messages": [AIMessage(content=f"文档结构规划完成。")],
    }


def generate_content(state: AgentState) -> dict:
    """LLM 生成 HTML 文档内容"""
    extracted = "\n\n".join(state.get("extracted_contents", []))
    plan = state.get("document_plan", "")
    user_prompt = state.get("user_prompt", "")

    _emit_think("生成内容", "正在生成 HTML 文档内容...")

    prompt = f"""根据以下信息生成完整的 HTML 文档。

用户要求: {user_prompt}

文档结构规划:
{plan[:3000]}

素材内容:
{extracted[:6000]}

要求：
1. 生成完整 HTML，包含 <style> 内联样式
2. 专业、美观、适合打印/阅读
3. 支持中英文混排
4. 如素材是产品相关，包含：封面、产品介绍、规格参数、安装说明、安全警告
"""

    from src.agent.llm import get_llm_safe
    llm = get_llm_safe(temperature=0.3)
    if not llm:
        # 回退模式：直接组装内容
        _emit_think("生成内容", "LLM 不可用，使用回退模式...")
        html = _fallback_html(state)
        return {
            "generated_html": html,
            "messages": [AIMessage(content="LLM 不可用，使用回退模式生成。")],
        }

    _emit_think("生成内容", "调用 LLM 生成 HTML 文档...")
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state.get("messages", []) + [
        HumanMessage(content=prompt)
    ]
    response = llm.invoke(messages)

    html = response.content
    # 提取 HTML
    if "```html" in html:
        html = html.split("```html")[1].split("```")[0]
    elif "```" in html:
        html = html.split("```")[1].split("```")[0]

    _emit_think("生成内容", f"✓ HTML 文档生成完成 ({len(html)} 字符)")

    return {
        "generated_html": html.strip(),
        "messages": [AIMessage(content="HTML 文档内容已生成。")],
    }


def render_document(state: AgentState) -> dict:
    """根据生成的 HTML 渲染最终文档（PDF 或 Word）"""
    html = state.get("generated_html", "")
    output_format = state.get("output_format", "pdf")

    if not html:
        _emit_think("渲染文档", "无内容可渲染")
        return {"output_path": None, "messages": [AIMessage(content="无内容可渲染。")]}

    # 生成文件名
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_doc_{timestamp}"

    _emit_think("渲染文档", f"正在渲染 {output_format.upper()} 文件...")

    if output_format == "docx":
        result = render_to_docx.invoke({
            "html_content": html,
            "output_filename": f"{filename}.docx",
        })
    else:
        result = render_to_pdf.invoke({
            "html_content": html,
            "output_filename": f"{filename}.pdf",
        })

    _emit_think("渲染文档", f"✓ 文档渲染完成: {Path(result).name if result else '失败'}")

    return {
        "output_path": result,
        "messages": [AIMessage(content=f"文档已生成: {result}")],
    }


def _fallback_html(state: AgentState) -> str:
    """LLM 不可用时的回退 HTML"""
    extracted = "\n\n".join(state.get("extracted_contents", []))
    user_prompt = state.get("user_prompt", "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
body {{ font-family: 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; line-height: 1.8; }}
h1 {{ color: #1a1a2e; border-bottom: 2px solid #4361ee; padding-bottom: 10px; }}
h2 {{ color: #4361ee; margin-top: 30px; }}
.content {{ white-space: pre-wrap; background: #f8f9fc; padding: 20px; border-radius: 8px; }}
.prompt {{ color: #666; font-style: italic; margin-bottom: 20px; }}
.note {{ background: #fff3cd; border: 1px solid #ffc107; padding: 12px; border-radius: 6px; margin-top: 30px; font-size: 13px; }}
</style>
</head>
<body>
<h1>Document</h1>
<p class="prompt">User request: {user_prompt}</p>
<div class="content">{extracted}</div>
<div class="note">⚠️ 此文档由回退模式生成（LLM 不可用）。请配置 LLM_API_KEY 以启用 AI 智能排版。</div>
</body>
</html>"""


# === 条件路由 ===

def should_continue(state: AgentState) -> Literal["analyze_input", "plan_layout", "generate_content", "render_document", "__end__"]:
    """根据状态决定下一步"""
    steps = len(state.get("messages", []))
    if steps >= MAX_STEPS:
        return END

    if not state.get("extracted_contents"):
        return "analyze_input"
    if not state.get("document_plan"):
        return "plan_layout"
    if not state.get("generated_html"):
        return "generate_content"
    if not state.get("output_path"):
        return "render_document"
    return END


# === 构建 Graph ===

def build_graph():
    """构建 LangGraph 状态图"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("analyze_input", analyze_input)
    graph.add_node("plan_layout", plan_layout)
    graph.add_node("generate_content", generate_content)
    graph.add_node("render_document", render_document)

    # 设置入口
    graph.set_entry_point("analyze_input")

    # 添加边（线性流程 + 条件终止）
    graph.add_edge("analyze_input", "plan_layout")
    graph.add_edge("plan_layout", "generate_content")
    graph.add_edge("generate_content", "render_document")
    graph.add_edge("render_document", END)

    return graph.compile()


# === 便捷入口 ===

def run_agent(user_prompt: str, file_paths: list, output_format: str = "pdf",
              think_callback: Optional[Callable[[str, str], None]] = None) -> dict:
    """运行 Agent，返回结果

    Args:
        user_prompt: 用户指令
        file_paths: 素材文件路径列表
        output_format: 输出格式 (pdf/docx)
        think_callback: 思考过程回调函数，接收 (step_name, content)
    """
    # 设置回调
    set_think_callback(think_callback)

    try:
        graph = build_graph()

        initial_state: AgentState = {
            "user_prompt": user_prompt,
            "file_paths": file_paths,
            "output_format": output_format,
            "extracted_contents": [],
            "document_plan": None,
            "generated_html": None,
            "output_path": None,
            "messages": [],
        }

        result = graph.invoke(initial_state, {"recursion_limit": MAX_STEPS})
        return result
    finally:
        # 清除回调
        set_think_callback(None)
