# Phase 2 重设计：评估驱动的访谈确认

## 背景与问题

Phase 2 原有设计定位不清晰：interview-agent 同时承担了"全量访谈"和"写 Ontology 文档"两个职责，且默认执行，不论 Phase 1 报告质量如何。

核心问题：Phase 1 调研报告的质量是未知项，需要通过 Phase 2 让专家来评估。评估结果决定是否需要补充——而不是无条件启动完整访谈。

## 新定位

> Phase 2 = Agent 先审报告质量 → 专家评审建议 → 按需定向补充

专家角色从"主讲人"变为"评审人"，只在有实质 gap 时才需要深入输入。

---

## 设计一：Phase 2 整体流程

### 新流程

```
Step 1  更新 chain-state 为 in_progress
Step 2  Dispatch evaluate-research（分析型 sub-skill）
Step 3  Phase 2 呈现评估结果，专家逐条选 A/B/C
Step 4  判断 CONFIRMED_GAPS：
          ├─ 无 → 直接进 G2
          └─ 有 → Dispatch reformed interview-agent（仅处理 gap）
Step 5  G2 门控
```

### 与原设计的关键差异

- interview-agent 从"默认执行"变为"按需触发"
- interview-agent 不再写 Ontology 文档（只写补充调研文档）
- Phase 3 新增可选输入 `SUPPLEMENT_PATH`

---

## 设计二：evaluate-research sub-skill（新增）

**类型：** 分析型（返回结构化问题清单，空列表 = 无问题）

### 输入

| 参数 | 说明 |
|------|------|
| `RESEARCH_REPORT_PATH` | Phase 1 调研报告路径 |
| `DOMAIN_CN` / `DOMAIN_EN` | 领域信息 |

### 评估维度（LLM 按 SKILL 文件定义逐项执行）

| 维度 | 检查内容 |
|------|---------|
| 覆盖度 | 基于领域名和报告内容，是否有明显缺失的核心概念 |
| 置信度分布 | 低置信候选占比是否过高（参考阈值 >30% 时警告） |
| 内部一致性 | 逻辑/动作节引用的对象名，是否都出现在对象候选节 |
| 领域边界 | 是否有候选明显属于相邻领域，应排除或标注 |
| 属性完整性 | 对象属性表是否过于稀疏，缺少类型/必填/关键字段 |

### 输出格式

```json
{
  "status": "ok | partial",
  "summary": {
    "confidence_distribution": {"高": N, "中": N, "低": N},
    "candidate_counts": {"objects": N, "logic": N, "actions": N, "rules": N},
    "overall_assessment": "一句话总体评价"
  },
  "issues": [
    {
      "dimension": "覆盖度",
      "severity": "警告",
      "target": null,
      "message": "未发现入库相关对象候选，采购领域通常包含此概念",
      "suggestion": "确认是否需要补充"
    }
  ]
}
```

### Phase 2 呈现格式

```
评估完成。总体：{overall_assessment}
候选统计：对象 N / 逻辑 K / 动作 M（高置信 X%）

发现 {N} 个待确认项：

[覆盖度]
⚠️ 未发现入库相关对象候选，采购领域通常包含此概念
   → A 确认为 gap，需补充
     B 忽略（不在本次范围）
     C [专家输入文本说明]
```

选 A 或 C 的条目汇入 `CONFIRMED_GAPS`，C 的文本作为该 gap 的补充上下文传入 interview-agent。

---

## 设计三：reformed interview-agent

**定位：** 定向补充，只处理 `CONFIRMED_GAPS`，不做全量访谈。

### 输入

| 参数 | 说明 |
|------|------|
| `CONFIRMED_GAPS` | 已确认的 gap 列表（含维度、描述、专家补充文本） |
| `RESEARCH_REPORT_PATH` | 原调研报告（上下文） |
| `DOMAIN_CN` / `DOMAIN_EN` | 领域信息 |

### 新状态机

```
GAP_ELICITATION → OPEN_FLOOR → CONFIRM → SUMMARY
```

原有 GREETING / PRE_INTERVIEW / DOMAIN_DISCOVERY / 全量 OBJECT/LOGIC/ACTION/RULE 访谈全部移除。

### GAP_ELICITATION — 按 gap 类型定向提问

| Gap 维度 | 提问策略 |
|---------|---------|
| 覆盖度 | "您/系统建议补充【X】，能描述一下它的主要信息和状态流转吗？" |
| 内部一致性 | "逻辑里引用了【X】，这是独立单据还是只是流程节点？" |
| 属性完整性 | "【X】的属性目前比较少，有没有金额、状态、时间这类信息？" |
| 领域边界 | "【X】被列进来了，这次是否要纳入范围，还是排除？" |

若专家在 C 选项里已提供文本，agent 先基于该文本整理后确认，而非从零发问。

### OPEN_FLOOR

所有 gap 处理完后，主动开放：

> "以上 gap 都补充完了。您还有什么想补充或讨论的吗？比如有没有特殊情况、例外规则、或者觉得还没聊到的重要概念？"

专家自由输入，整理后并入补充文档；回复"没有了"则进入 CONFIRM。

### 输出

写入补充调研文档（与调研报告平级，供 Phase 5-8 consume，**不写 Ontology 文档**）：

```
{VAULT_PATH}/RAWData/KEAOutput/research/{DOMAIN_EN}-supplement-{YYYY-MM-DD}.md
```

返回方式：交互型，Phase 2 检查补充文档是否写入来判断完成。

---

## 设计四：G2 门控更新

### 自动验证项

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 评估完成 | evaluate-research 返回有效 JSON | status 字段存在且 issues 已解析 |
| ② 所有 issue 已处置 | 检查每条 issue 是否有 A/B/C 选择 | 无未处置项 |
| ③ 补充文档（按需） | 若有 CONFIRMED_GAPS，检查补充文档存在 | 文件存在且非空；无 gap 时跳过 |
| ④ 候选数量满足 | 对象 ≥ 3，逻辑 ≥ 1，动作 ≥ 1 | 与 G1 一致 |

### 人类确认

> "评估已完成，gap 已处置。这份调研报告（含补充内容）是否已准确反映了【{DOMAIN_CN}】的核心业务概念，可以进入提取阶段？
> - ✅ 确认，可以开始提取
> - ✏️ 还有补充
> - 🔄 重新评估（调研报告质量存疑）"

### chain-state 记录格式

```markdown
| 2 | 访谈确认 | ✅ 通过 | {时间} | 评估 issue {N} 条，gap 确认 {K} 条，补充文档：{有/无} |
```

```markdown
### G2 通过记录（{YYYY-MM-DD HH:MM}）
- 调研报告：research/{DOMAIN_EN}-research.md ✅
- 补充文档：research/{DOMAIN_EN}-supplement-{date}.md ✅（若有）
- 传入 Phase 3：RESEARCH_REPORT_PATH + SUPPLEMENT_PATH（可选）
```

---

## 涉及文件变更

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `AgentFile/phases/phase-2-interview.md` | 重写 | 新增 evaluate 步骤，interview 改为按需触发 |
| `AgentFile/skills/interview/SKILL.md` | 重构 | 移除全量访谈状态机，新增 GAP_ELICITATION / OPEN_FLOOR |
| `AgentFile/skills/evaluate-research/SKILL.md` | 新增 | 分析型，5 维度评估，输出结构化 JSON |
| `AgentFile/phases/phase-3-flowchart-generate.md` | 小改 | 输入参数新增可选 `SUPPLEMENT_PATH` |
