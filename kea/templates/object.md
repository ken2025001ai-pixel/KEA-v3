---
type: object
id: {{id}}
name: {{name}}
aliases: [{{aliases}}]
english_name: {{english_name}}

agent_context:
  one_liner: "{{one_liner}}"
  typical_scenarios:
    - "{{scenario_1}}"
    - "{{scenario_2}}"
  common_misconceptions:
    - "{{misconception_1}}"
    - "{{misconception_2}}"
  related_importance:
    {{related_1}}: {{importance_1}}
    {{related_2}}: {{importance_2}}

relations:
  - target: {{relation_target_1}}
    type: {{relation_type_1}}
    cardinality: "{{cardinality_1}}"
    description: "{{relation_desc_1}}"
  - target: {{relation_target_2}}
    type: {{relation_type_2}}
    cardinality: "{{cardinality_2}}"
    description: "{{relation_desc_2}}"
---

# 对象描述

{{description}}

## 属性清单

| 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
| --- | --- | --- | --- | --- | --- |
| {{prop_name_1}} | {{prop_en_1}} | {{prop_desc_1}} | {{prop_pk_1}} | {{prop_type_1}} | {{prop_constraint_1}} |
| {{prop_name_2}} | {{prop_en_2}} | {{prop_desc_2}} | {{prop_pk_2}} | {{prop_type_2}} | {{prop_constraint_2}} |

## 状态机

```mermaid
stateDiagram-v2
    [*] --> {{state_1}}: {{trigger_1}}
    {{state_1}} --> {{state_2}}: {{trigger_2}}
    {{state_2}} --> [*]: {{trigger_3}}
```

## 状态转换规则

| 转换 | 触发条件 | 前置条件 | 执行动作 |
|------|---------|---------|---------|
| {{state_1}} → {{state_2}} | {{trigger_2}} | {{pre_1}} | {{action_1}} |

## 业务规则

- **R-{{id}}-001**: {{rule_1}}
- **R-{{id}}-002**: {{rule_2}}

## 关联对象

- 当前对象 {{relation_type_1}} → [[{{relation_target_1}}]]
- 当前对象 {{relation_type_2}} → [[{{relation_target_2}}]]
