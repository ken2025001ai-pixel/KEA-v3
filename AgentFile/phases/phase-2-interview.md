# Phase 2: 访谈确认（Interview Confirmation）

## 定位

本体萃取技能链第 2 阶段。以调研报告为底稿，通过对话访谈让业务专家确认领域边界、核心概念和关键流程，产出访谈摘要作为后续提取的权威输入。

**强制阶段**：即使有完整源文档，也必须经过业务专家的显式确认。访谈可以是"快速对齐"（5-10 分钟），但不可跳过。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` | 领域中文名 |
| `DOMAIN_EN` | 领域英文名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 产出的调研报告路径 |

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认：

- Phase 1 状态为 `✅ 通过` → 继续
- Phase 1 状态不为 `passed` → 终止，提示："请先完成并通过 Phase 1（调研）"

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

将 Phase 2 状态更新为 `🔄 进行中`。

### Step 2: 调用 interview-agent

读取 `~/.claude/skills/kea/skills/interview/SKILL.md`，以访谈模式执行，传入：

```
RESEARCH_REPORT_PATH: {RESEARCH_REPORT_PATH}
DOMAIN_CN: {DOMAIN_CN}
DOMAIN_EN: {DOMAIN_EN}
```

interview-agent 将执行以下状态：`GREETING → DOMAIN_DISCOVERY → OBJECT_INTERVIEW → OBJECT_CONFIRM → LOGIC_INTERVIEW → LOGIC_CONFIRM → ACTION_INTERVIEW → ACTION_CONFIRM → RULE_INTERVIEW → RULE_CONFIRM → SUMMARY`

**注意**：interview-agent 在 SUMMARY 状态用户选择【保存并生成索引】时，除写入 Ontology 文档外，还会将访谈摘要写入 Vault。

### Step 3: 获取访谈摘要路径

访谈完成后，读取摘要文件路径：
`{VAULT_PATH}/RAWData/KEAOutput/interviews/{YYYY-MM-DD}-{DOMAIN_EN}-summary.md`

向用户展示：

```
访谈完成。摘要已保存至：interviews/{filename}

访谈确认结果：
  对象已确认：{N} 个 — {名称列表}
  流程已确认：{K} 个 — {名称列表}
  动作已确认：{M} 个 — {名称列表}
  规则已确认：{R} 条（或"无独立规则"）
```

## 门控评估（G2）

### 自动验证项

读取访谈摘要文件（YAML front matter + 正文）：

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 摘要文件已写入 Vault | 检查文件存在 | 文件存在且非空 |
| ② 已确认对象数 | 读取 `objects_confirmed` 字段 | ≥ 1 |
| ③ 已确认逻辑数 | 读取 `logic_confirmed` 字段 | ≥ 1 |
| ④ 领域名与 DOMAIN_EN 一致 | 读取 `domain` 字段 | 与 DOMAIN_EN 匹配 |

展示自动验证结果。如有失败项，说明原因，不进入人类确认。

### 人类确认

自动验证全部通过后，询问：

> "上述核心业务概念是否已经准确反映了专家的理解？
>
> - ✅ 确认：核心业务概念已确认，可以开始提取
> - ✏️ 需要补充：[说明缺失或错误的内容]
> - 🔄 重新访谈：需要找其他专家或补充更多信息"

- **确认** → 进入门控通过流程
- **需要补充** → 针对性补充访谈（interview-agent 继续对话）→ 更新摘要 → 重新评估
- **重新访谈** → 重新执行 Step 2

## 门控通过 → 更新 chain-state.md

写入 G2 通过记录：

```markdown
| 2 | 访谈确认 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 确认：对象{N}/逻辑{K}/动作{M}/规则{R} |
```

在"门控记录"节追加：

```markdown
### G2 通过记录（{YYYY-MM-DD HH:MM}）
- 摘要路径：interviews/{filename} ✅
- objects_confirmed：{N} ≥ 1 ✅
- logic_confirmed：{K} ≥ 1 ✅
- 人类确认："核心业务概念已确认，可以开始提取" ✅
```

更新 `current_phase: 3`。

告知用户：

> "G2 通过。**下一阶段：流程图生成（Phase 3）**
> 是否现在继续？[继续 / 暂停]"

## 门控失败 → 回退处理

**自动验证失败**（摘要文件缺失/字段异常）：
- 检查 interview-agent 是否正确保存了文件
- 如未保存，重新执行 Step 2 的 SUMMARY 阶段（补存）

**人类拒绝**（需要补充/重新访谈）：
- 按用户指示执行，重新评估

在 chain-state.md 追加回退记录。
