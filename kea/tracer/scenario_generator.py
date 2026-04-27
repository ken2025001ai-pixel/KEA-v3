"""场景生成器 — 从知识文档自动生成测试场景.

基于 Logic/Action 的输入参数、边界条件和伪代码中的分支，
自动生成覆盖正常路径、异常路径和边界值的测试场景。"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from kea.parser.models import BoundaryCondition, DocType, InputParam, KnowledgeDocument


@dataclass
class Scenario:
    """测试场景."""

    name: str = ""
    description: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_path: str = ""       # 预期执行路径（如"正常完成"/"异常终止"）
    expected_output: dict[str, Any] = field(default_factory=dict)
    boundary_type: str = ""       # normal / boundary / error


def generate_scenarios(doc: KnowledgeDocument, count: int = 5) -> list[Scenario]:
    """为知识文档生成测试场景.

    Args:
        doc: Action 或 Logic 知识文档
        count: 期望生成的场景数量

    Returns:
        测试场景列表
    """
    if doc.doc_type not in (DocType.ACTION, DocType.LOGIC):
        return []

    scenarios = []

    # 1. 正常路径场景
    normal = _generate_normal_scenario(doc)
    if normal:
        scenarios.append(normal)

    # 2. 从边界条件生成场景
    for bc in doc.boundary_conditions:
        sc = _scenario_from_boundary(doc, bc)
        if sc:
            scenarios.append(sc)

    # 3. 从输入参数类型推断边界值
    for inp in doc.inputs:
        sc = _scenario_from_input_boundary(doc, inp)
        if sc and sc.name not in {s.name for s in scenarios}:
            scenarios.append(sc)

    # 4. 如果数量不足，补充随机正常场景
    while len(scenarios) < count:
        extra = _generate_normal_scenario(doc, suffix=f"_{len(scenarios)+1}")
        if extra and extra.name not in {s.name for s in scenarios}:
            scenarios.append(extra)
        else:
            break

    return scenarios[:count]


def _generate_normal_scenario(doc: KnowledgeDocument, suffix: str = "") -> Scenario | None:
    """生成正常路径场景."""
    inputs = {}
    for inp in doc.inputs:
        val = _generate_normal_value(inp)
        if val is not None:
            inputs[inp.name] = val

    return Scenario(
        name=f"{doc.id}_normal{suffix}",
        description=f"{doc.name} — 正常路径",
        inputs=inputs,
        expected_path="正常完成",
        boundary_type="normal",
    )


def _scenario_from_boundary(doc: KnowledgeDocument, bc: BoundaryCondition) -> Scenario | None:
    """从边界条件生成场景."""
    # 根据场景描述推断输入值
    inputs = _infer_inputs_from_description(doc, bc.scenario)

    boundary_type = "boundary"
    if any(kw in bc.scenario for kw in ("不足", "为空", "失败", "错误", "异常", "非法", "超时")):
        boundary_type = "error"
        expected = "异常终止"
    else:
        expected = "正常完成"

    return Scenario(
        name=f"{doc.id}_{_slugify(bc.scenario)}",
        description=f"{doc.name} — {bc.scenario}",
        inputs=inputs,
        expected_path=expected,
        boundary_type=boundary_type,
    )


def _scenario_from_input_boundary(doc: KnowledgeDocument, inp: InputParam) -> Scenario | None:
    """从输入参数的边界值生成场景."""
    if inp.type == "string":
        return Scenario(
            name=f"{doc.id}_{inp.name}_empty",
            description=f"{doc.name} — {inp.name}为空字符串",
            inputs={inp.name: ""},
            expected_path="异常终止",
            boundary_type="error",
        )
    elif inp.type in ("int", "integer", "number"):
        return Scenario(
            name=f"{doc.id}_{inp.name}_zero",
            description=f"{doc.name} — {inp.name}=0",
            inputs={inp.name: 0},
            expected_path="边界处理",
            boundary_type="boundary",
        )
    elif inp.type == "boolean":
        return Scenario(
            name=f"{doc.id}_{inp.name}_false",
            description=f"{doc.name} — {inp.name}=false",
            inputs={inp.name: False},
            expected_path="正常完成",
            boundary_type="boundary",
        )
    return None


def _generate_normal_value(inp: InputParam) -> Any:
    """为输入参数生成正常值."""
    type_ = inp.type.lower() if inp.type else "string"

    if type_ in ("string", "str"):
        return f"test_{inp.name}"
    elif type_ in ("int", "integer"):
        return random.randint(1, 100)
    elif type_ in ("float", "number", "金额"):
        return round(random.uniform(1.0, 1000.0), 2)
    elif type_ in ("bool", "boolean"):
        return True
    elif type_ == "array":
        return [1, 2, 3]
    elif type_ == "object":
        return {"key": "value"}
    return "test_value"


def _infer_inputs_from_description(doc: KnowledgeDocument, description: str) -> dict[str, Any]:
    """从场景描述中推断输入值."""
    # 简化实现：返回正常值，但标记为边界场景
    inputs = {}
    for inp in doc.inputs:
        val = _generate_normal_value(inp)
        # 根据描述关键字调整值
        if "不足" in description and "数量" in inp.name:
            val = 0
        elif "为空" in description and inp.type == "string":
            val = ""
        elif "不存在" in description:
            val = "NONEXISTENT"
        inputs[inp.name] = val
    return inputs


def _slugify(text: str) -> str:
    """将文本转为 slug（用于场景名称）."""
    import re
    text = text[:20]
    text = re.sub(r'[^\w\u4e00-\u9fa5]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')
