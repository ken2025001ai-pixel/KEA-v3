# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库结构

本仓库有两个子系统，Skill 编排层调用 Python 工具层完成工作：

```
KEA-v3/
├── AgentFile/          ← Claude Code Skill（编排层）
│   ├── SKILL.md        ← 主入口，10阶段技能链编排器
│   ├── phases/         ← 12个阶段文件（主 session 执行）
│   ├── skills/         ← 10个 sub-skills（subagent 执行）
│   ├── templates/      ← Ontology 文档模板（object/logic/action/rule）
│   ├── docs/           ← 规范文档（mermaid-spec 等）
│   └── install.sh      ← 安装到 ~/.claude/skills/kea/
│
└── kea/                ← Python 确定性工具层（被 Agent 调用）
    ├── cli.py / __main__.py  ← 统一 CLI 入口
    ├── parser/         ← 解析 Ontology 文档为 AST
    ├── validator/      ← 结构/契约/状态校验
    ├── tracer/         ← 伪代码场景执行
    ├── indexer/        ← 生成关系图和导航索引
    ├── generator/      ← 生成 OntologySkill 代码
    └── tests/          ← 单元测试
```

`kea/` 目录即 Python 包，直接以 `python3 -m kea` 方式运行，无需软链接。

## Python 工具层命令

```bash
# 在仓库根目录运行
cd /path/to/KEA-v3
python3 -m kea --help

# 常用命令
python3 -m kea validate ontology/ --format json
python3 -m kea parse ontology/objects/订单.md --format json
python3 -m kea trace ontology/logic/创建订单.md --format json
python3 -m kea status ontology/ --format json
python3 -m kea index ontology/ --format json
python3 -m kea impact 订单.md --base-dir ontology/ --format json
python3 -m kea codegen ontology/ --output codegen/ --format json

# 运行测试
python3 -m pytest kea/tests/
```

所有命令支持 `--format json`（供 Agent 消费）和 `--format human`（默认，可读输出）。

## 安装 Skill

```bash
cd AgentFile
bash install.sh                # 安装到 ~/.claude/skills/kea/
bash install.sh --obsidian     # 仅安装 Obsidian CSS
bash install.sh --both         # 两者都安装
```

安装后触发词：`kea`、`ontology`、`知识萃取`、`本体建模`

## 架构关键点

### 两层协作

- **AgentFile/**（编排层）：对话、状态管理、门控评估、人类确认——由 Claude 执行，**调用 kea/ 工具层**完成解析/校验/追踪等确定性操作
- **kea/**（工具层）：文档解析、校验、追踪——纯 Python，无 LLM 调用，输出可预期，**被 AgentFile 编排层通过 CLI 调用**

### 技能链（AgentFile/phases/）

12个强制阶段，每阶段末尾有门控（自动验证 + 人类确认），状态持久化在 Vault 的 `RAWData/KEAOutput/{domain}-chain-state.md`。阶段间依赖严格：前一阶段未通过则终止。

回退规则：同一类别错误 ≥5 条或影响 >30% 文件时触发跨阶段回退。

### Sub-skills（AgentFile/skills/）

每个 sub-skill 是独立 subagent，由 phase 文件 Dispatch。sub-skill **不与用户交互、不能再嵌套 Dispatch**。Phase 文件负责将必要上下文构造好后传入，sub-skill 返回结构化结果（DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED）。

### Ontology 文档格式

四种文档类型，均为带 YAML front matter 的 Markdown：
- **object**：业务对象，含属性清单（主键标注）和关系声明
- **logic**：业务流程，含 Mermaid 流程图和判断分支
- **action**：可执行动作，含输入参数、输出结果、异常处理
- **rule**：业务规则（validation/guard/derivation/policy），声明约束目标

模板在 `AgentFile/templates/`，规范在 `AgentFile/docs/mermaid-spec.md`。

### 配置文件

KEA Skill 安装后从 `~/.claude/skills/kea/config.md` 读取 `VAULT_PATH`（Obsidian vault 路径），这是唯一的运行时配置。

## AgentFile 开发规范

修改 AgentFile 时，参见 `AgentFile/CLAUDE.md`，关键约束：

- **SKILL.md description** 只写触发条件，不写流程（会导致 Claude 跳过正文）
- **Phase 文件**在主 session 执行，负责所有用户交互和门控；**Sub-skill** 在 subagent 执行，无用户交互
- **Sub-skill 顶部**需有 `<SUBAGENT-STOP>` 标记
- SKILL.md 主体 ≤ 500 行，引用层级只有一层深
