# KEA — 自主安装指南（HemersAgent / Openclaw）

本文件供 Agent 自主阅读后完成 KEA Skill 的安装与配置。

## 安装前提

- Python 3.11+
- Git（可选，用于版本管理）

## 安装步骤

### Step 1: 确认提取路径

本包已解压到某个目录（以下记为 `KEA_PACKAGE_DIR`），目录结构应为：

```
{KEA_PACKAGE_DIR}/
├── AgentFile/          ← Claude Code Skill 编排层
│   ├── install.sh      ← 安装脚本
│   ├── SKILL.md
│   ├── phases/
│   └── skills/
└── kea/                ← Python 确定性工具层（直接可用，无需软链接）
    ├── __main__.py
    └── ...
```

验证目录结构：`ls {KEA_PACKAGE_DIR}` 应看到 `AgentFile` 和 `kea` 两个目录。

### Step 2: 确认 Vault 路径

向用户询问 Obsidian Vault 的**绝对路径**（例如 `~/Documents/MyVault`）。

记为 `VAULT_PATH`。

若用户无 Obsidian Vault，可使用任意空目录，KEA 会自动创建所需子目录。

### Step 3: 运行安装脚本

以非交互方式运行（通过 `KEA_VAULT_PATH` 环境变量传入路径）：

```bash
KEA_VAULT_PATH="{VAULT_PATH}" bash {KEA_PACKAGE_DIR}/AgentFile/install.sh --claude-code
```

安装脚本会：
1. 验证 Python 3.11+
2. 验证 `{KEA_PACKAGE_DIR}/kea/` 目录存在并可运行 `python3 -m kea`
3. 运行单元测试（如有）
4. 将 Skill 文件安装到 `~/.claude/skills/kea/`
5. 在 `~/.claude/skills/kea/config.md` 写入：
   - `VAULT_PATH: {VAULT_PATH}`
   - `KEA_TOOLS_ROOT: {KEA_PACKAGE_DIR}`（运行 python3 -m kea 的工作目录）
6. 在 `{VAULT_PATH}` 创建所需子目录

### Step 4: 验证安装

```bash
cd {KEA_PACKAGE_DIR} && python3 -m kea --help
```

输出应显示 KEA CLI 帮助信息。

### Step 5: 向用户确认

安装完成后，告知用户：

> KEA 已安装完成。在 Claude Code 中输入 `kea`、`ontology` 或 `知识萃取` 即可触发。
>
> Vault 路径：{VAULT_PATH}

## 安装参数汇总

| 参数 | 说明 | 示例 |
|------|------|------|
| `KEA_VAULT_PATH` | Vault 绝对路径（env var） | `/Users/ken/Documents/Vault` |
| `--claude-code` | 安装至 Claude Code skills | 默认选项 |
| `--obsidian` | 仅安装 Obsidian CSS snippet | 需在 vault 目录内运行 |
| `--both` | 两者都安装 | |

## 可选增强依赖

安装后可 pip 安装以下库提升文档处理能力（可选）：

```bash
pip install pdfplumber       # PDF 表格提取
pip install surya-ocr        # 扫描件 OCR
pip install trafilatura      # URL 正文提取
```

未安装时自动降级到 markitdown，功能正常可用。

## 故障排除

**`python3 -m kea --help` 失败**：确认当前工作目录为 `{KEA_PACKAGE_DIR}`（含 `kea/` 子目录），且 Python 3.11+ 可用。

**Vault 目录不存在**：安装脚本会给出警告但继续执行，KEA 运行时会自动创建子目录。
