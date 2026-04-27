"""KEA ingester — 文档归一化模块.

将各种格式的源文档（PDF/Word/Excel/PPT/HTML/图片/URL）转换为
标准化 Markdown，写入 sources/{domain}/ 目录。

核心依赖: markitdown (Microsoft 开源)
设计原则: 纯工具，零 LLM 调用，确定性输出
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# markitdown 延迟导入（安装检查）
# ---------------------------------------------------------------------------

_MARKITDOWN_AVAILABLE: bool | None = None


def _check_markitdown() -> bool:
    global _MARKITDOWN_AVAILABLE
    if _MARKITDOWN_AVAILABLE is None:
        try:
            from markitdown import MarkItDown  # noqa: F401
            _MARKITDOWN_AVAILABLE = True
        except ImportError:
            _MARKITDOWN_AVAILABLE = False
    return _MARKITDOWN_AVAILABLE


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


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

SOURCE_TYPE_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".html": "html",
    ".htm": "html",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".csv": "csv",
    ".json": "json",
    ".xml": "xml",
    ".md": "markdown",
    ".txt": "text",
}


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


@dataclass
class IngestReport:
    """批量收录的汇总报告."""
    results: list[IngestResult] = field(default_factory=list)
    domain: str = ""
    output_dir: str = ""

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.status == "success")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    def to_dict(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for r in self.results:
            if r.status == "success":
                type_counts[r.source_type] = type_counts.get(r.source_type, 0) + 1
        return {
            "command": "ingest",
            "success": self.failed_count == 0,
            "domain": self.domain,
            "output_dir": self.output_dir,
            "total": len(self.results),
            "success_count": self.success_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "type_counts": type_counts,
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
        }


# ---------------------------------------------------------------------------
# YAML front matter 生成（无 PyYAML 依赖）
# ---------------------------------------------------------------------------

def _yaml_value(v: Any) -> str:
    """将 Python 值转为简单 YAML 标量."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(str(i) for i in v) + "]"
    # 字符串：含特殊字符时加引号
    s = str(v)
    if any(c in s for c in ":#{}[]|>&*!%@`'\"\\,\n"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _build_front_matter(fields: dict[str, Any]) -> str:
    """构建 YAML front matter 字符串（不含 --- 分隔符）."""
    lines = []
    for k, v in fields.items():
        lines.append(f"{k}: {_yaml_value(v)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 文件名处理
# ---------------------------------------------------------------------------

def _sanitize_filename(name: str, max_len: int = 60) -> str:
    """将原始文件名/URL 转为安全的文件名."""
    stem = Path(name).stem if "/" not in name or name.startswith("/") else name
    if name.startswith("http"):
        from urllib.parse import urlparse
        parsed = urlparse(name)
        stem = parsed.path.strip("/").replace("/", "-") or parsed.hostname or "url"
    stem = re.sub(r"[^\w\u4e00-\u9fff\-.]", "-", stem)
    stem = re.sub(r"-+", "-", stem).strip("-")
    return stem[:max_len] if stem else "untitled"


def _unique_path(directory: Path, stem: str, suffix: str = ".md") -> Path:
    """确保文件名不冲突."""
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        candidate = directory / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


# ---------------------------------------------------------------------------
# Manifest 管理
# ---------------------------------------------------------------------------

def _read_manifest(manifest_path: Path) -> set[str]:
    """读取 manifest 中已收录的 original_path 集合."""
    if not manifest_path.exists():
        return set()
    content = manifest_path.read_text(encoding="utf-8")
    paths: set[str] = set()
    for line in content.splitlines():
        if line.startswith("|") and not line.startswith("| 序号") and not line.startswith("|---"):
            cols = [c.strip() for c in line.split("|")]
            if len(cols) >= 5:
                paths.add(cols[4])
    return paths


def _write_manifest(
    manifest_path: Path,
    results: list[IngestResult],
    domain: str,
    domain_cn: str,
) -> None:
    """写入/更新 manifest 文件."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    existing_rows: list[str] = []
    next_idx = 1
    if manifest_path.exists():
        content = manifest_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("|") and not line.startswith("| 序号") and not line.startswith("|---"):
                cols = [c.strip() for c in line.split("|")]
                if len(cols) >= 5 and cols[1].isdigit():
                    existing_rows.append(line)
                    next_idx = int(cols[1]) + 1

    new_rows: list[str] = []
    for r in results:
        if r.status == "success":
            fname = Path(r.output_path).name if r.output_path else ""
            row = f"| {next_idx} | {fname} | {r.source_type} | {r.original_path} | {r.title} | ~{r.word_count} | {today} |"
            new_rows.append(row)
            next_idx += 1

    all_rows = existing_rows + new_rows
    total = len(all_rows)

    fm = _build_front_matter({
        "type": "kea-source-manifest",
        "domain": domain,
        "domain_cn": domain_cn,
        "total_sources": total,
        "last_updated": now,
        "tags": ["kea-source"],
    })

    lines = [
        "---",
        fm,
        "---",
        "",
        f"# {domain_cn} 源文档清单",
        "",
        "| 序号 | 文件名 | 来源类型 | 原始路径 | 标题 | 字数 | 收录时间 |",
        "|------|--------|---------|---------|------|------|---------|",
    ]
    lines.extend(all_rows)
    lines.append("")

    manifest_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 目录扫描
# ---------------------------------------------------------------------------

def _expand_source_dirs(source_dirs: list[str]) -> tuple[list[str], list[IngestResult]]:
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


# ---------------------------------------------------------------------------
# 核心转换
# ---------------------------------------------------------------------------

def _detect_source_type(path: str) -> str:
    """根据路径/URL 推断源类型."""
    if path.startswith("http://") or path.startswith("https://"):
        return "url"
    ext = Path(path).suffix.lower()
    return SOURCE_TYPE_MAP.get(ext, "text")


def _extract_md_title(content: str, fallback: str) -> tuple[str, str]:
    """从 markdown 内容中提取标题并去除 front matter，返回 (content, title)."""
    title = fallback
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm_text = content[3:end].strip()
            for line in fm_text.splitlines():
                if line.startswith("title:"):
                    title = line[6:].strip().strip("'\"")
                    break
                if line.startswith("name:"):
                    title = line[5:].strip().strip("'\"")
                    break
            content = content[end + 3:].strip()
    return content, title


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
        except Exception:
            pass  # surya 失败，降级到 markitdown

    # 主路径：markitdown
    if not _check_markitdown():
        raise ValueError("markitdown 未安装，无法处理 PDF。请运行: pip install markitdown")

    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(path)
    title = result.title or Path(path).stem
    content = result.text_content

    enhancement_note = ""
    if not has_text and not _check_surya():
        enhancement_note = (
            "检测到扫描件但 surya 未安装，已降级到 markitdown（OCR 质量可能较低）。"
            "安装: pip install surya-ocr"
        )

    return content, title, "", enhancement_note


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
                    meta = trafilatura.extract_metadata(downloaded)
                    title = (meta.title if meta else None) or url
                    return text, title, "trafilatura", ""
        except Exception:
            pass

    # 兜底：markitdown
    if not _check_markitdown():
        raise ValueError("markitdown 未安装，无法处理 URL。请运行: pip install markitdown")
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert_url(url)
    note = (
        ""
        if _check_trafilatura()
        else (
            "trafilatura 未安装，已使用 markitdown 处理 URL（可能含较多 boilerplate）。"
            "安装: pip install trafilatura"
        )
    )
    return result.text_content, result.title or url, "", note


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


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def ingest(
    sources: list[str],
    domain: str,
    domain_cn: str,
    output_dir: str | Path,
    source_dirs: list[str] | None = None,
) -> IngestReport:
    """批量收录源文档.

    Args:
        sources: 源文件路径或 URL 列表
        domain: 领域英文名（DOMAIN_EN）
        domain_cn: 领域中文名
        output_dir: 输出目录（sources/{domain}/）
        source_dirs: 递归扫描的源目录列表（可选）

    Returns:
        IngestReport 包含每个源的处理结果
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "_manifest.md"

    # 展开目录扫描
    source_dirs = source_dirs or []
    expanded, dir_skipped = _expand_source_dirs(source_dirs)
    all_sources = list(sources) + expanded

    existing_paths = _read_manifest(manifest_path)

    report = IngestReport(domain=domain, output_dir=str(out))
    # 先记录目录扫描中不支持格式的文件
    report.results.extend(dir_skipped)
    today = datetime.now().strftime("%Y-%m-%d")

    for src in all_sources:
        src = src.strip()
        if not src:
            continue

        if src in existing_paths:
            report.results.append(IngestResult(
                original_path=src,
                status="skipped",
                error="已存在于 manifest 中",
            ))
            continue

        source_type = _detect_source_type(src)
        result = IngestResult(original_path=src, source_type=source_type)

        try:
            content, title, enhanced_by, enhancement_note = _convert_single(src, source_type)
            result.enhanced = bool(enhanced_by)
            result.enhanced_by = enhanced_by
            result.enhancement_note = enhancement_note
            result.title = title
            result.word_count = len(content)

            stem = _sanitize_filename(src)
            output_path = _unique_path(out, stem)

            fm = _build_front_matter({
                "type": "kea-source",
                "source_type": source_type,
                "original_path": src,
                "domain": domain,
                "title": title,
                "converted_at": today,
                "word_count": len(content),
                "tags": ["kea-source"],
            })

            file_content = f"---\n{fm}\n---\n\n# {title}\n\n{content}\n"
            output_path.write_text(file_content, encoding="utf-8")

            result.output_path = str(output_path)
            result.status = "success"

        except Exception as e:
            result.status = "failed"
            result.error = str(e)

        report.results.append(result)

    _write_manifest(manifest_path, report.results, domain, domain_cn)

    return report
