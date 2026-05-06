# KEA Release & Package Guide

本文档记录如何构建可发布的 KEA 安装包（`.tar.gz`），供后续版本持续生成使用。

---

## 版本命名规则

`MAJOR.MINOR.PATCH`

| 变更类型 | 版本升级 | 示例 |
|---------|---------|------|
| Phase/Skill 重大重构、架构变更 | MINOR | 4.0.0 → 4.1.0 |
| Bug 修复、小幅优化、文档更新 | PATCH | 4.1.0 → 4.1.1 |
| 破坏性接口变更（kea CLI / SKILL.md 触发词） | MAJOR | 4.x → 5.0.0 |

---

## 打包前检查

```bash
cd /Users/kenkangning/KEA-v3

# 1. 全量测试通过
python3 -m pytest tests/ -q
# 期望：xx passed, 0 failed

# 2. AgentFile lint 无错误
python3 -m kea --format json lint AgentFile/ | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('errors:', d.get('summary',{}).get('errors',0))"
# 期望：errors: 0

# 3. 工作区干净（无未提交改动）
git status
# 期望：nothing to commit
```

---

## 打包步骤

### Step 1：更新版本号

编辑 `RELEASE.md` 版本历史表，新增当前版本记录。

### Step 2：构建安装包

包结构为**扁平化**：AgentFile 内容和 kea/ 工具层并列，提取后直接对应 skill 目录结构。

```bash
cd /Users/kenkangning/KEA-v3
VERSION="4.x.x"   # ← 改为新版本号

# 构建临时目录
rm -rf /tmp/kea-v${VERSION}
mkdir /tmp/kea-v${VERSION}

# 复制 AgentFile 内容（扁平，不含 AgentFile/ 目录前缀）
rsync -a \
  --exclude='.DS_Store' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  AgentFile/ /tmp/kea-v${VERSION}/

# 复制 kea/ 工具层（与 skill 文件并列）
rsync -a \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  kea/ /tmp/kea-v${VERSION}/kea/

# 打包
cd /tmp && tar -czf /Users/kenkangning/KEA-v3/kea-v${VERSION}.tar.gz kea-v${VERSION}/

echo "✅ 生成：kea-v${VERSION}.tar.gz ($(du -sh /Users/kenkangning/KEA-v3/kea-v${VERSION}.tar.gz | cut -f1))"
```

### Step 3：验证包内容

```bash
VERSION="4.x.x"
cd /Users/kenkangning/KEA-v3

# 文件总数
tar -tzf kea-v${VERSION}.tar.gz | wc -l

# 关键文件检查
tar -tzf kea-v${VERSION}.tar.gz | grep -E \
  "SKILL\.md|INSTALL\.md|phase-|assets/kea-graph-colors|mermaid-spec|templates/|kea/__main__"

# 无遗漏校验（kea/ 工具层）
diff \
  <(find kea/ -type f | grep -v __pycache__ | grep -v ".pyc" | sort) \
  <(tar -tzf kea-v${VERSION}.tar.gz | grep "kea-v${VERSION}/kea/" | \
    sed "s|kea-v${VERSION}/||" | grep -v "/$" | sort)
# 期望：无输出（完全一致）
```

### Step 4：提交版本记录

```bash
git add RELEASE.md
git commit -m "release: bump version to ${VERSION}"
```

> 注：`.tar.gz` 在 `.gitignore` 中，包文件本身不提交到 git。

---

## 包内容说明

安装包提取后直接对应 skill 目录结构（`{SKILL_DIR}/kea/`）：

| 路径 | 内容 |
|------|------|
| `SKILL.md` | 主入口，触发词和技能链路由 |
| `INSTALL.md` | 声明式安装说明（无可执行脚本） |
| `phases/` | 12 个阶段编排文件 |
| `skills/` | Sub-skill（subagent 指令） |
| `templates/` | Ontology 文档模板 |
| `docs/mermaid-spec.md` | Mermaid 节点语义规范 |
| `assets/kea-graph-colors.css` | Obsidian Graph View 着色 |
| `README.md` / `README-INSTALL.md` | 用户文档 |
| `kea/` | Python 工具层（解析/校验/追踪/生成） |

**排除内容**：`__pycache__`、`*.pyc`、`.DS_Store`。
`tests/`、`docs/superpowers/`、`CLAUDE.md` 均不包含在安装包中。

---

## 安装验证（打包后本地测试）

```bash
VERSION="4.x.x"
cd /tmp
tar -xzf /Users/kenkangning/KEA-v3/kea-v${VERSION}.tar.gz

# 验证工具层
cd kea-v${VERSION}
python3 -m kea --help
```

---

## 历史版本

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| 4.2.1 | 2026-05-06 | 添加 README.md；Diagram 重新定位为人类确认工具（不再是提取主源）；extract-objects 主源改为研究报告+访谈摘要；extract-logic 明确结构/内容分工 |
| 4.2.0 | 2026-05-01 | install.sh 替换为声明式 INSTALL.md；包结构扁平化，kea/ 工具层与 skill 文件并列；Phase 5-8 合并为统一本体提取流水线 |
| 4.1.3 | 2026-04-29 | Step 1.6 改为声明式指令：告知 LLM 插件列表和来源，由 LLM 自主完成安装 |
| 4.1.2 | 2026-04-29 | Step 1.6 插件安装改为 Python 标准库（跨平台，移除 bash 依赖） |
| 4.1.1 | 2026-04-28 | SKILL.md 新增 Step 1.5（Vault 路径检查 + 默认 ~/Documents/KEA-Vault）和 Step 1.6（5 个 Obsidian 插件每次检查/自动安装/状态展示） |
| 4.1.0 | 2026-04-28 | Phase 5-8 预处理改造（FLOWCHART_CANDIDATES / OBJECT_REGISTRY / LOGIC_REGISTRY / ACTION_REGISTRY / RULE_CANDIDATES）；kea mermaid 修复 .md 文件解析 |
| 4.0.0 | 2026-04-25 | 初始发布 |
