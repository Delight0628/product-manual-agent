"""PDF 写入器 — 使用 WeasyPrint 将 HTML 渲染为 PDF"""

import logging
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class PDFWriter:
    """将 HTML 内容渲染为 PDF 文件。

    用法::

        writer = PDFWriter()
        writer.write("<html><body><h1>Hello</h1></body></html>", "output.pdf")
    """

    def __init__(self):
        self._weasyprint_available = None

    def _check_weasyprint(self) -> bool:
        """检查 weasyprint 是否安装"""
        if self._weasyprint_available is None:
            try:
                import weasyprint  # noqa: F401
                self._weasyprint_available = True
            except ImportError:
                self._weasyprint_available = False
                logger.warning("weasyprint 未安装，PDF 输出将不可用。请运行: pip install weasyprint")
        return self._weasyprint_available

    def write(
        self,
        html_content: str,
        output_path: Union[str, Path],
        base_url: Optional[str] = None,
    ) -> Path:
        """将 HTML 渲染为 PDF 文件。

        Args:
            html_content: 完整的 HTML 文档字符串
            output_path: 输出 PDF 文件路径
            base_url: HTML 资源（图片、CSS）的基准 URL，默认为当前目录

        Returns:
            生成的 PDF 文件路径

        Raises:
            ImportError: weasyprint 未安装时
            Exception: PDF 渲染失败时
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._check_weasyprint():
            # 回退：保存为 HTML 文件
            fallback_path = output_path.with_suffix(".html")
            fallback_path.write_text(html_content, encoding="utf-8")
            raise ImportError(
                f"weasyprint 未安装，已将 HTML 保存到: {fallback_path}\n"
                "请安装 weasyprint: pip install weasyprint"
            )

        try:
            from weasyprint import HTML

            kwargs = {}
            if base_url:
                kwargs["base_url"] = base_url

            HTML(string=html_content, **kwargs).write_pdf(str(output_path))
            logger.info("PDF 已生成: %s", output_path)
            return output_path
        except Exception as e:
            # 回退：保存为 HTML
            fallback_path = output_path.with_suffix(".html")
            fallback_path.write_text(html_content, encoding="utf-8")
            logger.error("PDF 渲染失败: %s，已保存为 HTML: %s", e, fallback_path)
            raise
