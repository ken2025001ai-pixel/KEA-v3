<SUBAGENT-STOP>
本文件作为 subagent 执行。若你是主 session Claude，请通过 Agent 工具 Dispatch 本 skill，而非直接读取执行。
</SUBAGENT-STOP>

# generate-flowcharts — 流程图批量生成

你是一个生成型 subagent。根据传入的流程候选清单和源文档，生成符合 KEA 约定的 Mermaid 流程图文件，写入 DIAGRAMS_DIR。

**你不与用户交互，不做候选清单判断，只负责生成。**

## 输入参数（由 phase-3 在 Dispatch 时传入）

- `CONFIRMED_CANDIDATES`：用户确认的流程清单（JSON 数组，每项含 `name`（流程名）和 `description`（一句话描述））
- `RESEARCH_REPORT_PATH`：调研报告路径
- `INTERVIEW_SUMMARY_PATH`：访谈摘要路径
- `SUPPLEMENT_PATH`：可选，补充调研文档路径（为空时忽略）
- `DIAGRAMS_DIR`：输出目录（已含领域名，格式：`.../diagrams/{DOMAIN_EN}/`）
- `DOMAIN_CN` / `DOMAIN_EN`：领域信息
- `EXISTING_FILES`：可选，已有流程图文件列表（增量模式，传入时跳过已存在的）

## 执行步骤

### Step 0: 参数校验

若 `CONFIRMED_CANDIDATES` 为空或未传入，返回：
```
状态：NEEDS_CONTEXT
缺少信息：CONFIRMED_CANDIDATES 为空，无法确定需要生成哪些流程图
```

若 `DIAGRAMS_DIR` 为空或未传入，返回：
```
状态：NEEDS_CONTEXT
缺少信息：DIAGRAMS_DIR 未传入，无法确定写入位置
```

### Step 1: 读取源文档

依次读取以下文档作为生成上下文（使用 Read 工具）：
1. `RESEARCH_REPORT_PATH`（若存在）
2. `INTERVIEW_SUMMARY_PATH`（若存在）
3. `SUPPLEMENT_PATH`（若非空且存在）

优先级：补充文档 > 访谈摘要 > 调研报告（专家显式确认的优先）。

### Step 2: 逐一生成流程图

对 `CONFIRMED_CANDIDATES` 中每个条目，生成 Mermaid 流程图：

**节点约定（严格遵守，不允许自行发明其他形状）：**

| 形状语法 | 节点类型 | 约束 |
|---------|---------|------|
| `((开始\n输入: {参数名}))` | 开始节点 | 每图有且仅有 1 个 |
| `((结束\n输出: {结果名}))` | 结束节点 | 每图至少 1 个 |
| `[动作描述]` | 动作节点 | 描述一个业务操作 |
| `(活动描述)` | 活动节点 | 描述一个业务活动（带上下文） |
| `{条件?}` | 判断节点 | 必须有 `\|是\|` 和 `\|否\|` 两条出路 |
| `[[子流程名称]]` | 子流程引用 | 名称须与 CONFIRMED_CANDIDATES 中其他流程名一致 |

**文件格式**（写入 `{DIAGRAMS_DIR}/{流程名}.md`）：

写入的文件内容示例：

```
---
domain: {DOMAIN_EN}
process: {流程名}
phase: flowchart
created_at: {YYYY-MM-DD}
---

(mermaid代码块)
flowchart TD
  start(("开始\n输入: {输入参数}"))
  ...节点和边...
  finish(("结束\n输出: {输出结果}"))
(结束代码块)
```

每生成一个文件立即写入，不等所有生成完再批量写。

**低置信处理**：若源文档对某流程描述严重不足（找不到触发条件、关键判断节点等），在内部记录为低置信候选，最终在疑虑清单中列出。

### Step 3: 返回结果

**DONE（全部正常生成）：**
```
状态：DONE

生成统计：{N} 个流程图
  ✅ {流程名1} → diagrams/{DOMAIN_EN}/{流程名1}.md
  ✅ {流程名2} → diagrams/{DOMAIN_EN}/{流程名2}.md
  ...
```

**DONE_WITH_CONCERNS（有低置信项）：**
```
状态：DONE_WITH_CONCERNS

生成统计：{N} 个流程图（{K} 个存在疑虑）

疑虑清单：
- {流程名}：来源文档对该流程描述不足，{具体说明缺少的信息}，关键节点基于模型推断，置信度低
```

**NEEDS_CONTEXT：**
```
状态：NEEDS_CONTEXT
缺少信息：{具体说明}
```

**BLOCKED：**
```
状态：BLOCKED
卡点：{具体说明}
已尝试：{已尝试的方法}
```
