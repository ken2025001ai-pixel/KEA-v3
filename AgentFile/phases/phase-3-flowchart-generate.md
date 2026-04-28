# Phase 3: 流程图生成（Flowchart Generation）

## 定位

本体萃取技能链第 3 阶段。从源文档提取流程候选，由专家确认范围，Dispatch generate-flowcharts sub-skill 批量生成 Mermaid 流程图，经结构校验和批量人类确认后作为后续提取的**权威业务基准**。

**意义**：自然语言存在歧义；Mermaid 流程图将流程逻辑形式化，迫使歧义在提取之前消解。专家对流程图的背书等同于对业务逻辑真相的背书。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 产出的调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `SUPPLEMENT_PATH` | 可选，G2 补充调研文档路径（chain-state front matter 中 `supplement_path` 字段，为空时忽略） |
| `PROJECT_ROOT` | kea 工具层根目录（用于运行 `python3 -m kea`） |

目录变量：
```
DIAGRAMS_DIR: {VAULT_PATH}/30-Ontology/diagrams/{DOMAIN_EN}/
```

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认 Phase 2 状态为 `✅ 通过`，否则终止。

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

将 Phase 3 状态更新为 `🔄 进行中`。

### Step 2: 确定流程候选清单并获取用户确认

读取 `RESEARCH_REPORT_PATH` 和 `INTERVIEW_SUMMARY_PATH`，若 `SUPPLEMENT_PATH` 非空则同时读取补充文档，三份文档合并提取逻辑/流程候选清单。补充文档中的候选优先级高于调研报告。

检查 `DIAGRAMS_DIR` 中是否已有 `.md` 文件：
- **目录为空** → `EXISTING_FILES = []`，全量模式
- **目录已有文件** → 记录 `EXISTING_FILES`（已有文件名列表），展示给用户

展示候选清单并请用户确认生成范围：

```
流程候选清单（共 {N} 个）：

  【P1】{流程名} — {一句话描述}
  【P2】{流程名} — {一句话描述}
  ...

  已有流程图（如有）：
  ✅ 【P3】{流程名} — 已存在，默认保留

请确认生成范围：
  ✅ 全部生成（{N} 个，已有的重新覆盖）
  🔄 仅生成缺失（{M} 个，已有的保留）
  ➕ 添加额外流程：[描述]
  ✂️ 从清单移除：[P{n}]
```

等待用户确认，得到 `CONFIRMED_CANDIDATES`（JSON 数组，每项含 `name` + `description`）。

### Step 3: Dispatch generate-flowcharts sub-skill

读取 `~/.claude/skills/kea/skills/generate-flowcharts/SKILL.md`，以 Subagent 形式 Dispatch，传入：

```
CONFIRMED_CANDIDATES: {CONFIRMED_CANDIDATES JSON}
RESEARCH_REPORT_PATH: {RESEARCH_REPORT_PATH}
INTERVIEW_SUMMARY_PATH: {INTERVIEW_SUMMARY_PATH}
SUPPLEMENT_PATH: {SUPPLEMENT_PATH}（可选）
DIAGRAMS_DIR: {DIAGRAMS_DIR}
DOMAIN_CN: {DOMAIN_CN}
DOMAIN_EN: {DOMAIN_EN}
EXISTING_FILES: {EXISTING_FILES JSON}（可选）
```

等待返回，读取状态码。

**DONE_WITH_CONCERNS** → 疑虑前置：展示疑虑清单，告知用户哪些流程置信度低，进入 Step 4。

**NEEDS_CONTEXT / BLOCKED** → 展示问题，询问用户是否补充信息重试，或回退至 Phase 2。

**DONE** → 直接进入 Step 4。

### Step 4: 结构校验（kea flowchart-check）

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json flowchart-check {DIAGRAMS_DIR}
```

读取 JSON，展示结果：

```
结构校验（S1-S4）：
  总计：{N} 个，通过：{P} 个，失败：{F} 个
```

若 `summary.failed > 0`，展示失败详情：

```
  ❌ {文件名}：
     [S1] {message}
     [S3] {message}
```

提示：
> "请修复上述结构问题后回复"继续"重新校验。修复方式：直接编辑 `{DIAGRAMS_DIR}` 下对应文件。"

等待用户回复后重跑 `kea flowchart-check`，循环直到 `summary.failed = 0`。

### Step 5: 批量人类确认

结构校验全部通过后：

```
{N} 个流程图已生成并通过结构校验（S1-S4）。

请在 Obsidian 中查看渲染后的流程图：
  📁 30-Ontology/diagrams/{DOMAIN_EN}/

所有流程图审阅完毕后，请回复：
  ✅ 全部确认，继续
  ✏️ 需要调整：[列出流程名 + 具体修改]
```

若用户列出调整项，逐项修改对应 Mermaid 文件，修改后重跑 `kea flowchart-check` 确认无结构破坏，再次展示提示引导用户确认。

循环直到用户回复"全部确认"。

## 门控评估（G3）

### 自动验证项

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json flowchart-check {DIAGRAMS_DIR}
```

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 流程图文件已生成 | 统计 DIAGRAMS_DIR 下 .md 文件数 | ≥ CONFIRMED_CANDIDATES 数量 |
| ② 结构校验全部通过 | kea flowchart-check `summary.failed` | = 0 |
| ③ 专家已批量确认 | 用户在 Step 5 回复"全部确认" | 有记录 |

展示验证结果：

```
自动验证：
  ① 流程图数量：✅ {N} 个（≥ 候选数 {M}）
  ② 结构校验：✅ 全部通过（S1-S4）
  ③ 专家确认：✅ 已批量确认
```

如有失败项，说明原因，不进入人类确认。

### 人类确认

验证全部通过后：

> "流程图生成完成：
>
> - 已生成：{N} 个流程图
> - 结构校验：✅ 全部通过
> - 专家确认：✅ 已完成
>
> 是否进入流程图校验（Phase 4）做深度语义检查？
> - ✅ 继续：进入 Phase 4（建议）
> - ⏭️ 跳过：直接进入 Phase 5（对象提取）"

- **继续** → 更新 chain-state.md，进入 Phase 4
- **跳过** → 更新 chain-state.md，`current_phase: 5`

## 门控通过 → 更新 chain-state.md

```markdown
| 3 | 流程图生成 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 生成 {N} 个，结构校验通过，专家批量确认 |
```

追加门控记录：

```markdown
### G3 通过记录（{YYYY-MM-DD HH:MM}）
- 流程图数量：{N} 个 ✅
- 结构校验（kea flowchart-check）：全部通过 ✅
- 专家批量确认：✅
- 目录：diagrams/{DOMAIN_EN}/
```

更新 `current_phase: 4`（或 `5` 若跳过）。

## 门控失败 → 回退处理

| 失败类型 | 处置 |
|---------|------|
| sub-skill BLOCKED | 询问是否补充文档重试或回退 Phase 2 |
| 结构校验失败循环 > 3 次 | 提示用户考虑简化流程图或回退 Phase 2 补充访谈 |
| 专家拒绝全部流程图 | 回退至 Phase 2 重新访谈 |

在 chain-state.md 追加回退记录。
