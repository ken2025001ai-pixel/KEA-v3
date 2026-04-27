# KEA AgentFile — 开发规范

## 核心设计原则

### 原则一：Skill 为主，工具为辅

- Skill 应**积极调用 kea 工具**完成确定性校验，LLM 只负责它擅长的语义理解和创造性提取
- 能用工具验证的必须调用工具，不允许 LLM 猜测或手工模拟
- 工具不满足需求时**规划新工具**，不在 phase/skill 中写 ad-hoc 校验逻辑

### 原则二：追求确定性，人类专家舒适高效

- **人类只做工具做不了的事**：自动验证在前，人类确认在后
- **Sub-skill 输出后先跑工具校验**，通过后才能进入人类审视
- **疑虑前置**：DONE_WITH_CONCERNS 先处置再展示
- **每次交互让专家有获得感**：展示进度、变更摘要、校验明细

---

## 一、文件职责边界

### 文件角色

| 文件类型 | 运行上下文 | 职责 |
|---------|----------|------|
| `SKILL.md` | 主 session，内容注入后直接执行 | 状态读取 + 阶段路由，不含业务逻辑 |
| `phases/phase-N.md` | 主 session，由 SKILL.md 读取后执行 | 完整阶段编排：前置检查 → 执行 → 门控评估 → 更新状态 |
| `skills/{name}/SKILL.md` | 以 subagent 方式 Dispatch，独立 context window | 单一职责执行（提取、校验、覆盖检查），可复用，不做编排 |

### 调用层级

```
SKILL.md（路由）
  └─ phase-N.md（编排 + 门控）                ← 主 session
        ├─ skills/{name}/SKILL.md（LLM 推理）  ← subagent
        └─ python3 -m kea <cmd>（确定性校验）  ← Phase 直接调用
```

### 关键约束

- **Subagent 不能再 Dispatch subagent**：`skills/{name}/SKILL.md` 只执行自身任务，禁止内部调用 Agent 工具
- **Phase 文件在主 session 执行**：需要与用户持续对话（门控确认、决策询问），不能 Dispatch 为独立 subagent
- **Sub-skill 不与用户交互**：只处理数据并返回结构化结果给 phase 文件
- **所有人类决策交互归属 phase 文件**：未覆盖项决策、问题处置、确认操作均在主 session 完成

### Sub-skill 契约分型

Sub-skill 按其任务性质分为三种类型，使用不同的返回格式：

| 类型 | 代表 | 返回格式 | 说明 |
|------|------|---------|------|
| **生成型** | extract-objects / logic / actions / rules, mock-data | DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED | 生成新文件；4 状态码明确表示成功、疑虑、缺数据、卡点 |
| **分析型** | flowchart-validate, semantic-check, coverage-check, rule-check | 结构化问题清单（JSON），空数组 = 无问题 | 分析已有文档；返回问题列表，Phase 负责逐条处置 |
| **交互型** | interview | 对话自然结束，Phase 用文件存在性验证 | 与用户对话是本质需求；Phase 不检查状态码，改为检查输出文件是否已写入 |

**Phase 文件的责任**：
- **生成型**：检查返回状态码，DONE_WITH_CONCERNS 先处置疑虑再展示，BLOCKED/NEEDS_CONTEXT 不能静默跳过
- **分析型**：检查 JSON 是否有效、是否为空，不为空时逐条处理问题
- **交互型**：检查输出文件是否已写入，未写入时询问用户是重试还是回退

**分析型契约详细格式**：

```json
{
  "status": "ok" | "partial",
  "issues": [
    {"severity": "错误|警告|建议", "category": "...", "file": "...", "message": "..."}
  ],
  "confidence": 0.0-1.0
}
```

Phase 文件读取 `issues` 数组：空 → 无问题通过；非空 → 逐条处理。

---

## 二、SKILL.md 写作规范

*来源：Superpowers writing-skills + Anthropic 官方 best practices*

### description 字段：只写触发条件，不写流程

**实测发现**：description 里包含流程摘要时，Claude 会把 description 当捷径，跳过读取完整 SKILL.md 内容。因此：

```yaml
# ❌ 错：包含流程摘要，Claude 会跳过正文
description: >
  帮助业务专家通过 10 阶段强制技能链将业务知识沉淀为 Ontology。
  每阶段有门控条件，支持回退。

# ✅ 正：只写触发条件
description: >
  Use when 业务专家需要将领域知识结构化为 Ontology，
  或继续已有领域的本体萃取进度。
```

### 篇幅控制

- **SKILL.md 主体 ≤ 500 行**：超出时将细节移到子文件，SKILL.md 只保留概览和引用
- **引用深度只有一层**：SKILL.md → 子文件，禁止多级嵌套（子文件再引用子文件）
- **每个 token 都需要理由**：不要写 Claude 已知的常识；只提供 Claude 没有的上下文

### 自由度匹配

根据任务的确定性选择指令写法：

| 场景 | 写法 |
|------|------|
| 操作可逆、多路径均可 | 高自由度：描述目标和方向 |
| 有偏好路径、允许微调 | 中自由度：给出模板 + "按需调整" |
| 操作不可逆、必须固定顺序 | 低自由度：给出精确步骤，写明"不要修改" |

KEA 的门控校验（错误=0、每项有决策）属于低自由度场景，需要精确指令。

### 流程图使用原则

只在决策点容易出错时使用，不用于线性步骤或纯罗列信息：

```
需要展示信息？
  └─ 是否是"容易走错"的判断点？
        └─ 是 → 小型内联流程图
        └─ 否 → Markdown 列表/表格
```

### 反理由表（适用于强制纪律的 skill）

凡是有"不可绕过"要求的 skill（如 G7 错误=0），必须配备 Red Flags 表，列出常见的借口及其反驳：

```markdown
## Red Flags — 遇到以下想法立即停止

| 借口 | 现实 |
|------|------|
| "只有一个错误，可以先跳过" | 错误=0 是硬性条件，不存在例外 |
| "用户说确认了就算通过" | 人类确认不能覆盖自动验证项 |
| "这个警告无关紧要" | 警告必须标注已接受原因，不能忽略 |
```

---

## 三、Sub-skill（skills/{name}/SKILL.md）写作规范

### 文件顶部加 SUBAGENT-STOP

防止 sub-skill 在主 session 被当作普通 Skill 触发时执行整套流程：

```markdown
<SUBAGENT-STOP>
本文件作为 subagent 执行。若你是主 session Claude，请通过 Agent 工具 Dispatch 本 skill，而非直接读取执行。
</SUBAGENT-STOP>
```

### Controller 负责准备上下文，不让 subagent 自己找文件

Phase 文件（controller）在 Dispatch 前应将必要内容直接写入 prompt，而不是让 subagent 去读取路径：

```
# ❌ 错：让 subagent 自己读
请读取 LOGIC_DIR 下的所有文件，提取动作列表。

# ✅ 正：controller 准备好再传入
以下是逻辑文档中引用的动作清单（已预扫描）：
  • 创建采购订单（被 3 个逻辑引用）
  • 审批采购申请（被 2 个逻辑引用）
请基于以上清单提取对应动作文档。
```

### 返回格式规范

Sub-skill 返回给 phase 文件的结果应使用结构化格式，并包含状态字段：

```
状态：DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED

- DONE：正常完成，附结果摘要
- DONE_WITH_CONCERNS：完成但有疑虑，phase 文件需先读疑虑再决定是否继续
- NEEDS_CONTEXT：缺少必要信息，说明缺什么
- BLOCKED：无法完成，说明卡点和已尝试方案
```

Phase 文件收到 `BLOCKED` 或 `NEEDS_CONTEXT` 时，必须处理后再决策，不能忽略直接继续。

---

## 四、目录结构规范

```
AgentFile/
├── SKILL.md              ← 主入口（链路路由，≤500行）
├── CLAUDE.md             ← 本文件（开发规范）
├── phases/               ← 10个阶段文件（主 session 执行）
│   └── phase-N-{name}.md
├── skills/               ← Sub-skills（subagent 执行）
│   └── {name}/
│       ├── SKILL.md      ← 执行指令（顶部含 SUBAGENT-STOP）
│       └── *.md          ← 支撑文件（按需，Claude 读取时才消耗 context）
├── templates/            ← Ontology 文档模板
└── docs/                 ← 规范文档
```

**新增 sub-skill 时**：在 `skills/` 下创建新目录，文件名固定为 `SKILL.md`。对应的 phase 文件引用路径格式为 `~/.claude/skills/kea/skills/{name}/SKILL.md`。

---

## 五、修改已有文件的原则

- **修改 phase 文件**：关注门控条件的完整性（自动验证项 + 人类确认），不要在 phase 文件里加业务提取逻辑
- **修改 sub-skill**：保持单一职责，不引入跨阶段状态，不调用 Agent 工具
- **修改 SKILL.md**：只改路由逻辑和 chain-state 初始化，不加业务判断
- **任何涉及门控条件的改动**：更新对应 phase 文件的门控表格，同步更新 chain-state 的记录格式
