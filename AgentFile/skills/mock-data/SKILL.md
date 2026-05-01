<SUBAGENT-STOP>
本文件作为 subagent 执行。若你是主 session Claude，请通过 Agent 工具 Dispatch 本 skill，而非直接读取执行。
</SUBAGENT-STOP>

You are a mock data generation agent. Your job is to generate realistic test data for all business objects.

## Inputs (provided in the task prompt)

- `OBJECTS_DIR`: path to object docs. Default: `{VAULT_PATH}/30-Ontology/objects/` — read `{KEA_TOOLS_ROOT}/config.md` to resolve `VAULT_PATH`.
- `MOCK_DIR`: target directory. Default: `{VAULT_PATH}/30-Ontology/data-mock/`
- `OBJECT_NAMES` (optional): comma-separated object names to generate (if omitted, generate all)
- `EXISTING_FILES` (optional): comma-separated filenames to skip

## Step 1: Read object definitions

For each `.md` file in OBJECTS_DIR (or only those matching OBJECT_NAMES if provided):

1. **Skip if in EXISTING_FILES.**
2. Read the file and extract:
   - Attribute table (columns: 中文名称, 英文名称, 描述, 主键, 类型)
   - Primary key attributes
   - 关联对象 section — foreign key relationships

## Step 2: Determine generation order

Build a dependency graph: if Object A references Object B via 关联对象 or 对象引用 type, B must be generated first so A can reference valid IDs.

Sort objects topologically (independent objects first). If circular dependencies exist, break the cycle and note it.

## Step 3: Generate mock data

For each object (in dependency order), write `MOCK_DIR/{对象名称}.md`:

Before writing, read `{KEA_TOOLS_ROOT}/templates/mock-data-template.md` and follow its format exactly.

```markdown
# {对象名称} 测试数据

## 正常数据

| {属性1} | {属性2} | {属性3} | ... |
| ------- | ------- | ------- | --- |
| {值}    | {值}    | {值}    | ... |
...

## 边界数据

| {属性1} | {属性2} | {属性3} | ... |
| ------- | ------- | ------- | --- |
| {值}    | {值}    | {值}    | ... |
...

## 异常数据

| {属性1} | {属性2} | {属性3} | ... |
| ------- | ------- | ------- | --- |
| {值}    | {值}    | {值}    | ... |
...
```

**Output format requirements (must follow exactly):**
- The file structure must match `{KEA_TOOLS_ROOT}/templates/mock-data-template.md`
- Title must be exactly `# {对象名称} 测试数据`
- Use Chinese column headers matching the object's `中文名称`

**Data generation rules:**
- **正常数据**: 5-10 rows covering main business scenarios. Values must be realistic and domain-appropriate.
- **边界数据**: 3-5 rows covering edge cases (empty strings, zero values, max-length strings, enum boundary values, null-like states).
- **异常数据**: 3-5 rows covering error conditions (invalid types, missing required fields, constraint violations, out-of-range values).
- **Cross-object consistency**: If attribute X in Object A is a foreign key referencing Object B's primary key, then the values of X in A's mock data MUST exist in B's mock data.
- **Primary key uniqueness**: Primary key values must be unique across all rows within the same object.
- Use Chinese column headers matching the 中文名称 from the attribute table.

## Step 4: Return summary

```
生成完成。

新增测试数据（{M} 个）：
| 对象 | 正常数据 | 边界数据 | 异常数据 |
|------|---------|---------|---------|
| {name} | {N} 行 | {N} 行 | {N} 行 |
...

跳过（已存在，{N} 个）：
- {名称}.md
...

注意事项：
- {any circular dependencies, assumptions, or objects with insufficient attribute definitions}
```
