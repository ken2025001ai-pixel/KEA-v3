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

编辑 `AgentFile/install.sh`，修改：

```bash
KEA_VERSION="4.x.x"   # ← 改为新版本号
```

### Step 2：构建安装包

```bash
cd /Users/kenkangning/KEA-v3
VERSION="4.x.x"   # ← 与 install.sh 中保持一致

# 构建临时目录
rm -rf /tmp/kea-v${VERSION}
mkdir /tmp/kea-v${VERSION}

# 复制文件（排除不必要内容）
rsync -a \
  --exclude='.git' \
  --exclude='.DS_Store' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.playwright-mcp' \
  --exclude='test-playwright.png' \
  --exclude='docs/superpowers' \
  --exclude='tests' \
  AgentFile/ /tmp/kea-v${VERSION}/AgentFile/

rsync -a \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  kea/ /tmp/kea-v${VERSION}/kea/

cp CLAUDE.md MANIFEST.in /tmp/kea-v${VERSION}/

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
  "install.sh|SKILL.md|phase-|assets/kea-graph-colors|mermaid-spec|templates/"

# 无遗漏校验（源 vs 包）
diff \
  <(find kea/ -type f | grep -v __pycache__ | grep -v ".pyc" | sort) \
  <(tar -tzf kea-v${VERSION}.tar.gz | grep "kea-v${VERSION}/kea/" | \
    sed "s|kea-v${VERSION}/||" | grep -v "/$" | sort)
# 期望：无输出（完全一致）
```

### Step 4：提交版本号更新

```bash
git add AgentFile/install.sh
git commit -m "release: bump version to ${VERSION}"
```

> 注：`.tar.gz` 在 `.gitignore` 中，包文件本身不提交到 git。

---

## 包内容说明

| 路径 | 内容 |
|------|------|
| `AgentFile/SKILL.md` | 主入口，触发词和技能链路由 |
| `AgentFile/install.sh` | 安装脚本（含版本号） |
| `AgentFile/phases/` | 12 个阶段编排文件 |
| `AgentFile/skills/` | 12 个 sub-skill（subagent 指令） |
| `AgentFile/templates/` | 6 个 Ontology 文档模板 |
| `AgentFile/docs/mermaid-spec.md` | Mermaid 节点语义规范 |
| `AgentFile/assets/kea-graph-colors.css` | Obsidian Graph View 着色 |
| `AgentFile/README.md` / `README-INSTALL.md` | 用户文档 / Agent 安装指南 |
| `AgentFile/scripts/install.js` | OpenClaw 安装适配 |
| `AgentFile/package.json` | npm 包配置 |
| `kea/` | Python 工具层（解析/校验/追踪/生成） |
| `CLAUDE.md` | 开发规范 |

**排除内容**：`.git`、`__pycache__`、`tests/`、`docs/superpowers/`（设计文档/实施计划）、`.DS_Store`、playwright 截图。

---

## 安装验证（打包后本地测试）

```bash
VERSION="4.x.x"
cd /tmp
tar -xzf /Users/kenkangning/KEA-v3/kea-v${VERSION}.tar.gz

KEA_VAULT_PATH=~/Documents/TestVault \
  bash kea-v${VERSION}/AgentFile/install.sh --claude-code
```

---

## 历史版本

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| 4.1.1 | 2026-04-28 | SKILL.md 新增 Step 1.5（Vault 路径检查 + 默认 ~/Documents/KEA-Vault）和 Step 1.6（5 个 Obsidian 插件每次检查/自动安装/状态展示） |
| 4.1.0 | 2026-04-28 | Phase 5-8 预处理改造（FLOWCHART_CANDIDATES / OBJECT_REGISTRY / LOGIC_REGISTRY / ACTION_REGISTRY / RULE_CANDIDATES）；kea mermaid 修复 .md 文件解析 |
| 4.0.0 | 2026-04-25 | 初始发布 |
