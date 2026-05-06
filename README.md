# KEA — Knowledge Extraction Agent

KEA 是一个面向业务专家的**本体萃取工具链**，将领域知识结构化为可机器处理的 Ontology 文档。

---

## 核心能力

- **12 阶段强制萃取链**：从调研→访谈→流程图→提取→校验→追踪，每阶段有硬性门控
- **确定性工具层**：结构校验、死链检测、覆盖率计算、场景追踪全部由 Python 工具完成，不依赖 LLM 猜测
- **人类确认最小化**：自动校验在前，专家只审视工具无法判断的语义问题
- **跨平台**：支持 Claude Code、OpenClaw 等 Agent 平台，Windows/Linux/macOS 均可运行

---

## 项目结构

```
KEA-v3/
├── AgentFile/          ← Agent 编排层（Skill 指令文件）
│   ├── SKILL.md        ← 主入口：触发词 + 12 阶段路由
│   ├── INSTALL.md      ← 声明式安装指南
│   ├── phases/         ← 9 个阶段编排文件（主 session 执行）
│   ├── skills/         ← 12 个 sub-skill（subagent 执行）
│   ├── templates/      ← Ontology 文档模板（object/logic/action/rule）
│   ├── docs/           ← 规范文档（mermaid-spec 等）
│   └── assets/         ← Obsidian CSS 配色
│
└── kea/                ← Python 确定性工具层
    ├── cli.py          ← 统一 CLI 入口
    ├── parser/         ← 解析 Ontology 文档和 Mermaid 流程图
    ├── validator/      ← 结构/契约/死链校验
    ├── tracer/         ← 伪代码场景追踪
    ├── linter/         ← AgentFile 指令文件 lint
    └── generator/      ← Ontology → Python Skill 代码生成
```

---

## 技能链概览

```
Phase 1   领域调研      → 生成调研报告，确认候选清单
Phase 2   专家访谈      → 评估报告质量，专家确认 gap   [不可跳过]
Phase 3   流程图生成    → 生成 Mermaid 流程图，专家逐图确认
Phase 4   流程图校验    → 结构 + 语义 13 项校验        [硬性]
Phase 5   本体提取      → 对象→逻辑→动作→规则流水线，每类硬门 errors=0+dead_links=0，最终 1 次专家确认
Phase 9   结构校验      → 结构错误=0                  [硬性]
Phase 10  语义校验      → 语义错误=0                  [硬性]
Phase 11  完备性验证    → 每个未覆盖项有 A/B/C 决策
Phase 12  场景追踪      → 核心场景全通过，人类最终背书
```

---

## 安装

见 `AgentFile/INSTALL.md`。核心步骤：

1. 将包内所有文件复制到 Agent 平台的 skill 目录（如 `~/.claude/skills/kea/`）
2. 创建 `config.md`：

   ```
   # KEA Config
   VAULT_PATH: /path/to/obsidian/vault
   KEA_TOOLS_ROOT: /path/to/skill/dir
   ```

3. 验证：`cd {KEA_TOOLS_ROOT} && python3 -m kea --help`

**环境要求**：Python 3.11+，Git（可选），Obsidian（用于审视输出件）

---

## 触发词

在 Agent 会话中输入以下任意词触发 KEA：

```
kea  KEA  ontology  知识萃取  本体建模  本体萃取
```

---

## Python 工具层

```bash
cd /path/to/KEA-v3

# 结构校验
python3 -m kea validate ontology/ --format json

# 解析文档
python3 -m kea parse ontology/objects/订单.md --format json

# 解析 Mermaid 流程图目录
python3 -m kea mermaid ontology/diagrams/ --format json

# 场景追踪
python3 -m kea trace ontology/logic/创建订单.md --format json

# AgentFile lint
python3 -m kea lint AgentFile/ --format json

# 运行测试
python3 -m pytest tests/ -q
```

---

## Ontology 文档格式

四种文档类型，均为带 YAML front matter 的 Markdown：

| 类型 | 目录 | 描述 |
|------|------|------|
| `object` | `30-Ontology/objects/` | 业务对象，含属性清单和关系声明 |
| `logic` | `30-Ontology/logic/` | 业务流程，含 Mermaid 图和伪代码 |
| `action` | `30-Ontology/actions/` | 可执行动作，含输入输出和异常处理 |
| `rule` | `30-Ontology/rules/` | 业务规则（validation/guard/derivation/policy） |

模板在 `AgentFile/templates/`，Mermaid 节点规范在 `AgentFile/docs/mermaid-spec.md`。

---

## Obsidian 插件

KEA 依赖 Obsidian 作为人工审视界面，推荐安装以下插件（首次运行时 Agent 自动检查并安装）：

| 插件 | 用途 |
|------|------|
| Hover Editor | 悬停预览 `[[链接]]` |
| Code Styler | `pseudo` 代码块高亮 |
| Dataview | 基于 YAML 的动态审计查询 |
| Mermaid Links | 流程图节点跳转 |
| Breadcrumbs | 语义关系矩阵视图 |

---

## 版本

当前版本：**4.2.1**。详见 `RELEASE.md`。
