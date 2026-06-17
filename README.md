# codex-memory

<div align="center">

![Codex Memory](https://img.shields.io/badge/Codex-Memory-purple?style=for-the-badge&logo= brain&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-FTS5-brightgreen?style=for-the-badge&logo=sqlite&logoColor=white)

**Give Codex a memory it never forgets.**

Teach Codex your preferences once. It remembers them forever — across every new session, project, and conversation.

</div>

---

## The Problem

Every Codex session starts from scratch. You re-explain the same preferences. You repeat the same context. You re-make decisions you already made last week.

After 10 sessions, you've said the same things 10 times.

---

## The Solution

`codex-memory` gives Codex persistent, queryable long-term memory — without any external services or dependencies.

```
Session 1:  "记住我喜欢把输出文件放在 outputs/ 目录"
            ✅ Saved to SQLite

Session 2:  "把结果写到文件里"
            ✅ Codex recalls: outputs/ 目录
            ✅ Done

Session 10: No reminders needed.
```

---

## How It Works

| Memory Type | What it stores | Example |
|---|---|---|
| **Semantic** | Facts, preferences, relations | "用户偏好 Python 路径为 /usr/bin/python3" |
| **Episodic** | Events, decisions, conversations | "2026-06-17 决定采用 SQLite 存储方案" |
| **Procedural** | Workflows, patterns, conventions | "所有交付物放在 outputs/ 子目录" |

Each entry has a **confidence score** (user says = 1.0, auto-extracted = 0.7) and a **90-day time decay**, so recent and important memories rank highest.

---

## Features

- **BM25 full-text search** — Find the right memory instantly, ranked by relevance
- **Three memory layers** — Semantic, episodic, procedural — each with different semantics
- **Scope isolation** — Global memories + per-project memories, never confused
- **Self-improving loop** — After corrections, Codex asks: "记住这个吗？" — you confirm, it saves
- **Session handoff** — Generate a resume document at the end of a session for the next one
- **JSON export** — Full backup and portability, one command
- **Zero dependencies** — SQLite is built into macOS. Nothing to install except this skill.

---

## Install

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo 1761004122a-ops/codex-memory --path codex-memory
```

Then **restart Codex**. That's it.

---

## Usage

> Say **"记住"** or **"remember this"** and Codex saves it.

```
You: "记住我的项目都放在 ~/Documents/Codex/ 下"
Codex: "已记住：项目根目录 → ~/Documents/Codex/"
       [saved to semantic memory, confidence: 1.0]
```

> Say **"之前怎么做的"** or **"what did we decide before"** and Codex recalls it.

```
You: "上次我们是怎么处理 GitHub 代理的？"
Codex: "用户显式开启代理后，GitHub API 连通；关闭后超时。"
       [confidence: 95% | scope: global | 2026-06-17]
```

> At session end, Codex offers a **handoff summary**:

```
You: "差不多了，保存进度"
Codex: "需要我将本次 session 的关键工作写入记忆系统吗？"
You: "好"
Codex: [generates episodic entry + handoff markdown]
```

---

## Command Reference

```bash
TOOL=~/.codex/skills/codex-memory/scripts/memory_tool.py

python3 $TOOL init       # Initialize SQLite DB
python3 $TOOL save       # Save a memory
python3 $TOOL search     # BM25 full-text search
python3 $TOOL list       # List memories
python3 $TOOL retire     # Mark as obsolete (soft delete)
python3 $TOOL stats      # View memory stats
python3 $TOOL dump       # Export all as JSON
python3 $TOOL handoff    # Generate session resume document
```

---

## Architecture

```
~/.codex/
├── memory/
│   └── memory.db          ← SQLite + FTS5 (72KB for 5 memories)
└── skills/codex-memory/
    ├── SKILL.md           ← Codex triggers & instructions
    ├── scripts/
    │   └── memory_tool.py ← 427 lines, stdlib only
    └── agents/
        └── openai.yaml   ← UI metadata

Database schema:
  learnings   — Memory entries
  learn_fts   — FTS5 BM25 index
  sessions    — Session analytics
```

---

## Design Reference

Built on the SQLite + FTS5 memory pattern pioneered by [Pro Workflow](https://github.com/rohitg00/pro-workflow) (MIT, 2316★), adapted for Codex's skill architecture.

---

## Contributing

Issues and pull requests welcome. The skill format follows the [openai/skills](https://github.com/openai/skills) standard.

---

## License

MIT — free to use, modify, and distribute.
