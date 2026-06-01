"""Agent 状态定义"""

from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """LangGraph Agent 的共享状态"""
    # 用户输入
    user_prompt: str
    file_paths: List[str]
    output_format: str  # "pdf" / "docx"

    # Agent 工作流中间结果
    extracted_contents: List[str]  # 从文件提取的文本/图片描述
    document_plan: Optional[str]  # LLM 规划的文档结构
    generated_html: Optional[str]  # 生成的 HTML 内容
    output_path: Optional[str]  # 最终输出文件路径

    # LangGraph 消息历史
    messages: Annotated[List[BaseMessage], add_messages]
