# Phase 11: 完备性验证（Coverage Check）

## 定位

本体萃取技能链第 11 阶段。将已提取的 Ontology 文档与原始源材料进行覆盖率对比，确保没有遗漏的业务概念，对每个未覆盖项做出明确决策。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `OBJECTS_DIR` / `LOGIC_DIR` / `ACTIONS_DIR` / `RULES_DIR` | 各类型目录 |
| `COVERAGE_THRESHOLD` | 覆盖率阈值（来自 chain-state.md front matter） |

## 前置条件检查

确认 Phase 10 状态为 `✅ 通过`，否则终止。

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

### Step 2: 运行 kea status 获取基线统计

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json status {VAULT_PATH}/30-Ontology/
```

从 JSON 输出中提取各类型文档数量和状态，作为覆盖率仪表盘的基线数据。将 `{doc_count}`、`{doc_stats}` 等结果传入 Step 3 的 Dispatch prompt。

### Step 3: Dispatch 完备性检查 Agent

读取 `~/.claude/skills/kea/skills/coverage-check/SKILL.md`，Dispatch，全量模式：

```
SOURCE_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {OBJECTS_DIR}
LOGIC_DIR: {LOGIC_DIR}
ACTIONS_DIR: {ACTIONS_DIR}
RULES_DIR: {RULES_DIR}
CHECK_TYPE: all
KEY_DOC_COUNTS: {kea status 输出的各类型文档计数}
```

等待完成，获取覆盖率报告。

### Step 4: 展示覆盖率仪表盘

```
完备性验证结果：

  对象覆盖率：{OC}/{OT} ({OP}%)   {'✅' if OP >= THRESHOLD else '❌'}
  逻辑覆盖率：{LC}/{LT} ({LP}%)   {'✅' if LP >= THRESHOLD else '❌'}
  动作覆盖率：{AC}/{AT} ({AP}%)   {'✅' if AP >= THRESHOLD else '❌'}
  规则覆盖率：{RC}/{RT} ({RP}%)   {'✅' if RP >= THRESHOLD else '❌' if RT > 0 else 'N/A'}

  ─────────────────────────────
  总覆盖率：{TC}/{TT} ({TP}%)

  [覆盖率阈值：{COVERAGE_THRESHOLD}%]
```

若有未覆盖项（❌），展示明细：

```
未覆盖项明细：

  对象未覆盖（{N} 个）：
  ❌ {名称} — {简短描述}
  ...

  逻辑未覆盖（{K} 个）：
  ❌ {名称} — {简短描述}
  ...
```

### Step 4: 对每个未覆盖项要求决策

对每个未覆盖项，逐一询问或批量处理：

> "以下 {N} 个条目在源材料中被提及，但未提取为 Ontology 文档：
>
> 请为每项做出决策：
> - **A** 提取：纳入本次 Ontology，需要回退补充提取
> - **B** 排除：不在本次范围内（需填写原因）
> - **C** 延后：已知但本次暂不处理（需填写原因）
>
> 格式：`1=A, 2=B(超出采购领域范围), 3=C(待下期迭代)`"

记录每个未覆盖项的决策，写入报告。

## 门控评估（G11）

### 自动验证项

| 条件 | 通过标准 | 是否可绕过 |
|------|---------|---------|
| ① 对象覆盖率 | ≥ COVERAGE_THRESHOLD% | 可以通过 B/C 决策达到阈值 |
| ② 逻辑覆盖率 | ≥ COVERAGE_THRESHOLD% | 同上 |
| ③ 动作覆盖率 | ≥ COVERAGE_THRESHOLD% | 同上 |
| ④ 每个未覆盖项有决策 | 所有 ❌ 项均有 A/B/C 决策且原因非空 | **❌ 不可绕过** |
| ⑤ 报告已保存 | 报告文件存在 | ❌ 不可绕过 |

**覆盖率计算说明**：
- 标注 A（提取）的项→纳入"需要补充"，覆盖率暂不达标，需触发回退
- 标注 B（排除）/C（延后）的项→从分母中移除，覆盖率重新计算
- 调整后覆盖率 ≥ 阈值 → 条件 ①②③ 通过

### 人类确认

条件全部满足后询问：

> "完备性验证通过（调整后覆盖率：对象 {OP}%，逻辑 {LP}%，动作 {AP}%）。
>
> - ✅ 确认：未覆盖项决策已完成
> - ✏️ 需要调整决策 [说明]"

## 门控通过 → 更新 chain-state.md

```markdown
| 11 | 完备性验证 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 对象{OP}%/逻辑{LP}%/动作{AP}%，未覆盖项已决策 |
```

门控记录含：各类覆盖率、未覆盖项决策汇总（A/B/C 各多少条）、报告路径。

更新 `current_phase: 12`。

## 门控失败 → 回退处理

**有未覆盖项决策为 A（需要提取）**：

触发回退，补充提取对应类型的文档：

| 决策 A 的类型 | 回退目标 |
|-------------|---------|
| 对象类 | Phase 5（增量） |
| 逻辑类 | Phase 6（增量） |
| 动作类 | Phase 7（增量） |
| 规则类 | Phase 8（增量） |
| 混合多类型 | 从最早的阶段开始，依次增量补充 |

补充提取完成后，重新运行 Phase 9→10→11（快速通道：如果补充的文档经 rule-check 和 semantic-check 子集验证无问题，可直接重新运行 Phase 11）。

**覆盖率仍低于阈值（排除/延后后仍不足）**：
- 说明源材料中的候选项比实际提取数多很多
- 需要回退到 Phase 1 追加调研，或确认候选清单本身有误（需与用户讨论）

在 chain-state.md 追加回退记录（如发生阶段回退）。
