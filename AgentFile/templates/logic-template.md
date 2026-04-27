---
type: logic
id: {snake_case_id}
name: {中文名称}
english_name: {PascalCaseEnglishName}
domain: {业务领域，如"订单管理"}
status: draft
version: "1.0"
tags: [kea-logic]
aliases: [{别名1, 别名2}]

agent_context:
  one_liner: "{一句话描述该逻辑的业务本质}"
  typical_scenarios:
    - "{业务场景1}"
    - "{业务场景2}"
  common_misconceptions:
    - "{常见误解1}"
    - "{常见误解2}"

relations:
  - target: {对象或动作id}
    type: {uses|produces|supports|calls|precedes|follows|part_of}
    cardinality: "{1:1|1:N|N:1|N:M}"
    description: "{关系描述}"

inputs:
  - name: {参数名}
    type: {string|int|bool|array|object}
    required: {true|false}
    description: "{参数描述}"
    schema:
      - name: {子属性名}
        type: {类型}

outputs:
  - name: {结果名}
    type: {类型}
    description: "{结果描述}"
    schema:
      - name: {子属性名}
        type: {类型}
---

# 业务描述

{该流程的业务目的、范围和重要性}

## 输入输出

### 输入

| 参数名称 | 参数类型 | 多值 | 描述 | 示例 |
|------|------|------|------|------|
| {参数1} | {类型} | {是/否} | {描述} | {示例值} |
| {参数2} | {类型} | {是/否} | {描述} | {示例值} |

### 输出

| 参数名称 | 参数类型 | 描述 |
|------|------|------|
| {结果1} | {类型} | {描述} |
| {结果2} | {类型} | {描述} |

## 前提

1. {前置条件1}
2. {前置条件2}

## 效果

1. {执行后的业务效果1}
2. {执行后的业务效果2}

## 逻辑描述

```pseudo
function {函数名}(
    {参数1}: {类型},
    {参数2}: {类型}
) -> {返回类型}:
    
    // ========== Step 1: {步骤描述} ==========
    {变量} = {操作}
    assert {条件}, "{错误信息}"
    
    // ========== Step 2: {步骤描述} ==========
    for {item} in {集合}:
        assert {条件}, "{错误信息}"
        {操作}
    
    // ========== Step N: {决策分支} ==========
    if {条件}:
        {操作}
    else:
        {操作}
    
    // ========== Step N+1: {子流程调用} ==========
    {结果} = call_action("{动作名称}", {{参数: 值}})
    
    return {
        {结果字段}: {值}
    }
```

## 边界条件

| 场景 | 处理 |
|------|------|
| {异常场景1} | {处理方式} |
| {异常场景2} | {处理方式} |

## 回滚规则

```pseudo
function rollback({上下文参数}):
    // {回滚操作描述}
    for {item} in {集合}:
        {回滚操作}
```

## 关联对象与调用

- 使用 → [[{对象名称}]]
- 调用 → Action: [[{动作名称}]]
