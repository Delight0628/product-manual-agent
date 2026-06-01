# Product Manual Agent v2 — 开发计划

**日期：** 2026-05-31
**目标：** 新增「素材上传 + AI Agent 智能排版」模式，与现有亚马逊链接模式并存

---

## 一、需求分析

### 用户输入（两种模式）

| 模式 | 输入 | 说明 |
|------|------|------|
| **A. 亚马逊链接**（已有） | URL + 目标语言 | 自动抓取 → 翻译 → 生成 PDF |
| **B. 素材 + 提示词**（新增） | 图片/文本文件 + 自然语言 Prompt | 用户描述想要什么格式、怎么排版 |

### 输出格式

- PDF（已有）
- Word / .docx（新增）
- 未来可扩展：PPT、HTML

### 核心流程（模式 B）

```
用户上传素材(图片+文本) + 输入提示词
        ↓
  AI Agent 接收并分析
        ↓
  ┌─────────────────────────────┐
  │  1. 提取素材内容（OCR/读取）   │
  │  2. 理解用户意图（LLM）       │
  │  3. 规划排版结构（LLM）       │
  │  4. 生成文档内容（LLM）       │
  │  5. 调用渲染工具生成文件       │
  └─────────────────────────────┘
        ↓
  输出 PDF / Word
```

---

## 二、技术选型

### 2.1 AI Agent 框架：LangChain + LangGraph

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **LangChain + LangGraph** | 生态成熟、Tool 定义方便、Agent 状态管理好、社区活跃 | 较重、依赖多 | ✅ 推荐 |
| OpenAI 原生 Function Calling | 轻量、延迟低 | Agent 编排能力弱、多步 Tool 调用需自己写循环 | ❌ 不适合多步 Agent |
| CrewAI | 多 Agent 协作好 | 过度设计，本场景单 Agent 够用 | ❌ |
| 自研 ReAct Loop | 完全可控 | 重复造轮子、维护成本高 | ❌ |

**最终选择：LangChain + LangGraph**

理由：
1. 用户明确提到 LangChain
2. 本场景需要 Agent 循环调用多个 Tool（提取内容 → 分析意图 → 生成文档），LangGraph 的状态机模式很适合
3. 与 OpenAI 兼容接口无缝对接

### 2.2 大模型接入

```
基础 URL:   https://token-plan-sgp.xiaomimimo.com/v1
协议:       OpenAI 兼容 (chat/completions)
模型:       mimo-v2.5（全模态，支持 Vision + Text）
API Key:    存入 .env
```

LangChain 接入方式：
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://token-plan-sgp.xiaomimimo.com/v1",
    api_key=os.getenv("XIAOMI_API_KEY"),
    model="模型名称",  # 需确认
    temperature=0.3,
)
```

### 2.3 关键依赖选型

| 能力 | 工具 | 理由 |
|------|------|------|
| Agent 编排 | `langchain` + `langgraph` | 状态机管理多步 Tool 调用 |
| LLM 调用 | `langchain-openai` | 兼容 OpenAI 接口 |
| 文本提取 | `pypdf` + `python-docx` | 读取上传的 PDF/Word |
| 图片理解 | LLM Vision API | 多模态模型直接理解图片 |
| HTML 渲染 PDF | `weasyprint`（已有） | HTML → PDF，排版灵活 |
| HTML 渲染 Word | `mammoth`（反向）+ `python-docx` | HTML → Word |
| 模板引擎 | `jinja2`（已有） | 生成 HTML 模板 |
| 文件上传 | `python-multipart`（已有） | FastAPI 文件上传 |

### 2.4 最终依赖清单（新增部分）

```toml
dependencies = [
    # ... 现有依赖保持不变 ...

    # === v2 新增 ===
    "langchain>=0.3",
    "langchain-openai>=0.3",
    "langgraph>=0.4",
    "pypdf>=5.0",
    "python-docx>=1.1",
    "mammoth>=1.8",        # HTML → Word（备用）
]
```

---

## 三、架构设计

### 3.1 目录结构（新增部分用 ★ 标记）

```
D:/product-manual-agent/
├── .env                          ★ LLM 配置
├── pyproject.toml                # 更新依赖
├── src/
│   ├── models.py                 # 更新：新增 DocumentRequest 等模型
│   ├── api/
│   │   ├── main.py               # 更新：新增上传接口
│   │   └── templates/
│   │       └── index.html        # 更新：新增素材上传区域
│   ├── agent/                    ★ 新增：AI Agent 模块
│   │   ├── __init__.py
│   │   ├── graph.py              ★ Agent 状态图（LangGraph）
│   │   ├── tools.py              ★ Agent 工具集
│   │   ├── prompts.py            ★ System Prompt 模板
│   │   └── schemas.py            ★ Agent 中间数据结构
│   ├── scraper/                  # 保持不变
│   ├── translator/               # 保持不变
│   ├── pdf_generator/            # 保持不变
│   └── doc_generator/            ★ 新增：通用文档生成器
│       ├── __init__.py
│       ├── html_renderer.py      ★ HTML 模板渲染
│       ├── pdf_writer.py         ★ HTML → PDF
│       └── docx_writer.py        ★ HTML → Word
├── templates/                    ★ 新增：文档 HTML 模板
│   ├── manual.html               # 说明书模板
│   ├── report.html               # 报告模板
│   └── custom.html               # 自定义模板
└── tests/
    └── test_agent.py             ★ Agent 测试
```

### 3.2 Agent 工作流（LangGraph 状态图）

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         ↓
                ┌────────────────┐
                │  analyze_input  │ ← 分析用户输入类型
                └───────┬────────┘
                        ↓
            ┌───────────┴───────────┐
            ↓                       ↓
   ┌─────────────┐        ┌─────────────────┐
   │ amazon_flow  │        │ material_flow    │
   │ (现有逻辑)    │        │ (素材+提示词模式)  │
   └──────┬──────┘        └────────┬────────┘
          ↓                        ↓
   ┌──────────────┐       ┌────────────────┐
   │ scrape_data   │       │ extract_content │ ← 提取文件内容
   └──────┬───────┘       └────────┬───────┘
          ↓                        ↓
   ┌──────────────┐       ┌────────────────┐
   │ translate     │       │ understand_intent│ ← LLM 理解意图
   └──────┬───────┘       └────────┬───────┘
          ↓                        ↓
   ┌──────────────┐       ┌────────────────┐
   │ generate_pdf  │       │ plan_layout     │ ← LLM 规划排版
   └──────┬───────┘       └────────┬───────┘
          ↓                        ↓
          │               ┌────────────────┐
          │               │ generate_content│ ← LLM 生成内容
          │               └────────┬───────┘
          │                        ↓
          │               ┌────────────────┐
          │               │ render_document │ ← 渲染 PDF/Word
          │               └────────┬───────┘
          ↓                        ↓
          └───────────┬────────────┘
                      ↓
               ┌──────────┐
               │  OUTPUT   │
               └──────────┘
```

### 3.3 Agent Tool 定义

```python
# src/agent/tools.py

@tool
def extract_text_from_file(file_path: str) -> str:
    """从上传的文件中提取文本内容（支持 PDF/TXT/Word/Markdown）"""

@tool
def analyze_image(image_path: str) -> str:
    """使用多模态 LLM 分析图片内容，返回图片描述"""

@tool
def generate_html_from_content(content: str, layout: str, style: str) -> str:
    """根据内容和排版要求生成 HTML"""

@tool
def render_to_pdf(html_content: str, output_path: str) -> str:
    """将 HTML 渲染为 PDF 文件"""

@tool
def render_to_docx(html_content: str, output_path: str) -> str:
    """将 HTML 渲染为 Word 文件"""

@tool
def search_furniture_glossary(term: str, target_lang: str) -> str:
    """查询家具行业术语翻译（复用现有术语表）"""
```

### 3.4 API 接口设计

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/upload` | 上传素材文件，返回文件 ID |
| `POST` | `/api/generate` | **已修改**：新增 `mode` 字段，支持 `amazon` / `material` |
| `POST` | `/api/generate-material` | **新增**：素材模式专用接口 |

**新增请求模型：**

```python
class MaterialRequest(BaseModel):
    """素材模式请求"""
    prompt: str                              # 用户提示词
    file_ids: List[str] = []                 # 已上传的文件 ID
    output_format: str = "pdf"               # pdf / docx
    output_lang: Optional[LanguageCode] = None  # 可选：指定语言

class UploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    filename: str
    size: int
    content_type: str
```

### 3.5 前端 UI 改动

红框位置改为 **Tab 切换**：

```
┌──────────────────────────────────────────┐
│  [ 亚马逊链接 ]  [ 素材上传 + AI 排版 ]    │  ← Tab 切换
├──────────────────────────────────────────┤
│                                          │
│  Tab 1: 现有 Amazon 链接输入              │
│                                          │
│  Tab 2:                                 │
│  ┌────────────────────────────────────┐  │
│  │  📁 拖拽或点击上传文件              │  │
│  │  支持: PDF, Word, TXT, 图片        │  │
│  └────────────────────────────────────┘  │
│                                          │
│  💬 告诉 AI 你想要什么:                  │
│  ┌────────────────────────────────────┐  │
│  │ 例如: 帮我把这些素材整理成一份       │  │
│  │ 产品说明书，输出为 PDF 格式，        │  │
│  │ 包含封面、目录、产品介绍、           │  │
│  │ 安装说明和安全警告                   │  │
│  └────────────────────────────────────┘  │
│                                          │
│  输出格式: ○ PDF  ○ Word                 │
│                                          │
│  [ 🤖 开始生成 ]                         │
└──────────────────────────────────────────┘
```

---

## 四、开发分期

### Phase 1：基础搭建（Day 1-2）

| 任务 | 负责 | 产出 |
|------|------|------|
| 创建 `.env` 配置 LLM 连接 | backend | `.env` 文件 |
| 新增 `langchain` 等依赖 | backend | `pyproject.toml` 更新 |
| 搭建 `src/agent/` 模块骨架 | backend | Agent 基础框架 |
| 验证 LLM 连通性 | backend | `test_llm_connection.py` |

### Phase 2：Agent 核心（Day 3-5）

| 任务 | 负责 | 产出 |
|------|------|------|
| 实现 Agent Tool（文件提取、图片分析） | backend | `tools.py` |
| 实现 Agent Prompt 模板 | backend | `prompts.py` |
| 实现 LangGraph 状态图 | backend | `graph.py` |
| 实现 `POST /api/upload` 文件上传接口 | backend | API 接口 |
| 实现 `POST /api/generate-material` 接口 | backend | API 接口 |

### Phase 3：文档渲染（Day 6-7）

| 任务 | 负责 | 产出 |
|------|------|------|
| HTML 模板设计（说明书/报告/自定义） | frontend | `templates/*.html` |
| HTML → PDF 渲染（复用 weasyprint） | backend | `pdf_writer.py` |
| HTML → Word 渲染 | backend | `docx_writer.py` |
| 端到端测试 | QA | 测试通过 |

### Phase 4：前端集成（Day 8-9）

| 任务 | 负责 | 产出 |
|------|------|------|
| Tab 切换 UI（亚马逊 / 素材上传） | frontend | `index.html` 更新 |
| 文件拖拽上传组件 | frontend | 上传交互 |
| Prompt 输入区 | frontend | 文本域 |
| 输出格式选择 | frontend | Radio 按钮 |
| 进度展示（Agent 思考过程） | frontend | 实时状态 |

### Phase 5：联调 + 优化（Day 10）

| 任务 | 负责 | 产出 |
|------|------|------|
| 全流程联调 | all | 功能可用 |
| 错误处理 + 重试 | backend | 健壮性 |
| Agent 输出质量调优 | backend | Prompt 优化 |
| 文档排版美化 | frontend | 模板迭代 |

---

## 五、关键技术细节

### 5.1 LLM 连接配置

```python
# src/agent/llm.py
import os
from langchain_openai import ChatOpenAI

def get_llm(temperature=0.3):
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1"),
        api_key=os.getenv("LLM_API_KEY", ""),
        model=os.getenv("LLM_MODEL", "mimo-v2.5"),
        temperature=temperature,
    )
```

### 5.2 Agent 核心 Prompt

```
你是一个专业的文档排版助手。用户会给你一些素材文件和排版要求。

你的工作流程：
1. 分析用户上传的素材（文本、图片）
2. 理解用户的排版意图（什么格式、什么风格、包含哪些章节）
3. 规划文档结构
4. 生成完整的文档内容
5. 调用渲染工具生成最终文件

你有以下工具可用：
- extract_text: 从文件中提取文本
- analyze_image: 理解图片内容
- render_pdf: 生成 PDF
- render_docx: 生成 Word

输出要求：
- 内容完整，不遗漏素材中的信息
- 排版符合用户描述的风格
- 包含适当的标题层级、段落间距
```

### 5.3 上传文件存储

```python
# 文件保存到项目目录下
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 文件命名: {uuid}_{original_name}
# 限制: 单文件 10MB, 总共 50MB
```

### 5.4 .env 文件模板

```env
# === LLM 配置 ===
LLM_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
LLM_API_KEY=your_api_key_here
LLM_MODEL=mimo-v2.5

# === 服务配置 ===
PORT=8000
MAX_UPLOAD_SIZE_MB=10

# === 翻译 API（可选） ===
DEEPL_API_KEY=
OPENAI_API_KEY=
```

---

## 六、风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| LLM API 延迟高 | 生成时间长 | 流式输出 + 进度实时推送（SSE） |
| 素材内容过长超出上下文 | Agent 丢信息 | 分块处理 + 摘要压缩 |
| 图片理解质量差 | 排版不符合预期 | 支持用户手动补充描述 |
| Word 排版不如 PDF | 用户体验差 | 优先推 PDF，Word 作为备选 |
| Agent 死循环 | 任务卡死 | LangGraph 设置 max_steps=10 |

---

## 七、交付标准

- [ ] 两种模式（亚马逊链接 / 素材上传）可自由切换
- [ ] 上传 PDF/TXT/图片后 AI 能正确提取内容
- [ ] Prompt 输入后 AI 能理解意图并规划排版
- [ ] 输出 PDF 格式正确、排版美观
- [ ] 输出 Word 格式可用、内容完整
- [ ] 进度条实时展示 Agent 工作状态
- [ ] 错误情况有友好提示
- [ ] 单元测试覆盖核心 Tool
- [ ] Railway 部署成功，公网可访问

---

## 八、Railway 部署方案

### 8.1 为什么选 Railway

| 平台 | 优点 | 缺点 | 适合场景 |
|------|------|------|----------|
| **Railway** | 零配置部署、自动构建、$5/月免费额度、支持 Docker | 免费额度有限 | ✅ 本项目（轻量级 Python 服务） |
| Render | 免费 tier | 冷启动 30s、构建慢 | 不适合 |
| Fly.io | 边缘部署 | 配置复杂 | 不适合初期 |
| Vercel | 免费 | 不支持后台长任务 | 不适合 |

### 8.2 部署架构

```
                    ┌─────────────────┐
  用户浏览器 ──────→│   Railway CDN   │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │   FastAPI App   │ ← Railway 容器
                    │   port: 8000    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ↓              ↓              ↓
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ /api/    │  │ /api/    │  │  LLM API │ ← 外部调用
        │ generate │  │ upload   │  │  (小米)   │
        └──────────┘  └──────────┘  └──────────┘
              ↓
        ┌──────────┐
        │ output/  │ ← Railway 临时文件系统（重启丢失）
        └──────────┘
```

### 8.3 Railway 部署步骤

**Step 1：GitHub 仓库准备**

```bash
cd D:/product-manual-agent
git init
git add .
git commit -m "feat: initial product-manual-agent v2"
# 推送到 GitHub
gh repo create delight0628/product-manual-agent --public --push
```

**Step 2：Railway 配置**

1. 打开 [railway.app](https://railway.app) → GitHub 登录
2. 点击「New Project」→「Deploy from GitHub repo」
3. 选择 `product-manual-agent` 仓库
4. Railway 会自动检测 Dockerfile 并构建

**Step 3：设置环境变量**

在 Railway 项目 Dashboard → Variables 标签页添加：

```env
LLM_BASE_URL=https://token-plan-sgp.xiaomimimo.com/v1
LLM_API_KEY=你的真实 API Key
LLM_MODEL=mimo-v2.5
PORT=8000
```

**Step 4：生成自定义域名**

在 Railway 项目 → Settings → Networking → Generate Domain

会得到类似 `product-manual-agent-production.up.railway.app` 的域名。

### 8.4 Dockerfile（精简版）

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 Playwright Chromium（用于真实网页抓取）
RUN apt-get update && apt-get install -y \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libpango-1.0-0 libcairo2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.5 注意事项

| 事项 | 说明 |
|------|------|
| **文件存储** | Railway 容器重启后 `output/` 和 `uploads/` 会丢失。生产环境应接 OSS/S3。初期可接受。 |
| **冷启动** | 免费 tier 15 分钟无请求后会休眠，首次访问有 3-5s 冷启动。 |
| **构建时间** | Playwright 安装约 2-3 分钟，首次部署需等待。 |
| **日志查看** | Railway Dashboard → Deployments → 点击版本 → Logs |
| **费用** | $5/月免费额度（约 500 小时运行），超出后 $0.000463/min |

### 8.6 部署检查清单

- [ ] `.env` 文件已加入 `.gitignore`
- [ ] Dockerfile 已创建
- [ ] GitHub 仓库已推送
- [ ] Railway 项目已创建并关联 GitHub
- [ ] 环境变量已在 Railway 设置
- [ ] 首次部署成功（查看 Logs 无报错）
- [ ] 公网域名可访问
- [ ] `/api/languages` 返回正常
- [ ] 上传文件 → 生成文档 → 下载 全流程通过
