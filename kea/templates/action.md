---
type: action
id: {{id}}
name: {{name}}
aliases: [{{aliases}}]

agent_context:
  one_liner: "{{one_liner}}"
  typical_scenarios:
    - "{{scenario_1}}"
  common_misconceptions:
    - "{{misconception_1}}"

relations:
  - target: {{uses_target_1}}
    type: uses
    description: "{{uses_desc_1}}"
  - target: {{modifies_target_1}}
    type: modifies
    description: "{{modifies_desc_1}}"

inputs:
  - name: {{input_name_1}}
    type: {{input_type_1}}
    required: true
    description: "{{input_desc_1}}"

outputs:
  - name: {{output_name_1}}
    type: {{output_type_1}}
    unit: "{{output_unit_1}}"
    description: "{{output_desc_1}}"
---

# 触发条件

{{trigger_condition}}

## 前置条件

1. {{precondition_1}}
2. {{precondition_2}}

## 执行逻辑

```pseudo
function {{function_name}}({{input_name_1}}: {{input_type_1}}) -> {{output_type_1}}:
    // Step 1: {{step_1_desc}}
    {{step_1}}
    
    // Step 2: {{step_2_desc}}
    {{step_2}}
    
    return {
        {{output_name_1}}: {{output_expr}}
    }
```

## 后置条件

1. {{postcondition_1}}
2. {{postcondition_2}}

## 回滚规则

{{rollback_description}}

```pseudo
function rollback({{rollback_param}}):
    {{rollback_step}}
```

## 边界条件

| 场景 | 处理 |
|------|------|
| {{boundary_1}} | {{handling_1}} |
| {{boundary_2}} | {{handling_2}} |
