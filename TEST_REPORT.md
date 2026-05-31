# Product Manual Agent — Web UI 测试报告

**测试日期：** 2026-05-31  
**测试环境：** http://localhost:8001  
**测试员：** qa-engineer  
**测试范围：** Web UI 全流程 + API 接口

---

## Executive Summary

| 指标 | 数值 |
|------|------|
| 发现问题总数 | 10 |
| Critical | 1 |
| High | 3 |
| Medium | 4 |
| Low | 2 |
| 测试用例通过率 | 7/10 (70%) |

**结论：** 核心功能可用，但存在依赖缺失、输入验证不足等问题，需修复后方可交付。

---

## 缺陷列表

### BUG-001: fpdf2 未声明为依赖 [Critical]

**分类：** Functional / Dependency  
**URL：** 项目配置文件  
**描述：** 代码 `src/pdf_generator/pdf_generator.py` 第 9 行 `from fpdf import FPDF`，但 `pyproject.toml` 和 `requirements.txt` 均未声明 `fpdf2` 依赖。

**复现步骤：**
1. 全新环境 `pip install -r requirements.txt`
2. 运行服务并尝试生成 PDF

**预期结果：** PDF 正常生成  
**实际结果：** `ModuleNotFoundError: No module named 'fpdf'`，回退到纯文本输出

**影响：** 新用户无法获得 PDF 输出，只能得到 .txt 和 .json 文件

**修复建议：** 在 `pyproject.toml` 和 `requirements.txt` 中添加 `fpdf2`

---

### BUG-002: API 不验证空 languages 数组 [High]

**分类：** Functional / Validation  
**URL：** POST `/api/generate`  
**描述：** API 接受空 `languages` 数组 `{"url":"...", "languages":[]}`，不返回错误，正常执行生成任务。

**复现步骤：**
```bash
curl -X POST http://localhost:8001/api/generate \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.amazon.com/dp/B0TEST","languages":[]}'
```

**预期结果：** 返回 422 Validation Error，提示至少选择一种语言  
**实际结果：** 返回 200，任务正常执行，生成空内容的说明书

**影响：** 用户可能误操作生成无意义文件，浪费资源

**修复建议：** 在 `ManualRequest` 模型中添加 `min_length=1` 验证：
```python
languages: List[LanguageCode] = Field(..., min_length=1)
```

---

### BUG-003: output 目录使用相对路径 [High]

**分类：** Functional / Path  
**URL：** `src/api/main.py` 第 46、109、122 行  
**描述：** `PDFGenerator(output_dir="output")` 和文件下载/列表接口均使用相对路径 `Path("output")`，依赖进程工作目录。

**复现步骤：**
1. 在 `/home/user` 目录启动服务
2. 生成 PDF
3. 文件实际写入 `/home/user/output/` 而非项目目录

**预期结果：** 输出目录固定在项目 `output/` 下  
**实际结果：** 输出位置随启动目录变化

**影响：** 部署时文件位置不可预测，下载接口可能找不到文件

**修复建议：** 使用 `Path(__file__).parent.parent.parent / "output"` 或配置化

---

### BUG-004: 端口硬编码为 8000 [High]

**分类：** Functional / Configuration  
**URL：** `src/api/main.py` 第 170 行  
**描述：** `start_app()` 硬编码 `port=8000`，无法通过环境变量或参数修改。

**复现步骤：**
1. 8000 端口被占用时启动服务
2. 报错 `Address already in use`

**预期结果：** 支持配置端口（环境变量或命令行参数）  
**实际结果：** 直接崩溃

**影响：** 部署灵活性差，与其他服务冲突时无法调整

**修复建议：** 
```python
import os
port = int(os.environ.get("PORT", 8000))
uvicorn.run(app, host="0.0.0.0", port=port)
```

---

### BUG-005: 直接修改 Pydantic 模型属性 [Medium]

**分类：** Functional / Compatibility  
**URL：** `src/api/main.py` 第 142-148 行  
**描述：** 代码 `tasks[task_id].progress = 10` 直接修改 Pydantic model 属性。Pydantic v2 默认 `model_config = ConfigDict(frozen=False)` 可工作，但若启用 `frozen=True` 或 `model_config` 变更则会报错。

**复现步骤：** 升级 Pydantic 到 v2 并启用 frozen 模式

**预期结果：** 使用 `model_copy(update=...)` 或 `setattr` 安全更新  
**实际结果：** 可能抛出 `ValidationError`

**影响：** Pydantic 版本升级时可能 breaking change

**修复建议：** 使用 `tasks[task_id] = tasks[task_id].model_copy(update={"progress": 10})`

---

### BUG-006: 测试覆盖不足 [Medium]

**分类：** Quality / Testing  
**URL：** `tests/test_basic.py`  
**描述：** `test_pdf_generator` 仅断言 `output_dir.exists()`，未验证 PDF 是否成功生成、内容是否正确。

**复现步骤：** 运行 `pytest tests/test_basic.py -v`

**预期结果：** 测试应验证 PDF 文件存在、大小 > 0、格式正确  
**实际结果：** 测试通过但不验证实际输出

**影响：** 无法发现 PDF 生成回归问题

**修复建议：** 
```python
def test_pdf_generator():
    generator = PDFGenerator(output_dir="output/test")
    product = ProductData(...)
    translations = {LanguageCode.EN: TranslatedContent(...)}
    path = generator.generate_manual(product, translations)
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
```

---

### BUG-007: Mock 翻译质量差 [Medium]

**分类：** Content / Quality  
**URL：** `src/translator/translator.py` 第 208-231 行  
**描述：** Mock 模式仅在文本前添加 `[DE]`、`[FR]` 等前缀，不是真实翻译。Demo 演示时用户体验差。

**复现步骤：** 使用 Mock 模式生成多语言说明书

**预期结果：** Mock 模式应提供合理的占位翻译  
**实际结果：** 输出 `[DE] Solid Wood Dining Table` 而非 `Massivholz Esstisch`

**影响：** Demo 演示效果不佳，无法展示产品价值

**修复建议：** 为 Mock 模式内置常见词汇的真实翻译映射

---

### BUG-008: 安装说明/安全警告缺少 IT/FR/ES [Medium]

**分类：** Content / Completeness  
**URL：** `src/pdf_generator/pdf_generator.py` 第 149-171 行  
**描述：** `installation_steps` 字典只定义了 EN/DE/JP 三种语言，缺少 IT/FR/ES。PDF 中这些语言会回退到英文。

**复现步骤：** 生成包含 IT/FR/ES 语言的说明书

**预期结果：** 每种支持的语言都有对应的安装说明  
**实际结果：** IT/FR/ES 使用英文安装说明

**影响：** 多语言说明书不完整

**修复建议：** 补全 IT/FR/ES 的安装说明和安全警告翻译

---

### BUG-009: CORS 配置过于宽松 [Low]

**分类：** Security / CORS  
**URL：** `src/api/main.py` 第 32-38 行  
**描述：** `allow_origins=["*"]` 允许所有来源访问 API。

**预期结果：** 生产环境应限制允许的域名  
**实际结果：** 任何网站都可调用 API

**影响：** 潜在的 CSRF 和数据泄露风险

**修复建议：** 生产环境配置具体域名，开发环境保留 `*`

---

### BUG-010: 无 API 速率限制 [Low]

**分类：** Security / Rate Limiting  
**URL：** 所有 API 端点  
**描述：** API 无速率限制，可被恶意高频调用。

**预期结果：** 应有基本的速率限制  
**实际结果：** 无限制

**影响：** 可能被滥用导致服务不可用

**修复建议：** 添加 `slowapi` 或类似中间件

---

## 测试通过项

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 页面加载 | ✅ | 主页面正常渲染，渐变背景、表单布局正确 |
| HTML5 表单验证 | ✅ | 空 URL 提交时显示"请填写此字段" |
| Mock 数据生成 | ✅ | 输入 B0DEFAULT/B0COUCH01/B0SHELF01 均正常 |
| 任务轮询 | ✅ | 进度条从 0% 到 100%，状态正确更新 |
| PDF 下载 | ✅ | `/api/download/{filename}` 正常返回 PDF 文件 |
| 文件列表 | ✅ | `/api/files` 正确返回已生成文件 |
| Swagger UI | ✅ | `/docs` 正常渲染，所有端点可见 |
| 404 处理 | ✅ | 不存在的任务/文件返回正确错误信息 |
| 语言列表 | ✅ | `/api/languages` 返回 6 种语言 |

---

## 截图证据

| 文件 | 说明 |
|------|------|
| `tests/screenshots/01-homepage.png` | 主页面布局 |
| `tests/screenshots/02-generation-success.png` | 生成成功状态 |
| `tests/screenshots/03-empty-validation.png` | 空表单验证 |
| `tests/screenshots/04-swagger-ui.png` | Swagger API 文档 |

---

## 测试未覆盖项

- Playwright 真实亚马逊页面抓取（仅测试了 Mock 模式）
- DeepL/OpenAI 真实翻译 API（未配置 API Key）
- 并发任务处理
- 大文件上传/超长 URL
- 浏览器兼容性（仅测试了 Chromium）
- 移动端响应式布局

---

## 修复优先级建议

1. **立即修复：** BUG-001（依赖缺失）、BUG-002（输入验证）
2. **尽快修复：** BUG-003（路径问题）、BUG-004（端口配置）
3. **计划修复：** BUG-005 ~ BUG-008
4. **后续优化：** BUG-009、BUG-010
