---
type: object
id: {snake_case_id}
name: {中文名称}
english_name: {PascalCaseEnglishName}
domain: {业务领域，如"订单管理"}
status: draft
version: "1.0"
tags: [kea-object]
aliases: [{别名1, 别名2}]

agent_context:
  one_liner: "{一句话描述该对象的业务本质}"
  typical_scenarios:
    - "{业务场景1}"
    - "{业务场景2}"
  common_misconceptions:
    - "{常见误解1}"
    - "{常见误解2}"
  related_importance:
    {关联对象A}: high
    {关联对象B}: medium

relations:
  - target: {target_id}
    type: {contains|belongs_to|has|references|uses|depends_on|consumed_by|located_at|logs}
    cardinality: "{1:1|1:N|N:1|N:M}"
    description: "{关系描述}"
---

# 对象描述

{该对象是什么，在业务流程中的作用，为什么重要}

## 对象别名

{常用同义词别名，逗号分隔，如果没有填'无'}

## 属性清单

| 名称 | 英文名 | 描述 | 主键 | 类型 | 约束 |
| --- | --- | --- | --- | --- | --- |
| {属性1} | {property1} | {描述} | 是 | 字符串 | {pattern, max_length, unique} |
| {属性2} | {property2} | {描述} | 否 | 整型 | {min, max, required, default} |
| {属性3} | {property3} | {描述} | 否 | 枚举 | {values: [值1, 值2], required} |
| {属性4} | {property4} | {描述} | 否 | 金额 | {min, precision, required} |
| {属性5} | {property5} | {描述} | 否 | 对象引用 | {target: 对象id, required} |
| {属性6} | {property6} | {描述} | 否 | 时间戳 | {required, immutable} |

## 状态机

```mermaid
stateDiagram-v2
    [*] --> {状态1}: {触发条件}
    {状态1} --> {状态2}: {触发条件}
    {状态2} --> {状态3}: {触发条件}
    {状态3} --> [*]: {结束条件}
```

## 状态转换规则

| 转换 | 触发条件 | 前置条件 | 执行动作 |
|------|---------|---------|---------|
| {状态A} → {状态B} | {什么情况下发生转换} | {转换前必须满足的条件} | {转换时执行的操作} |
| {状态B} → {状态C} | {什么情况下发生转换} | {转换前必须满足的条件} | {转换时执行的操作} |

## 业务规则

- **R-{DOMAIN}-{001}**: {规则描述}
- **R-{DOMAIN}-{002}**: {规则描述}

## 关联对象

- 当前对象 contains → [[{对象名称}]]
- 当前对象 belongs_to → [[{对象名称}]]
- 当前对象 has → [[{对象名称}]]
- 当前对象 references → [[{对象名称}]]
