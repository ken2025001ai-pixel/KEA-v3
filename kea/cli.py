"""KEA 统一命令行入口 — Python 确定性工具层.

设计原则：
1. 纯工具，不编排工作流、不调用 LLM、不处理用户交互
2. 所有命令支持 --format json，供 Agent 平台机器消费
3. 输入是文件/目录，输出是 JSON 或人类可读文本
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from kea.generator.registry_meta import RegistryMetaGenerator
from kea.generator.skill_generator import SkillGenerator
from kea.indexer.ontology_indexer import OntologyIndexer
from kea.parser.document_parser import DocumentParser
from kea.parser.mermaid_parser import parse_file as parse_mermaid_file
from kea.tracer.pseudocode_executor import ExecutionTrace, PseudocodeExecutor
from kea.tracer.scenario_generator import Scenario, generate_scenarios
from kea.validator.contract_validator import ContractValidator
from kea.validator.rule_validator import RuleValidator
from kea.validator.state_validator import StateValidator

from kea.ingester import ingest as run_ingest


# ---------------------------------------------------------------------------
# 输出辅助
# ---------------------------------------------------------------------------

class OutputFormatter:
    """统一输出格式化器."""

    def __init__(self, fmt: str) -> None:
        self.fmt = fmt

    def print(self, data: dict[str, Any]) -> None:
        if self.fmt == "json":
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            self._print_human(data)

    def _print_human(self, data: dict[str, Any]) -> None:
        """人类可读格式（各命令自行实现详细输出）."""
        pass


def _json_out(data: dict[str, Any]) -> None:
    """输出 JSON 并确保是最后一个 stdout 输出."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

def cmd_parse(args: argparse.Namespace) -> int:
    """解析命令."""
    parser = DocumentParser()
    target = Path(args.target)

    documents: list[dict[str, Any]] = []

    if target.is_file():
        doc = parser.parse_file(target)
        documents.append(_doc_to_dict(doc))
    else:
        docs = parser.parse_directory(target)
        for doc in docs:
            documents.append(_doc_to_dict(doc))

    if args.format == "json":
        _json_out({
            "command": "parse",
            "success": True,
            "count": len(documents),
            "documents": documents,
        })
    else:
        print(f"✅ 已解析 {len(documents)} 个文档")
        for d in documents:
            print(f"  - {d['type']}/{d['id']}: {d['name']}")

    return 0


def _doc_to_dict(doc: Any) -> dict[str, Any]:
    """将 KnowledgeDocument 转为可序列化字典（精简版）."""
    return {
        "id": doc.id,
        "type": doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type),
        "name": doc.name,
        "english_name": doc.english_name,
        "aliases": doc.aliases,
        "relations": [
            {"target": r.target, "type": r.type, "cardinality": r.cardinality, "description": r.description}
            for r in doc.relations
        ],
        "properties": [
            {"name": p.name, "english_name": p.english_name, "type": p.type, "is_primary_key": p.is_primary_key}
            for p in doc.properties
        ],
        "inputs": [
            {"name": i.name, "type": i.type, "required": i.required, "description": i.description}
            for i in doc.inputs
        ],
        "outputs": [
            {"name": o.name, "type": o.type, "description": o.description}
            for o in doc.outputs
        ],
        "preconditions": doc.preconditions,
        "postconditions": doc.postconditions,
        "rollback_rules": doc.rollback_rules,
        "boundary_conditions": [
            {"scenario": b.scenario, "handling": b.handling}
            for b in doc.boundary_conditions
        ],
        "state_transitions": [
            {"from": s.from_state, "to": s.to_state, "trigger": s.trigger}
            for s in doc.state_transitions
        ],
        "pseudocode": doc.pseudocode,
        "mermaid_diagram": doc.mermaid_diagram,
        "file_path": doc.file_path,
    }


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> int:
    """校验命令."""
    target = Path(args.target)
    parser = DocumentParser()

    # 加载所有文档用于交叉引用
    all_docs: dict[str, Any] = {}
    if target.is_dir():
        docs = parser.parse_directory(target)
    else:
        docs = [parser.parse_file(target)]

    for doc in docs:
        if doc.id:
            all_docs[doc.id] = doc

    rule_validator = RuleValidator(all_docs)
    contract_validator = ContractValidator(all_docs)
    state_validator = StateValidator()

    reports_data: list[dict[str, Any]] = []
    for doc in docs:
        report = rule_validator.validate(doc)
        if doc.doc_type.value in ("logic", "action"):
            report.issues.extend(contract_validator.validate(doc).issues)
        if doc.doc_type.value == "object":
            report.issues.extend(state_validator.validate(doc).issues)
        reports_data.append(report.to_dict())

    total_issues = sum(r["summary"]["total"] for r in reports_data)
    total_errors = sum(r["summary"]["errors"] for r in reports_data)
    total_warnings = sum(r["summary"]["warnings"] for r in reports_data)
    total_infos = sum(r["summary"]["infos"] for r in reports_data)

    if args.format == "json":
        _json_out({
            "command": "validate",
            "success": total_errors == 0,
            "total_docs": len(reports_data),
            "total_issues": total_issues,
            "errors": total_errors,
            "warnings": total_warnings,
            "infos": total_infos,
            "reports": reports_data,
        })
    else:
        print(f"\n{'='*60}")
        print(f"📋 校验报告")
        print(f"{'='*60}")
        print(f"文档数: {len(reports_data)}")
        print(f"总问题: {total_issues} (🔴 {total_errors} / 🟡 {total_warnings} / 🟢 {total_infos})")
        print(f"{'='*60}\n")

        for report in reports_data:
            if not report["issues"]:
                continue
            print(f"📄 {report['doc_name']} ({report['doc_id']})")
            for issue in report["issues"]:
                icon = {"error": "🔴", "warning": "🟡", "info": "🟢"}.get(issue["severity"], "•")
                print(f"  {icon} [{issue['category']}] {issue['message']}")
            print()

    return 1 if total_errors > 0 else 0


# ---------------------------------------------------------------------------
# trace
# ---------------------------------------------------------------------------

def cmd_trace(args: argparse.Namespace) -> int:
    """场景追踪命令."""
    logic_path = Path(args.logic)
    parser = DocumentParser()
    doc = parser.parse_file(logic_path)

    # 加载 scenarios
    scenarios: list[Scenario] = []
    if args.scenarios:
        scenarios_data = json.loads(Path(args.scenarios).read_text(encoding="utf-8"))
        for s in scenarios_data:
            scenarios.append(Scenario(
                name=s.get("name", ""),
                description=s.get("description", ""),
                inputs=s.get("inputs", {}),
                expected_path=s.get("expected_path", ""),
                expected_output=s.get("expected_output", {}),
                boundary_type=s.get("boundary_type", "normal"),
            ))
    else:
        # 自动生成场景
        scenarios = generate_scenarios(doc, count=args.count)

    # 加载 mock data
    mock_data: dict[str, Any] = {}
    if args.mock:
        mock_dir = Path(args.mock)
        if mock_dir.exists():
            for f in mock_dir.glob("*.json"):
                mock_data[f.stem] = json.loads(f.read_text(encoding="utf-8"))

    executor = PseudocodeExecutor(mock_data=mock_data)
    traces_data: list[dict[str, Any]] = []

    for scenario in scenarios:
        trace = executor.execute(doc, scenario)
        traces_data.append(_trace_to_dict(trace))

    if args.format == "json":
        _json_out({
            "command": "trace",
            "success": True,
            "logic": str(logic_path),
            "scenarios_executed": len(scenarios),
            "traces": traces_data,
        })
    else:
        print(f"\n{'='*60}")
        print(f"🔍 场景追踪: {doc.name}")
        print(f"{'='*60}\n")
        for t in traces_data:
            status = "✅" if t["reached_end"] else "❌"
            print(f"{status} {t['scenario_name']}")
            for step in t["steps"]:
                print(f"   {step['step_num']}. {step['line']}")
            if t["issues"]:
                print(f"   ⚠️ 问题: {', '.join(t['issues'])}")
            print()

    return 0


def _trace_to_dict(trace: ExecutionTrace) -> dict[str, Any]:
    return {
        "scenario_name": trace.scenario_name,
        "reached_end": trace.reached_end,
        "steps": [
            {
                "step_num": s.step_num,
                "line": s.line,
                "state_before": s.state_before,
                "state_after": s.state_after,
                "result": s.result,
                "issue": s.issue,
            }
            for s in trace.steps
        ],
        "final_state": trace.final_state,
        "issues": trace.issues,
    }


# ---------------------------------------------------------------------------
# codegen
# ---------------------------------------------------------------------------

def cmd_codegen(args: argparse.Namespace) -> int:
    """代码生成命令."""
    target = Path(args.target)
    output_dir = Path(args.output) if args.output else Path("codegen")
    output_dir.mkdir(parents=True, exist_ok=True)

    parser = DocumentParser()
    if target.is_dir():
        docs = parser.parse_directory(target)
    else:
        docs = [parser.parse_file(target)]

    skill_gen = SkillGenerator()
    meta_gen = RegistryMetaGenerator()

    generated: list[dict[str, str]] = []
    for doc in docs:
        if doc.doc_type.value in ("action", "logic", "object"):
            code = skill_gen.generate(doc)
            code_file = output_dir / f"{doc.id}.py"
            code_file.write_text(code, encoding="utf-8")

            meta = meta_gen.generate(doc)
            meta_file = output_dir / f"{doc.id}.registry.yml"
            meta_file.write_text(meta, encoding="utf-8")

            generated.append({
                "doc_id": doc.id,
                "py_file": str(code_file),
                "meta_file": str(meta_file),
            })

    module_file = None
    catalog_file = None
    if len(docs) > 1:
        module_code = skill_gen.generate_module(docs)
        module_file = output_dir / "__init__.py"
        module_file.write_text(module_code, encoding="utf-8")

        catalog = meta_gen.generate_catalog(docs)
        catalog_file = output_dir / "registry_catalog.yml"
        catalog_file.write_text(catalog, encoding="utf-8")

    if args.format == "json":
        result: dict[str, Any] = {
            "command": "codegen",
            "success": True,
            "output_dir": str(output_dir),
            "generated": generated,
        }
        if module_file:
            result["module_file"] = str(module_file)
            result["catalog_file"] = str(catalog_file)
        _json_out(result)
    else:
        for g in generated:
            print(f"✅ {g['doc_id']}: {Path(g['py_file']).name} + {Path(g['meta_file']).name}")
        if module_file:
            print(f"✅ 模块汇总: {module_file.name}")
            print(f"✅ 注册目录: {catalog_file.name}")
        print(f"\n🎉 共生成 {len(generated)} 个 OntologySkill")

    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_mermaid(args: argparse.Namespace) -> int:
    """解析 Mermaid 流程图命令."""
    target = Path(args.target)

    results: list[dict[str, Any]] = []
    if target.is_file():
        chart = parse_mermaid_file(target)
        results.append(chart.to_dict())
    else:
        for f in sorted(target.glob("*.mermaid")):
            chart = parse_mermaid_file(f)
            d = chart.to_dict()
            d["file"] = str(f)
            results.append(d)

    if args.format == "json":
        _json_out({
            "command": "mermaid",
            "success": True,
            "count": len(results),
            "charts": results,
        })
    else:
        print(f"✅ 已解析 {len(results)} 个流程图")
        for r in results:
            print(f"\n📄 {r.get('file', 'unknown')}")
            print(f"  方向: {r['direction']}")
            print(f"  节点: {len(r['nodes'])} 个")
            for n in r["nodes"]:
                print(f"    • {n['id']}: {n['label']} ({n['type']})")
            print(f"  边: {len(r['edges'])} 条")
            for e in r["edges"]:
                label = f"|{e['label']}|" if e["label"] else ""
                print(f"    • {e['source']} -->{label} {e['target']}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """状态查看命令."""
    target = Path(args.target)
    parser = DocumentParser()

    if target.is_dir():
        docs = parser.parse_directory(target)
    else:
        docs = [parser.parse_file(target)]

    by_type: dict[str, list[Any]] = {}
    quality_scores: dict[str, int] = {}
    for doc in docs:
        by_type.setdefault(doc.doc_type.value, []).append(doc)

    rule_validator = RuleValidator({d.id: d for d in docs if d.id})
    for doc in docs:
        report = rule_validator.validate(doc)
        score = max(100 - report.error_count() * 10 - report.warning_count() * 3, 0)
        quality_scores[doc.id] = score

    total_errors = sum(
        rule_validator.validate(d).error_count() for d in docs
    )

    low_quality = [
        {"id": d.id, "name": d.name, "score": quality_scores.get(d.id, 100)}
        for d in docs if quality_scores.get(d.id, 100) < 80
    ]

    by_type_summary: dict[str, dict[str, Any]] = {}
    for t, ds in sorted(by_type.items()):
        avg_score = sum(quality_scores.get(d.id, 0) for d in ds) / len(ds) if ds else 0
        by_type_summary[t] = {"count": len(ds), "avg_score": round(avg_score, 1)}

    if args.format == "json":
        _json_out({
            "command": "status",
            "success": True,
            "path": str(target),
            "total_docs": len(docs),
            "by_type": by_type_summary,
            "total_errors": total_errors,
            "low_quality_docs": low_quality,
        })
    else:
        print(f"\n{'='*60}")
        print(f"📊 知识库状态")
        print(f"{'='*60}\n")
        print(f"📁 路径: {target}")
        print(f"📄 文档总数: {len(docs)}")
        for t, info in sorted(by_type_summary.items()):
            print(f"  • {t}: {info['count']} 个 (平均质量分: {info['avg_score']:.0f})")

        if total_errors > 0:
            print(f"\n⚠️  共 {total_errors} 个错误待修复")
        else:
            print(f"\n✅ 无错误")

        if low_quality:
            print(f"\n🔧 建议优先修复（质量分 < 80）:")
            for item in sorted(low_quality, key=lambda x: x["score"]):
                print(f"  • {item['name']} ({item['id']}): {item['score']} 分")

        print(f"\n{'='*60}")

    return 0


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------

def cmd_index(args: argparse.Namespace) -> int:
    """索引命令 — 生成关系图和导航索引."""
    target = Path(args.target)
    indexer = OntologyIndexer(target)
    indexer.scan()

    if args.format == "json":
        result = indexer.to_dict()
        result["command"] = "index"
        result["success"] = True
        _json_out(result)
    else:
        print(f"\n{'='*60}")
        print(f"📇 Ontology 索引")
        print(f"{'='*60}")
        print(f"📁 路径: {target}")
        print(f"📄 文档数: {len(indexer.documents)}")

        by_type: dict[str, int] = {}
        for d in indexer.documents:
            by_type[d.doc_type] = by_type.get(d.doc_type, 0) + 1
        for t, c in sorted(by_type.items()):
            print(f"  • {t}: {c}")

        print(f"🔗 关系数: {len(indexer.relationships)}")

        rel_types: dict[str, int] = {}
        for r in indexer.relationships:
            rel_types[r.rel_type] = rel_types.get(r.rel_type, 0) + 1
        print("\n关系类型:")
        for rt, c in sorted(rel_types.items(), key=lambda x: -x[1]):
            print(f"  • {rt}: {c}")

        print(f"\n{'='*60}")

    return 0


# ---------------------------------------------------------------------------
# impact
# ---------------------------------------------------------------------------

def cmd_impact(args: argparse.Namespace) -> int:
    """影响分析命令 — 分析文档变更的影响范围."""
    base_dir = Path(args.base_dir)
    target = args.target

    indexer = OntologyIndexer(base_dir)
    indexer.scan()
    report = indexer.analyze_impact(target)

    if args.format == "json":
        result = report.to_dict()
        result["command"] = "impact"
        result["success"] = report.target_doc is not None
        _json_out(result)
    else:
        if not report.target_doc:
            print(f"❌ 未找到文档: {target}")
            return 1

        print(f"\n{'='*60}")
        print(f"⚠️  变更影响分析: {report.target_doc.name or report.target_doc.id}")
        print(f"{'='*60}")

        print(f"\n📄 目标文档: {report.target_doc.rel_path}")
        print(f"   类型: {report.target_doc.doc_type}")
        print(f"   领域: {report.target_doc.domain or '未分类'}")

        s = report.summary
        print(f"\n📊 影响范围:")
        print(f"   被引用 (incoming): {s.get('incoming_count', 0)}")
        print(f"   引用他人 (outgoing): {s.get('outgoing_count', 0)}")
        print(f"   传递性影响: {s.get('transitive_count', 0)}")
        print(f"   总计受影响文档: {s.get('total_affected', 0)}")

        if report.incoming:
            print(f"\n⬅️  被以下文档引用:")
            for group in report.incoming:
                print(f"   [{group['rel_type']}] ({group['count']} 个)")
                for d in group["docs"]:
                    print(f"      • {d['rel_path']}")

        if report.outgoing:
            print(f"\n➡️  引用了以下文档:")
            for group in report.outgoing:
                print(f"   [{group['rel_type']}] ({group['count']} 个)")
                for d in group["docs"]:
                    print(f"      • {d['rel_path']}")

        if report.transitive:
            print(f"\n🔁 传递性影响（二级）:")
            for t in report.transitive:
                via_doc = indexer._doc_by_path.get(t["via"], {})
                via_name = via_doc.name if hasattr(via_doc, "name") else t["via"]
                print(f"   • {t['doc']['rel_path']} (通过 {via_name})")

        print(f"\n{'='*60}")

    return 0


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

def cmd_ingest(args: argparse.Namespace) -> int:
    """文档收录命令."""
    if not args.source and not args.source_dir:
        print("错误：至少需要指定 --source 或 --source-dir 之一", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir)
    domain = args.domain
    domain_cn = getattr(args, "domain_cn", domain)

    report = run_ingest(
        sources=args.source or [],
        source_dirs=args.source_dir or [],
        domain=domain,
        domain_cn=domain_cn,
        output_dir=output_dir,
    )

    if args.format == "json":
        _json_out(report.to_dict())
    else:
        print(f"{'✅' if report.failed_count == 0 else '⚠️'} 文档收录完成")
        print(f"  成功: {report.success_count} 个")
        if report.skipped_count:
            print(f"  跳过: {report.skipped_count} 个（已存在）")
        if report.failed_count:
            print(f"  失败: {report.failed_count} 个")
        print()
        for r in report.results:
            icon = {"success": "✅", "skipped": "⏭️", "failed": "❌"}[r.status]
            if r.status == "success":
                print(f"  {icon} {r.title} ({r.source_type}, ~{r.word_count}字) → {Path(r.output_path).name}")
            elif r.status == "skipped":
                print(f"  {icon} {r.original_path} — {r.error}")
            else:
                print(f"  {icon} {r.original_path} — {r.error}")
        if report.success_count:
            print(f"\n  清单: {output_dir}/_manifest.md")

    return 0 if report.failed_count == 0 else 1


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    """主入口."""
    parser = argparse.ArgumentParser(
        prog="kea",
        description="KEA — Knowledge Extraction Agent 确定性工具层\n"
                    "供 Agent 平台调用，输入文件/目录，输出结构化结果。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  kea parse ontology/objects/订单.md --format json
  kea validate ontology/ --format json
  kea trace ontology/logic/创建订单.md --format json
  kea codegen ontology/ --output codegen/ --format json
  kea status ontology/ --format json
  kea index ontology/ --format json
  kea impact 订单.md --base-dir ontology/ --format json
        """,
    )

    parser.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="输出格式：human（人类可读）或 json（机器可读，供 Agent 消费）",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # parse
    parse_parser = subparsers.add_parser("parse", help="解析知识文档为 AST")
    parse_parser.add_argument("target", help="目标文件或目录")
    parse_parser.set_defaults(func=cmd_parse)

    # mermaid
    mermaid_parser_cmd = subparsers.add_parser("mermaid", help="解析 Mermaid 流程图")
    mermaid_parser_cmd.add_argument("target", help="目标 .mermaid 文件或目录")
    mermaid_parser_cmd.set_defaults(func=cmd_mermaid)

    # validate
    validate_parser = subparsers.add_parser("validate", help="校验知识文档")
    validate_parser.add_argument("target", help="目标文件或目录")
    validate_parser.set_defaults(func=cmd_validate)

    # trace
    trace_parser = subparsers.add_parser("trace", help="场景追踪（伪代码执行）")
    trace_parser.add_argument("logic", help="逻辑文档路径")
    trace_parser.add_argument("--scenarios", help="场景 JSON 文件路径（可选，自动生成）")
    trace_parser.add_argument("--mock", help="Mock 数据目录路径（可选）")
    trace_parser.add_argument("--count", type=int, default=5, help="自动生成场景数量（默认 5）")
    trace_parser.set_defaults(func=cmd_trace)

    # codegen
    codegen_parser = subparsers.add_parser("codegen", help="生成 OntologySkill 代码")
    codegen_parser.add_argument("target", help="目标文件或目录")
    codegen_parser.add_argument("-o", "--output", default="codegen", help="输出目录")
    codegen_parser.set_defaults(func=cmd_codegen)

    # status
    status_parser = subparsers.add_parser("status", help="查看知识库状态")
    status_parser.add_argument("target", default="ontology/", nargs="?", help="目标目录")
    status_parser.set_defaults(func=cmd_status)

    # index
    index_parser = subparsers.add_parser("index", help="生成 Ontology 索引和关系图")
    index_parser.add_argument("target", default="ontology/", nargs="?", help="目标目录")
    index_parser.set_defaults(func=cmd_index)

    # impact
    impact_parser = subparsers.add_parser("impact", help="分析文档变更的影响范围")
    impact_parser.add_argument("target", help="目标文档路径或 ID")
    impact_parser.add_argument("--base-dir", default="ontology/", help="Ontology 根目录")
    impact_parser.set_defaults(func=cmd_impact)

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="收录源文档（PDF/Word/Excel/PPT/HTML/URL/图片）→ 标准化 MD")
    ingest_parser.add_argument("--source", action="append", default=[], help="源文件路径或 URL（可多次指定）")
    ingest_parser.add_argument(
        "--source-dir",
        action="append",
        dest="source_dir",
        default=[],
        help="源文档目录（递归扫描，可多次指定）",
    )
    ingest_parser.add_argument("--domain", required=True, help="领域英文名（DOMAIN_EN）")
    ingest_parser.add_argument("--domain-cn", default="", help="领域中文名（可选）")
    ingest_parser.add_argument("--output-dir", required=True, help="输出目录（sources/{domain}/）")
    ingest_parser.set_defaults(func=cmd_ingest)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
