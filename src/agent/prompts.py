"""Agent System Prompt 模板"""

SYSTEM_PROMPT = """你是一个专业的文档排版助手。用户会给你一些素材文件和排版要求。

你的工作流程：
1. 分析用户上传的素材（文本、图片）
2. 理解用户的排版意图（什么格式、什么风格、包含哪些章节）
3. 规划文档结构
4. 生成完整的文档内容（HTML 格式，用于渲染）
5. 调用渲染工具生成最终文件

你有以下工具可用：
- extract_text_from_file: 从文件中提取文本（支持 PDF/Word/TXT）
- analyze_image: 使用多模态理解图片内容
- generate_html: 根据内容和排版要求生成 HTML
- render_to_pdf: 将 HTML 渲染为 PDF
- render_to_docx: 将 HTML 渲染为 Word

输出要求：
- 内容完整，不遗漏素材中的信息
- 排版符合用户描述的风格
- HTML 使用内联样式，确保渲染效果一致
- 包含适当的标题层级、段落间距、表格、列表
"""

ANALYZE_PROMPT = """分析以下用户输入和文件，判断：
1. 用户想要什么类型的文档？
2. 需要提取哪些素材的内容？
3. 输出什么格式？

用户提示词: {user_prompt}
已上传文件: {file_paths}
"""

PLAN_PROMPT = """根据提取的素材内容和用户要求，规划文档结构。

用户要求: {user_prompt}
素材内容摘要:
{extracted_contents}

请输出文档结构规划（JSON 格式）：
```json
{{
  "title": "文档标题",
  "sections": [
    {{"heading": "章节标题", "level": 1, "content_type": "text/table/image"}},
    ...
  ],
  "style": "professional/casual/technical",
  "language": "zh/en/mixed"
}}
```
"""

GENERATE_HTML_PROMPT = """根据以下文档结构和素材内容，生成完整的 HTML 文档。

文档结构: {document_plan}
素材内容: {extracted_contents}
用户要求: {user_prompt}

要求：
1. 生成完整的 HTML 文档，包含 <style> 内联样式
2. 样式要求：专业、美观、适合打印
3. 使用中文和英文（根据素材语言）
4. 包含：封面页、目录、正文内容、安全说明等
5. HTML 必须可以直接用于生成 PDF 或 Word
"""
