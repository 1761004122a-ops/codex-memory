---
name: codex-memory
description: |
  跨 Session 长期记忆系统。保存用户偏好、技术决策、工作流约定，并在新 Session 启动时自动注入相关记忆。
  触发时机：
  - 用户说"记住"、"记住这个"、"save this"、"add to rules"
  - 用户说"之前怎么做"、"回忆一下"、"what do I know about"
  - 技术选型、方案确认后（自动提取决策）
  - Session 结束时（生成交接文档）
  - 新项目启动时（自动加载项目记忆）
  - 用户说"忘掉"、"过时了"、"retire"
---

# Codex Memory — 长期记忆系统

> 参考设计：Pro Workflow（MIT, 2316★）自纠正记忆 + SQLite FTS5 BM25 检索

## 系统架构

```
Session 启动 ──→ 加载相关记忆 ──→ 注入 Context
用户对话  ──→ Save / Search / Retire
Session 结束 ──→ 决策提取 ──→ 写入 SQLite
                          ──→ Handoff 文档
```

## 存储

- **数据库**：`~/.codex/memory/memory.db`（SQLite + FTS5，macOS 内置无需依赖）
- **Schema**：`learnings`（记忆主体）+ `learn_fts`（BM25 全文索引）+ `sessions`（会话分析）

## 三层记忆分类

| 类型 | 内容 | Category 示例 |
|---|---|---|
| `semantic` | 原子事实、偏好、关系 | preference, tooling, decision |
| `episodic` | 事件、对话、决策历史 | event, conversation, milestone |
| `procedural` | 工作流、模式、约定 | convention, workflow, pattern |

## 核心操作

### Save — 写入记忆

```bash
python3 ~/.codex/skills/codex-memory/scripts/memory_tool.py save \
  --type semantic \
  --scope global \
  --subject "Codex 网络行为" \
  --predicate "使用代理访问 GitHub" \
  --object "用户显式开启代理后连通" \
  --confidence 0.95 \
  --category preference \
  --tags network github proxy
```

### Search — BM25 全文检索

```bash
python3 ~/.codex/skills/codex-memory/scripts/memory_tool.py search "GitHub 代理"
python3 ~/.codex/skills/codex-memory/scripts/memory_tool.py search "输出" --scope global
```

**评分算法**：`BM25(全文匹配) × confidence × exp(-age/90天)`

### List — 列出记忆

```bash
# 全局偏好
memory_tool.py list --scope global --type semantic

# 当前项目
memory_tool.py list --scope project:my-project
```

### Retire — 遗忘（不物理删除）

```bash
memory_tool.py retire <uuid> --reason "已过时"
```

### Handoff — Session 交接文档

```bash
memory_tool.py handoff --scope project:my-project
```

## 决策提取（参考 Pro Workflow learn-rule）

**触发条件** → 提议话术：

| 场景 | 话术 |
|---|---|
| 用户确认了一个方案 | "需要记住这个技术选型吗？" |
| 用户放弃某个方向 | "要记录'不采用 X'这个决策吗？" |
| 用户提供偏好信息 | （直接记忆，不询问） |
| 长对话（>10 轮）结束 | "需要我总结本次 session 到记忆系统吗？" |

**格式**：

```
[LEARN] Category: 一句话规则
Mistake : （可选）之前错的
Correction: 正确的做法
```

## Session 生命周期集成

```
启动时（自动）：
  1. 读取工作目录名称 → 确定 project scope
  2. search --scope project:<name> --limit 8
  3. search --scope global --limit 5
  4. 注入到 Context 前

对话中：
  - 响应 "记住 XXX" → save
  - 响应 "之前怎么做" → search
  - 重要决策节点 → 主动提取

结束时：
  - 询问是否生成 handoff
  - 如同意：提取 episodic 条目 + handoff 文档
```

## 字段说明

| 字段 | 说明 |
|---|---|
| `type` | semantic / episodic / procedural |
| `scope` | global / project:<name> / thread:<id> |
| `subject` | 记忆主体（名词） |
| `predicate` | 关系或动作（动词） |
| `object` | 值或结果 |
| `confidence` | 0.0–1.0，用户显式告知=1.0，自动提取=0.7 |
| `category` | 细分类型（decision/preference/tooling/convention/event等） |
| `tags` | 关键词标签，用于过滤 |
| `derived_from` | explicit / auto-extract / episodic-extraction |

## 已知限制

- **中文全文检索**：FTS5 BM25 对中文支持依赖 LIKE 回退；英文词检索效果最佳
- **跨语言**：建议 tag 使用英文（如 `github` 而非 `GitHub`）以获得最佳检索质量
- **FTS5 BM25**：评分越负越相关（标准 BM25 约定）

## 备份与迁移

```bash
# 导出全部记忆为 JSON
memory_tool.py dump > memory_backup.json

# 数据库文件位置
~/.codex/memory/memory.db
```

## 工具完整命令列表

```
memory_tool.py init       初始化数据库
memory_tool.py save       写入记忆
memory_tool.py search     BM25 全文检索
memory_tool.py list       列出记忆
memory_tool.py get        获取单条（按 UUID）
memory_tool.py retire     标记废弃
memory_tool.py stats      统计摘要
memory_tool.py dump       导出 JSON
memory_tool.py handoff    生成交接文档
```
