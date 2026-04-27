---
type: rule
id: rule_{snake_case_id}
name: {规则名称}
category: {状态机约束|数据一致性|计算公式|权限控制|业务校验}
severity: {critical|high|medium|low}

applies_to:
  - object: {对象id}
    field: {字段名}
  - action: {动作id}

trigger: {什么情况下触发此规则}

rule_expression: |
  {规则的具体表达式或逻辑描述：
   - 允许的/禁止的行为
   - 计算公式
   - 约束条件
   - 权限矩阵
   - 阈值判断}

error_message: "{违反规则时的错误提示信息，可使用{变量}占位符}"
---

# 规则说明

{该规则的业务背景，为什么需要这条规则，违反的后果}

## 适用场景

- {场景1}
- {场景2}

## 相关对象与动作

- 约束对象: [[{对象名称}]]
- 触发动作: [[{动作名称}]]

## 规则示例

**合法情况：**
- {输入} → {输出}（满足规则）

**非法情况：**
- {输入} → {输出}（违反规则，触发 error_message）
