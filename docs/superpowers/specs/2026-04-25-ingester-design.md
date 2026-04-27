# Ingester 功能完善设计文档

**日期**：2026-04-25  
**状态**：待实现  
**范围**：KEA-tools/ingester 模块扩展 + AgentFile/phases/phase-1-research.md + skills/research/SKILL.md 重构

---

## 背景

ingester 模块已有基础实现：支持多格式文档→标准化 MD 转换，依赖 markitdown，提供 CLI 命令 `kea ingest`。

**定位原则**：KEA 是专业的知识萃取 Agent，不是通用 DeepResearch Agent。Phase 1 调研的目的是从业务文档中萃取候选清单，模型自身知识已足够支撑大多数领域，web search 仅用于客户明确指定的信息源或文档中引用的外部标准。

本次目标：
1. **ingester 功能完整性**：支持目录扫描，引入 pdfplumber / surya / trafilatura 提升处理能力
2. **Phase 1 集成**：Phase 1 收到本地文档后先 ingest，再将标准化 MD 传给 research sub-skill
3. **research sub-skill 重构**：去除 DeepResearch 方法论，改为以文档萃取为核心，web search 仅限客户指定信息源

---

## 一、ingester 功能扩展

### 1.1 目录扫描

CLI 新增 `--source-dir` 参数，与现有 `--source` 并存，可混用：

```bash
# 目录扫描
python3 -m kea ingest --source-dir ./raw-docs/ --domain caigou --domain-cn 采购 --output-dir ./sources/caigou/

# 混合使用
python3 -m kea ingest --source-dir ./raw-docs/ --source https://example.com/guide --domain caigou --domain-cn 采购 --output-dir ./sources/caigou/
```

**实现**：
- `ingest()` 函数新增 `source_dirs: list[str] = []` 参数
- 递归展开：遍历目录下所有文件，只收录 `SOURCE_TYPE_MAP` 中已知扩展名的文件
- 未知扩展名文件静默跳过，在 JSON 输出中记录 `status: "skipped"` + `error: "unsupported format"`
- `source_dirs` 展开后合并到 `sources` 列表，走同一 `IngestResult` 数据结构

### 1.2 多库路由策略

在 `_convert_single()` 内部，按格式和内容特征选择最合适的工具：

```
PDF 文件
  ├─ 文字层存在？
  │    ├─ 是 → markitdown 主转换
  │    │        + pdfplumber 检测并提取表格 → 以标准 Markdown 表格格式覆盖插入
  │    └─ 否（扫描件）→ surya-ocr 提取文字 → 封装为 Markdown
URL
  → trafilatura 提取正文 → markitdown 兜底（trafilatura 失败或返回空时）
Word / Excel / PPT / 图片 / HTML / 其他
  → markitdown（原有逻辑不变）
```

**依赖分层（避免破坏现有用户）**：
- **必选**：`markitdown`（已有）
- **可选，lazy import**：`pdfplumber`、`surya`、`trafilatura`
  - 未安装时降级到 markitdown，`IngestResult` 中标注 `enhanced: false` 及原因
  - 安装即自动启用，无需配置

**PDF 文字层检测**：使用 `pdfplumber` 打开 PDF，检查第一页 `extract_text()` 是否返回有效内容（非空且字符数 > 50）。`pdfplumber` 未安装时跳过检测，直接走 markitdown。

### 1.3 IngestResult 字段扩展

新增字段：
```python
enhanced: bool = True       # 是否使用了增强工具
enhanced_by: str = ""       # 使用了哪个增强工具（"pdfplumber", "surya", "trafilatura"）
enhancement_note: str = ""  # 降级原因（增强工具未安装时记录）
```

---

## 二、Phase 1 集成

### 2.1 改动位置

`AgentFile/phases/phase-1-research.md`

在现有 **Step 1（确认本地文档）** 和原 **Step 2（设置调研模式）** 之间，插入新的 **Step 2：文档预处理（Ingest）**，原 Step 2 顺延为 Step 3，其余步骤编号顺延。

### 2.2 新 Step 2：文档预处理

若 `LOCAL_DOC_PATHS` 或 `LOCAL_DOC_DIRS` 非空，执行：

```bash
python3 -m kea ingest \
  [--source <path> ...]       \  # 来自 LOCAL_DOC_PATHS
  [--source-dir <dir> ...]    \  # 来自 LOCAL_DOC_DIRS
  --domain {DOMAIN_EN}        \
  --domain-cn {DOMAIN_CN}     \
  --output-dir {VAULT_PATH}/RAWData/sources/{DOMAIN_EN}/ \
  --format json
```

读取 JSON 输出，向用户展示摘要：

```
文档预处理完成：
  成功：5 个（pdf×3, docx×2）
  跳过：1 个（已存在）
  失败：0 个

源文档已归档至：RAWData/sources/{DOMAIN_EN}/
```

将 `SOURCES_DIR = {VAULT_PATH}/RAWData/sources/{DOMAIN_EN}/` 写入阶段变量。

**失败处理**（`failed_count > 0`）：
- 展示失败文件列表和原因
- 询问：**A 忽略失败文件继续** / **B 修复后重试** / **C 取消本次调研**
- 选 A：继续，在 chain-state 备注节记录被忽略的文件
- 选 B/C：停在 Step 2，不进入 Step 3

### 2.3 调研模式重定义（原 Step 2 → Step 3）

信源优先级：**客户文档 → 模型内置知识 → 客户指定 URL / 外部标准**

| 情况 | 调研模式 | 说明 |
|------|---------|------|
| 有 `SOURCES_DIR` | `WEB_RESEARCH_MODE = supplement` | 文档优先，自动设为补充模式，不询问 |
| 无本地文档 | `WEB_RESEARCH_MODE = model_knowledge` | 依赖模型内置知识，按需查询客户指定源 |

移除原来"是否进行网络调研"的询问。

### 2.4 research sub-skill 接口变更与重构

**接口变更**：Phase 1 传给 research sub-skill 的参数：

原：
```
Local document paths: {LOCAL_DOC_PATHS}
Web research mode: {WEB_RESEARCH_MODE}
```

改为：
```
Sources directory: {SOURCES_DIR}         ← 已转换的标准化 MD 目录（有文档时传入）
Source file list: [file1.md, file2.md]   ← Phase 1 预扫描（排除 _manifest.md），直接告知子任务有哪些文件
Web research mode: supplement            ← 有文档时固定传入
Explicit web sources: {用户在对话中指定的 URL 列表，可为空}
```

**research sub-skill 行为重构**（需重写 skills/research/SKILL.md 的 Step 1~3）：

```
Step 1: 文档萃取（主路径）
  - 按 Source file list 逐份读取文档
  - 从每份文档中提取候选对象/逻辑/动作/规则，标注来源文件
  - 遇到文档中引用的外部标准/规章名称 → 记录为"待查外部标准"清单

Step 2: 知识补全（模型内置）
  - 对文档中提到但未定义的行业术语，用模型内置知识补充定义
  - 无需 web search，直接写入报告并标注「模型推断」

Step 3: 定向 web 查询（仅限以下两类）
  - 类型 A：Explicit web sources — 客户明确指定的 URL，直接 WebFetch 读取全文
  - 类型 B：待查外部标准 — 文档引用了具体标准名称（如「ISO 9001」「采购管理办法」），搜索并摘要关键条款
  - ❌ 禁止：行业趋势、市场规模、专家观点、案例研究、"McKinsey report" 类泛化搜索
```

**NEEDS_CONTEXT 触发条件更新**：
- `SOURCES_DIR` 传入但目录为空 → 返回 `NEEDS_CONTEXT: SOURCES_DIR 目录为空，无可读文档`
- `Source file list` 中的文件不存在 → 返回 `NEEDS_CONTEXT: 文件 X 不存在`

**无文档时（model_knowledge 模式）**：
- 跳过 Step 1，直接用模型内置知识生成候选清单
- 仅查询 Explicit web sources（如有）
- 不做任何主动 web 搜索

### 2.5 Vault 目录结构新增

```
{VAULT_PATH}/RAWData/
  ├── sources/
  │   └── {domain}/              ← ingest 输出（新增）
  │       ├── _manifest.md       ← 收录清单（自动维护）
  │       ├── spec-v2.md         ← 转换后的标准化 MD
  │       └── guide.md
  └── KEAOutput/                  ← 原有，不变
```

---

## 三、不在本次范围内

- ingester 单元测试（`KEA-tools/tests/` 目前为空，后续独立补充）
- Phase 2 及后续阶段对 `SOURCES_DIR` 的利用
- ingester 的 markitdown 可选附加依赖的安装脚本（用户手动 pip install）

---

## 四、文件改动清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `KEA-tools/ingester/__init__.py` | 修改 | 新增 `source_dirs` 参数、多库路由、`IngestResult` 字段扩展 |
| `KEA-tools/cli.py` | 修改 | 新增 `--source-dir` CLI 参数 |
| `AgentFile/phases/phase-1-research.md` | 修改 | 插入 Step 2（ingest）、调整 Step 3（调研模式）、更新 sub-skill 接口 |
| `AgentFile/skills/research/SKILL.md` | **重写** | 去除 DeepResearch 4阶段方法论；改为文档萃取主路径 + 模型知识补全 + 定向 web 查询（仅客户指定源和外部标准） |
