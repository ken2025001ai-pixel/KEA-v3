# Phase 2: 访谈确认（Interview Confirmation）

## 定位

本体萃取技能链第 2 阶段。由 Agent 评估 Phase 1 调研报告质量，专家逐条确认评估建议，按需触发定向补充访谈，产出补充调研文档供后续提取使用。

**强制阶段**：即使有完整源文档，也必须经过专家对报告质量的显式评估与确认。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` | 领域中文名 |
| `DOMAIN_EN` | 领域英文名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 产出的调研报告路径 |

输出（写入 chain-state 供 Phase 3 使用）：
- `SUPPLEMENT_PATH`：补充文档路径（若有，否则为空）

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认：
- Phase 1 状态为 `✅ 通过` → 继续
- 否则 → 终止，提示"请先完成并通过 Phase 1（调研）"

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

将 Phase 2 状态更新为 `🔄 进行中`，`last_updated` 更新为当前时间。

### Step 2: Dispatch evaluate-research

读取 `~/.claude/skills/kea/skills/evaluate-research/SKILL.md`，以 Subagent 形式 Dispatch，传入：

```
RESEARCH_REPORT_PATH: {RESEARCH_REPORT_PATH}
DOMAIN_CN: {DOMAIN_CN}
DOMAIN_EN: {DOMAIN_EN}
```

等待返回，解析 JSON 结果。

**若返回 NEEDS_CONTEXT**：展示错误，告知用户检查 Phase 1 报告路径，终止。

### Step 3: 呈现评估结果，专家逐条确认

向用户展示评估摘要：

```
评估完成。{overall_assessment}

候选统计：对象 {N} / 逻辑 {K} / 动作 {M} / 规则 {R}
置信度：高 {H} / 中 {M} / 低 {L}（低置信占比 {X}%）
```

若 `issues` 为空：

```
未发现明显问题，报告质量良好。
```

跳至 Step 5（G2 门控）。

若 `issues` 非空，逐条展示，每条等待专家回复后再展示下一条：

```
发现 {N} 个待确认项，请逐条确认：

第 {i}/{N} 条 [{dimension}]
⚠️  {message}
    建议：{suggestion}

→ A 确认为 gap，需补充
  B 忽略（不在本次范围）
  C 我来说明：[请输入]
```

收集每条回复，汇总为 `CONFIRMED_GAPS`（选 A 或 C 的条目）：

```json
[
  {
    "id": "issue-001",
    "dimension": "覆盖度",
    "message": "未发现入库相关对象候选",
    "expert_note": "（选 C 时的专家输入文本，选 A 时为空字符串）"
  }
]
```

### Step 4: 判断是否需要定向补充

若 `CONFIRMED_GAPS` 为空：告知用户"所有问题已处置，无需补充访谈"，直接进入 Step 6（G2 门控）。

若 `CONFIRMED_GAPS` 非空：

定义补充文档路径：
```
SUPPLEMENT_PATH = {VAULT_PATH}/RAWData/KEAOutput/research/{DOMAIN_EN}-supplement-{YYYY-MM-DD}.md
```

告知用户：
> "已确认 {K} 个 gap，现在开始定向补充访谈。"

读取 `~/.claude/skills/kea/skills/interview/SKILL.md`，以 Subagent 形式 Dispatch，传入：

```
CONFIRMED_GAPS: {CONFIRMED_GAPS JSON}
RESEARCH_REPORT_PATH: {RESEARCH_REPORT_PATH}
SUPPLEMENT_OUTPUT_PATH: {SUPPLEMENT_PATH}
DOMAIN_CN: {DOMAIN_CN}
DOMAIN_EN: {DOMAIN_EN}
```

等待 interview-agent 自然完成（交互型，Phase 2 等待用户与 interview-agent 对话结束）。

### Step 5: 验证补充文档（若有）

若 `CONFIRMED_GAPS` 非空，检查 `SUPPLEMENT_PATH` 文件是否存在：

- **文件存在** → 继续
- **文件不存在** → 访谈可能被中断：
  > "未找到补充文档。是否重新开始定向补充？
  > - ✅ 重新开始
  > - ❌ 跳过补充（在 chain-state 备注中标注"补充未完成"）"

## 门控评估（G2）

### 自动验证项

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 评估已完成 | evaluate-research 返回有效 JSON | status 字段存在且已解析 |
| ② 所有 issue 已处置 | 检查每条 issue 是否有 A/B/C 选择记录 | 无未处置项 |
| ③ 补充文档（按需） | 若 CONFIRMED_GAPS 非空，检查文件存在 | 文件存在且非空；无 gap 时跳过 |
| ④ 候选数量满足 | 读取评估结果中 candidate_counts | objects ≥ 3，logic ≥ 1，actions ≥ 1 |

展示验证结果：

```
自动验证：
  ① 评估完成：✅
  ② issue 全部处置：✅（{N} 条，{K} 条确认为 gap，{M} 条忽略）
  ③ 补充文档：✅ {SUPPLEMENT_PATH}（或"无需补充"）
  ④ 候选数量：✅ 对象 {N}（≥3）/ 逻辑 {K}（≥1）/ 动作 {M}（≥1）
```

如有验证失败项，说明原因，不进入人类确认。

### 人类确认

自动验证全部通过后：

> "评估已完成，gap 已处置。这份调研报告（含补充内容）是否已准确反映了【{DOMAIN_CN}】的核心业务概念，可以进入提取阶段？
>
> - ✅ 确认，可以开始提取
> - ✏️ 还有补充
> - 🔄 重新评估（调研报告质量存疑）"

- **确认** → 门控通过
- **还有补充** → 重新执行 Step 4（增量模式，追加到现有 SUPPLEMENT_PATH）
- **重新评估** → 重新执行 Step 2

## 门控通过 → 更新 chain-state.md

写入 G2 通过记录：

```markdown
| 2 | 访谈确认 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 评估 issue {N} 条，gap 确认 {K} 条，补充文档：{有路径/无} |
```

在"门控记录"节追加：

```markdown
### G2 通过记录（{YYYY-MM-DD HH:MM}）
- 调研报告：research/{DOMAIN_EN}-research.md ✅
- 评估 issue：{N} 条（确认 {K} 条，忽略 {M} 条）
- 补充文档：{SUPPLEMENT_PATH}（若有）✅ / 无需补充
- 人类确认："可以进入提取阶段" ✅
```

在 chain-state.md front matter 中写入（供 Phase 3 读取）：

```yaml
supplement_path: {SUPPLEMENT_PATH}  # 若无补充则留空
```

更新 `current_phase: 3`，`last_updated`。

告知用户：

> "G2 通过。**下一阶段：流程图生成（Phase 3）**
> 是否现在继续？[继续 / 暂停]"

## 门控失败 → 回退处理

**自动验证失败（issue 未全部处置）**：
- 展示未处置的 issue 列表，要求专家逐条确认后重新验证

**自动验证失败（补充文档缺失）**：
- 询问是否重新执行 Step 4

**人类拒绝（需要补充/重新评估）**：
- 按用户指示执行，重新评估

在 chain-state.md 追加回退记录。
