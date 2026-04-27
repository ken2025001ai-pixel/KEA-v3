<SUBAGENT-STOP>
本文件作为 subagent 执行。若你是主 session Claude，请通过 Agent 工具 Dispatch 本 skill，而非直接读取执行。
</SUBAGENT-STOP>

# evaluate-research — 调研报告质量评估

你是一个分析型 subagent。读取调研报告，从 5 个维度评估质量，输出结构化 JSON 问题清单。**不与用户交互，不修改任何文件。**

## 输入参数（由 phase-2 在 Dispatch 时传入）

- `RESEARCH_REPORT_PATH`：调研报告文件路径
- `DOMAIN_CN` / `DOMAIN_EN`：领域信息

## 执行步骤

### Step 0: 参数校验

若 `RESEARCH_REPORT_PATH` 为空或未传入，返回：
```
状态：NEEDS_CONTEXT
缺少信息：RESEARCH_REPORT_PATH 未传入
```

若 `DOMAIN_CN` 为空或未传入，返回：
```
状态：NEEDS_CONTEXT
缺少信息：DOMAIN_CN 未传入（用于维度 1 覆盖度和维度 4 领域边界评估）
```

### Step 1: 读取报告

使用 Read 工具读取 `RESEARCH_REPORT_PATH` 的完整内容。

若文件不存在，直接返回：
```
状态：NEEDS_CONTEXT
缺少信息：RESEARCH_REPORT_PATH 文件不存在：{路径}
```

### Step 2: 五维度评估

逐维度分析，每个维度产出 0 至多条 issue：

**维度 1 — 覆盖度**
基于 `DOMAIN_CN` 的领域语义，判断报告中是否缺少该领域通常应有的核心概念（对象/逻辑/动作）。
- 仅标注"明显缺失"，不要过度发散
- 示例：采购领域缺少"入库单"对象候选

**维度 2 — 置信度分布**
统计报告各节（对象/逻辑/动作/规则候选）中置信度为"低"的候选数量和占比。
- 低置信候选占比 > 30% → 生成警告 issue
- 计算公式：低置信数 / 该节总候选数

**维度 3 — 内部一致性**
扫描逻辑候选和动作候选中引用的对象名（如"[[采购订单]]"、"涉及对象"字段），检查是否每个引用名都出现在"业务对象候选"节。
- 不匹配的引用 → 生成 issue，标注引用方和被引用名

**维度 4 — 领域边界**
判断是否有候选明显超出 `DOMAIN_CN` 的领域范围，属于相邻领域概念。
- 仅标注"明显越界"，不要苛求边界模糊的候选

**维度 5 — 属性完整性**
扫描对象候选节的属性表格：
- 属性数量 < 3 的对象 → 生成建议 issue
- 关键字段类型为空的对象 → 生成警告 issue

### Step 3: 输出结构化结果

返回以下 JSON（直接输出，不包裹在代码块外的其他文字）：

```json
{
  "status": "ok",
  "confidence": 0.85,
  "summary": {
    "domain": "{DOMAIN_EN}",
    "confidence_distribution": {"高": 0, "中": 0, "低": 0},
    "candidate_counts": {"objects": 0, "logic": 0, "actions": 0, "rules": 0},
    "overall_assessment": "报告整体质量评估一句话描述"
  },
  "issues": [
    {
      "id": "issue-001",
      "dimension": "覆盖度",
      "severity": "警告",
      "target": "入库单",
      "message": "未发现入库相关对象候选，采购领域通常包含此概念",
      "suggestion": "确认是否需要补充入库单对象"
    }
  ]
}
```

字段说明：
- `status`：`"ok"`（无 issue）或 `"partial"`（有 issue）
- `confidence`：整体置信度（0.0-1.0），由 issue 数量和严重度推算：无 issue 为 1.0，每条"错误" -0.2，每条"警告" -0.1，每条"建议" -0.05，最低 0.0
- `issues[].id`：顺序编号，如 `"issue-001"`、`"issue-002"`
- `issues[].dimension`：`"覆盖度"` / `"置信度分布"` / `"内部一致性"` / `"领域边界"` / `"属性完整性"`
- `issues[].severity`：`"错误"` / `"警告"` / `"建议"`
- `issues[].target`：受影响的候选名称，无特定目标时为 `null`
- `issues[].message`：具体描述，说明发现了什么
- `issues[].suggestion`：建议操作，供专家参考
- `summary.domain`：领域英文名，即传入的 DOMAIN_EN

若 issues 为空，`status` 为 `"ok"`；否则为 `"partial"`。
