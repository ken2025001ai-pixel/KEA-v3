# Phase 5: 对象提取（Object Extraction）

## 定位

本体萃取技能链第 5 阶段。基于调研报告、访谈摘要和**已校验的流程图**，提取结构化业务对象文档，并通过覆盖率检查和人类确认确保完整性。

流程图是对象提取的**首要数据源**——经专家确认的流程图中出现的名词性实体（输入/输出参数、数据引用）是最可靠的对象候选。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `DIAGRAMS_DIR` | G3/G4 已校验流程图目录 |
| `COVERAGE_THRESHOLD` | 覆盖率阈值，默认 80（读自 chain-state.md front matter） |

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认：

- Phase 4（或 Phase 3，若跳过 Phase 4）状态为 `✅ 通过` → 继续
- 否则 → 终止，提示需先完成 Phase 3/4（流程图生成与校验）

## 执行步骤

### Step 1: 确定提取模式

检查 `{VAULT_PATH}/30-Ontology/objects/{DOMAIN_EN}/` 目录：

- **为空**（首次提取）→ `MODE = full`
- **有文件**（回退后重入）→ `MODE = incremental`，收集 `EXISTING_FILES` = 目录下已有文件名列表，告知用户："检测到已有对象文件，将以增量模式补充提取。"

### Step 2: 更新 chain-state.md 为 in_progress

### Step 3: Dispatch 对象提取 Agent

读取 `~/.claude/skills/kea/skills/extract-objects/SKILL.md`，以 Subagent 形式 Dispatch：

```
DIAGRAMS_DIR: {DIAGRAMS_DIR}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {VAULT_PATH}/30-Ontology/objects/{DOMAIN_EN}/
EXISTING_FILES: {EXISTING_FILES（MODE=incremental 时）}
```

等待完成，读取返回状态。

### Step 4: 处理提取结果

根据 sub-skill 返回的状态码分别处理：

**DONE** → 直接进入 Step 5

**DONE_WITH_CONCERNS** → 疑虑前置处理（必须在专家审视文件前完成）：

展示疑虑清单：

```
对象提取完成（新增 {M} 个），但以下 {K} 项需要您先确认：

  ⚠️ {对象名}：{疑虑描述，如"流程图中出现但缺少属性细节，仅生成框架"}
     → 请在 Obsidian 中查看：objects/{DOMAIN_EN}/{对象名}.md
     处置：A 保留（后续补充属性）| B 删除（不是独立对象）| C 合并到 {另一对象}

  ⚠️ {对象名}：{疑虑描述，如"两个流程图中名称略有差异，已按 X 名称统一"}
     → 请确认：A 统一名称正确 | B 应使用 {另一名称}
  ...
```

等待用户逐项处置完毕后，执行对应操作（删除文件 / 重命名 / 保留标注）。

**NEEDS_CONTEXT** → 展示缺失信息，询问用户补充后重新 Dispatch Step 3。

**BLOCKED** → 展示卡点和已尝试方案，询问用户处置方式。

### Step 5: 专家审视对象文件

提示专家在 Obsidian 中打开对象目录浏览文件：

> "已生成 {N} 个对象文件，请在 Obsidian 中审视：
>
> 📂 `30-Ontology/objects/{DOMAIN_EN}/`
>
> 每个文件包含：对象描述、属性清单（含主键标注）、关联对象。
> 也可在 Graph View 中查看对象关系网络（红色节点 = 业务对象）。
>
> 审视完毕后回复"继续"进入自动校验，或直接指出需要修改的内容。"

等待用户回复：
- **继续** → 进入 Step 6
- **修改指令** → 按指令修改文件 → 等待再次"继续"

### Step 6: Dispatch 覆盖率检查 Agent

读取 `~/.claude/skills/kea/skills/coverage-check/SKILL.md`，Dispatch：

```
SOURCE_PATHS: {DIAGRAMS_DIR},{RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {VAULT_PATH}/30-Ontology/objects/{DOMAIN_EN}/
CHECK_TYPE: objects
```

等待完成，获取覆盖率数值和未覆盖清单。

## 门控评估（G5）

### 自动验证项

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 对象数量 | 统计 objects/{DOMAIN_EN}/ 下 .md 文件数 | ≥ `ceil(G1候选对象数 × COVERAGE_THRESHOLD / 100)` |
| ② 覆盖率 | 读取 coverage-check 报告 | ≥ COVERAGE_THRESHOLD% |
| ③ 每个对象有主键 | Grep 每个文件中 `主键.*是` | 全部对象至少 1 个主键字段 |
| ④ 结构错误 | 运行 rule-check-agent（仅 objects 范围） | 错误 = 0 |
| ⑤ 死链 | 检查每个文件中 `[[链接]]` 是否有对应文件 | 死链 = 0 |

展示检查结果。如有失败项（❌），说明原因，进入失败处理流程。

### 人类确认

自动验证全部通过后，展示校验摘要，询问最终确认：

> "自动校验全部通过：
>
> | 检查项 | 结果 |
> |--------|------|
> | 对象数量 | {N} 个（覆盖率 {X}%） |
> | 主键完整 | {N}/{N} ✅ |
> | 结构错误 | 0 ✅ |
> | 死链 | 0 ✅ |
>
> 您已在 Obsidian 中审视过对象文件。请最终确认：
>
> - ✅ 确认：对象提取完整准确，进入逻辑提取
> - ✏️ 需要修改 {对象名}：[说明修改内容]
> - ➕ 缺少 {对象名}：[说明该对象的业务含义]"

- **确认** → 门控通过
- **需要修改** → 直接修改对应文件 → 重新评估条件 ④⑤ → 询问是否继续
- **缺少** → 触发增量提取（将缺失对象名加入补充提取目标）→ 重新 Step 3 → 重新评估

## 门控通过 → 更新 chain-state.md

```markdown
| 5 | 对象提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 提取{N}个，覆盖率{X}% |
```

门控记录：

```markdown
### G5 通过记录（{YYYY-MM-DD HH:MM}）
- 对象数量：{N} ≥ {ceil(G1候选 × 0.8)} ✅
- 覆盖率：{X}% ≥ {COVERAGE_THRESHOLD}% ✅
- 主键完整：{N}/{N} ✅
- 结构错误：0 ✅
- 死链：0 ✅
- 人类确认："对象定义准确完整" ✅
```

更新 `current_phase: 6`。

## 门控失败 → 回退处理

**覆盖率 / 数量不足**：
- 询问原因：领域边界偏差 or 提取遗漏？
  - 提取遗漏 → 增量补提取（不回退，直接 Step 3 增量模式）
  - 领域边界偏差（如发现大量应纳入的对象）→ **回退到 Phase 2**，补充访谈
  - 候选数本身不准确 → **回退到 Phase 1**，追加调研

**主键缺失**：
- 指定对应文件，直接修改补充主键字段，重新验证条件 ③

**结构错误 / 死链**：
- 当前阶段内修复对应文件，重新验证条件 ④⑤

在 chain-state.md 追加回退记录（如发生阶段回退）：

```markdown
### 回退记录（{YYYY-MM-DD HH:MM}）
- 触发阶段：G5 失败
- 原因：{覆盖率不足 / 领域边界偏差 / ...}
- 回退目标：Phase {N}
- 处置：{增量补提取 / 补充访谈 / 追加调研}
```
