---
name: kea
version: 4.0.0
description: >
  Use when 业务专家需要将领域知识结构化为 Ontology，
  或继续已有领域的本体萃取进度。
triggers:
  - "kea"
  - "KEA"
  - "ontology"
  - "知识萃取"
  - "提取业务对象"
  - "提取业务逻辑"
  - "本体建模"
  - "本体萃取"
  - "ontology extract"
  - "ontology validate"
  - "ontology trace"
  - "ontology codegen"
metadata:
  openclaw:
    permissions:
      version: 1
      declared_purpose: "Business knowledge extraction and ontology modeling via 12-phase chain with gate conditions and state persistence"
      filesystem:
        - "read:~/.claude/skills/kea/config.md"
        - "read:~/.claude/skills/kea/phases"
        - "read:{VAULT_PATH}/30-Ontology"
        - "read:{VAULT_PATH}/RAWData/KEAOutput"
        - "read:./AgentFile/skills"
        - "read:./AgentFile/templates"
        - "read:./AgentFile/phases"
        - "write:{VAULT_PATH}/30-Ontology"
        - "write:{VAULT_PATH}/RAWData/KEAOutput"
        - "write:./.obsidian/snippets"
        - "write:./.obsidian/community-plugins.json"
      exec:
        - "python3"
        - "python"
        - "git"
      env:
        - "PATH"
---

# KEA — Knowledge Extraction Agent

## 主执行逻辑

**每次触发 KEA，按以下顺序执行：**

### Step 1: 读取配置

```
VAULT_PATH      = ~/.claude/skills/kea/config.md 中 "VAULT_PATH:" 的值
KEA_TOOLS_ROOT  = ~/.claude/skills/kea/config.md 中 "KEA_TOOLS_ROOT:" 的值
PROJECT_ROOT    = KEA_TOOLS_ROOT（传给 phase 文件，用于 cd {PROJECT_ROOT} && python3 -m kea）
```

### Step 1.5: 检查 Vault 路径

读取 `VAULT_PATH` 后，检查目录是否存在：

**若目录存在** → 继续 Step 1.6。

**若目录不存在** → 询问用户：

> "配置中的 Vault 路径不存在：`{VAULT_PATH}`
>
> 请输入正确的 Vault 绝对路径，或直接回车使用默认路径：
> **默认：`~/Documents/KEA-Vault`**"

- 用户输入路径 → 将 `VAULT_PATH` 更新为用户输入的路径，同时更新 `~/.claude/skills/kea/config.md`
- 用户直接回车 → 将 `VAULT_PATH` 设为 `~/Documents/KEA-Vault`（展开 `~` 为 `$HOME`），创建目录，更新 `~/.claude/skills/kea/config.md`

创建 Vault 目录后展示提示：

> "已创建 Vault 目录：`{VAULT_PATH}`
>
> 请在 Obsidian 中手动打开此 Vault：
> **File → Open Vault → 选择文件夹 → 找到上述目录**
>
> 打开后 KEA 将在此 Vault 中创建 Ontology 文档。"

等待用户确认后继续。

### Step 1.6: 检查并安装 Obsidian 插件

检查以下 5 个插件是否已安装于 `{VAULT_PATH}/.obsidian/plugins/`。如有缺失，自行完成安装并启用。

| Plugin ID | 下载来源 | 用途 |
|-----------|---------|------|
| `obsidian-hover-editor` | https://github.com/nothingislost/obsidian-hover-editor/releases | 悬停预览 `[[链接]]`，审视时不跳离当前文件 |
| `code-styler` | https://github.com/mayurankv/Obsidian-Code-Styler/releases | `pseudo` 代码块语法高亮 |
| `dataview` | https://github.com/blacksmithgu/obsidian-dataview/releases | 基于 YAML 的动态审计查询 |
| `obsidian-mermaid-links` | https://github.com/vinayaugustine/obsidian-mermaid-links/releases | 流程图节点一键跳转编辑器 |
| `breadcrumbs` | https://github.com/SkepticMystic/breadcrumbs/releases | 语义关系矩阵视图 |

**安装要求：**
- 每个插件需将 `main.js`、`manifest.json`（以及可选的 `styles.css`）放入 `{VAULT_PATH}/.obsidian/plugins/{plugin-id}/`
- 确保上述 plugin ID 均已列入 `{VAULT_PATH}/.obsidian/community-plugins.json`

完成后展示各插件安装状态（✅ 已就绪 / 🆕 已安装 / ❌ 失败），并提示用户在 Obsidian 中重载插件。

### Step 2: 确定领域

若用户未指定领域，询问：

> "您要萃取哪个业务领域的本体？（如：采购、合同、库存）"

获得 `DOMAIN_CN`（中文名）后，推导：
```
DOMAIN_EN = DOMAIN_CN 的拼音首字母小写（如 "采购" → "caigou"）
            或用户提供的英文名
```

### Step 3: 读取或初始化 chain-state.md

```
CHAIN_STATE_PATH = {VAULT_PATH}/RAWData/KEAOutput/{DOMAIN_EN}-chain-state.md
```

**若文件不存在**，创建并写入：

```markdown
---
domain_cn: {DOMAIN_CN}
domain_en: {DOMAIN_EN}
status: in_progress
current_phase: 1
coverage_threshold: 80
created_at: {YYYY-MM-DD HH:MM}
updated_at: {YYYY-MM-DD HH:MM}
---

# {DOMAIN_CN} 本体萃取链状态

| 阶段 | 名称 | 状态 | 通过时间 | 备注 |
|------|------|------|---------|------|
| 1 | 领域调研 | ⏳ 待执行 | — | — |
| 2 | 专家访谈 | ⏳ 待执行 | — | — |
| 3 | 流程图生成 | ⏳ 待执行 | — | — |
| 4 | 流程图校验 | ⏳ 待执行 | — | — |
| 5 | 本体提取 | ⏳ 待执行 | — | — |
| 9 | 结构校验 | ⏳ 待执行 | — | — |
| 10 | 语义校验 | ⏳ 待执行 | — | — |
| 11 | 完备性验证 | ⏳ 待执行 | — | — |
| 12 | 场景追踪 | ⏳ 待执行 | — | — |
```

**若文件存在**，读取 `current_phase` 和 `status`，展示当前进度：

```
《{DOMAIN_CN}》本体萃取进度：

  Phase 1  领域调研      ✅ 通过  2026-04-20
  Phase 2  专家访谈      ✅ 通过  2026-04-20
  Phase 3  流程图生成    ✅ 通过  2026-04-21（共 5 个流程图）
  Phase 4  流程图校验    ✅ 通过  2026-04-21
  Phase 5  本体提取      ✅ 通过  2026-04-21（对象12 逻辑8 动作20 规则3）
  Phase 9  结构校验      🔄 进行中

  → 继续执行 Phase 9（结构校验）
```

### Step 4: 路由到当前阶段

根据 `current_phase` 读取并执行对应 phase 文件的**全部内容**：

| current_phase | 执行文件 |
|--------------|---------|
| 1 | `~/.claude/skills/kea/phases/phase-1-research.md` |
| 2 | `~/.claude/skills/kea/phases/phase-2-interview.md` |
| 3 | `~/.claude/skills/kea/phases/phase-3-flowchart-generate.md` |
| 4 | `~/.claude/skills/kea/phases/phase-4-flowchart-validate.md` |
| 5 | `~/.claude/skills/kea/phases/phase-5-extract-ontology.md` |
| 9 | `~/.claude/skills/kea/phases/phase-9-rule-check.md` |
| 10 | `~/.claude/skills/kea/phases/phase-10-semantic-check.md` |
| 11 | `~/.claude/skills/kea/phases/phase-11-coverage-check.md` |
| 12 | `~/.claude/skills/kea/phases/phase-12-scenario-trace.md` |
| done | 展示完成状态（见下方） |

执行 phase 文件时，将以下变量传入：

```
DOMAIN_CN:              {DOMAIN_CN}
DOMAIN_EN:              {DOMAIN_EN}
VAULT_PATH:             {VAULT_PATH}
PROJECT_ROOT:           {KEA_TOOLS_ROOT}
CHAIN_STATE_PATH:       {CHAIN_STATE_PATH}
COVERAGE_THRESHOLD:     chain-state.md front matter 中 coverage_threshold 的值
OBJECTS_DIR:            {VAULT_PATH}/30-Ontology/objects/{DOMAIN_EN}/
LOGIC_DIR:              {VAULT_PATH}/30-Ontology/logic/{DOMAIN_EN}/
ACTIONS_DIR:            {VAULT_PATH}/30-Ontology/actions/{DOMAIN_EN}/
RULES_DIR:              {VAULT_PATH}/30-Ontology/rules/{DOMAIN_EN}/
DIAGRAMS_DIR:           {VAULT_PATH}/30-Ontology/diagrams/{DOMAIN_EN}/
RESEARCH_REPORT_PATH:   {VAULT_PATH}/RAWData/KEAOutput/research/{DOMAIN_EN}-research.md
INTERVIEW_SUMMARY_PATH: {VAULT_PATH}/RAWData/KEAOutput/interviews/{DOMAIN_EN}-interview-summary.md
SUPPLEMENT_PATH:        {chain-state front matter 中 supplement_path 字段的值，为空时传空字符串}
```

### Step 5: 阶段完成后

每个 phase 文件末尾会更新 chain-state.md 中的 `current_phase`。下次触发 KEA 时，自动继续下一阶段。

### Step 6: done 状态展示

当 `current_phase = done` 时：

```
╔══════════════════════════════════════════╗
║     《{DOMAIN_CN}》本体萃取 — 已完成 ✅  ║
╠══════════════════════════════════════════╣
║ 对象：{OC} 个 | 逻辑：{LC} 个           ║
║ 动作：{AC} 个 | 规则：{RC} 个           ║
║ 覆盖率：对象{OP}%/逻辑{LP}%/动作{AP}%  ║
║ 完成时间：{completed_at}                ║
╚══════════════════════════════════════════╝

后续操作：
  /ontology-codegen   生成 Python Skill 代码
  /ontology-index     生成关系图与导航索引
  /ontology-impact    变更影响分析
  kea new <领域名>    开始新领域的萃取
```

---

## 技能链概览

```
Phase 1  领域调研      → 生成调研报告，确认候选清单
Phase 2  专家访谈      → 评估报告质量，专家确认 gap，按需定向补充  [不可跳过]
Phase 3  流程图生成    → 生成 Mermaid 流程图，专家逐图确认
Phase 4  流程图校验    → 结构 + 语义 13 项校验，严重问题=0    [硬性]
Phase 5  本体提取      → 对象→逻辑→动作→规则流水线，每类硬门 errors=0+dead_links=0，最终1次专家确认
Phase 9  结构校验      → 结构错误=0                           [硬性，不可绕过]
Phase 10 语义校验      → 语义错误=0                           [硬性，不可绕过]
Phase 11 完备性验证    → 每个未覆盖项有A/B/C决策
Phase 12 场景追踪      → 核心场景全通过，人类最终背书
```

每个阶段末尾均有**门控评估**（自动验证 + 人类确认），未通过时触发回退。

---

## 后续独立命令

技能链完成后，以下命令可随时单独调用：

| 命令 | 功能 |
|------|------|
| `/ontology-codegen` | 将 Ontology 生成 Python Skill 代码 |
| `/ontology-index` | 生成关系图和导航索引 |
| `/ontology-impact <文件>` | 变更影响分析 |
| `/ontology-flowchart` | 创建/更新 Mermaid 流程图 |
| `kea new <领域名>` | 开始新领域的萃取链 |

---

## Vault 目录结构

```
{VAULT_PATH}/
├── 30-Ontology/
│   ├── objects/{domain}/      ← Phase 5 输出
│   │   └── _shared/           ← 跨域共用对象
│   ├── logic/{domain}/        ← Phase 6 输出
│   │   └── _shared/
│   ├── actions/{domain}/      ← Phase 7 输出
│   │   └── _shared/
│   ├── rules/{domain}/        ← Phase 8 输出
│   │   └── _shared/           ← 跨域策略规则
│   ├── diagrams/{domain}/     ← Phase 3 输出（Mermaid 流程图）
│   └── data-mock/
└── RAWData/KEAOutput/
    ├── {domain}-chain-state.md    ← 阶段状态持久化
    ├── research/                   ← G1 调研报告
    ├── interviews/                 ← G2 访谈摘要
    └── reports/
        ├── coverage/               ← 覆盖率报告
        └── validation/             ← 结构/语义/流程图校验报告
```

---

## 架构说明

```
SKILL.md（主编排）
    │
    ├── 读取 chain-state.md → 当前阶段
    │
    ├── 路由到 phases/phase-N.md（在主 session 上下文中执行）
    │       │
    │       ├── Dispatch 到 skills/{name}/SKILL.md（独立 subagent，LLM 推理）
    │       │
    │       └── python3 -m kea <cmd> --format json（确定性操作，Phase 直接调用）
    │
    └── 更新 chain-state.md → 下一阶段
```

**设计原则**：
- SKILL.md 只做状态读取和路由，不含业务逻辑
- Phase 文件负责完整的阶段编排（含门控），直接调用 kea CLI 进行确定性校验
- Sub-skill 负责 LLM 推理任务（提取、语义分析），不建议直接调用 kea
- Python 工具层负责确定性操作（零外部依赖）

---

## Graph View 颜色配置

Ontology 节点类型与颜色映射：

| tag | 颜色 | 类型 |
|-----|------|------|
| `#kea-domain` | 紫色 | 领域 |
| `#kea-object` | 红色 | 业务对象 |
| `#kea-logic` | 蓝色 | 业务逻辑 |
| `#kea-action` | 绿色 | 业务动作 |
| `#kea-rule` | 橙色 | 业务规则 |

配置步骤：Obsidian Settings → Appearance → CSS snippets → 启用 `kea-graph-colors`，然后在 Graph View → Groups 面板按上表添加分组规则。

---

## 推荐 Obsidian 插件

以下插件由 Step 1.6 自动检查并安装。

| 插件 | Plugin ID | 用途 | 市场 |
|------|-----------|------|------|
| **Hover Editor** | `obsidian-hover-editor` | 悬停预览 `[[链接]]`，审视时不跳离当前文件 | ✅ 社区市场 |
| **Code Styler** | `code-styler` | `pseudo` 代码块高亮（Phase 6/7 逻辑/动作文件可读性）。安装后在 Code Styler 设置中将 `pseudo` 映射为 Python 高亮。 | ✅ 社区市场 |
| **Dataview** | `dataview` | 基于 YAML front matter 的动态审计查询（如"哪些对象缺少主键"） | ✅ 社区市场 |
| **Mermaid Links** | `obsidian-mermaid-links` | 流程图节点一键跳转 Mermaid Live Editor（Phase 3/4 审视） | ⚠️ 非市场，GitHub 安装 |
| **Breadcrumbs** | `breadcrumbs` | 语义关系矩阵视图（Matrix/Tree），需配合 `relations` 字段使用 | ✅ 社区市场 |

