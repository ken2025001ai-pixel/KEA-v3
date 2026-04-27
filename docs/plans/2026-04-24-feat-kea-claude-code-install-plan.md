---
title: "feat: KEA Claude Code 安装优化"
type: feat
status: active
date: 2026-04-24
---

# feat: KEA Claude Code 安装优化

## 背景

当前 `openclaw/install.sh` 设计目标是 OpenClaw 平台，但存在多个错误和遗漏，导致在 Claude Code 环境中无法正常安装。目标是让整个包在 Claude Code 中一键可用。

## 问题清单（install.sh 中的 Bug）

### Bug 1: CSS snippet 路径逻辑错误（永远无法执行）
```bash
CSS_SRC="${PROJECT_ROOT}/.obsidian/snippets/kea-graph-colors.css"
if [ ! -f "${CSS_SRC}" ]; then
    # 这里尝试从另一个路径 copy，但那个路径也不存在
    if [ -f "${PROJECT_ROOT}/ontology-modeling/.obsidian/snippets/kea-graph-colors.css" ]; then
        cp ...
    fi
fi
```
**问题**：`kea-graph-colors.css` 文件根本不在仓库里，两个路径都不存在，`cp` 永远不会执行。但安装脚本不报错，静默跳过，用户以为配置成功了。

### Bug 2: Claude Code 安装路径完全缺失
当前脚本只处理 Obsidian 配置，对 Claude Code 的安装目标路径（`~/.claude/skills/kea/`）完全没有涉及。

### Bug 3: Python 版本比较逻辑在某些 shell 下不可靠
```bash
if [ "${PYTHON_MAJOR}" -lt 3 ] || ([ "${PYTHON_MAJOR}" -eq 3 ] && [ "${PYTHON_MINOR}" -lt 11 ]); then
```
括号 `()` 在 sh（非 bash）环境中会 fork 子 shell，`-lt`/`-eq` 是整数比较运算，但版本号提取用 `cut`，如果版本字符串格式异常（如 `3.11.0rc1`），minor 提取可能包含非数字字符导致算术比较报错。

### Bug 4: unittest discover 路径假设错误
```bash
if ${PYTHON_CMD} -m unittest discover -v tests/ > /tmp/kea-test.log 2>&1; then
```
`discover` 从当前目录（`${KEA_DIR}`）找 `tests/`，但 `kea/` 目录下根本没有 `tests/` 子目录（现有结构中不存在），会静默 0 test 通过，误导用户。

### Bug 5: 安装脚本没有为 Claude Code 创建任何文件
整个安装后，`~/.claude/skills/kea/SKILL.md` 不会被创建，Claude Code 无法识别该 skill。

### Bug 6: kea 的 SKILL.md 位置不对
当前 `kea/kea/skills/SKILL.md` 是内部工具层文档（面向开发者），而 OpenClaw 的 `openclaw/SKILL.md` 才是 Skill 定义文件。Claude Code 需要的是一个适配 Claude Code 平台的 SKILL.md，放在 `~/.claude/skills/kea/SKILL.md`。

## 解决方案

### Phase 1: 创建 Claude Code 专用 SKILL.md

在 `kea/kea/skills/SKILL.md` 目前是内部文档。需要：
- 将 `openclaw/SKILL.md` 作为 OpenClaw 平台版本（保留）
- 新建一个适配 Claude Code 格式的 SKILL.md（实际上 `openclaw/SKILL.md` 本身内容兼容，只需安装到正确位置）

**目标路径**：`~/.claude/skills/kea/SKILL.md`

### Phase 2: 重写 install.sh（修复所有 Bug）

新的安装脚本支持两种模式：
1. `--claude-code`（默认）：安装到 `~/.claude/skills/kea/`
2. `--obsidian`：安装 Obsidian CSS snippet（当 .obsidian 目录存在时）
3. `--both`：两者都安装

### Phase 3: 生成缺失的 kea-graph-colors.css

当前仓库中不存在这个文件，需要创建它，或在脚本中内联生成。

### Phase 4: 修复 tests 路径问题

在 `kea/` 下添加占位符 `tests/` 目录，或修改脚本在测试目录不存在时跳过并说明。

## 实现计划

### Task 1: 修复 install.sh
**文件**: `openclaw/install.sh`
**改动**:
- 增加 `--claude-code` 安装路径逻辑：将 `openclaw/SKILL.md` + `openclaw/agents/` 复制到 `~/.claude/skills/kea/`
- 修复 CSS snippet 路径（内联生成 CSS，不依赖外部文件）
- 修复版本比较（用 `python3 -c "import sys; ..."` 替代 shell 字符串比较）
- 修复 unittest discover（检查 tests/ 是否存在）
- 增加安装成功验证：检查 `~/.claude/skills/kea/SKILL.md` 存在

**成功标准**:
- [ ] `bash install.sh` 在 Claude Code 环境中执行无错误
- [ ] `~/.claude/skills/kea/SKILL.md` 被创建
- [ ] `~/.claude/skills/kea/agents/` 目录被复制
- [ ] Python 版本检查不误报

### Task 2: 生成 kea-graph-colors.css
**文件**: `.obsidian/snippets/kea-graph-colors.css`（由脚本生成）或 `openclaw/assets/kea-graph-colors.css`（源文件）
**改动**:
- 创建 `openclaw/assets/kea-graph-colors.css` 源文件（Obsidian Graph View 颜色编码）
- 安装脚本从这里 cp，而不是从不存在的路径

**成功标准**:
- [ ] CSS 文件存在且语法正确
- [ ] 安装后 `.obsidian/snippets/kea-graph-colors.css` 存在（当有 .obsidian 目录时）

### Task 3: 更新 README.md（安装说明）
**文件**: `openclaw/README.md`
**改动**:
- 更新 Claude Code 安装步骤为正确的命令
- 说明安装后在 Claude Code 中如何触发（trigger words）

**成功标准**:
- [ ] README 的安装步骤可以被直接执行

### Task 4: 创建 tests/ 目录占位符
**文件**: `kea/tests/__init__.py`（或 `kea/tests/test_placeholder.py`）
**改动**:
- 防止 `python -m unittest discover tests/` 在空目录失败

**成功标准**:
- [ ] `cd kea && python3 -m unittest discover tests/` 输出 "Ran 0 tests in ..."（或已有测试通过）

## 验收标准

- [ ] 从零开始（只有本仓库），执行 `bash openclaw/install.sh`，Claude Code 可以识别 kea skill
- [ ] 在 Claude Code 输入 `kea` 或 `知识萃取`，skill 被触发
- [ ] install.sh 对错误有清晰的错误信息，不静默失败
- [ ] Obsidian 配置路径逻辑正确（CSS 文件存在）
