# KEA 安装说明

本文件供 Agent 平台（Claude Code、OpenClaw 等）读取后自行完成安装。无需执行脚本。

---

## 环境依赖

| 依赖 | 版本要求 | 必需 |
|------|---------|------|
| Python | 3.11+ | 是 |
| Git | 任意 | 否（用于版本追踪） |
| Obsidian | 任意 | 否（用于审视本体输出件） |

---

## 安装步骤

### Step 1: 确定 Skill 目录

将包内所有文件复制到你的 Agent 平台对应的 skill 目录：

| 平台 | 目标路径 |
|------|---------|
| Claude Code | `~/.claude/skills/kea/` |
| 其他平台 | 按平台 skill 目录约定，建立 `kea/` 子目录 |

安装后目录结构应为：

```
{SKILL_DIR}/
├── SKILL.md
├── INSTALL.md
├── config.md         ← Step 2 创建
├── phases/
├── skills/
├── templates/
├── docs/
├── assets/
└── kea/              ← Python 工具层
    ├── __main__.py
    ├── cli.py
    └── ...
```

### Step 2: 创建 config.md

在 `{SKILL_DIR}/` 下创建 `config.md`，写入：

```
# KEA Config
VAULT_PATH: {Obsidian vault 的绝对路径}
KEA_TOOLS_ROOT: {SKILL_DIR 的绝对路径}
```

示例（Claude Code）：

```
# KEA Config
VAULT_PATH: /Users/username/Documents/MyVault
KEA_TOOLS_ROOT: /Users/username/.claude/skills/kea
```

若 Vault 路径尚未确定，可先设为空，KEA 启动时会引导确认。

### Step 3: 验证工具层

```
cd {KEA_TOOLS_ROOT} && python3 -m kea --help
```

期望输出：kea CLI 帮助信息（含 validate / parse / mermaid 等子命令）。

若失败，检查：
- Python 版本 ≥ 3.11
- `kea/` 目录已正确复制到 `{SKILL_DIR}/`
- 当前工作目录为 `{KEA_TOOLS_ROOT}`（`python3 -m kea` 依赖 CWD 下存在 `kea/` 包）

---

## 触发词

安装完成后，在 Agent 会话中输入以下任意词触发 KEA：

`kea` `KEA` `ontology` `知识萃取` `本体建模` `本体萃取`

---

## Vault 目录结构（首次运行时自动创建）

```
{VAULT_PATH}/
├── 30-Ontology/
│   ├── objects/{domain}/
│   ├── logic/{domain}/
│   ├── actions/{domain}/
│   ├── rules/{domain}/
│   ├── diagrams/{domain}/
│   └── data-mock/
└── RAWData/KEAOutput/
    ├── {domain}-chain-state.md
    ├── research/
    ├── interviews/
    └── reports/
```
