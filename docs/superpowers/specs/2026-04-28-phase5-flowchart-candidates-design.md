# Phase 5 对象提取优化设计：工具扫描流程图候选

**日期**：2026-04-28  
**状态**：已确认  
**涉及文件**：
- `kea/parser/mermaid_parser.py`
- `kea/cli.py`
- `AgentFile/phases/phase-5-extract-objects.md`
- `AgentFile/skills/extract-objects/SKILL.md`

---

## 问题背景

Phase 5 当前将 `DIAGRAMS_DIR` 路径直接传给 extract-objects subagent，由 subagent 自己读取原始 Mermaid 文件并解析节点。这违反了 CLAUDE.md 原则："Controller 负责准备上下文，不让 subagent 自己找文件"，且存在以下具体缺陷：

1. **`kea mermaid` 目录模式扫描 `*.mermaid`**，而流程图文件实际以 `.md` 存储，导致工具在 Phase 5 中无法使用
2. **`parse_file` 对含 YAML front matter 的 `.md` 文件解析错误**：用正则剥首尾代码块，front matter 内容会污染节点解析
3. **subagent 职责混乱**：同时承担"Mermaid 解析"（确定性）和"语义判断+文件生成"（LLM）两类性质不同的工作，遗漏风险高、中间状态不透明

---

## 设计目标

- 工具层负责确定性的 Mermaid 解析，产出结构化候选 JSON
- Phase 5 消费工具输出，将结构化候选文本内嵌入 subagent prompt
- Subagent 专注语义分类、去重、属性推断、文件生成

---

## Section 1：`kea mermaid` 修复

### 1.1 修复 `parse_file` 对 `.md` 的处理

**文件**：`kea/parser/mermaid_parser.py`

将 `parse_file` 改为：先检测文件是否含有 ` ```mermaid ... ``` ` 代码块；若有则提取代码块内容传入 `parse_mermaid()`；若无则将整个文件内容视为纯 Mermaid 语法（兼容 `.mermaid` 文件）。

```python
def parse_file(path: str) -> MermaidFlowchart:
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # 提取第一个 ```mermaid ... ``` 代码块
    m = re.search(r'```mermaid\s*\n(.*?)```', content, re.DOTALL)
    if m:
        content = m.group(1)
    return parse_mermaid(content)
```

### 1.2 修复目录模式 glob

**文件**：`kea/cli.py`，`cmd_mermaid` 函数

```python
# 改前
for f in sorted(target.glob("*.mermaid")):
# 改后
for f in sorted(target.glob("*.md")):
```

### 1.3 输出格式（不变）

```json
{
  "command": "mermaid",
  "success": true,
  "count": 2,
  "charts": [
    {
      "file": "创建采购订单.md",
      "title": "",
      "direction": "TD",
      "nodes": [
        {"id": "N1", "label": "采购订单", "type": "action"},
        {"id": "N2", "label": "是否已审批", "type": "decision"}
      ],
      "edges": [
        {"source": "N1", "target": "N2", "label": "采购申请单"}
      ],
      "subgraphs": []
    }
  ]
}
```

---

## Section 2：Phase 5 流程改动

**文件**：`AgentFile/phases/phase-5-extract-objects.md`

### 新增 Step 2.5（位于"更新 chain-state 为 in_progress"之后、Dispatch 之前）

```
Step 2.5: 用工具扫描流程图候选

执行：
  python3 -m kea --format json mermaid {DIAGRAMS_DIR}

从 JSON 输出格式化候选摘要文本 FLOWCHART_CANDIDATES：

  流程图扫描结果（{N} 个文件，{M} 个节点，{K} 条边）：

  文件：创建采购订单.md
    节点：采购订单[action], 供应商[action], 审批人[subprocess], 是否满足条件[decision] ...
    边标签：采购申请单, 审批结果, 库存数量 ...

  文件：采购收货.md
    节点：...
    边标签：...

失败处理：
  - count=0 或命令报错 → 展示错误详情，询问用户：
    A 检查 DIAGRAMS_DIR 路径后重试
    B 跳过工具扫描（fallback：传原始路径给 subagent，退回旧行为）
```

### Step 3 Dispatch prompt 修改

移除 `DIAGRAMS_DIR`，替换为 `FLOWCHART_CANDIDATES`：

```
FLOWCHART_CANDIDATES: {Step 2.5 生成的候选摘要文本}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {VAULT_PATH}/30-Ontology/objects/{DOMAIN_EN}/
EXISTING_FILES: {EXISTING_FILES（MODE=incremental 时）}
```

---

## Section 3：extract-objects SKILL.md 改动

**文件**：`AgentFile/skills/extract-objects/SKILL.md`

### 3.1 Inputs 表更新

| 参数 | 必填 | 说明 |
|---|---|---|
| `FLOWCHART_CANDIDATES` | **是** | Phase 5 用 `kea mermaid` 扫描后的结构化候选文本（替换原 `DIAGRAMS_DIR`） |
| `SUMMARY_PATHS` | 是 | 调研报告 + 访谈摘要（补充属性细节） |
| `OBJECTS_DIR` | 是 | 输出目录 |
| `EXISTING_FILES` | 否 | 增量模式：跳过的已有文件名列表 |
| `补充提取目标` | 否 | 范围过滤器：仅提取指定名称 |

移除 `DIAGRAMS_DIR` 和 `REPORT_PATHS` 参数。

### 3.2 Step 1 重写

移除"读取 DIAGRAMS_DIR 下所有 Mermaid 文件"指令，改为：

```
## Step 1: 读取输入

从 FLOWCHART_CANDIDATES 中读取已解析的候选清单（由 Phase 5 用 kea mermaid 生成）。
候选按文件分组，每条记录含节点标签、节点类型、边标签。

从 SUMMARY_PATHS 文件补充：属性细节、业务上下文、关系说明（流程图不包含的部分）。

源优先级：FLOWCHART_CANDIDATES > SUMMARY_PATHS

识别对象候选时按以下置信度分级处理：
```

### 3.3 新增：语义分类置信度指引（接 Step 1）

| 候选来源 | 置信度 | 处理方式 |
|---|---|---|
| 边标签（edge label） | 高 | 直接列为候选 |
| `subprocess` 节点标签 | 中高 | 去掉动词前缀后列为候选 |
| `action` 节点标签中的名词部分 | 中 | 提取名词，排除动词 |
| `decision` 节点标签 | 低 | 仅在明确含实体名时纳入 |

### 3.4 Step 2 及后续保持不变

提取、写文件、`kea parse` 自验流程不变。

---

## 不涉及的范围

- 覆盖率检查（coverage-check sub-skill）不改动
- G5 门控条件不改动
- 回退逻辑不改动
- Phase 6/7/8 不涉及
