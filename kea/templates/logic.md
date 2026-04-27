---
type: logic
id: {{id}}
name: {{name}}
aliases: [{{aliases}}]

agent_context:
  one_liner: "{{one_liner}}"
  typical_scenarios:
    - "{{scenario_1}}"
    - "{{scenario_2}}"
  common_misconceptions:
    - "{{misconception_1}}"

relations:
  - target: {{uses_target_1}}
    type: uses
    cardinality: "N:1"
    description: "{{uses_desc_1}}"
  - target: {{calls_target_1}}
    type: calls
    cardinality: "1:1"
    description: "{{calls_desc_1}}"

inputs:
  - name: {{input_name_1}}
    type: {{input_type_1}}
    required: true
    description: "{{input_desc_1}}"

outputs:
  - name: {{output_name_1}}
    type: {{output_type_1}}
    description: "{{output_desc_1}}"
---

# 业务描述

{{description}}

## 输入输出

### 输入

| 参数名称 | 参数类型 | 多值 | 描述 | 示例 |
|------|------|------|------|------|
| {{input_name_1}} | {{input_type_1}} | 否 | {{input_desc_1}} | {{input_example_1}} |

### 输出

| 参数名称 | 参数类型 | 描述 |
|------|------|------|
| {{output_name_1}} | {{output_type_1}} | {{output_desc_1}} |

## 前提

1. {{precondition_1}}
2. {{precondition_2}}

## 效果

1. {{postcondition_1}}
2. {{postcondition_2}}

## 逻辑描述

```pseudo
function {{function_name}}({{input_name_1}}: {{input_type_1}}) -> {{output_type_1}}:
    // 前置校验
    {{validation_step}}
    
    // 业务逻辑
    {{logic_step_1}}
    
    // 子调用
    result = call_action("{{calls_target_1}}", {
        {{param_1}}: {{value_1}}
    })
    
    return {
        {{output_name_1}}: result
    }
```

## 边界条件

| 场景 | 处理 |
|------|------|
| {{boundary_1}} | {{handling_1}} |
| {{boundary_2}} | {{handling_2}} |

## 回滚规则

```pseudo
function rollback({{rollback_param}}):
    // {{rollback_desc}}
    {{rollback_step}}
```

## 关联对象与调用

- 使用 → [[{{uses_target_1}}]]
- 调用 → Action: [[{{calls_target_1}}]]
