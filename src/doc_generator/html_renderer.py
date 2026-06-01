"""HTML 渲染器 — 使用 Jinja2 将结构化内容渲染为 HTML 文档"""

import logging
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# 默认模板目录
DEFAULT_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


class HTMLRenderer:
    """使用 Jinja2 渲染 HTML 模板。

    用法::

        renderer = HTMLRenderer()
        html = renderer.render(content_dict, template_name="manual")
    """

    def __init__(self, templates_dir: Optional[Path | str] = None):
        """
        Args:
            templates_dir: Jinja2 模板目录路径，默认为项目根目录下的 templates/
        """
        self.templates_dir = Path(templates_dir) if templates_dir else DEFAULT_TEMPLATES_DIR

        if not self.templates_dir.exists():
            logger.warning("模板目录不存在: %s，将使用内置简易模板", self.templates_dir)

        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, content_dict: dict[str, Any], template_name: str = "manual") -> str:
        """将结构化内容字典渲染为 HTML。

        Args:
            content_dict: 文档内容，结构如下::

                {
                    "title": "文档标题",
                    "subtitle": "副标题（可选）",
                    "metadata": {
                        "author": "作者",
                        "date": "2024-01-01",
                        "version": "1.0",
                        "language": "zh-CN"
                    },
                    "sections": [
                        {
                            "heading": "章节标题",
                            "level": 1,
                            "type": "text|list|table|warning",
                            "body": "正文内容（文本或 HTML 片段）",
                            "items": ["列表项1", "列表项2"],  # type=list 时使用
                            "columns": [["列1","列2"], ["值1","值2"]],  # type=table 时使用
                        }
                    ]
                }

            template_name: 模板名称（不含 .html 后缀）

        Returns:
            渲染后的完整 HTML 字符串
        """
        # 填充默认值
        content_dict = self._apply_defaults(content_dict)

        # 选择模板
        try:
            template = self.env.get_template(f"{template_name}.html")
        except Exception:
            logger.warning("模板 %s.html 不存在，使用内置模板", template_name)
            return self._render_fallback(content_dict)

        try:
            return template.render(**content_dict)
        except Exception as e:
            logger.error("模板渲染失败: %s", e)
            return self._render_fallback(content_dict)

    def _apply_defaults(self, content: dict[str, Any]) -> dict[str, Any]:
        """填充默认字段"""
        content.setdefault("title", "Untitled Document")
        content.setdefault("subtitle", "")
        content.setdefault("metadata", {})
        content["metadata"].setdefault("author", "")
        content["metadata"].setdefault("date", "")
        content["metadata"].setdefault("version", "1.0")
        content["metadata"].setdefault("language", "zh-CN")

        # 为每个 section 添加默认值
        for section in content.get("sections", []):
            section.setdefault("heading", "")
            section.setdefault("level", 1)
            section.setdefault("type", "text")
            section.setdefault("body", "")
            section.setdefault("list_items", [])
            section.setdefault("columns", [])

        return content

    def _render_fallback(self, content: dict[str, Any]) -> str:
        """内置简易模板回退"""
        meta = content.get("metadata", {})
        sections_html = ""

        for section in content.get("sections", []):
            level = section.get("level", 2)
            heading = section.get("heading", "")
            body = section.get("body", "")
            sec_type = section.get("type", "text")

            if sec_type == "heading":
                sections_html += f'<h{level}>{body}</h{level}>\n'
            elif heading:
                sections_html += f'<h{level}>{heading}</h{level}>\n'

            if sec_type == "text":
                sections_html += f'<p>{body}</p>\n'
            elif sec_type == "list":
                items = section.get("list_items", [])
                sections_html += "<ul>\n"
                for item in items:
                    sections_html += f"  <li>{item}</li>\n"
                sections_html += "</ul>\n"
            elif sec_type == "table":
                columns = section.get("columns", [])
                if columns:
                    sections_html += '<table border="1" cellpadding="8" cellspacing="0">\n'
                    for row in columns:
                        sections_html += "  <tr>"
                        for cell in row:
                            sections_html += f"<td>{cell}</td>"
                        sections_html += "</tr>\n"
                    sections_html += "</table>\n"
            elif sec_type == "warning":
                sections_html += f'<div class="warning">{body}</div>\n'

        return f"""<!DOCTYPE html>
<html lang="{meta.get('language', 'zh-CN')}">
<head>
<meta charset="UTF-8">
<title>{content.get('title', '')}</title>
<style>
  body {{ font-family: 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
         max-width: 800px; margin: 40px auto; padding: 0 20px;
         line-height: 1.8; color: #333; }}
  h1 {{ color: #1a1a2e; border-bottom: 2px solid #4361ee; padding-bottom: 10px; }}
  .warning {{ background: #fff3cd; border-left: 4px solid #ffc107;
              padding: 12px 16px; margin: 16px 0; border-radius: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f5f5f5; }}
</style>
</head>
<body>
  <h1>{content.get('title', '')}</h1>
  {sections_html}
</body>
</html>"""
