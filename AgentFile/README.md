# KEA for OpenClaw

> KEA (Knowledge Extraction Agent) — 业务知识萃取与本体建模工具
>
> 帮助业务专家通过自然对话将业务经验和知识沉淀为结构化的 Ontology。

## 安装

### Claude Code（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-org/kea.git KEA-v3
cd KEA-v3/AgentFile

# 安装 Skill 到 ~/.claude/skills/kea/
bash install.sh

# 验证安装
ls ~/.claude/skills/kea/SKILL.md
```

安装完成后，在 Claude Code 中输入触发词即可启动：`kea`、`ontology`、`知识萃取`

### OpenClaw（通过 npm）

```bash
cd ~/clawd/workspace
npm install kea-openclaw
./node_modules/kea-openclaw/install.sh
```

### OpenClaw（通过 CLI）

```bash
# 从 ClawHub 安装（发布后）
openclaw skill install kea

# 或从本地路径安装
openclaw skill install ./KEA-v3/AgentFile
```

### Obsidian CSS 配置（可选）

在 Obsidian vault 根目录下运行：

```bash
bash KEA-v3/AgentFile/install.sh --obsidian
```

同时安装 Claude Code 和 Obsidian：

```bash
bash KEA-v3/AgentFile/install.sh --both
```

## 前提条件

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 工具层运行时 |
| Node.js | 22+ | OpenClaw 运行时 |
| Git | 任意 | 版本控制 |
| Obsidian | 最新 | 推荐（知识库载体） |

## 验证安装

```bash
# 检查 Python 工具层
cd kea && python3 -m kea --help

# 运行测试
python3 -m unittest discover -v tests/
```

## 使用

安装完成后，在 OpenClaw 对话中输入触发词即可：

```
你: "kea"
Agent: "您好！我是您的业务知识整理助手。您负责的是哪个业务领域？"

你: "我想整理采购部的业务流程"
Agent: "好的！我们先从您最熟悉的环节开始..."
```

### 完整命令

| 命令 | 功能 |
|------|------|
| `/ontology` | 主入口，智能导航 |
| `/ontology-extract` | 对话式提取业务知识 |
| `/ontology-validate` | 一致性检查 |
| `/ontology-index` | 生成关系图和索引 |
| `/ontology-research` | 领域调研 |
| `/ontology-flowchart` | 创建流程图 |
| `/ontology-trace` | 场景追踪验证 |
| `/ontology-impact` | 变更影响分析 |
| `/ontology-codegen` | 生成代码 |

## 文件结构

```
your-obsidian-vault/
├── openclaw/                  # 本目录（OpenClaw Skill）
│   ├── SKILL.md               # Skill 定义
│   ├── package.json           # npm 配置
│   ├── install.sh             # 安装脚本
│   └── README.md              # 本文件
│
├── kea/                       # Python 工具层
│   ├── kea/
│   │   ├── cli.py             # CLI 入口
│   │   ├── parser/            # 文档解析
│   │   ├── validator/         # 校验器
│   │   ├── tracer/            # 场景追踪
│   │   ├── indexer/           # 索引生成
│   │   └── generator/         # 代码生成
│   └── tests/                 # 单元测试
│
├── ontology/                  # 生成的 Ontology 文档
│   ├── objects/               # 业务对象
│   ├── logic/                 # 业务流程
│   ├── actions/               # 业务动作
│   ├── diagrams/              # Mermaid 流程图
│   └── README.md              # 自动生成的索引
│
├── .obsidian/                 # Obsidian 配置
│   └── snippets/
│       └── kea-graph-colors.css
│
└── .claude/                   # Claude Code 配置（可选）
    ├── skills/kea/SKILL.md
    ├── commands/
    └── agents/
```

## 跨平台支持

KEA 的设计是**平台无关**的：

| 平台 | 状态 | 说明 |
|------|------|------|
| **Claude Code** | ✅ 原生支持 | 主开发平台，`.claude/` 目录 |
| **OpenClaw** | ✅ 本包 | `openclaw/` 目录，通过 SKILL.md |
| **Cursor** | ⚠️ 待验证 | 理论上兼容，需测试 |
| **其他 Agent 平台** | ✅ 可适配 | 只需重写 SKILL.md，Python 工具层复用 |

**核心原则**: Agent 平台差异只影响编排层（SKILL.md），Python 工具层（`kea/`）在所有平台复用。

## 发布到 ClawHub

```bash
# 1. 更新版本号
#    修改 package.json 和 SKILL.md 中的 version

# 2. 运行安全审计
openclaw security audit

# 3. 打包
npm pack

# 4. 发布到 npm
npm publish --access public

# 5. 提交到 ClawHub（待审核）
#    访问 https://clawhub.openclaw.ai 提交
```

## 安全

KEA 的权限声明：

```yaml
permissions:
  filesystem:
    - "read:./ontology"
    - "write:./ontology"
  exec:
    - "python3"
    - "git"
```

- **零外部依赖**: Python 工具层只用标准库
- **不访问网络**: 除 `git` 外无网络操作
- **本地运行**: 所有数据保存在本地文件系统
- **无 API 密钥**: 不需要存储任何第三方密钥

## 问题反馈

- GitHub Issues: https://github.com/your-org/kea/issues
- 文档: `kea/docs/`

## License

MIT
