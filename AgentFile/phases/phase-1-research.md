# Phase 1: 调研（Research）

## 定位

本体萃取技能链第 1 阶段。通过调研建立领域背景知识，产出候选对象/逻辑/动作清单，为后续访谈和提取提供基础。

## 输入参数

由链式编排器传入：

| 参数 | 说明 |
|------|------|
| `DOMAIN_CN` | 领域中文名，如"采购管理" |
| `DOMAIN_EN` | 领域英文名（snake_case），如"procurement" |
| `VAULT_PATH` | 来自 `~/.claude/skills/kea/config.md` |
| `CHAIN_STATE_PATH` | `{VAULT_PATH}/RAWData/KEAOutput/{DOMAIN_EN}-chain-state.md` |
| `LOCAL_DOC_PATHS` | 可选，用户提供的本地文档路径（逗号分隔） |
| `LOCAL_DOC_DIRS` | 可选，用户提供的本地文档目录路径（逗号分隔，递归扫描） |

## 前置条件检查

读取 `CHAIN_STATE_PATH`：

- **首次执行**：文件不存在 → 初始化 chain-state.md（写入 YAML 头部和空表格），继续执行。
- **Phase 1 状态为 `rolled_back`**：允许重新执行，继续。
- **Phase 1 状态为 `passed`**：告知用户"Phase 1 已通过"，展示已有报告路径，询问是否重新调研（覆盖现有报告）。
- **Phase 1 状态为 `in_progress`**：告知用户"上次调研未完成"，询问是否继续或重新开始。

## 执行步骤

### Step 1: 确认是否有本地文档

如果 `LOCAL_DOC_PATHS` 和 `LOCAL_DOC_DIRS` 均未由编排器提供，询问用户：

> "是否有现成的领域文档（业务说明书、流程规范、PRD 等）？
> - 有文件 → 请提供文件路径（逗号分隔）
> - 有目录 → 请提供目录路径（逗号分隔，将递归扫描目录下所有支持格式文件）
> - 无 → 直接回复"无""

将用户回复解析为：
- 文件路径列表 → 记录为 `LOCAL_DOC_PATHS`（可为空列表）
- 目录路径列表 → 记录为 `LOCAL_DOC_DIRS`（可为空列表）

### Step 2: 文档预处理（Ingest）

若 `LOCAL_DOC_PATHS` 或 `LOCAL_DOC_DIRS` 非空，执行以下命令将源文档转换为标准化 MD：

```bash
python3 -m kea ingest \
  [--source <path>（每个 LOCAL_DOC_PATHS 条目）] \
  [--source-dir <dir>（每个 LOCAL_DOC_DIRS 条目）] \
  --domain {DOMAIN_EN} \
  --domain-cn {DOMAIN_CN} \
  --output-dir {VAULT_PATH}/RAWData/sources/{DOMAIN_EN}/ \
  --format json
```

读取 JSON 输出，向用户展示摘要：

```
文档预处理完成：
  成功：{success_count} 个（如 pdf×3, docx×2）
  跳过：{skipped_count} 个（已存在）
  失败：{failed_count} 个
```

若 `failed_count > 0`，展示失败文件列表和原因，询问：

> "部分文件转换失败，如何处理？
> - A 忽略失败文件，继续调研
> - B 修复后重试
> - C 取消本次调研"

- 选 A：继续，在 chain-state.md 的"备注"节记录被忽略的文件列表
- 选 B/C：停在 Step 2，不进入 Step 3

若预处理成功（或无文档），记录：
```
SOURCES_DIR = {VAULT_PATH}/RAWData/sources/{DOMAIN_EN}/
```

若无本地文档（LOCAL_DOC_PATHS 和 LOCAL_DOC_DIRS 均为空），跳过本步，`SOURCES_DIR` 留空。

在 chain-state.md 备注中记录收录摘要：`sources: {success_count} 个文档已归档至 RAWData/sources/{DOMAIN_EN}/`

### Step 3: 确定调研模式

信源优先级：**客户文档 → 模型内置知识 → 客户指定 URL / 文档引用的外部标准**

| 情况 | 调研模式 | 说明 |
|------|---------|------|
| `SOURCES_DIR` 非空 | `WEB_RESEARCH_MODE = supplement` | 文档优先，自动设定，不询问用户 |
| `SOURCES_DIR` 为空 | `WEB_RESEARCH_MODE = model_knowledge` | 依赖模型内置知识，按需查询客户指定源 |

同时收集用户在对话中明确提及的 URL：`EXPLICIT_WEB_SOURCES`（可为空列表）

### Step 4: 更新 chain-state.md 为 in_progress

将 Phase 1 状态更新为 `🔄 进行中`，`last_updated` 更新为当前时间。

### Step 5: 调研执行

若 `SOURCES_DIR` 非空，扫描该目录下所有 `.md` 文件（排除 `_manifest.md`），构建 `SOURCE_FILE_LIST`（文件绝对路径列表）。

读取 `~/.claude/skills/kea/skills/research/SKILL.md`，以 Subagent 形式 Dispatch，传入参数：

```
Research topic: {DOMAIN_CN}
Sources directory: {SOURCES_DIR}（如有，否则留空）
Source file list: {SOURCE_FILE_LIST}（如有，排除 _manifest.md 后的绝对路径列表）
Web research mode: {WEB_RESEARCH_MODE}
Explicit web sources: {EXPLICIT_WEB_SOURCES}（可为空列表）
Output path: {VAULT_PATH}/RAWData/KEAOutput/research/{DOMAIN_EN}-research.md
```

等待 Subagent 完成，读取返回状态。

### Step 6: 处理调研结果

根据 sub-skill 返回状态码处理：

**DONE** → 进入 Step 7

**DONE_WITH_CONCERNS** → 疑虑前置：

```
调研完成，但以下 {K} 项需要您确认：

  ⚠️ {候选名}：置信度低 — {原因，如"仅单一来源，未交叉验证"}
     处置：A 保留 | B 移除 | C 补充调研方向

  ⚠️ {候选名}：边界模糊 — {原因，如"可能属于相邻领域"}
     处置：A 纳入本领域 | B 排除
  ...
```

等待用户逐项处置后更新报告。

**NEEDS_CONTEXT** → 展示缺失信息（如"LOCAL_DOC_PATHS 文件不存在"），询问用户补充后重新 Dispatch。

**BLOCKED** → 展示卡点（如"网络调研无结果"），询问用户是否提供本地文档。

### Step 7: 展示调研摘要并引导审视

读取生成的报告，向用户展示：

```
调研完成。报告已保存至：research/{DOMAIN_EN}-research.md

候选清单摘要：
  对象候选：{N} 个 — {名称1}、{名称2}、...
  逻辑候选：{K} 个 — {名称1}、{名称2}、...
  动作候选：{M} 个 — {名称1}、{名称2}、...
  规则候选：{R} 个 — {名称1}、{名称2}、...（或"无"）

主要发现：
  • {bullet 1}
  • {bullet 2}
  • {bullet 3}
```

引导专家审视完整报告：

> "完整调研报告可在 Obsidian 中查看：
> 📄 `RAWData/KEAOutput/research/{DOMAIN_EN}-research.md`
>
> 报告包含每个候选的详细属性、关联关系和置信度评估。
> 审视完毕后回复"继续"进入门控评估。"

等待用户回复后继续。

## 门控评估（G1）

### 自动验证项

依次检查（使用 Read 工具读取报告文件）：

| 条件 | 检查方式 | 通过标准 |
|------|---------|---------|
| ① 报告文件已写入 Vault | 检查文件是否存在 | 文件存在且非空 |
| ② 候选对象数量 | 统计报告中"核心业务对象候选"节下的条目数 | ≥ 3 |
| ③ 候选逻辑数量 | 统计报告中"核心业务逻辑候选"节下的条目数 | ≥ 1 |
| ④ 候选动作数量 | 统计报告中"核心业务动作候选"节下的条目数 | ≥ 1 |

展示自动验证结果：

```
自动验证：
  ① 报告文件：✅ research/{DOMAIN_EN}-research.md
  ② 候选对象：✅ {N} 个（要求 ≥ 3）
  ③ 候选逻辑：✅ {K} 个（要求 ≥ 1）
  ④ 候选动作：✅ {M} 个（要求 ≥ 1）
```

如有自动验证失败项（❌），说明失败原因，触发门控失败流程，**不询问人类确认**。

### 人类确认

自动验证全部通过后，询问：

> "您已审视过调研报告。以上候选清单是否准确反映了【{DOMAIN_CN}】的领域边界？
>
> - ✅ 确认：领域边界和候选清单准确
> - ✏️ 需要调整：[请说明具体调整内容]
> - 🔄 重新调研：需要补充更多方向"

- **确认** → 进入门控通过流程
- **需要调整** → 用户说明调整内容 → 重新执行 Step 5（追加模式）→ 重新评估
- **重新调研** → 重新执行 Step 1

## 门控通过 → 更新 chain-state.md

向 chain-state.md 写入 G1 通过记录：

```markdown
| 1 | 调研 | ✅ 通过 | {YYYY-MM-DD HH:MM} | 候选：对象{N}/逻辑{K}/动作{M} |
```

在"门控记录"节追加：

```markdown
### G1 通过记录（{YYYY-MM-DD HH:MM}）
- 报告路径：research/{DOMAIN_EN}-research.md ✅
- 候选对象：{N} ≥ 3 ✅
- 候选逻辑：{K} ≥ 1 ✅
- 候选动作：{M} ≥ 1 ✅
- 人类确认："领域边界和候选清单准确" ✅
```

更新 `current_phase: 2`，`last_updated`。

告知用户：

> "G1 通过。**下一阶段：访谈确认（Phase 2）**
> 是否现在继续？[继续 / 暂停]"

如用户选择继续，编排器载入 `phase-2-interview.md` 执行。

## 门控失败 → 回退处理

**自动验证失败**（报告缺少候选节）：
- 更新 Phase 1 状态为 `🔄 进行中`
- 重新执行 Step 5，要求 research-agent 补充缺失的候选节

**自动验证失败**（候选数量不足 < 阈值）：
- 提示用户："候选数量不足，可能因为领域范围过窄或素材不足"
- 询问："是否补充本地文档或扩大调研范围？"
- 重新执行 Step 1

**人类拒绝确认（需要调整）**：
- 按用户指示调整后，重新执行调研，重新评估门控

在 chain-state.md 的"回退历史"节追加：

```markdown
### 回退记录（{YYYY-MM-DD HH:MM}）
- 阶段：Phase 1 G1 失败
- 原因：{具体失败原因}
- 处置：{补充调研 / 调整范围}
```
