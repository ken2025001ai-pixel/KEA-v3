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


def test_check_pdfplumber_returns_bool():
    """_check_pdfplumber() 应返回 bool，不抛异常（不管是否安装）。"""
    from kea.ingester import _check_pdfplumber
    result = _check_pdfplumber()
    assert isinstance(result, bool)


def test_check_trafilatura_returns_bool():
    """_check_trafilatura() 应返回 bool，不抛异常（不管是否安装）。"""
    from kea.ingester import _check_trafilatura
    result = _check_trafilatura()
    assert isinstance(result, bool)


def test_cli_source_dir_argument():
    """CLI 应接受 --source-dir 参数并传给 ingest()."""
    import subprocess
    import json
    src_dir = Path(tempfile.mkdtemp())
    (src_dir / "a.md").write_text("# 测试", encoding="utf-8")
    out_dir = Path(tempfile.mkdtemp())

    result = subprocess.run(
        [
            "python3", "-m", "kea",
            "--format", "json",
            "ingest",
            "--source-dir", str(src_dir),
            "--domain", "test",
            "--domain-cn", "测试",
            "--output-dir", str(out_dir),
        ],
        capture_output=True, text=True,
        cwd="/Users/kenkangning/KEA-v3",
    )
    assert result.returncode == 0, f"CLI 失败: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["success_count"] == 1
