#!/usr/bin/env python3
"""启动脚本"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.main import start_app

if __name__ == "__main__":
    print("=" * 50)
    print("Product Manual Agent - 多语言产品说明书生成器")
    print("=" * 50)
    print()
    print("启动服务中...")
    print("访问 http://localhost:8000 使用 Web 界面")
    print("访问 http://localhost:8000/docs 查看 API 文档")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 50)

    start_app()
