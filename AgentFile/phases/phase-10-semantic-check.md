# Phase 10: 语义校验（Semantic Check）

## 定位

本体萃取技能链第 10 阶段。对全部 Ontology 文档进行语义一致性检查，包括逻辑完整性、对象生命周期、字段引用有效性、规则目标一致性。**错误 = 0 是硬性要求。**

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `OBJECTS_DIR` / `LOGIC_DIR` / `ACTIONS_DIR` / `RULES_DIR` | 各类型目录 |

## 前置条件检查

确认 Phase 9 状态为 `✅ 通过`，否则终止。

## 执行步骤

### Step 1: 更新 chain-state.md 为 in_progress

### Step 2: Dispatch 语义校验 Agent

读取 `~/.claude/skills/kea/skills/semantic-check/SKILL.md`，Dispatch，全量模式：

```
OBJECTS_DIR: {OBJECTS_DIR}
LOGIC_DIR: {LOGIC_DIR}
ACTIONS_DIR: {ACTIONS_DIR}
RULES_DIR: {RULES_DIR}
MODE: full
```

等待完成，获取 JSON 格式问题数组。

### Step 3: 生成编号报告

解析 JSON，按文件分组，按严重性排序（错误 → 警告 → 建议），为每个问题分配**全局唯一编号**（从 1 开始，回归检查发现的新问题继续编号）。

报告保存至：
```
{VAULT_PATH}/RAWData/KEAOutput/reports/validation/{YYYY-MM-DD}-{DOMAIN_EN}-semantic-check.md
```

向用户展示编号汇总：

```
语义校验完成，共 {N} 个问题（{E} 错误 / {W} 警告 / {S} 建议）：

1. ❌ [逻辑缺陷] logic/xx.md → {message}
2. ❌ [字段不一致] objects/yy.md → {message}
3. ⚠️ [生命周期缺陷] objects/zz.md → {message}
4. ⚠️ [规则字段不存在] rules/rr.md → {message}
5. 💡 [描述歧义] actions/aa.md → {message}

要处理哪些？[全部 / 输入编号如 1,3 / 跳过]
```

### Step 4: 逐条处理选中问题

对每个被选中的问题，按编号顺序处理：

```
[语义修改 {N}/{TOTAL}]
编号：{id}
文件：{file}
问题：{message}

修改方案：
{具体的修改建议}

[确认修改] [我来提供方案] [跳过]
```

记录：已修复编号集合（`FIXED`）、已跳过集合（`SKIPPED`）、实际修改的文件集合（`MODIFIED_FILES`）。

### Step 5: 回归语义检查

如 `MODIFIED_FILES` 非空，**重新 Dispatch semantic-check-agent**，增量模式：

```
TARGET_FILES: {MODIFIED_FILES 中的文件名 stem}
MODE: incremental
```

过滤已在本轮出现过的问题（`file` + `message` 组合），仅报告新问题。

如有新问题：继续编号，追加到报告，重复 Step 3-4-5。

### Step 6: 更新报告状态标记

- 已修复编号 → `✅`
- 已跳过编号 → `⏭️`（接受时必须在跳过理由栏写明原因）
- 未选中的编号 → 保持原样

## 门控评估（G10）

### 自动验证项

| 条件 | 通过标准 | 是否可绕过 |
|------|---------|---------|
| ① 错误数 = 0 | 所有 severity="错误" 的问题已修复 | **❌ 硬性，不可绕过** |
| ② 警告已处理 | 每条警告已标注"已修复"或"已接受（原因不为空）" | 可接受但需说明 |
| ③ 报告已保存 | 报告文件存在 | ❌ 不可绕过 |

**硬性规则**：如报告中仍有 severity="错误" 的未处理问题，本阶段不通过。

### 人类确认

询问：

> "语义校验问题已处理完毕（错误 0，警告 {W} 条已处理）。
>
> - ✅ 确认：语义校验问题处理完毕
> - ✏️ 还需调整 [说明]"

## 门控通过 → 更新 chain-state.md

```markdown
| 10 | 语义校验 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 错误0，警告{W}已处理，建议{S}条 |
```

门控记录（含错误数、警告处理情况、报告路径）。

更新 `current_phase: 11`。

## 门控失败 → 回退处理

**错误修复后仍有错误**（回归检查引入新错误）：
- 当前阶段内继续修复，不触发跨阶段回退

**错误指向上游阶段质量问题**（如大量对象生命周期缺陷、大量字段引用错误）：

| 错误类型 | 回退目标 |
|---------|---------|
| 大量 `字段不一致`（字段引用无效） | Phase 5（对象） |
| 大量 `逻辑缺陷`（分支缺失） | Phase 6（逻辑） |
| 大量 `孤立动作` | Phase 7（动作） |
| 大量 `规则字段不存在` | Phase 8（规则）或 Phase 5（对象） |
| 大量 `生命周期缺陷` | Phase 5 或 Phase 6 |

回退阈值：同一类别错误 ≥ 5 条，或涉及文件数量 > 30% 时，触发跨阶段回退。

在 chain-state.md 追加回退记录（如发生跨阶段回退）。
