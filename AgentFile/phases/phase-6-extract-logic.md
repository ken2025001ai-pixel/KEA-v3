# Phase 6: 逻辑提取（Logic Extraction）

## 定位

本体萃取技能链第 6 阶段。基于**已校验的流程图**、调研报告、访谈摘要和已确认的对象文档，提取业务逻辑/流程文档。每个流程图几乎 1:1 对应一个逻辑文档。所有逻辑文档中的 `[[链接]]` 必须指向已存在的对象文件。

## 输入参数

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` / `DOMAIN_EN` | 领域名 |
| `VAULT_PATH` | Vault 路径 |
| `CHAIN_STATE_PATH` | chain-state 文件路径 |
| `RESEARCH_REPORT_PATH` | G1 调研报告路径 |
| `INTERVIEW_SUMMARY_PATH` | G2 访谈摘要路径 |
| `DIAGRAMS_DIR` | G3/G4 已校验流程图目录 |
| `OBJECTS_DIR` | Phase 5 输出的对象文档目录 |
| `COVERAGE_THRESHOLD` | 覆盖率阈值（来自 chain-state.md） |

## 前置条件检查

读取 `CHAIN_STATE_PATH`，确认：

- Phase 5 状态为 `✅ 通过` → 继续
- 否则 → 终止，提示需先完成 Phase 5（对象提取）

## 执行步骤

### Step 1: 确定提取模式

检查 `{VAULT_PATH}/30-Ontology/logic/{DOMAIN_EN}/`：

- 为空 → `MODE = full`
- 有文件 → `MODE = incremental`，收集 `EXISTING_FILES`

### Step 2: 更新 chain-state.md 为 in_progress

### Step 3: Dispatch 逻辑提取 Agent

读取 `~/.claude/skills/kea/skills/extract-logic/SKILL.md`，Dispatch：

```
DIAGRAMS_DIR: {DIAGRAMS_DIR}
SUMMARY_PATHS: {RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
OBJECTS_DIR: {OBJECTS_DIR}
LOGIC_DIR: {VAULT_PATH}/30-Ontology/logic/{DOMAIN_EN}/
EXISTING_FILES: {EXISTING_FILES（如有）}
```

等待完成，读取返回状态。

### Step 4: 处理提取结果

根据 sub-skill 返回的状态码分别处理：

**DONE** → 直接进入 Step 5

**DONE_WITH_CONCERNS** → 疑虑前置处理：

```
逻辑提取完成（新增 {M} 个），但以下 {K} 项需要您先确认：

  ⚠️ {逻辑名}：{疑虑描述，如"流程图判断分支在逻辑步骤中缺少细节，已标注 TODO"}
     → 请在 Obsidian 中查看：logic/{DOMAIN_EN}/{逻辑名}.md
     处置：A 保留（后续补充）| B 此流程不需要独立逻辑文档 | C 合并到 {另一逻辑}

  ⚠️ {逻辑名}：{疑虑描述，如"引用了对象 X 但 OBJECTS_DIR 中不存在，已标注为待提取"}
     → 处置：A 回退 Phase 5 补提取该对象 | B 该引用应改为 {已有对象名}
  ...
```

等待用户逐项处置后执行对应操作。

**NEEDS_CONTEXT** → 展示缺失信息，询问用户补充后重新 Dispatch Step 3。

**BLOCKED** → 展示卡点和已尝试方案，询问用户处置方式。

### Step 5: 专家审视逻辑文件

> "已生成 {K} 个逻辑文件，请在 Obsidian 中审视：
>
> 📂 `30-Ontology/logic/{DOMAIN_EN}/`
>
> 每个文件包含：业务描述、对象/动作/流程关联、输入输出参数表、逻辑步骤伪代码。
> 也可在 Graph View 中查看逻辑关联网络（蓝色节点 = 业务逻辑）。
>
> 审视完毕后回复"继续"进入自动校验，或直接指出需要修改的内容。"

等待用户回复：
- **继续** → 进入 Step 6
- **修改指令** → 按指令修改文件 → 等待再次"继续"

### Step 6: Dispatch 覆盖率检查 Agent

```
SOURCE_PATHS: {DIAGRAMS_DIR},{RESEARCH_REPORT_PATH},{INTERVIEW_SUMMARY_PATH}
LOGIC_DIR: {VAULT_PATH}/30-Ontology/logic/{DOMAIN_EN}/
CHECK_TYPE: logic
```

等待完成。根据返回结果：
- **返回有效覆盖率报告** → 获取覆盖率数值和未覆盖清单，进入 Step 7
- **返回空或格式异常** → 询问用户："覆盖率报告异常，是否跳过覆盖率检查？"
- **BLOCKED / NEEDS_CONTEXT** → 展示原因，询问用户处置

### Step 7: 运行 kea validate 结构校验

```bash
cd {PROJECT_ROOT} && python3 -m kea --format json validate {LOGIC_DIR}
```

从 JSON 输出中提取：
- `errors` — 结构错误数（条件 ⑦）
- `reports[].issues[]` 中 category 为 `引用失效` 的 issue — 即 dead links（条件 ③）
- `reports[].issues[]` 中 category 为 `输入缺失` / `输出缺失` 的 issue（条件 ④）
- `reports[].issues[]` 中 category 为 `伪代码引用失效` 的 issue — 子流程引用错误（条件 ⑥）

条件 ⑤（判断节点分支完整性）仍需手工检查：Grep 逻辑描述中以 `?` 结尾的行，检查后续是否有 `- 若` 分支。

若 `errors > 0`，展示错误明细，询问用户处置方式。
    
## 门控评估（G6）

### 自动验证项

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 逻辑数量 | 统计 logic/{DOMAIN_EN}/ 下 .md 文件数 | ≥ `ceil(G1候选逻辑数 × COVERAGE_THRESHOLD / 100)` |
| ② 覆盖率 | 读取 coverage-check 报告 | ≥ COVERAGE_THRESHOLD% |
| ③ 对象链接有效性 | `kea validate` 输出中 category=`引用失效` 的 issue | 死链 = 0 |
| ④ 输入/输出表完整性 | `kea validate` 输出中 category=`输入缺失`/`输出缺失` 的 issue | 缺失 = 0 |
| ⑤ 判断节点分支完整性 | Grep 逻辑描述中以 `?` 结尾的行 | 每个判断节点 ≥ 2 个分支 |
| ⑥ 子流程引用一致性 | `kea validate` 输出中 category=`伪代码引用失效` 的 issue | 不一致 = 0 |
| ⑦ 结构错误 | `kea validate` 输出的 `errors` 字段 | 错误 = 0 |

**条件 ③ 是最高优先级验证**：死链意味着 Phase 5 输出不完整，必须回退。

展示所有验证结果。

### 人类确认

自动验证全部通过后，展示校验摘要，询问最终确认：

> "自动校验全部通过：
>
> | 检查项 | 结果 |
> |--------|------|
> | 逻辑数量 | {K} 个（覆盖率 {X}%） |
> | 对象死链 | 0 ✅ |
> | 输入/输出表 | {K}/{K} 完整 ✅ |
> | 判断分支 | 全部 ≥2 ✅ |
> | 子流程引用 | 一致 ✅ |
> | 结构错误 | 0 ✅ |
>
> 您已在 Obsidian 中审视过逻辑文件。请最终确认：
>
> - ✅ 确认：流程定义准确，分支完整，进入动作提取
> - ✏️ 需要修改 {逻辑名}：[说明修改内容]
> - ➕ 缺少 {逻辑名}：[说明该流程的业务用途]"

## 门控通过 → 更新 chain-state.md

```markdown
| 6 | 逻辑提取 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 提取{K}个，覆盖率{X}%，死链0 |
```

门控记录（G6 通过，记录各条件结果）。

更新 `current_phase: 7`。

## 门控失败 → 回退处理

| 失败条件 | 回退目标 | 处置方式 |
|---------|---------|---------|
| ③ 死链（对象缺失） | Phase 5 | 增量补提取缺失对象 |
| ① 逻辑数量不足 / ② 覆盖率不足 | Phase 6（当前，增量） | 补充提取缺失逻辑 |
| ① 覆盖率不足 + 源文档不足 | Phase 1 | 追加调研 |
| ④ 输入输出表缺失 | Phase 6（当前） | 修复对应文件 |
| ⑤ 判断节点缺分支 | Phase 6（当前） | 修复对应文件 |
| ⑥ 子流程引用不一致 | Phase 6（当前） | 修复对应文件 |
| ⑦ 结构错误 | Phase 6（当前） | 修复对应文件 |

在 chain-state.md 追加回退记录（如发生阶段回退）。
