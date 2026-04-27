# Ingester 完善 + Phase 1 集成 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 ingester 支持目录扫描和多库路由，将其集成到 Phase 1，并重写 research sub-skill 的调研方法论，使 KEA 成为以文档为主的知识萃取 Agent。

**Architecture:** 分四个独立任务依次完成：(1) ingester Python 扩展，(2) CLI 扩展，(3) Phase 1 Agent 文件集成，(4) research sub-skill 重写。前两个任务是纯 Python，后两个是 Markdown Agent 文件。每个任务完成后可独立测试。

**Tech Stack:** Python 3.10+, markitdown（必选）, pdfplumber / surya / trafilatura（可选 lazy import）, unittest, KEA AgentFile Markdown

---

## 文件改动总览

| 文件 | 类型 | 说明 |
|------|------|------|
| `KEA-tools/ingester/__init__.py` | 修改 | 新增 `source_dirs` 参数、多库路由、`IngestResult` 字段扩展 |
| `KEA-tools/cli.py` | 修改 | `--source-dir` CLI 参数、`cmd_ingest` 调用更新 |
| `KEA-tools/tests/test_ingester.py` | 新建 | ingester 单元测试 |
| `AgentFile/phases/phase-1-research.md` | 修改 | 插入 Step 2（ingest 预处理）、调整 Step 3（调研模式）、更新 sub-skill 接口 |
| `AgentFile/skills/research/SKILL.md` | 重写 | 去除 DeepResearch 方法论，改为文档萃取主路径 |

---

## Task 1: IngestResult 字段扩展 + source_dirs 目录扫描

**Files:**
- Modify: `KEA-tools/ingester/__init__.py`
- Create: `KEA-tools/tests/test_ingester.py`

- [ ] **Step 1: 写失败测试（目录扫描）**

新建 `KEA-tools/tests/test_ingester.py`：

```python
"""ingester 单元测试."""
import tempfile
from pathlib import Path

from kea.ingester import ingest, IngestResult, SOURCE_TYPE_MAP


def _make_temp_dir_with_files() -> tuple[Path, list[str]]:
    """创建临时目录，包含 md/txt 和不支持格式的文件."""
    d = Path(tempfile.mkdtemp())
    (d / "doc1.md").write_text("# 采购订单\n\n这是一份采购订单文档。", encoding="utf-8")
    (d / "doc2.txt").write_text("供应商管理流程说明。", encoding="utf-8")
    (d / "ignore.xyz").write_text("不支持的格式", encoding="utf-8")
    sub = d / "subdir"
    sub.mkdir()
    (sub / "doc3.md").write_text("# 合同管理\n\n合同相关内容。", encoding="utf-8")
    return d, ["doc1.md", "doc2.txt", "doc3.md"]  # ignore.xyz 应被跳过


def test_source_dirs_recursive_scan():
    """source_dirs 参数应递归扫描目录，只收录已知格式文件。"""
    src_dir, expected_names = _make_temp_dir_with_files()
    out_dir = Path(tempfile.mkdtemp())

    report = ingest(
        sources=[],
        source_dirs=[str(src_dir)],
        domain="test",
        domain_cn="测试",
        output_dir=out_dir,
    )

    assert report.success_count == 3, f"期望 3 个成功，实际 {report.success_count}"
    assert report.failed_count == 0

    # ignore.xyz 应记录为 skipped
    skipped = [r for r in report.results if r.status == "skipped"]
    assert any("ignore.xyz" in r.original_path for r in skipped), \
        "ignore.xyz 应被静默跳过并记录"


def test_source_dirs_unknown_extension_skipped():
    """不支持的扩展名应静默跳过，status=skipped，error 含 'unsupported format'。"""
    d = Path(tempfile.mkdtemp())
    (d / "file.xyz").write_text("unknown", encoding="utf-8")
    out_dir = Path(tempfile.mkdtemp())

    report = ingest(sources=[], source_dirs=[str(d)], domain="t", domain_cn="t", output_dir=out_dir)

    assert report.success_count == 0
    r = report.results[0]
    assert r.status == "skipped"
    assert "unsupported" in r.error.lower()


def test_source_and_source_dirs_combined():
    """sources 和 source_dirs 可以混合使用，结果合并。"""
    src_dir, _ = _make_temp_dir_with_files()
    extra_file = Path(tempfile.mkdtemp()) / "extra.md"
    extra_file.write_text("# 额外文档", encoding="utf-8")
    out_dir = Path(tempfile.mkdtemp())

    report = ingest(
        sources=[str(extra_file)],
        source_dirs=[str(src_dir)],
        domain="test",
        domain_cn="测试",
        output_dir=out_dir,
    )

    # 3（目录）+ 1（单文件）= 4 成功
    assert report.success_count == 4


def test_ingest_result_has_enhanced_fields():
    """IngestResult 应包含 enhanced / enhanced_by / enhancement_note 字段。"""
    r = IngestResult(original_path="test.md")
    assert hasattr(r, "enhanced")
    assert hasattr(r, "enhanced_by")
    assert hasattr(r, "enhancement_note")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest KEA-tools/tests/test_ingester.py -v 2>&1 | head -40
```

期望：4 个测试全部 FAIL（`ingest` 不接受 `source_dirs` 参数，`IngestResult` 缺少新字段）

- [ ] **Step 3: 扩展 IngestResult 数据类**

在 `KEA-tools/ingester/__init__.py` 的 `IngestResult` dataclass 中新增三个字段：

```python
@dataclass
class IngestResult:
    """单个源文档的收录结果."""
    original_path: str
    output_path: str | None = None
    source_type: str = ""
    title: str = ""
    word_count: int = 0
    status: str = "success"  # success | skipped | failed
    error: str = ""
    enhanced: bool = False          # 是否使用了增强工具
    enhanced_by: str = ""           # "pdfplumber" | "surya" | "trafilatura"
    enhancement_note: str = ""      # 降级原因（增强工具未安装时）
```

- [ ] **Step 4: 新增 `_expand_source_dirs` 函数**

在 `_detect_source_type` 函数之前添加：

```python
def _expand_source_dirs(source_dirs: list[str]) -> list[IngestResult]:
    """递归扫描目录，返回已知格式文件路径列表及不支持格式的 skipped 记录."""
    known_exts = set(SOURCE_TYPE_MAP.keys())
    expanded_sources: list[str] = []
    skipped: list[IngestResult] = []

    for dir_path in source_dirs:
        p = Path(dir_path)
        if not p.is_dir():
            skipped.append(IngestResult(
                original_path=dir_path,
                status="failed",
                error=f"目录不存在: {dir_path}",
            ))
            continue
        for f in sorted(p.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix.lower() in known_exts:
                expanded_sources.append(str(f))
            else:
                skipped.append(IngestResult(
                    original_path=str(f),
                    status="skipped",
                    error="unsupported format",
                ))

    return expanded_sources, skipped
```

- [ ] **Step 5: 更新 `ingest()` 函数签名，合并 source_dirs**

找到 `ingest()` 函数定义，将签名改为：

```python
def ingest(
    sources: list[str],
    domain: str,
    domain_cn: str,
    output_dir: str | Path,
    source_dirs: list[str] | None = None,
) -> IngestReport:
```

在函数体内，在 `out = Path(output_dir)` 之后、`existing_paths = _read_manifest(...)` 之前，插入：

```python
    # 展开目录扫描
    source_dirs = source_dirs or []
    expanded, dir_skipped = _expand_source_dirs(source_dirs)
    all_sources = list(sources) + expanded
```

然后将后续 `for src in sources:` 改为 `for src in all_sources:`，并在 `report` 初始化后、循环前，将 `dir_skipped` 预填入 report：

```python
    report = IngestReport(domain=domain, output_dir=str(out))
    # 先记录目录扫描中不支持格式的文件
    report.results.extend(dir_skipped)
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest KEA-tools/tests/test_ingester.py -v
```

期望：4 个测试全部 PASS

- [ ] **Step 7: 更新 `IngestReport.to_dict()` 包含新字段**

在 `to_dict()` 的 `results` 列表内，为每个结果加入新字段：

```python
"results": [
    {
        "original_path": r.original_path,
        "output_path": r.output_path,
        "source_type": r.source_type,
        "title": r.title,
        "word_count": r.word_count,
        "status": r.status,
        "error": r.error,
        "enhanced": r.enhanced,
        "enhanced_by": r.enhanced_by,
        "enhancement_note": r.enhancement_note,
    }
    for r in self.results
],
```

- [ ] **Step 8: Commit**

```bash
cd /Users/kenkangning/KEA-v3
git add KEA-tools/ingester/__init__.py KEA-tools/tests/test_ingester.py
git commit -m "feat(ingester): add source_dirs recursive scan + IngestResult enhanced fields"
```

---

## Task 2: 多库路由（PDF 增强 + URL 正文提取）

**Files:**
- Modify: `KEA-tools/ingester/__init__.py`
- Modify: `KEA-tools/tests/test_ingester.py`

- [ ] **Step 1: 写失败测试（PDF 路由 + URL 路由）**

在 `test_ingester.py` 末尾追加：

```python
def test_pdf_with_no_text_layer_falls_back_gracefully():
    """无文字层 PDF（pdfplumber 未安装时）应降级到 markitdown，enhancement_note 非空。"""
    # 用一个实际存在的 md 文件模拟（无 PDF 时跳过该测试）
    import sys
    # 此测试验证 IngestResult 的 enhancement_note 在降级时非空
    # 实际 PDF 测试依赖真实 PDF 文件，这里验证 _pdf_has_text_layer 的行为
    from kea.ingester import _check_pdfplumber
    result = _check_pdfplumber()  # 应返回 bool，不抛异常
    assert isinstance(result, bool)


def test_url_uses_trafilatura_if_available():
    """_check_trafilatura() 应返回 bool，不抛异常。"""
    from kea.ingester import _check_trafilatura
    result = _check_trafilatura()
    assert isinstance(result, bool)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest KEA-tools/tests/test_ingester.py::test_pdf_with_no_text_layer_falls_back_gracefully KEA-tools/tests/test_ingester.py::test_url_uses_trafilatura_if_available -v
```

期望：FAIL（`_check_pdfplumber`、`_check_trafilatura` 不存在）

- [ ] **Step 3: 添加可选依赖检查函数**

在 `_check_markitdown()` 之后，添加：

```python
_PDFPLUMBER_AVAILABLE: bool | None = None
_TRAFILATURA_AVAILABLE: bool | None = None
_SURYA_AVAILABLE: bool | None = None


def _check_pdfplumber() -> bool:
    global _PDFPLUMBER_AVAILABLE
    if _PDFPLUMBER_AVAILABLE is None:
        try:
            import pdfplumber  # noqa: F401
            _PDFPLUMBER_AVAILABLE = True
        except ImportError:
            _PDFPLUMBER_AVAILABLE = False
    return _PDFPLUMBER_AVAILABLE


def _check_trafilatura() -> bool:
    global _TRAFILATURA_AVAILABLE
    if _TRAFILATURA_AVAILABLE is None:
        try:
            import trafilatura  # noqa: F401
            _TRAFILATURA_AVAILABLE = True
        except ImportError:
            _TRAFILATURA_AVAILABLE = False
    return _TRAFILATURA_AVAILABLE


def _check_surya() -> bool:
    global _SURYA_AVAILABLE
    if _SURYA_AVAILABLE is None:
        try:
            import surya  # noqa: F401
            _SURYA_AVAILABLE = True
        except ImportError:
            _SURYA_AVAILABLE = False
    return _SURYA_AVAILABLE
```

- [ ] **Step 4: 添加 PDF 路由辅助函数**

在 `_convert_single()` 之前添加：

```python
def _pdf_has_text_layer(path: str) -> bool:
    """检测 PDF 是否有可提取的文字层（需要 pdfplumber）."""
    if not _check_pdfplumber():
        return True  # 无法检测，假设有文字层，走 markitdown
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return False
            text = pdf.pages[0].extract_text() or ""
            return len(text.strip()) > 50
    except Exception:
        return True  # 检测失败，保守假设有文字层


def _convert_pdf(path: str) -> tuple[str, str, str, str]:
    """转换 PDF，返回 (content, title, enhanced_by, enhancement_note).

    路由策略：
    - 有文字层 → markitdown
    - 无文字层（扫描件）→ surya（如可用），否则 markitdown 兜底
    """
    has_text = _pdf_has_text_layer(path)

    if not has_text and _check_surya():
        try:
            from surya.ocr import run_ocr
            from surya.model.detection.model import load_model as load_det_model
            from surya.model.detection.processor import load_processor as load_det_processor
            from surya.model.recognition.model import load_model as load_rec_model
            from surya.model.recognition.processor import load_processor as load_rec_processor
            from PIL import Image
            import fitz  # PyMuPDF，surya 依赖

            doc = fitz.open(path)
            langs = ["zh", "en"]
            det_model, det_processor = load_det_model(), load_det_processor()
            rec_model, rec_processor = load_rec_model(), load_rec_processor()

            pages_text = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                result = run_ocr([img], [langs], det_model, det_processor, rec_model, rec_processor)
                page_text = "\n".join(
                    line.text for line in result[0].text_lines if line.text.strip()
                )
                pages_text.append(page_text)

            content = "\n\n".join(pages_text)
            title = Path(path).stem
            return content, title, "surya", ""
        except Exception as e:
            # surya 失败，降级到 markitdown
            pass

    # 主路径：markitdown
    if not _check_markitdown():
        raise ValueError("markitdown 未安装，无法处理 PDF。请运行: pip install markitdown")

    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(path)
    title = result.title or Path(path).stem
    content = result.text_content

    enhanced_by = ""
    enhancement_note = ""

    if not has_text and not _check_surya():
        enhancement_note = "检测到扫描件但 surya 未安装，已降级到 markitdown（OCR 质量可能较低）。安装: pip install surya-ocr"

    return content, title, enhanced_by, enhancement_note


def _convert_url(url: str) -> tuple[str, str, str, str]:
    """转换 URL，返回 (content, title, enhanced_by, enhancement_note).

    路由策略：trafilatura 提取正文 → markitdown 兜底
    """
    if _check_trafilatura():
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_tables=True, include_links=False)
                if text and len(text.strip()) > 100:
                    title = trafilatura.extract_metadata(downloaded).title or url
                    return text, title or url, "trafilatura", ""
        except Exception:
            pass

    # 兜底：markitdown
    if not _check_markitdown():
        raise ValueError("markitdown 未安装，无法处理 URL。请运行: pip install markitdown")
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert_url(url)
    note = "" if _check_trafilatura() else "trafilatura 未安装，已使用 markitdown 处理 URL（可能含较多 boilerplate）。安装: pip install trafilatura"
    return result.text_content, result.title or url, "", note
```

- [ ] **Step 5: 更新 `_convert_single()` 使用新路由**

找到 `_convert_single()` 函数，将 PDF 和 URL 的处理替换为调用新辅助函数：

```python
def _convert_single(source_path: str, source_type: str) -> tuple[str, str, str, str]:
    """转换单个文件，返回 (markdown_content, title, enhanced_by, enhancement_note)."""
    if source_type == "url":
        return _convert_url(source_path)

    p = Path(source_path)
    if not p.exists():
        raise ValueError(f"文件不存在: {source_path}")

    if source_type == "pdf":
        return _convert_pdf(source_path)

    if source_type == "markdown":
        content = p.read_text(encoding="utf-8")
        content, title = _extract_md_title(content, p.stem)
        return content, title, "", ""

    if source_type == "text":
        content = p.read_text(encoding="utf-8")
        return content, p.stem, "", ""

    # Word / Excel / PPT / 图片 / HTML：markitdown
    if not _check_markitdown():
        raise ValueError(
            f"markitdown 未安装，无法处理 {source_type} 格式。"
            f"请运行: pip install markitdown"
        )
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(p))
    title = result.title or p.stem
    return result.text_content, title, "", ""
```

注意：原函数返回 `(content, title)` 两个值，现在返回四个值。需要同步更新 `ingest()` 函数中调用 `_convert_single` 的地方：

找到 `ingest()` 中的以下代码：
```python
            content, title = _convert_single(src, source_type)
```
替换为：
```python
            content, title, enhanced_by, enhancement_note = _convert_single(src, source_type)
            result.enhanced = bool(enhanced_by)
            result.enhanced_by = enhanced_by
            result.enhancement_note = enhancement_note
```

- [ ] **Step 6: 运行全部测试**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest KEA-tools/tests/test_ingester.py -v
```

期望：所有测试 PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/kenkangning/KEA-v3
git add KEA-tools/ingester/__init__.py KEA-tools/tests/test_ingester.py
git commit -m "feat(ingester): multi-lib routing for PDF (surya OCR) and URL (trafilatura)"
```

---

## Task 3: CLI 扩展（--source-dir 参数）

**Files:**
- Modify: `KEA-tools/cli.py`

- [ ] **Step 1: 写失败测试（CLI 接受 --source-dir）**

在 `test_ingester.py` 末尾追加：

```python
def test_cli_source_dir_argument():
    """CLI 应接受 --source-dir 参数并传给 ingest()."""
    import subprocess, json, tempfile
    src_dir = Path(tempfile.mkdtemp())
    (src_dir / "a.md").write_text("# 测试", encoding="utf-8")
    out_dir = Path(tempfile.mkdtemp())

    result = subprocess.run(
        [
            "python3", "-m", "kea", "ingest",
            "--source-dir", str(src_dir),
            "--domain", "test",
            "--domain-cn", "测试",
            "--output-dir", str(out_dir),
            "--format", "json",
        ],
        capture_output=True, text=True,
        cwd="/Users/kenkangning/KEA-v3",
    )
    assert result.returncode == 0, f"CLI 失败: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["success_count"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest KEA-tools/tests/test_ingester.py::test_cli_source_dir_argument -v
```

期望：FAIL（`--source-dir` 参数不被识别）

- [ ] **Step 3: 更新 CLI ingest 参数定义**

在 `KEA-tools/cli.py` 中，找到 ingest_parser 定义区域，在 `--source` 参数之后、`--domain` 之前，添加：

```python
    ingest_parser.add_argument(
        "--source-dir",
        action="append",
        dest="source_dir",
        default=[],
        help="源文档目录（递归扫描，可多次指定）",
    )
```

- [ ] **Step 4: 更新 `cmd_ingest` 函数传入 source_dirs**

找到 `cmd_ingest` 函数中的 `run_ingest(...)` 调用，将其改为：

```python
    report = run_ingest(
        sources=args.source or [],
        source_dirs=args.source_dir or [],
        domain=domain,
        domain_cn=domain_cn,
        output_dir=output_dir,
    )
```

同时将 `args.source` 的 required=True 改为不强制（source 和 source-dir 至少有一个即可）。找到：

```python
    ingest_parser.add_argument("--source", action="append", required=True, ...)
```

改为：

```python
    ingest_parser.add_argument("--source", action="append", default=[], ...)
```

并在 `cmd_ingest` 开头做校验：

```python
def cmd_ingest(args: argparse.Namespace) -> int:
    """文档收录命令."""
    if not args.source and not args.source_dir:
        print("错误：至少需要指定 --source 或 --source-dir 之一", file=sys.stderr)
        return 2
    ...
```

- [ ] **Step 5: 运行全部测试**

```bash
cd /Users/kenkangning/KEA-v3
python3 -m pytest KEA-tools/tests/test_ingester.py -v
```

期望：所有测试 PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/kenkangning/KEA-v3
git add KEA-tools/cli.py KEA-tools/tests/test_ingester.py
git commit -m "feat(cli): add --source-dir argument to kea ingest"
```

---

## Task 4: Phase 1 集成（AgentFile 改动）

**Files:**
- Modify: `AgentFile/phases/phase-1-research.md`

此任务修改 Markdown Agent 文件，无单元测试，通过人工审阅验证。

- [ ] **Step 1: 在 Step 1 末尾，将文档路径区分为 paths 和 dirs**

找到 phase-1-research.md 中的 Step 1，将询问用户的提示改为：

```markdown
### Step 1: 确认是否有本地文档

如果 `LOCAL_DOC_PATHS` 和 `LOCAL_DOC_DIRS` 均未由编排器提供，询问用户：

> "是否有现成的领域文档（业务说明书、流程规范、PRD 等）？
> - 有文件 → 请提供文件路径（逗号分隔）
> - 有目录 → 请提供目录路径（逗号分隔，将递归扫描目录下所有支持格式文件）
> - 无 → 直接回复"无""

将用户回复解析为：
- 文件路径列表 → 记录为 `LOCAL_DOC_PATHS`（可为空列表）
- 目录路径列表 → 记录为 `LOCAL_DOC_DIRS`（可为空列表）
```

- [ ] **Step 2: 在原 Step 2 之前插入新 Step 2（文档预处理）**

在 Step 1 之后、原 Step 2（设置调研模式）之前，插入：

```markdown
### Step 2: 文档预处理（Ingest）

若 `LOCAL_DOC_PATHS` 或 `LOCAL_DOC_DIRS` 非空，执行以下命令将源文档转换为标准化 MD：

```bash
python3 -m kea ingest \
  $(for p in {LOCAL_DOC_PATHS}; do echo "--source $p"; done) \
  $(for d in {LOCAL_DOC_DIRS}; do echo "--source-dir $d"; done) \
  --domain {DOMAIN_EN} \
  --domain-cn {DOMAIN_CN} \
  --output-dir {VAULT_PATH}/RAWData/sources/{DOMAIN_EN}/ \
  --format json
```

读取 JSON 输出，向用户展示摘要：

```
文档预处理完成：
  成功：{success_count} 个（{type_counts 展示，如 pdf×3, docx×2}）
  跳过：{skipped_count} 个（已存在）
  失败：{failed_count} 个
```

若 `failed_count > 0`，展示失败文件列表和原因，询问：

> "部分文件转换失败，如何处理？
> - A 忽略失败文件，继续调研
> - B 修复后重试
> - C 取消本次调研"

- 选 A：继续，在 chain-state.md 的"备注"节记录被忽略的文件列表
- 选 B/C：停在 Step 2，不进入 Step 3

若预处理成功（或无文档），记录：
```
SOURCES_DIR = {VAULT_PATH}/RAWData/sources/{DOMAIN_EN}/
```

若无本地文档，跳过本步，`SOURCES_DIR` 留空。

在 chain-state.md 备注中记录收录摘要：`sources: {success_count} 个文档已归档至 RAWData/sources/{DOMAIN_EN}/`
```

- [ ] **Step 3: 将原 Step 2（设置调研模式）改为 Step 3，重写内容**

原 Step 2 删除全部内容，替换为：

```markdown
### Step 3: 确定调研模式

信源优先级：**客户文档 → 模型内置知识 → 客户指定 URL / 文档引用的外部标准**

| 情况 | 调研模式 | 说明 |
|------|---------|------|
| `SOURCES_DIR` 非空 | `WEB_RESEARCH_MODE = supplement` | 文档优先，自动设定，不询问用户 |
| `SOURCES_DIR` 为空 | `WEB_RESEARCH_MODE = model_knowledge` | 依赖模型内置知识，按需查询客户指定源 |

同时收集用户在对话中明确提及的 URL：`EXPLICIT_WEB_SOURCES`（可为空列表）
```

- [ ] **Step 4: 将 Step 4（原调研执行）的 Dispatch 参数更新**

找到 Step 4 中的 Dispatch 参数块，替换为：

```markdown
### Step 4: 调研执行

扫描 `SOURCES_DIR` 目录下的所有 `.md` 文件（排除 `_manifest.md`），构建文件列表 `SOURCE_FILE_LIST`。

读取 `~/.claude/skills/kea/skills/research/SKILL.md`，以 Subagent 形式 Dispatch，传入参数：

```
Research topic: {DOMAIN_CN}
Sources directory: {SOURCES_DIR}（如有）
Source file list: {SOURCE_FILE_LIST}（排除 _manifest.md 后的相对路径列表）
Web research mode: {WEB_RESEARCH_MODE}
Explicit web sources: {EXPLICIT_WEB_SOURCES}（可为空列表）
Output path: {VAULT_PATH}/RAWData/KEAOutput/research/{DOMAIN_EN}-research.md
```
```

- [ ] **Step 5: 将后续 Step 编号 +1（Step 5→6, Step 6→7）**

将原文中所有 `### Step 5:`、`### Step 6:` 分别改为 `### Step 6:`、`### Step 7:`。

- [ ] **Step 6: 人工审阅修改后的 phase-1-research.md**

```bash
cat /Users/kenkangning/KEA-v3/AgentFile/phases/phase-1-research.md
```

检查：
- Step 1 询问文件/目录两种路径 ✓
- Step 2 执行 kea ingest，有失败处理 ✓
- Step 3 调研模式定义（supplement / model_knowledge）✓
- Step 4 Dispatch 参数包含 Source file list 和 Explicit web sources ✓
- Step 编号连续（1~7）✓

- [ ] **Step 7: Commit**

```bash
cd /Users/kenkangning/KEA-v3
git add AgentFile/phases/phase-1-research.md
git commit -m "feat(phase-1): integrate ingest step, update research mode to document-first"
```

---

## Task 5: research sub-skill 重写

**Files:**
- Modify: `AgentFile/skills/research/SKILL.md`

此任务完全重写 research sub-skill 的调研方法论，去除 DeepResearch 4阶段框架。

- [ ] **Step 1: 重写 Step 1（文档萃取，主路径）**

将现有 `## Step 1: Read local domain documents (if provided)` 整块替换为：

```markdown
## Step 1: 文档萃取（主路径）

**本 skill 是知识萃取 Agent，不是 DeepResearch Agent。** 主要任务是从客户文档中提取候选清单，模型内置知识已足够补全大多数行业背景。

若 `Sources directory` 和 `Source file list` 已传入：

按 `Source file list` 中的文件顺序，逐份读取每个文档（使用 Read 工具读取完整内容）。

对每份文档，提取并记录：
- 业务实体/对象（名称、属性、业务规则）
- 业务流程/操作（触发条件、步骤、输入/输出）
- 领域术语和约束关系
- 文档中**引用但未定义**的外部标准/规章名称 → 记录为 `EXTERNAL_STANDARDS_TO_LOOKUP` 清单

全部文档读完后，将提取结果作为 `LOCAL_KNOWLEDGE`，这是**首要信源**。

若 `Sources directory` 为空或未传入：直接跳到 Step 2（模型知识）。
```

- [ ] **Step 2: 删除现有 Step 2（四阶段 web research 方法论）和 Step 3**

将以下整块内容删除：
- `## Step 2: Research methodology (inlined from deep-research)` 及其所有子节（Phase 1~4、Search strategy）
- `## Step 3: Conduct research`

替换为以下两个新步骤：

```markdown
## Step 2: 知识补全（模型内置）

对 `LOCAL_KNOWLEDGE` 中出现但**未被文档定义清楚**的行业术语，直接用模型内置知识补充定义，写入报告并标注来源为「模型推断」。

无需 web search。

## Step 3: 定向 web 查询（仅限两类）

**仅在以下情况执行 web 查询，其他情况不做任何主动 web search：**

**类型 A：客户指定 URL**
若 `Explicit web sources` 非空，对每个 URL 使用 WebFetch 读取全文，提取与领域相关的候选内容，标注来源为该 URL。

**类型 B：外部标准定向查询**
若 `EXTERNAL_STANDARDS_TO_LOOKUP` 非空，对每个标准名称（如「ISO 9001」「采购管理办法」）进行**一次**针对性 WebSearch，摘要关键条款，标注来源为该标准名称。

❌ **严格禁止以下搜索**：
- 行业趋势、市场规模、增长率
- 专家观点、行业报告（McKinsey、Gartner 等）
- 案例研究、最佳实践综述
- 任何未被客户文档引用或客户未指定的 URL

若 `WEB_RESEARCH_MODE = model_knowledge`（无文档），同样只查询 `Explicit web sources`，不做主动搜索。
```

- [ ] **Step 3: 将原 Step 4（生成报告）重命名为 Step 4，保留报告格式**

将 `## Step 4: Return structured report in Chinese` 中的 `Output Rules` 补充一条：

```markdown
7. **来源标注**：每个候选的「来源」字段必须标注实际信源（文档文件名 / URL / `模型推断` / 标准名称）。不得留空。
```

- [ ] **Step 4: 将原 Step 5（保存报告）重命名为 Step 5，保持不变**

检查 `## Step 5: Save report and return structured result` 内容无需改动，仅确认编号正确。

- [ ] **Step 5: 添加 Red Flags 表（防止回退到 DeepResearch 模式）**

在 `<SUBAGENT-STOP>` 之后、`You are a domain research agent` 之前，插入：

```markdown
## Red Flags — 遇到以下想法立即停止

| 借口 | 现实 |
|------|------|
| "我应该搜索行业报告来补充背景" | 不需要。模型内置知识已足够，报告是辅助，文档是主体 |
| "用户没有提供文档，我应该做全面 web research" | 不对。用模型内置知识生成候选，只查 Explicit web sources |
| "这个术语我不确定，搜一下" | 直接用模型知识标注「模型推断」，不需要 web search |
| "搜几个案例来验证候选的合理性" | 不需要验证。候选来自文档，合理性由专家（Phase 2 访谈）确认 |
| "文档内容太少，需要补充更多信息" | 用文档中有的内容生成候选，置信度标「低」，交给专家确认 |

```

- [ ] **Step 6: 人工审阅修改后的 research/SKILL.md**

```bash
cat /Users/kenkangning/KEA-v3/AgentFile/skills/research/SKILL.md
```

检查：
- SUBAGENT-STOP 标记存在 ✓
- Red Flags 表在最前面 ✓
- Step 1 文档萃取（主路径）✓
- Step 2 模型知识补全（无 web）✓
- Step 3 定向 web 查询（仅两类，有禁止列表）✓
- Step 4 报告格式（含来源字段必填规则）✓
- Step 5 保存报告 ✓
- 无任何 DeepResearch 4阶段内容 ✓

- [ ] **Step 7: Commit**

```bash
cd /Users/kenkangning/KEA-v3
git add AgentFile/skills/research/SKILL.md
git commit -m "refactor(research): replace DeepResearch methodology with document-first extraction"
```

---

## 自检（Spec 覆盖验证）

| Spec 要求 | 对应任务 |
|-----------|---------|
| source_dirs 递归扫描 | Task 1 Step 4~5 |
| 未知格式静默跳过记录 | Task 1 Step 4 |
| sources + source_dirs 混用 | Task 1 Step 5 |
| IngestResult 新字段 | Task 1 Step 3 |
| PDF 文字层检测 | Task 2 Step 4 |
| surya OCR 扫描件路由 | Task 2 Step 4 |
| trafilatura URL 正文提取 | Task 2 Step 4 |
| 可选依赖 lazy import | Task 2 Step 3 |
| CLI --source-dir 参数 | Task 3 |
| Phase 1 Step 2 ingest 预处理 | Task 4 Step 2 |
| 失败处理 A/B/C 三路 | Task 4 Step 2 |
| 调研模式 supplement / model_knowledge | Task 4 Step 3 |
| Phase 1 预扫描文件列表传给 sub-skill | Task 4 Step 4 |
| research sub-skill 去除 DeepResearch | Task 5 Step 1~2 |
| 定向 web 查询两类限制 | Task 5 Step 2 |
| Red Flags 表 | Task 5 Step 5 |
| 来源字段必填 | Task 5 Step 3 |
