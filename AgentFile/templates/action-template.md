---
type: action
id: {snake_case_id}
name: {中文名称}
english_name: {PascalCaseEnglishName}
domain: {业务领域，如"订单管理"}
status: draft
version: "1.0"
tags: [kea-action]
aliases: [{别名1, 别名2}]

agent_context:
  one_liner: "{一句话描述该动作的业务本质}"
  typical_scenarios:
    - "{业务场景1}"
    - "{业务场景2}"
  common_misconceptions:
    - "{常见误解1}"
    - "{常见误解2}"

relations:
  - target: {所属逻辑id}
    type: part_of
    description: "被{逻辑名称}调用"
  - target: {对象id}
    type: uses
    description: "读取{对象名称}"
  - target: {对象id}
    type: modifies
    description: "修改{对象名称}"

inputs:
  - name: {参数名}
    type: {string|int|bool|float|date|enum|array|object}
    required: {true|false}
    description: "{参数描述}"

outputs:
  - name: {结果名}
    type: {类型}
    unit: "{单位}"
    description: "{结果描述}"
---

# 触发条件

{什么情况下触发此动作，由哪个逻辑节点的哪个步骤调用}

## 前置条件

1. {前置条件1}
2. {前置条件2}

## 执行逻辑

```pseudo
function {函数名}(
    {参数1}: {类型},
    {参数2}: {类型}
) -> {返回类型}:
    
    assert {条件}, "{错误信息}"
    
    // Step 1: {步骤描述}
    {操作}
    
    // Step 2: {步骤描述}
    if {条件}:
        {操作}
    else:
        {操作}
    
    // Step 3: {步骤描述}
    {结果} = {计算}
    
    return {
        {结果字段}: {值}
    }
```

## 后置条件

1. {执行后必须满足的条件1}
2. {执行后必须满足的条件2}

## 回滚规则

{如有副作用（修改数据、创建记录），描述如何回滚}

```pseudo
function rollback({参数}):
    // {回滚操作}
```

## 边界条件

| 场景 | 处理 |
|------|------|
| {异常场景1} | {处理方式} |
| {异常场景2} | {处理方式} |

## 异常处理

- **{异常类型1}**: {触发条件} → {处理策略}
- **{异常类型2}**: {触发条件} → {处理策略}
