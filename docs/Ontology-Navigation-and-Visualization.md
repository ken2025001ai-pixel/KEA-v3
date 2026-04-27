# Ontology Navigation & Visualization Design

> **Version**: 1.0  
> **Date**: 2026-04-24  
> **Status**: Implemented  
> **Scope**: KEA Ontology human review & navigation experience

---

## 1. Problem Statement

When Ontology knowledge is split across dozens or hundreds of Markdown files in `ontology/objects/`, `ontology/logic/`, `ontology/actions/`, humans face three cognitive efficiency bottlenecks:

| Bottleneck | Symptom | Impact |
|-----------|---------|--------|
| **Type invisibility** | In Obsidian Graph View, Object/Logic/Action nodes look identical | Cannot distinguish node types at a glance |
| **Relation semantics missing** | `[[订单]]` could mean "input object" or "output object" — the link carries no type | Cannot understand the nature of associations |
| **Impact untraceable** | Changing `订单.md` affects unknown downstream Logic/Action docs | Review misses dependencies, causing inconsistencies |

This document describes the four-layer progressive enhancement that solves these problems.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HUMAN REVIEW LAYER                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Obsidian     │  │ Breadcrumbs  │  │ Agent-Generated Indices  │  │
│  │ Graph View   │  │ Matrix/Tree  │  │ (README.md, Dataview)    │  │
│  │ + CSS Groups │  │ + Typed Links│  │ + Mermaid Graphs         │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                       │                │
│         └─────────────────┼───────────────────────┘                │
│                           ▼                                        │
│              ┌────────────────────────┐                            │
│              │    OntologyIndexer     │                            │
│              │  (kea/indexer/)        │                            │
│              │  - Scan directory      │                            │
│              │  - Parse YAML FM       │                            │
│              │  - Extract wikilinks   │                            │
│              │  - Build graph         │                            │
│              │  - Generate Mermaid    │                            │
│              └───────────┬────────────┘                            │
│                          │                                         │
│              ┌───────────▼────────────┐                            │
│              │   KnowledgeDocument      │                            │
│              │   - doc_type             │                            │
│              │   - domain, status, tags │                            │
│              │   - relations[]          │  ← Single Source of Truth │
│              └──────────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      KNOWLEDGE EXTRACTION LAYER                      │
│  LLM Agents (extract-objects-agent, extract-logic-agent, ...)       │
│  → Auto-populate YAML front matter + relations[] during extraction  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Four-Layer Enhancement

### Layer 1 — YAML Front Matter Standardization

Every ontology document MUST include standardized YAML front matter:

```yaml
---
type: logic                 # object | logic | action | rule
domain: 订单管理             # Business domain
status: validated           # draft | validated | approved
version: "1.0"
tags: [kea-logic]           # kea-object | kea-logic | kea-action | kea-domain
aliases: [创建销售订单]
---
```

**Why**: This is the data layer that powers all downstream visualization and querying.

**Implementation**:
- Templates updated: `object-template.md`, `logic-template.md`, `action-template.md`
- Parser extended: `YAMLFMParser` now extracts `domain`, `status`, `tags`
- Model extended: `KnowledgeDocument` carries these fields

---

### Layer 2 — Obsidian Graph View Color Coding (Zero Plugins)

Obsidian's native Graph View supports **Groups** — filter by tag and assign colors.

**Setup**:

1. Enable CSS snippet: `.obsidian/snippets/kea-graph-colors.css`
2. Open Graph View → Groups panel → Add groups (in priority order):
   | Group Rule | Color | Meaning |
   |-----------|-------|---------|
   | `tag:#kea-domain` | Purple 🟣 | Business domain |
   | `tag:#kea-object` | Red 🔴 | Business object |
   | `tag:#kea-logic` | Blue 🔵 | Business logic/process |
   | `tag:#kea-action` | Green 🟢 | Business action |

3. Result: Graph View immediately shows typed nodes by color

**Limitation**: Graph View shows connections but cannot label edge types. Layer 3 solves this.

---

### Layer 3 — Breadcrumbs Typed Links (Recommended Plugin)

**Breadcrumbs** is an Obsidian community plugin that adds typed links to notes.

**How it complements the architecture**:

| Source | Data | Consumer |
|--------|------|----------|
| YAML `relations` | Machine-structured | Indexer, Validator, Codegen |
| Inline fields `uses:: [[A]]` | Human-augmented | Breadcrumbs Matrix View |
| Wikilinks `[[A]]` | Natural writing | Obsidian Backlinks |

**Breadcrumbs Edge Field Mapping**:

| Position | Field | KEA Semantic |
|----------|-------|-------------|
| ↑ Up | `part_of` | Belongs to domain |
| ↓ Down | `contains` | Contains sub-items |
| ← Same | `related` | Related objects/logic |
| → Next | `follows` | Next process |
| ← Prev | `precedes` | Previous process |

**Matrix View example** for `创建订单.md`:

```
           ↑ part_of
      [[订单管理域]]

← precedes          follows →
  [[审批订单]]        [[支付流程]]

Same: uses → [[用户]], [[库存]]
Same: produces → [[订单]]
Same: calls → [[扣减库存]]
```

**Important**: Breadcrumbs is a **reading enhancement**, not a dependency. KEA's core pipeline works without it.

---

### Layer 4 — Agent-Generated Indices & Impact Analysis

#### 4A — `ontology-index` Command

The Agent command `/ontology-index` runs the Python indexer:

```bash
python -m kea index ontology/ --format json
```

And auto-generates:

| Generated File | Content |
|---------------|---------|
| `ontology/README.md` | Global Mermaid graph + Dataview tables + domain stats |
| `ontology/index-objects.md` | Dataview query table of all objects |
| `ontology/index-logic.md` | Dataview query table of all logic |
| `ontology/index-actions.md` | Dataview query table of all actions |
| `ontology/diagrams/{domain}-graph.mermaid` | Per-domain relationship graphs |

#### 4B — `ontology-impact` Command

The Agent command `/ontology-impact <doc>` analyzes change scope:

```bash
python -m kea impact 订单.md --base-dir ontology/ --format json
```

Output includes:
- **Incoming**: Documents that reference the target
- **Outgoing**: Documents the target references
- **Transitive**: Second-level affected documents
- **Summary**: Total affected count with severity recommendation

---

## 4. Relationship Data: Single Source of Truth

### The `relations` Field

```yaml
---
type: logic
domain: 订单管理
relations:
  - {target: "用户", type: "uses", description: "输入数据"}
  - {target: "订单", type: "produces", description: "输出数据"}
  - {target: "扣减库存", type: "calls", description: "触发动作"}
  - {target: "支付流程", type: "precedes", description: "前置流程"}
---
```

### Relation Type Reference

| Type | Source Type | Target Type | Semantic |
|------|------------|-------------|----------|
| `uses` | logic/action | object | Uses as input |
| `produces` | logic/action | object | Produces as output |
| `supports` | logic | object | Supporting data |
| `calls` | logic | action | Directly invokes |
| `triggers` | logic | action | Async trigger |
| `precedes` | logic | logic | Comes before |
| `follows` | logic | logic | Comes after |
| `part_of` | object/logic/action | domain | Belongs to domain |
| `contains` | domain/object | object/logic | Contains |
| `belongs_to` | object | object | Ownership |
| `has` | object | object | Has property |
| `references` | object | object | Refers to |
| `modifies` | action | object | Modifies state |

### Priority Rule (Indexer)

When building the relationship graph, the Indexer follows this priority:

1. **L1: YAML `relations`** — Structured, typed, Agent-generated (highest priority)
2. **L2: Inline fields** — `uses:: [[A]]` (optional human augmentation)
3. **L3: Wikilinks** — `[[A]]` in body (fallback, type = "link")

If L1 covers a `(source, target)` pair, L2/L3 for that pair are skipped.

---

## 5. OntologyIndexer Implementation

### Module: `kea/indexer/ontology_indexer.py`

```python
class OntologyIndexer:
    def scan() -> None
        """Scan ontology/objects/, ontology/logic/, ontology/actions/
        Parse YAML front matter, extract wikilinks & inline fields"""

    def build_graph() -> None
        """Build doc-to-doc relationship graph from L1→L2→L3 sources"""

    def generate_mermaid_graph(scope="global") -> str
        """Generate Mermaid diagram code with subgraphs per domain"""

    def generate_dataview_index() -> str
        """Generate Markdown with Dataview queries and Mermaid embeds"""

    def analyze_impact(target: str) -> ImpactReport
        """Analyze change scope: incoming, outgoing, transitive"""
```

### CLI Integration

```bash
# Build index
python -m kea index ontology/ --format json

# Impact analysis
python -m kea impact 订单.md --base-dir ontology/ --format json

# Human-readable output (omit --format json)
python -m kea index ontology/
python -m kea impact 订单.md --base-dir ontology/
```

---

## 6. Complete Workflow

### Knowledge Extraction Phase

The extraction pipeline is **input-agnostic**. It accepts multiple input sources:

```
Input Source (any of the following):
  ├── Flowchart summaries  (ontology/diagrams-summary/*.md)
  ├── Research reports     (research/*.md)
  ├── Requirement docs     (user-provided PRD/spec)
  └── User description     (interactive or $ARGUMENTS)
              │
              ▼
      /ontology-extract
              │
              ├──→ Phase 1: Objects
              ├──→ Phase 2: Logic
              └──→ Phase 3: Action
                          │
                          ▼
              Auto-populates YAML front matter + relations[]
              Writes ontology/{objects,logic,actions}/*.md
```

**When to use flowcharts** (recommended but not required):
- ✅ Complex business processes with many decision branches
- ✅ Team collaboration needs a visual review checkpoint
- ✅ Starting from rough business descriptions
- ❌ Detailed PRD/spec already exists
- ❌ Simple domain with straightforward processes
- ❌ Quick prototyping

### Validation Phase

```
/ontology-validate
  → Phase A: python -m kea validate ontology/ --format json
  → Phase B: LLM semantic check

/ontology-trace 创建订单
  → python -m kea trace ontology/logic/创建订单.md --format json
```

### Navigation Phase (this document)

```
/ontology-index
  → python -m kea index ontology/ --format json
  → generates ontology/README.md, index-*.md, diagrams/*-graph.mermaid

/ontology-impact 订单.md
  → python -m kea impact 订单.md --base-dir ontology/ --format json
  → displays affected documents with severity recommendation
```

### Code Generation Phase

```
/ontology-codegen
  → python -m kea codegen ontology/ --output codegen/ --format json
```

---

## 7. File Reference

| File | Purpose |
|------|---------|
| `.claude/templates/object-template.md` | Object doc template with YAML FM + relations |
| `.claude/templates/logic-template.md` | Logic doc template with YAML FM + relations |
| `.claude/templates/action-template.md` | Action doc template with YAML FM + relations |
| `.claude/templates/breadcrumbs-config.md` | Breadcrumbs plugin setup guide |
| `.claude/skills/kea/SKILL.md` | Claude Skill manifest with full command reference |
| `.obsidian/snippets/kea-graph-colors.css` | Graph View color coding CSS |
| `.obsidian/community-plugins.json` | Recommended plugin list |
| `kea/kea/indexer/ontology_indexer.py` | Core indexer implementation |
| `kea/kea/cli.py` | CLI entry with `index` and `impact` commands |
| `kea/tests/test_indexer.py` | Indexer unit tests |

---

## 8. Dependencies

| Component | Required? | Purpose |
|-----------|-----------|---------|
| Obsidian (any version) | **Yes** | Knowledge base host |
| `obsidian-mermaid-links` | Recommended | Mermaid → Live Editor jump |
| Dataview | Recommended | Dynamic index tables |
| Breadcrumbs | Optional | Typed link visualization |
| Python 3.11+ | **Yes** | CLI tool layer |

---

## 9. Migration Guide (from pre-visualization KEA)

If you have existing ontology docs without YAML front matter:

1. Run `/ontology-index` — Indexer will infer relationships from wikilinks
2. The generated `ontology/README.md` will show isolated docs (no links)
3. Optionally: Ask Agent to batch-add YAML front matter to existing docs
4. Going forward: New docs use templates with full YAML FM + relations

---

## 10. Cross-Platform Agent Support

KEA is designed as an **Agent Platform Skill**, not a standalone Agent. The LLM orchestration layer (Claude Code, OpenClaw, etc.) handles reasoning and dialogue; the Python layer (`kea/`) handles deterministic operations. This separation enables cross-platform portability.

### 10.1 Supported Platforms

| Platform | Integration Type | Status | Installation |
|----------|-----------------|--------|-------------|
| **Claude Code** | Native Skill (`.claude/skills/kea/`) | ✅ Active | Built-in |
| **OpenClaw** | Skill + Plugin (`install/openclaw/`) | ✅ Packaged | `claw install kea` or side-load |
| **Other Claw-compatible** | `SKILL.md` standard | ✅ Compatible | Copy `skill.md` + wrapper |

### 10.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT PLATFORM                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Claude Code  │  │   OpenClaw   │  │  Future Platforms │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                   │            │
│         └─────────────────┼───────────────────┘            │
│                           │                                │
│                    ┌──────▼───────┐                        │
│                    │ SKILL.md     │  ← Manifest + Instructions │
│                    │ claw.json    │  ← Tool registration (OpenClaw)│
│                    └──────┬───────┘                        │
│                           │ subprocess                     │
│                    ┌──────▼───────┐                        │
│                    │ kea-wrapper  │  ← Node.js / Python bridge │
│                    └──────┬───────┘                        │
│                           │ python3 -m kea <cmd> --format json │
│                    ┌──────▼───────┐                        │
│                    │   KEA Core   │  ← Zero-dependency Python   │
│                    │   (kea/)     │  ← Parser / Indexer / CLI   │
│                    └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 10.3 Installation Methods

#### A. Claude Code (Built-in)
Already included in `.claude/skills/kea/`. Just type `/kea` or `ontology-index` in Claude Code.

#### B. OpenClaw (Three Tiers)

**Tier 1 — ClawHub Registry (Recommended)**
```bash
# Public registry install
claw install kea

# Or specific version
claw install kea@3.0.0
```

**Tier 2 — Private Registry (Enterprise)**
```bash
# Configure private registry
claw registry add https://registry.your-company.com
claw install kea --registry private
```

**Tier 3 — Side-load (Development)**
```bash
# Clone and side-load
git clone https://github.com/your-org/kea.git
cd kea
claw install ./openclaw/
```

#### C. Manual Installation (Any Platform)
```bash
# 1. Copy skill manifest
cp install/openclaw/skill.md ./SKILL.md

# 2. Ensure Python 3.11+ is available
python3 --version

# 3. Verify KEA CLI works
python3 -m kea --help
```

### 10.4 Permission Manifest

OpenClaw requires explicit permissions. KEA declares minimal access:

```yaml
# openclaw/SKILL.md
permissions:
  filesystem:
    read:
      - ./ontology/        # Read ontology documents
      - ./.claude/         # Read agent definitions
    write:
      - ./ontology/        # Write generated ontology docs
      - ./.obsidian/       # Obsidian snippets & plugins
```

### 10.5 Tool Registration (`claw.json`)

OpenClaw auto-discovers tools via `claw.json`:

| Tool Name | Command | Purpose |
|-----------|---------|---------|
| `kea_parse` | `python3 -m kea parse` | Parse single document |
| `kea_validate` | `python3 -m kea validate` | Validate ontology consistency |
| `kea_trace` | `python3 -m kea trace` | Trace relationship chains |
| `kea_codegen` | `python3 -m kea codegen` | Generate code artifacts |
| `kea_index` | `python3 -m kea index` | Build ontology index |
| `kea_impact` | `python3 -m kea impact` | Analyze change impact |

### 10.6 Distribution Checklist

When releasing a new KEA version, verify:

- [ ] `install/openclaw/skill.md` — version matches `kea/__init__.py`
- [ ] `install/openclaw/claw.json` — tool list matches CLI commands
- [ ] `install/openclaw/kea-wrapper.js` — handles all CLI exit codes
- [ ] `install/openclaw/README.md` — installation instructions up-to-date
- [ ] `install/openclaw/INSTALL.md` — troubleshooting section current
- [ ] All 42 tests pass: `python3 -m pytest kea/tests/`
- [ ] Zero external dependency rule maintained

---

## 11. File Inventory

| File | Platform | Purpose |
|------|----------|---------|
| `.claude/skills/kea/SKILL.md` | Claude Code | Native skill manifest |
| `.claude/agents/extract-*-agent.md` | Claude Code | Agent definitions |
| `.claude/commands/ontology-*.md` | Claude Code | Slash commands |
| `openclaw/SKILL.md` | OpenClaw | Skill manifest with permissions |
| `openclaw/package.json` | OpenClaw | npm package manifest |
| `openclaw/install.sh` | OpenClaw | Bash install script |
| `openclaw/scripts/install.js` | OpenClaw | Node.js postinstall script |
| `openclaw/README.md` | OpenClaw | User-facing install guide |

---

*End of Document*
