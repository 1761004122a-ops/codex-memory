# codex-memory

> Cross-session long-term memory for Codex. SQLite + FTS5 BM25, zero dependencies.

**Store user preferences, technical decisions, and workflow conventions across sessions.**  
Memory is auto-loaded on session start, searchable with BM25 ranking, and exportable as JSON.

---

## Features

- **SQLite + FTS5 BM25** — fast full-text search, built into macOS (no dependencies)
- **Three memory layers** — semantic (facts), episodic (events), procedural (patterns)
- **Scope isolation** — global, project-level, or thread-level memories
- **Confidence scoring** — explicit facts = 1.0, auto-extracted = 0.7
- **Time decay** — 90-day half-life, older memories rank lower
- **Session handoff** — generate resume documents for the next session
- **JSON export** — backup and portability
- **MIT licensed** — publish to GitHub, let others install it

---

## Install

```bash
# Via Codex skill-installer (once published to GitHub):
# python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
#   --repo <your-username>/codex-memory --path codex-memory

# Or manually:
git clone https://github.com/<your-username>/codex-memory.git \
  ~/.codex/skills/codex-memory
```

Then **restart Codex**.

---

## Quick Start

```bash
TOOL=~/.codex/skills/codex-memory/scripts/memory_tool.py

# Initialize
python3 $TOOL init

# Save a fact
python3 $TOOL save --type semantic --scope global \
  --subject "Default Python" --predicate "Uses Python at" \
  --object "/usr/bin/python3" --confidence 0.9 \
  --category tooling --tags python macos

# Search
python3 $TOOL search "python"
# → Returns ranked results with BM25 scores

# Session handoff
python3 $TOOL handoff --scope project:my-project
```

---

## Schema

```sql
learnings     -- Memory entries (INTEGER PK = rowid, TEXT uuid = UUID)
learn_fts     -- FTS5 full-text index (BM25 ranking)
sessions      -- Session analytics
```

---

## Design Reference

Inspired by [Pro Workflow](https://github.com/rohitg00/pro-workflow) (MIT, 2316★),
which introduced the SQLite + FTS5 self-correction memory pattern for AI coding agents.

---

## License

MIT — see [LICENSE.txt](LICENSE.txt)
