# 知识萃取 Agent 设计分析

> 主题：当前 Skill 实现与最新架构设计的差距分析，以及知识萃取 Agent 的架构设计  
> 日期：2026-04-22  
> 状态：分析稿，待评审  

---

## 执行摘要

**核心结论：当前实现不可直接沿用，但业务语义资产（50+ 对象定义、7 个操作流程）可完整重用。推荐采取「双轨运行」策略——训练时迁移为 OntologySkill + 运行时保留 SKILL.md 作为兜底桥接，逐步过渡。**

| 维度 | 当前实现 | 最新设计 | 可重用性 |
|------|---------|---------|---------|
| 读取时机 | **运行时**读取 Markdown | **构建时**读取 Markdown | ❌ 必须改 |
| 执行模式 | Agent 实时解释自然语言 | 调用**固化确定性资产** | ❌ 必须改 |
| 文档格式 | 自然语言表格，无 YAML FM | YAML FM + 伪代码 + 状态机 | ❌ 必须改 |
| 业务语义 | 50+ 对象、7 个流程、完整关系 | 需要迁移 | ✅ 可重用 |
| taxonomy | operations/ 混合 Logic+Action | logic/ + actions/ 严格拆分 | ⚠️ 需拆分 |
| 数据查询 | mindsdb_client.py 自然语言→SQL | OntologySkill 内嵌数据访问层 | ⚠️ 可封装 |
| 确定性 | 低（每次回答重新理解） | 高（编译后代码执行） | ❌ 必须改 |
| 可测试性 | 无（无法自动验证） | 沙箱执行 + 契约覆盖 | ❌ 必须改 |

---

## 1. 当前实现深度剖析

### 1.1 SKILL.md 的本质：运行时 Agent 指令

当前的 `SKILL.md` 不是知识文档，而是一份**运行时 Agent 操作手册**。它的核心机制是：

```
用户提问
    ↓
Agent 读取 SKILL.md（获取"如何工作"的指令）
    ↓
Agent 识别问题类型 → 匹配 operations/ 中的 SOP 文档
    ↓
Agent 读取 objects/ 中的对象定义（理解字段含义和关系）
    ↓
Agent 生成自然语言查询 → 调用 mindsdb_client.py → 获取真实数据
    ↓
Agent 按 SOP 中的自然语言步骤执行计算/分析
    ↓
返回结果给用户
```

**关键特征**：
- **运行时理解**：每次回答问题时，Agent 都要重新读取、重新理解 Markdown 文件
- **自然语言执行**：SOP 中的步骤是plaintext（如"1. 找出当前ECO变更涉及的所有物料"），Agent 用 LLM 能力将其转化为执行计划
- **无编译环节**：没有"知识→资产"的转化过程，Agent 直接解释执行
- **混合层次**：SKILL.md 同时包含知识层（对象定义说明）、运行时层（查询协议）、训练层（调用关系）的内容

### 1.2 当前实现的隐性假设

这套机制建立在几个隐性假设之上，这些假设在原型阶段成立，但在生产环境会暴露严重问题：

| 隐性假设 | 原型阶段 | 生产环境 |
|---------|---------|---------|
| "Agent 每次都能准确理解文档" | ✓ 问题简单时基本正确 | ✗ 复杂逻辑时理解偏差导致错误结果 |
| "自然语言步骤足够精确" | ✓ 步骤少、分支简单时 | ✗ 嵌套条件、循环、异常处理时歧义多 |
| "文档变更立即可生效" | ✓ 方便快速迭代 | ✗ 未经审核的文档变更可能破坏生产逻辑 |
| "查询结果可以直接用于计算" | ✓ 数据量小、格式固定 | ✗ 数据格式变化时 Agent 可能错误解析 |
| "所有操作都是无副作用的查询" | ✓ 目前主要是分析类 | ✗ 未来涉及写操作时没有事务保障 |

### 1.3 当前实现的价值：原型验证了三件事

尽管存在架构问题，当前实现成功验证了三个关键假设，这是最有价值的资产：

1. **Agent 能够理解 Markdown 格式的业务文档**  
   证明了我们选择的"Agent-Native Markdown"方向是正确的，Agent 确实可以从结构化文本中提取业务语义。

2. **区分元数据和真实数据的策略是有效的**  
   `objects/` 作为元数据定义 + `mindsdb_client.py` 查询真实数据的分层，避免了 Agent 用演示数据回答用户，这一原则应在最新设计中保留。

3. **SOP 文档可以指导 Agent 完成多步骤任务**  
   ECO 变更影响分析（涉及 3 个子调用、循环、条件分支）能被 Agent 执行，说明业务逻辑的 LLM 可解释性已经达到可用水平。

---

## 2. 最新设计回顾：编译时理解 + 运行时调用

### 2.1 核心范式转换

最新设计完成了一个根本性的范式转换：

| 维度 | 旧范式（当前实现） | 新范式（最新设计） |
|------|------------------|------------------|
| **知识何时被理解** | 运行时（每次回答重新理解） | 构建时（训练时一次性编译） |
| **知识理解者** | 运行时 Agent（通用 LLM） | 知识萃取 Agent（专用 Agent + 人类审核） |
| **执行载体** | Agent 动态生成的执行计划 | Registry 中固化的 OntologySkill/BPM |
| **确定性来源** | 提示工程 + 上下文约束 | 编译后的确定性代码 + 签名验证 |
| **质量保障** | 无（依赖 Agent 自身能力） | 评估层自动验证 + 人类审核 + 沙箱执行 |
| **版本控制** | Git 管理 Markdown | Git 管理知识 + Registry 管理资产 |

### 2.2 运行时层的极简职责

最新设计中，运行时 Agent（Orchestrator）的职责被严格限制为：

```python
# 运行时 Agent 只做 5 件事
1. 理解用户意图（LLM）
2. 识别涉及的业务实体
3. 从 Registry 匹配固化资产（OntologySkill / BPM）
4. 从用户输入中提取参数，填充到资产输入模式
5. 调用执行，返回结果

# 运行时 Agent 不做的事
- 不读取知识文档
- 不理解业务逻辑细节
- 不生成执行计划
- 不直接查询数据库（由 OntologySkill 内部处理）
```

---

## 3. 差距矩阵：逐项分析

### 3.1 知识层文档格式差距

| 要素 | 当前实现 | 最新设计 | 迁移成本 | 策略 |
|------|---------|---------|---------|------|
| YAML Front Matter | ❌ 无 | ✅ 必须 | 中 | 为每份文档补充 YAML FM，可用脚本批量生成初版 |
| `type` 字段 | ❌ 无 | ✅ object/logic/action/rule | 低 | 根据目录和文件名推断 |
| `id` 字段 | ❌ 无 | ✅ 全局唯一标识 | 低 | 基于文件名生成（如 `eco_change_order`） |
| `agent_context` | ❌ 无 | ✅ one_liner + scenarios + misconceptions | **高** | 需要人工补充或 Agent 从内容推断 |
| `relations` | ⚠️ 自然语言 prose | ✅ 结构化数组 | 中 | 从 prose 中解析提取 |
| 属性表 | ✅ 有（自然语言） | ✅ 有（+ 约束表达式） | 低 | 增加约束列（pattern/min/max 等） |
| 状态机 | ❌ 无 | ✅ Mermaid | **高** | 需人工补充或从 Status 枚举推断 |
| 伪代码 | ❌ plaintext 步骤 | ✅ `pseudo` 代码块 | **高** | 核心工作：将自然语言步骤转化为伪代码 |
| 输入输出模式 | ⚠️ 表格（无 schema） | ✅ 结构化 schema | 中 | 从表格中结构化提取 |
| 前置/后置/回滚 | ⚠️ 有（自然语言） | ✅ 伪代码 + 断言 | 中 | 从 prose 中提取转化 |

### 3.2 架构层次差距

| 层次 | 当前实现 | 最新设计 | 差距说明 |
|------|---------|---------|---------|
| **知识层** | `objects/` + `operations/` + `rules/` + `SKILL.md` | `objects/` + `logic/` + `actions/` + `rules/` | 当前 `operations/` 混合 Logic+Action；`SKILL.md` 跨层混合 |
| **训练层** | ❌ 不存在 | Agent 生成 + 人类审核 + 评估 + Registry | 需要全新建设 |
| **实例化层** | ❌ 不存在 | Registry + Neo4j | 需要全新建设 |
| **运行时层** | Agent 直接读 Markdown 执行 | Orchestrator 调用固化资产 | 运行时 Agent 职责完全改变 |
| **评估层** | ❌ 不存在 | 契约提取 + 多 LLM 共识 + 沙箱 | 需要全新建设 |

### 3.3 执行模式差距

| 场景 | 当前实现 | 最新设计 | 影响 |
|------|---------|---------|------|
| 用户问"ECO-001影响多大" | Agent 读 ECO变更影响分析计算.md → 理解步骤 → 查询数据 → 按步骤计算 | Orchestrator 匹配 `eco_impact_analysis` OntologySkill → 参数填充 → 沙箱执行 | 当前模式可能理解偏差；新模式确定性高 |
| 文档更新了步骤 | 下次回答自动按新步骤执行（无审核） | 触发训练管道 → Agent 重新生成 → 评估 → 审核 → 注册 | 当前模式变更即时生效但无质量控制 |
| 复杂分支条件 | Agent 从自然语言推断（可能漏掉边界） | 伪代码明确表达，沙箱测试覆盖所有分支 | 当前模式可靠性低 |
| 并发请求 | Agent 各自独立读文档执行（状态不一致风险） | OntologySkill Runtime 统一调度（事务保障） | 当前模式有数据竞争风险 |

---

## 4. 重用策略：什么能留，什么必须改

### 4.1 可直接重用的资产（✅）

| 资产 | 重用方式 | 说明 |
|------|---------|------|
| **50+ 对象定义的业务语义** | 作为知识萃取 Agent 的输入，转化为新格式 | 属性名称、英文名称、描述、主键/类型/多值标记全部保留 |
| **对象间关系 prose** | 解析为 `relations` 结构化数组 | "ECO变更单可以对应一个或多个ECO变更执行周期" → `{target: eco_execution_cycle, type: has, cardinality: "1:N"}` |
| **7 个 operations 的业务步骤** | 转化为 logic/actions 的伪代码 | 步骤的先后顺序、条件判断、子调用关系是核心语义 |
| **mindsdb_client.py** | 封装为 OntologySkill 的数据访问层组件 | 自然语言→SQL 的能力是通用的，可作为数据查询 OntologySkill 的底层 |
| **查询规则（单表/合并/原子化）** | 转化为数据访问 OntologySkill 的约束规范 | 这些规则本质上是数据访问的最佳实践 |
| **目录结构（workspaces/domain/knowledge）** | 保留并扩展 | 增加 `logic/` 和 `actions/` 子目录，拆分 `operations/` |

### 4.2 需要改造的资产（⚠️）

| 资产 | 改造内容 | 工作量评估 |
|------|---------|-----------|
| **SKILL.md** | 解体为三部分：(1) 每份文档的 YAML FM agent_context → 知识层；(2) 调用关系 → logic 的 relations；(3) 查询协议 → 数据访问 OntologySkill 规范 | 中 |
| **operations/*.md** | 按 Logic/Action 边界拆分：含子调用的 → logic/；原子操作 → actions/ | 中（需人工判断边界） |
| **属性表** | 增加约束表达式列（pattern/min/max/default 等） | 低 |
| **输入输出表格** | 结构化提取为 YAML FM `inputs` / `outputs` | 低 |

### 4.3 必须新建的组件（❌）

| 组件 | 说明 | 优先级 |
|------|------|--------|
| **知识萃取 Agent** | 读取 Agent-Native Markdown → 生成 OntologySkill 候选 | P0 |
| **契约提取器** | 从知识文档提取前置/后置/回滚的形式化契约 | P0 |
| **Registry** | 固化资产的存储、版本化、签名、溯源 | P0 |
| **评估层（沙箱 + 多 LLM 共识）** | 自动验证生成的 OntologySkill | P1 |
| **OntologySkill Runtime** | 沙箱执行、前置后置检查、审计日志 | P1 |
| **Orchestrator** | 意图理解 + 资产匹配 + 参数填充 | P1 |
| **BPM Engine** | 流程编排（长流程、并行网关、人工任务） | P2 |
| **完备性检查 CI** | R1-R7 规则自动检查 | P1 |

---

## 5. 知识萃取 Agent 架构设计

### 5.1 定位与职责

知识萃取 Agent（Knowledge Extraction Agent，简称 KEA）是**训练层的核心引擎**。它不是运行时回答用户问题的 Agent，而是专职做"知识文档 → 确定性资产"转化的构建时 Agent。

```
┌─────────────────────────────────────────────────────────────┐
│                    知识萃取 Agent (KEA)                      │
│                                                             │
│  输入：Agent-Native Markdown 知识文档（objects/logic/actions/rules） │
│  输出：OntologySkill 候选 + BPM 候选 + 测试用例 + 评估报告     │
│                                                             │
│  工作模式：构建时运行（CI/CD 管道中），非运行时               │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 核心处理管线

```
知识文档变更（Git push / PR）
    ↓
Step 1: 文档解析器（Document Parser）
    ├─ 解析 YAML Front Matter（结构化元数据）
    ├─ 解析 Markdown Body（自然语言描述）
    ├─ 解析伪代码块（执行逻辑）
    ├─ 解析状态机（Mermaid → 状态转移表）
    └─ 解析属性表（列名映射、约束提取）
    ↓
Step 2: 语义理解引擎（Semantic Understanding Engine）
    ├─ 对象关系图谱构建（从 relations 和属性引用）
    ├─ 调用链分析（从 logic 的 call_action）
    ├─ 数据流分析（输入输出模式匹配）
    └─ 状态机可达性分析（死状态检测、不可达状态检测）
    ↓
Step 3: 资产生成器（Asset Generator）
    ├─ Action → OntologySkill 代码片段（Python/JS）
    ├─ Logic → BPMN 流程定义 或 OntologySkill 编排器
    ├─ Object → Schema Cache（JSON Schema）
    └─ Rule → 可执行断言 / 校验函数
    ↓
Step 4: 契约提取器（Contract Extractor）
    ├─ 从前置条件提取：输入断言
    ├─ 从后置条件提取：输出断言
    ├─ 从回滚规则提取：补偿逻辑
    └─ 从边界条件提取：异常场景
    ↓
Step 5: 测试用例生成器（Test Generator）
    ├─ 边界值测试（刚好满足/刚好不满足/零值/极大值）
    ├─ 等价类测试（有效输入 / 无效输入）
    ├─ 状态机遍历（所有状态转换路径）
    └─ 组合测试（前置条件的真假组合）
    ↓
Step 6: 评估层提交（提交给 Evaluation Layer）
    ├─ 语法/结构验证（AST 解析）
    ├─ 契约覆盖检查（前置/后置/回滚是否实现）
    ├─ 沙箱执行（测试用例通过率）
    ├─ 语义一致性（多 LLM 共识：代码逻辑 vs 知识文档）
    └─ 安全扫描（注入/密钥/权限）
    ↓
Step 7: 人类审核门户（Human Review Portal）
    ├─ 展示：diff（知识文档 vs 生成代码）
    ├─ 展示：评估报告雷达图
    ├─ 展示：测试用例覆盖情况
    ├─ 展示：多 LLM 共识分歧点
    └─ 决策：通过 / 驳回 / 要求修正
    ↓
Step 8: Registry 注册
    ├─ 版本化（semver）
    ├─ 签名（防篡改）
    ├─ 溯源（知识文档路径 + git commit hash）
    └─ 依赖解析（子调用引用的 OntologySkill 版本锁定）
```

### 5.3 KEA 的模块设计

#### 5.3.1 文档解析器（Document Parser）

```python
class DocumentParser:
    """将 Agent-Native Markdown 解析为结构化 AST"""
    
    def parse(self, file_path: str) -> KnowledgeDocument:
        content = read_file(file_path)
        
        # 1. 解析 YAML Front Matter
        yaml_fm = extract_yaml_front_matter(content)
        
        # 2. 解析 Markdown Body 为区块序列
        sections = parse_markdown_sections(content)
        # sections = [
        #   {"type": "heading", "level": 1, "text": "对象描述"},
        #   {"type": "paragraph", "text": "..."},
        #   {"type": "table", "headers": [...], "rows": [...]},
        #   {"type": "code", "lang": "pseudo", "content": "..."},
        #   {"type": "mermaid", "diagram_type": "stateDiagram-v2", "content": "..."}
        # ]
        
        # 3. 语义标注（识别表格类型：属性表 vs 输入输出表 vs 边界条件表）
        annotated = self.annotate_semantics(sections)
        
        return KnowledgeDocument(
            type=yaml_fm["type"],  # object / logic / action / rule
            id=yaml_fm["id"],
            yaml_fm=yaml_fm,
            sections=annotated,
            ast=self.build_ast(annotated)
        )
    
    def annotate_semantics(self, sections: list) -> list:
        """识别每个区块的语义角色"""
        for section in sections:
            if section["type"] == "table":
                if "属性" in section.get("title", ""):
                    section["semantic_role"] = "property_table"
                elif "输入" in section.get("title", ""):
                    section["semantic_role"] = "input_schema"
                elif "输出" in section.get("title", ""):
                    section["semantic_role"] = "output_schema"
                elif "边界" in section.get("title", ""):
                    section["semantic_role"] = "boundary_conditions"
                elif "状态转换" in section.get("title", ""):
                    section["semantic_role"] = "state_transitions"
            elif section["type"] == "code" and section["lang"] == "pseudo":
                section["semantic_role"] = "execution_logic"
            elif section["type"] == "mermaid":
                section["semantic_role"] = "state_machine"
        return sections
```

#### 5.3.2 资产生成器（Asset Generator）

资产生成器是 KEA 的核心，负责将解析后的 AST 转化为可执行资产。

**Action → OntologySkill 的生成策略**：

```python
class ActionAssetGenerator:
    """将 Action 知识文档转化为 OntologySkill 代码"""
    
    def generate(self, doc: KnowledgeDocument) -> OntologySkill:
        assert doc.type == "action"
        
        # 1. 生成函数签名（从 inputs/outputs YAML FM）
        function_signature = self.build_signature(doc.yaml_fm["inputs"], doc.yaml_fm["outputs"])
        
        # 2. 生成前置条件检查代码（从伪代码中的 assert 和前置条件区）
        preconditions = self.extract_preconditions(doc)
        
        # 3. 生成核心业务逻辑（从伪代码块）
        # 策略：伪代码是"高级语言"，需要转化为目标语言（Python/JS）
        # 伪代码中的"查询X" → 数据访问层调用
        # 伪代码中的"call_action" → 子 OntologySkill 调用
        core_logic = self.translate_pseudocode(doc.get_section("execution_logic"))
        
        # 4. 生成后置条件检查代码
        postconditions = self.extract_postconditions(doc)
        
        # 5. 生成回滚逻辑
        rollback = self.extract_rollback(doc)
        
        # 6. 组装完整代码
        code = self.assemble_code(
            signature=function_signature,
            preconditions=preconditions,
            core_logic=core_logic,
            postconditions=postconditions,
            rollback=rollback,
            doc_id=doc.id
        )
        
        return OntologySkill(
            id=doc.id,
            name=doc.yaml_fm["name"],
            code=code,
            language="python",
            input_schema=doc.yaml_fm["inputs"],
            output_schema=doc.yaml_fm["outputs"],
            preconditions=preconditions,
            postconditions=postconditions,
            rollback=rollback,
            knowledge_source=file_path,
            knowledge_version=git_commit_hash
        )
    
    def translate_pseudocode(self, pseudo_section: Section) -> str:
        """
        将伪代码翻译为 Python。
        伪代码是受限的自然语言，有明确的结构：
        - function 定义
        - 变量声明和赋值
        - if/elif/else 分支
        - for 循环
        - assert 断言
        - call_action 子调用
        - 查询操作（"查询X" → 数据访问层）
        """
        pseudo_ast = parse_pseudocode(pseudo_section.content)
        
        python_code = []
        for node in pseudo_ast:
            if node.type == "function_def":
                python_code.append(f"def {node.name}({node.params}):")
            elif node.type == "assert":
                python_code.append(f"    assert {node.condition}, {node.message}")
            elif node.type == "query":
                # "查询库存(sku_id)" → "dao.inventory.get(sku_id)"
                python_code.append(f"    {node.target} = dao.{node.entity}.get({node.params})")
            elif node.type == "call_action":
                # "call_action('calculate_price', {...})" → "registry.call('calculate_price', {...})"
                python_code.append(f"    {node.result_var} = registry.call('{node.action_id}', {node.params})")
            elif node.type == "if":
                python_code.append(f"    if {node.condition}:")
            elif node.type == "for":
                python_code.append(f"    for {node.var} in {node.iterable}:")
            elif node.type == "assignment":
                python_code.append(f"    {node.target} = {node.value}")
            elif node.type == "return":
                python_code.append(f"    return {node.value}")
        
        return "\n".join(python_code)
```

**Logic → BPMN 的生成策略**：

```python
class LogicAssetGenerator:
    """将 Logic 知识文档转化为 BPMN 流程定义"""
    
    def generate(self, doc: KnowledgeDocument) -> BPMNProcess:
        assert doc.type == "logic"
        
        # 1. 构建流程节点（从伪代码中的步骤）
        nodes = []
        pseudo_ast = parse_pseudocode(doc.get_section("execution_logic"))
        
        for i, node in enumerate(pseudo_ast):
            if node.type == "function_def":
                # 起点
                nodes.append(StartEvent(id="start", name="开始"))
            elif node.type == "assert":
                # 前置条件检查 → 排他网关（通过/拒绝）
                nodes.append(ExclusiveGateway(
                    id=f"gateway_{i}",
                    name=node.condition,
                    conditions={
                        "true": SequenceFlow(to=f"step_{i+1}"),
                        "false": SequenceFlow(to="end_rejected", condition="条件不满足")
                    }
                ))
            elif node.type == "call_action":
                # 子调用 → Service Task
                nodes.append(ServiceTask(
                    id=f"task_{node.action_id}",
                    name=f"调用: {node.action_id}",
                    skill_asset=node.action_id,
                    input_mapping=node.params,
                    output_mapping=node.result_var
                ))
            elif node.type == "if":
                # 条件分支 → 排他网关
                nodes.append(ExclusiveGateway(
                    id=f"gateway_{i}",
                    name=node.condition,
                    conditions=self.parse_branch_conditions(node)
                ))
            elif node.type == "for":
                # 循环 → 循环子流程或递归调用
                # 策略：简单的 for 循环 → 多实例任务
                # 复杂的循环 → 子流程
                nodes.append(MultiInstanceTask(
                    id=f"loop_{i}",
                    name=f"循环: {node.iterable}",
                    collection=node.iterable,
                    element_var=node.var,
                    inner_task=self.build_inner_task(node.body)
                ))
            elif node.type == "return":
                # 终点
                nodes.append(EndEvent(id="end", name="完成"))
        
        # 2. 组装流程定义
        return BPMNProcess(
            id=doc.id,
            name=doc.yaml_fm["name"],
            nodes=nodes,
            start_node="start",
            knowledge_source=file_path
        )
```

#### 5.3.3 契约提取器（Contract Extractor）

```python
class ContractExtractor:
    """从知识文档中提取形式化契约"""
    
    def extract(self, doc: KnowledgeDocument) -> ContractSet:
        contracts = ContractSet()
        
        # 1. 从 YAML FM 提取契约（最结构化）
        if "inputs" in doc.yaml_fm:
            for input_def in doc.yaml_fm["inputs"]:
                contracts.inputs.append(InputContract(
                    name=input_def["name"],
                    type=input_def["type"],
                    required=input_def.get("required", True),
                    constraints=input_def.get("constraints", {}),
                    schema=input_def.get("schema")
                ))
        
        # 2. 从伪代码中的 assert 提取前置条件
        pseudo_ast = parse_pseudocode(doc.get_section("execution_logic"))
        for node in pseudo_ast:
            if node.type == "assert":
                contracts.preconditions.append(Precondition(
                    expression=node.condition,
                    message=node.message,
                    source="pseudocode_assert"
                ))
        
        # 3. 从前置条件区提取（自然语言 → 形式化）
        precondition_section = doc.get_section_by_title("前置条件")
        if precondition_section:
            for line in precondition_section.content.split("\n"):
                # "1. 库存.可用数量 >= 订单.商品数量" → "inventory.available >= order.quantity"
                formal = self.natural_language_to_formal(line)
                if formal:
                    contracts.preconditions.append(Precondition(
                        expression=formal,
                        message=line,
                        source="document_preconditions"
                    ))
        
        # 4. 从后置条件区提取
        postcondition_section = doc.get_section_by_title("后置条件")
        if postcondition_section:
            for line in postcondition_section.content.split("\n"):
                formal = self.natural_language_to_formal(line)
                if formal:
                    contracts.postconditions.append(Postcondition(
                        expression=formal,
                        message=line
                    ))
        
        # 5. 从回滚规则提取
        rollback_section = doc.get_section_by_title("回滚规则")
        if rollback_section:
            contracts.rollback = RollbackRule(
                description=rollback_section.content,
                # 尝试提取具体的回滚操作
                operations=self.extract_rollback_operations(rollback_section)
            )
        
        # 6. 从边界条件提取测试场景
        boundary_section = doc.get_section_by_title("边界条件")
        if boundary_section:
            contracts.boundary_scenarios = self.parse_boundary_table(boundary_section)
        
        return contracts
    
    def natural_language_to_formal(self, text: str) -> Optional[str]:
        """
        将自然语言约束转化为形式化表达式。
        示例：
        "库存.可用数量 >= 订单.商品数量" → "inventory.available >= order.quantity"
        "状态必须为「待决策」" → "status == '待决策'"
        """
        # 使用 LLM + 规则混合策略
        # 先用规则匹配常见模式，再用 LLM 处理复杂情况
        patterns = [
            (r"(.+?)必须(.+?)", lambda m: f"{m.group(1)} == {m.group(2)}"),
            (r"(.+?)>=\s*(.+)", lambda m: f"{m.group(1)} >= {m.group(2)}"),
            (r"(.+?)<=\s*(.+)", lambda m: f"{m.group(1)} <= {m.group(2)}"),
        ]
        for pattern, transformer in patterns:
            match = re.search(pattern, text)
            if match:
                return transformer(match)
        
        # 复杂情况 fallback 到 LLM
        return llm_transform_to_formal(text)
```

### 5.4 KEA 与运行时 Agent 的关系

| 维度 | 知识萃取 Agent (KEA) | 运行时 Agent (Orchestrator) |
|------|---------------------|---------------------------|
| **运行时机** | 构建时（CI/CD 管道） | 运行时（用户请求时） |
| **输入** | 知识文档（Markdown） | 用户自然语言查询 |
| **输出** | OntologySkill / BPM / 测试用例 | 执行结果 |
| **是否调用 LLM** | 是（理解知识、生成代码） | 是（理解意图、匹配资产） |
| **是否产生副作用** | 否（只生成代码，不修改生产数据） | 是（调用 OntologySkill 执行） |
| **人类介入** | 必须（审核后才能注册） | 可选（长流程中的人工任务节点） |
| **失败处理** | 生成报告，阻塞注册 | 回滚或降级处理 |

---

## 6. 渐进式迁移路线图

### 阶段一：双轨运行（1-2 个月）

**目标**：新系统上线，旧系统作为兜底保留。

```
用户请求
    ↓
Orchestrator
    ├─ 尝试匹配 Registry 中的 OntologySkill（新路径）
    │   └─ 存在 → 沙箱执行 → 返回结果
    │
    └─ 不存在 → fallback 到 SKILL.md 机制（旧路径）
        └─ Agent 读 Markdown → 查询数据 → 执行 → 返回结果
```

**工作项**：
1. 选择 1-2 个高频操作（如「待删除物料的成本影响计算」），按新格式重写
2. 手工编写对应的 OntologySkill（不依赖 KEA，先验证 Runtime）
3. 部署 Registry 和 OntologySkill Runtime（最小可用版本）
4. 改造 Orchestrator，支持双路径 fallback

### 阶段二：KEA 上线（2-3 个月）

**目标**：KEA 自动化生成 OntologySkill，人工审核后注册。

**工作项**：
1. 开发文档解析器（YAML FM + 伪代码 + 状态机）
2. 开发资产生成器（Action→代码、Logic→BPMN）
3. 开发契约提取器和测试用例生成器
4. 开发评估层（沙箱执行 + 多 LLM 共识）
5. 开发人类审核门户
6. 将所有 50+ 对象、7 个操作按新格式重写
7. KEA 批量生成 OntologySkill，人工审核后注册

### 阶段三：旧系统退役（3-4 个月）

**目标**：所有路径都有 OntologySkill，SKILL.md 机制退役。

**工作项**：
1. 完备性检查（R1-R7）自动化运行
2. 监控 fallback 到 SKILL.md 的频率，逐步降为 0
3. 移除 SKILL.md 和 mindsdb_client.py 的 runtime 调用
4. mindsdb_client.py 转型为数据访问 OntologySkill 的底层实现

---

## 7. 关键风险与缓解策略

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| **KEA 生成代码质量不稳定** | 高 | 强制人类审核 + 评估层多维度验证 + 沙箱执行所有测试用例 |
| **伪代码到真实代码的语义丢失** | 高 | 多 LLM 共识验证（比较生成的代码与知识文档的语义一致性） |
| **业务专家不习惯写伪代码** | 中 | 提供伪代码模板 + AI 辅助生成（从自然语言草稿生成伪代码初版） |
| **迁移期间两套系统并存维护成本高** | 中 | 限制阶段一的范围（只迁移 2-3 个高频操作），快速验证后全面推广 |
| **运行时 fallback 到旧路径导致结果不一致** | 高 | 增加 A/B 对比日志，当新旧路径结果不一致时告警，人工介入分析 |
| **对象关系复杂导致 KEA 理解错误** | 中 | 从简单对象开始（无状态机、无复杂关系），逐步增加复杂度 |

---

## 8. 结论与建议

### 8.1 对「能否重用现有实现」的回答

**不能直接沿用，但可以渐进式重用业务语义资产。**

- **SKILL.md 的运行时解释执行机制**：必须废弃。运行时 Agent 重新理解文档的模式在复杂场景下确定性不足，无法通过自动测试验证。
- **50+ 对象定义和 7 个操作流程的业务语义**：完整保留。这是最有价值的资产，只需要改变表达格式（增加 YAML FM、伪代码、状态机）。
- **mindsdb_client.py 的自然语言→SQL 能力**：可重用。封装为数据访问层组件，供 OntologySkill 内部调用。
- **目录结构和 workspaces 分层思想**：保留并扩展。

### 8.2 对「如何做好知识萃取 Agent」的回答

**知识萃取 Agent 不是运行时 Agent 的增强版，而是一个独立的构建时组件。**

它的核心设计原则：

1. **输入是结构化知识，不是自然语言**：KEA 读取的是 Agent-Native Markdown（有 YAML FM、伪代码、状态机），不是自由格式的文本。这保证了 KEA 可以可靠地解析，而不是依赖 LLM 的"理解"。

2. **输出是确定性资产，不是动态计划**：KEA 生成的是可编译、可测试、可签名的代码/流程定义，不是每次运行时重新生成的执行计划。

3. **人类在关键环节必须介入**：KEA 可以自动化 80% 的工作（生成代码、生成测试用例、执行评估），但最终的 Registry 注册必须经过人类审核。这是质量的最后防线。

4. **评估层是 KEA 的"编译器"**：就像传统编程语言的编译器会检查语法、类型、引用，KEA 的评估层检查契约覆盖、语义一致性、沙箱执行、安全合规。

### 8.3 下一步行动建议

1. **本周**：评审本文档，确认双轨运行策略和迁移路线图
2. **下周**：选择 1 个 Action（如「待删除物料的成本影响计算」）和 1 个 Object（如「ECO变更单」），按新格式手工重写，验证端到端流程
3. **第 3-4 周**：基于验证经验，开发 KEA 的 MVP（文档解析器 + 简单的资产生成器 + 沙箱执行）
4. **第 5-8 周**：KEA 批量处理现有文档，人类审核，Registry 注册，双轨运行
5. **第 9-12 周**：完备性检查自动化，逐步退役旧路径

---

> **附：当前 SKILL.md 内容在新架构中的归宿**
>
> | SKILL.md 中的内容 | 新架构中的位置 | 转化方式 |
> |------------------|--------------|---------|
> | 四步执行流程 | Orchestrator 的默认策略 | 编码为 Orchestrator 的配置 |
> | operations 目录清单和描述 | 各 logic/action 文档的 YAML FM `agent_context` | 分解到每份文档 |
> | 操作文件调用关系 | logic 文档的 `relations`（`calls:`） | 结构化提取 |
> | 应用层次（战略→策略→执行） | Logic 文档的 `relations`（`composed_of:`） | 结构化提取 |
> | 单表/合并/原子化查询规则 | 数据访问 OntologySkill 的约束规范 | 编码为查询 OntologySkill 的前置条件 |
> | mindsdb_client.py 使用方法 | 数据访问层组件的内部实现 | 封装为 DAO 组件 |
> | 数据验证规范 | 各 Action 的前置条件 + 后置条件 | 从 prose 中提取形式化断言 |
> | 异常处理规范 | Orchestrator 的 fallback 策略 | 编码为运行时配置 |
