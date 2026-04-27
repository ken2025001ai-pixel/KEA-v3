---
type: rule
id: {{id}}
name: {{name}}
category: {{category}}
severity: {{severity}}

applies_to:
  - object: {{applies_object_1}}
    field: {{applies_field_1}}

trigger: {{trigger}}

rule_expression: |
  {{rule_expression}}

error_message: "{{error_message}}"
---

# 规则说明

{{description}}

## 适用对象

- **{{applies_object_1}}**.{{applies_field_1}}

## 触发时机

{{trigger_description}}

## 规则表达式

```
{{rule_expression}}
```

## 示例

**满足规则：**
- {{example_valid_1}}

**违反规则：**
- {{example_invalid_1}} → {{error_message}}
