"""Validator 单元测试 — RuleValidator 规则覆盖."""
import pytest
from kea.parser.document_parser import DocumentParser
from kea.validator.rule_validator import RuleValidator


def _parse(text: str):
    return DocumentParser().parse_text(text)


class TestObjectValidation:
    def test_object_no_properties(self):
        doc = _parse("""---
type: object
id: empty_obj
name: 空对象
---
# 对象描述
没有属性
""")
        v = RuleValidator()
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "结构缺失" in cats  # R-OBJ-001

    def test_object_no_primary_key(self):
        doc = _parse("""---
type: object
id: obj
name: 对象
---
## 属性清单
| 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
| --- | --- | --- | --- | --- | --- |
| 名称 | name | 名称 | 否 | 字符串 | |
""")
        v = RuleValidator()
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "主键缺失" in cats  # R-OBJ-002

    def test_object_valid_passes(self):
        doc = _parse("""---
type: object
id: order
name: 订单
---
## 属性清单
| 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
| --- | --- | --- | --- | --- | --- |
| 编码 | code | ID | 是 | 字符串 | unique |
""")
        v = RuleValidator()
        report = v.validate(doc)
        assert not report.has_errors()


class TestLogicValidation:
    def test_logic_no_pseudocode(self):
        doc = _parse("""---
type: logic
id: test_logic
name: 测试流程
---
# 业务描述
没有伪代码
""")
        v = RuleValidator()
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "伪代码缺失" in cats  # R-LOG-002

    def test_logic_dead_reference(self):
        doc = _parse("""---
type: logic
id: test_logic
name: 测试流程
relations:
  - target: nonexistent_obj
    type: uses
    description: 引用不存在的对象
---
# 业务描述
test
""")
        all_docs = {"test_logic": doc}
        v = RuleValidator(all_docs)
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "引用失效" in cats  # R-COM-003


class TestActionValidation:
    def test_action_orphan_detection(self):
        doc = _parse("""---
type: action
id: lonely_action
name: 孤立动作
relations: []
---
# 触发条件
test
""")
        all_docs = {"lonely_action": doc}
        v = RuleValidator(all_docs)
        report = v.validate(doc)
        # 孤立检测是 INFO 级别
        infos = [i for i in report.issues if i.severity.value == "info"]
        cats = [i.category for i in infos]
        assert "孤立动作" in cats  # R-ACT-005

    def test_action_missing_inputs(self):
        doc = _parse("""---
type: action
id: act
name: 动作
---
# 触发条件
test
""")
        v = RuleValidator()
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "输入缺失" in cats  # R-ACT-001


class TestRuleValidation:
    def test_rule_missing_trigger(self):
        doc = _parse("""---
type: rule
id: rule_x
name: 规则X
category: 数据一致性
---
# 规则描述
test
""")
        v = RuleValidator()
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "触发条件缺失" in cats  # R-RULE-001

    def test_rule_applies_to_invalid_target(self):
        doc = _parse("""---
type: rule
id: rule_x
name: 规则X
category: 数据一致性
applies_to:
  - object: ghost_object
    field: ghost_field
trigger: test
rule_expression: "1=1"
---
# 规则描述
test
""")
        all_docs = {"rule_x": doc}
        v = RuleValidator(all_docs)
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "引用失效" in cats  # R-RULE-002 applies_to target check


class TestCommonValidation:
    def test_missing_id(self):
        doc = _parse("""---
type: object
name: 无名
---
""")
        v = RuleValidator()
        report = v.validate(doc)
        errors = [i for i in report.issues if i.severity.value == "error"]
        cats = [i.category for i in errors]
        assert "ID 缺失" in cats  # R-COM-001

    def test_agent_context_missing(self):
        doc = _parse("""---
type: object
id: obj
name: 对象
---
## 属性清单
| 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
| --- | --- | --- | --- | --- | --- |
| 编码 | code | ID | 是 | 字符串 | unique |
""")
        v = RuleValidator()
        report = v.validate(doc)
        warnings = [i for i in report.issues if i.severity.value == "warning"]
        cats = [i.category for i in warnings]
        assert "agent_context 缺失" in cats  # R-COM-004
