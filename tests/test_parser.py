"""Parser 单元测试 — DocumentParser, YAMLFMParser."""
import pytest
from kea.parser.document_parser import DocumentParser
from kea.parser.yaml_fm_parser import YAMLFMParser
from kea.parser.models import DocType


class TestYAMLFMParser:
    def test_parse_object_yaml(self):
        p = YAMLFMParser()
        raw = """---
type: object
id: sales_order
name: 销售订单
english_name: SalesOrder
domain: 订单管理
version: "1.2"
status: draft
tags: [kea-object]
aliases: [订单, SO]
agent_context:
  one_liner: 记录客户购买意向和订单详情
  typical_scenarios:
    - 客户下单
  common_misconceptions:
    - 不等于发货单
relations:
  - target: customer
    type: belongs_to
    cardinality: "N:1"
    description: 订单归属客户
---
# 对象描述
测试
"""
        doc, body = p.parse(raw)
        assert doc.doc_type == DocType.OBJECT
        assert doc.id == "sales_order"
        assert doc.name == "销售订单"
        assert doc.version == "1.2"
        assert doc.aliases == ["订单", "SO"]
        assert doc.agent_context.one_liner == "记录客户购买意向和订单详情"
        assert len(doc.relations) == 1
        assert doc.relations[0].cardinality == "N:1"

    def test_parse_rule_with_rule_type(self):
        p = YAMLFMParser()
        raw = """---
type: rule
id: rule_test
name: 测试规则
category: 数据一致性
rule_type: validation
severity: high
applies_to:
  - object: order
    field: amount
trigger: 创建时
rule_expression: amount > 0
error_message: 金额必须大于0
---
# 规则描述
测试
"""
        doc, body = p.parse(raw)
        assert doc.rule_type == "validation"
        assert doc.category == "数据一致性"
        assert doc.severity == "high"
        assert len(doc.applies_to) == 1
        assert doc.applies_to[0]["object"] == "order"

    def test_parse_minimal_object(self):
        """解析最小化 object 文档，验证默认值."""
        p = YAMLFMParser()
        raw = """---
type: object
id: test
name: 测试
---
"""
        doc, body = p.parse(raw)
        assert doc.id == "test"
        assert doc.relations == []
        assert doc.agent_context is None


class TestDocumentParser:
    def test_parse_object_with_properties(self):
        p = DocumentParser()
        raw = """---
type: object
id: product
name: 商品
domain: 库存
---
# 对象描述
商品基础信息

## 属性清单
| 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
| --- | --- | --- | --- | --- | --- |
| 编码 | code | 唯一标识 | 是 | 字符串 | unique |
| 名称 | name | 商品名 | 否 | 字符串 | required |
| 价格 | price | 售价 | 否 | 数字 | min:0 |
"""
        doc = p.parse_text(raw)
        assert len(doc.properties) == 3
        assert doc.properties[0].name == "编码"
        assert doc.properties[0].is_primary_key is True
        assert doc.properties[2].type == "数字"

    def test_parse_logic_with_pseudocode(self):
        p = DocumentParser()
        raw = """---
type: logic
id: create_order
name: 创建订单
domain: 订单
---
# 业务描述
创建销售订单

## 逻辑描述
```pseudo
function main(order_id: str) -> dict:
    assert order_id != '', 'order_id required'
    call_action('check_inventory')
    return {'success': True}
```
"""
        doc = p.parse_text(raw)
        assert "function main" in doc.pseudocode
        assert "call_action" in doc.pseudocode

    def test_parse_object_wikilinks(self):
        p = DocumentParser()
        raw = """---
type: object
id: order
name: 订单
---
# 对象描述
参考 [[customer]] 和 [[product]]

## 关联对象
- 当前对象 belongs_to → [[customer]]
"""
        doc = p.parse_text(raw)
        assert "customer" in doc.wikilinks
        assert "product" in doc.wikilinks

    def test_parse_rule_body_sections(self):
        p = DocumentParser()
        raw = """---
type: rule
id: rule_high_value
name: 大额审批规则
category: 权限控制
rule_type: policy
severity: high
trigger: 订单创建时
rule_expression: amount > 100000
---
# 规则描述
大额需审批

## 规则条件
```
IF 采购订单.总金额 > 100000
THEN 必须经过CFO审批
```

## 违规处理
- 违规等级：硬约束
- 处理方式：拦截并返回错误
- 错误信息：金额超过10万，需CFO审批

## 例外情况
- 战略采购：走快速通道
"""
        doc = p.parse_text(raw)

        assert doc.rule_type == "policy"
        assert len(doc.business_rules) == 3
        assert "拦截并返回错误" in doc.business_rules[1]
        assert len(doc.boundary_conditions) == 1
        assert doc.boundary_conditions[0].scenario == "战略采购"
