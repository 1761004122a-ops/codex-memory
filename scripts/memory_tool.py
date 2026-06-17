#!/usr/bin/env python3
"""
codex-memory v2.0 — SQLite + FTS5 (BM25 排名) 长期记忆系统
参考 Pro Workflow (MIT, 2316★) 的设计思路。

Schema：
  learnings   — 记忆主体（INTEGER id = rowid，TEXT uuid = UUID）
  learn_fts   — FTS5 全文索引（row_id → learnings.id）
  sessions    — Session 分析
"""

import argparse, json, math, os, re, sqlite3, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

# ─── 路径 ─────────────────────────────────────────────────
CODEX_HOME  = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
SKILL_DIR   = Path(__file__).parent.parent
DB_PATH     = CODEX_HOME / "memory" / "memory.db"
MEMORY_DIR  = CODEX_HOME / "memory"

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+08:00")

def _conn() -> sqlite3.Connection:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _dict(row: sqlite3.Row) -> dict:
    return dict(row)

# ─── Schema ────────────────────────────────────────────────
def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS learnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('semantic','episodic','procedural')),
            scope TEXT NOT NULL DEFAULT 'global',
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 1.0,
            category TEXT NOT NULL DEFAULT 'general',
            tags TEXT NOT NULL DEFAULT '[]',
            derived_from TEXT NOT NULL DEFAULT 'explicit',
            status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','superseded','retracted')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            retired_at TEXT,
            retire_reason TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS learn_fts USING fts5(
            row_id UNINDEXED,
            uuid,
            type,
            scope,
            subject,
            predicate,
            object,
            body,
            category,
            tags,
            tokenize='porter unicode61'
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            correction_count INTEGER NOT NULL DEFAULT 0,
            edit_count INTEGER NOT NULL DEFAULT 0,
            prompts_count INTEGER NOT NULL DEFAULT 0,
            summary TEXT NOT NULL DEFAULT '',
            key_decisions TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TRIGGER IF NOT EXISTS fts_ins AFTER INSERT ON learnings BEGIN
            INSERT INTO learn_fts(row_id, uuid, type, scope, subject, predicate, object, body, category, tags)
            VALUES (new.id, new.uuid, new.type, new.scope, new.subject,
                    new.predicate, new.object, new.body, new.category, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS fts_del AFTER DELETE ON learnings BEGIN
            DELETE FROM learn_fts WHERE row_id = old.id;
        END;

        CREATE TRIGGER IF NOT EXISTS fts_upd AFTER UPDATE ON learnings BEGIN
            UPDATE learn_fts SET
                uuid=new.uuid, type=new.type, scope=new.scope,
                subject=new.subject, predicate=new.predicate, object=new.object,
                body=new.body, category=new.category, tags=new.tags
            WHERE row_id = old.id;
        END;
    """)
    for col, tbl in [('uuid','learnings'),('scope','learnings'),('status','learnings'),
                      ('type','learnings'),('created_at','learnings')]:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_{col} ON {tbl}({col})")
        except sqlite3.OperationalError:
            pass
    conn.commit()


# ─── Init ──────────────────────────────────────────────────
def cmd_init(args) -> None:
    conn = _conn()
    _init_schema(conn)
    conn.close()
    print(f"✅ Initialized: {DB_PATH}")
    print("   Schema: learnings (INTEGER PK) + learn_fts (FTS5/BM25) + sessions")


# ─── Save ──────────────────────────────────────────────────
def cmd_save(conn: sqlite3.Connection, args) -> None:
    eid = str(uuid.uuid4())
    now = _now()

    # 如果传入 JSON 数据包，直接解析
    if args.json_data:
        d = json.loads(args.json_data)
        etype  = d.get('type', args.type or 'semantic')
        scope  = d.get('scope', args.scope or 'global')
        subj   = d.get('subject', args.subject or '')
        pred   = d.get('predicate', args.predicate or '')
        obj    = d.get('object', args.object or '')
        body   = d.get('body', args.body or '')
        conf   = d.get('confidence', args.confidence or 1.0)
        cat    = d.get('category', args.category or 'general')
        tags   = d.get('tags', args.tags or [])
        deriv  = d.get('derived_from', args.derived_from or 'explicit')
    else:
        etype  = args.type
        scope  = args.scope or 'global'
        subj   = args.subject
        pred   = args.predicate
        obj    = args.object
        body   = args.body or ''
        conf   = args.confidence or 1.0
        cat    = args.category or 'general'
        tags   = args.tags or []
        deriv  = args.derived_from or 'explicit'

    tags_json = json.dumps(tags, ensure_ascii=False)

    conn.execute("""
        INSERT INTO learnings
            (uuid, type, scope, subject, predicate, object, body,
             confidence, category, tags, derived_from, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
    """, (eid, etype, scope, subj, pred, obj, body,
          conf, cat, tags_json, deriv, now, now))
    conn.commit()
    print(f"SAVED {eid}")
    print(f"TYPE {etype} | SCOPE {scope} | SUBJECT {subj[:40]}")


# ─── Search (BM25 via FTS5) ─────────────────────────────────
def cmd_search(conn: sqlite3.Connection, args) -> None:
    query  = args.query
    limit  = args.limit or 5
    scope  = getattr(args, 'scope', None) or ''
    etype  = getattr(args, 'type', None) or ''
    now_ts = datetime.now(timezone.utc).timestamp()

    # 过滤条件
    cond, params = ["l.status = 'active'"], []
    if scope:
        if ':' in scope:
            cond.append("l.scope = ?"); params.append(scope)
        else:
            cond.append("l.scope = ?"); params.append(scope)
    if etype:
        cond.append("l.type = ?"); params.append(etype)
    where = " AND ".join(cond)

    # FTS5 BM25 检索：join on row_id
    sql = f"""
        SELECT
            l.uuid, l.type, l.scope, l.subject, l.predicate, l.object,
            l.body, l.confidence, l.category, l.tags,
            l.created_at, l.updated_at,
            bm25(learn_fts) AS rank,
            snippet(learn_fts, 3, '[', ']', '…', 40) AS snippet
        FROM learn_fts
        JOIN learnings l ON l.id = learn_fts.row_id
        WHERE learn_fts MATCH ?
          AND {where}
        ORDER BY rank
        LIMIT ?
    """
    try:
        cur = conn.execute(sql, [query, *params, limit])
    except sqlite3.OperationalError:
        # FTS5 语法错误，退回 LIKE
        like_q = f"%{query}%"
        cur = conn.execute(
            f"SELECT uuid, type, scope, subject, predicate, object, body, "
            f"       confidence, category, tags, created_at, updated_at, "
            f"       0.0 AS rank, '' AS snippet "
            f"FROM learnings WHERE status='active' "
            f"  AND (subject LIKE ? OR predicate LIKE ? OR object LIKE ? OR tags LIKE ?) "
            f"ORDER BY updated_at DESC LIMIT ?",
            [like_q, like_q, like_q, like_q, limit]
        )

    rows = cur.fetchall()
    if not rows:
        print("NO_RESULTS")
        return

    print(f"RESULTS {len(rows)} (BM25, 负值=更相关)\n")
    for r in rows:
        tags = json.loads(r['tags'])
        days = (now_ts - datetime.fromisoformat(r['created_at']).timestamp()) / 86400
        decay = math.exp(-days / 90)
        score = abs(r['rank'] or 0) * r['confidence'] * decay

        print(f"UUID     : {r['uuid']}")
        print(f"Type     : {r['type']} | Scope: {r['scope']} | Category: {r['category']}")
        print(f"Subject  : {r['subject']}")
        print(f"         {r['predicate']} → {r['object']}")
        print(f"Confidence: {r['confidence']:.0%} | Age: {days:.0f}d | Score: {score:.3f}")
        if r['snippet']: print(f"Snippet  : {r['snippet']}")
        print()


# ─── List ──────────────────────────────────────────────────
def cmd_list(conn: sqlite3.Connection, args) -> None:
    cond, params = ["status = 'active'"], []
    if args.scope: cond.append("scope = ?"); params.append(args.scope)
    if args.type:  cond.append("type = ?");  params.append(args.type)
    if args.tag:
        cond.append("tags LIKE ?"); params.append(f"%{args.tag}%")

    sql = f"""SELECT uuid, type, scope, subject, category, confidence, tags, created_at
              FROM learnings WHERE {' AND '.join(cond)}
              ORDER BY created_at DESC LIMIT ?"""
    params.append(args.limit or 20)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("(no entries)"); return

    print(f"{'UUID':8} | {'TYPE':9} | {'SCOPE':25} | {'SUBJECT':22} | {'CAT':10} | CONF | DATE")
    print("-" * 110)
    for r in rows:
        print(f"{r['uuid'][:8]} | {r['type']:9} | {r['scope']:25} | "
              f"{r['subject'][:22]:22} | {r['category']:10} | "
              f"{r['confidence']:.0%} | {r['created_at'][:10]}")


# ─── Get ────────────────────────────────────────────────────
def cmd_get(conn: sqlite3.Connection, args) -> None:
    r = conn.execute("SELECT * FROM learnings WHERE uuid = ?", (args.id,)).fetchone()
    if not r:
        print(f"ERROR: {args.id} not found", file=sys.stderr); sys.exit(1)
    d = dict(r)
    d['tags'] = json.loads(d['tags'])
    print(json.dumps(d, ensure_ascii=False, indent=2))


# ─── Retire ────────────────────────────────────────────────
def cmd_retire(conn: sqlite3.Connection, args) -> None:
    now = _now()
    n = conn.execute(
        "UPDATE learnings SET status='retracted', retired_at=?, retire_reason=?, updated_at=? WHERE uuid=?",
        (now, args.reason, now, args.id)
    ).rowcount
    conn.commit()
    if n == 0:
        print(f"ERROR: {args.id} not found", file=sys.stderr); sys.exit(1)
    print(f"RETIRED {args.id}")


# ─── Stats ─────────────────────────────────────────────────
def cmd_stats(conn: sqlite3.Connection, args) -> None:
    def count(sql, p=()):
        return conn.execute(sql, p).fetchone()[0]
    total   = count("SELECT COUNT(*) FROM learnings")
    active  = count("SELECT COUNT(*) FROM learnings WHERE status='active'")
    recent  = count("SELECT COUNT(*) FROM learnings WHERE status='active' AND created_at > datetime('now','-7 days')")
    by_type = dict(conn.execute("SELECT type, COUNT(*) FROM learnings WHERE status='active' GROUP BY type").fetchall())
    by_scope= dict(conn.execute("SELECT scope, COUNT(*) FROM learnings WHERE status='active' GROUP BY scope").fetchall())
    by_cat  = dict(conn.execute("SELECT category, COUNT(*) FROM learnings WHERE status='active' GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10").fetchall())

    print(f"Total entries : {total}")
    print(f"Active       : {active}")
    print(f"Last 7 days  : {recent} new entries")
    print(f"By type      : {by_type}")
    print(f"By scope     : {by_scope}")
    print(f"Top categories: {by_cat}")
    print(f"DB path      : {DB_PATH}")


# ─── Dump ───────────────────────────────────────────────────
def cmd_dump(conn: sqlite3.Connection, args) -> None:
    learnings = [_dict(r) for r in conn.execute(
        "SELECT * FROM learnings ORDER BY created_at")]
    for l in learnings:
        l['tags'] = json.loads(l['tags'])
    print(json.dumps({"version":"1.0","exported_at":_now(),"learnings":learnings},
                      ensure_ascii=False, indent=2))


# ─── Handoff ────────────────────────────────────────────────
def cmd_handoff(conn: sqlite3.Connection, args) -> None:
    now = _now()
    scope = args.scope or 'global'

    rows = conn.execute("""
        SELECT uuid, type, scope, subject, predicate, object, category, tags, confidence, updated_at
        FROM learnings
        WHERE status='active' AND scope IN ('global', ?)
        ORDER BY updated_at DESC LIMIT 30
    """, (scope,)).fetchall()

    decisions = [r for r in rows if r['category'] in ('decision','preference','architecture')]
    prefs     = [r for r in rows if r['type']=='semantic' and r not in decisions]
    procs     = [r for r in rows if r['type']=='procedural']
    epis      = [r for r in rows if r['type']=='episodic']

    print(f"# Session Handoff — {now[:10]} {now[11:19]}")
    print(f"\n## 记忆库概览")
    print(f"- 范围: **{scope}** | 总计: {len(rows)} 条")
    print(f"- 技术决策: {len(decisions)} | 偏好: {len(prefs)} | 流程: {len(procs)} | 事件: {len(epis)}")

    if decisions:
        print(f"\n## 技术决策")
        for r in decisions:
            print(f"- **{r['subject']}**: {r['predicate']} → {r['object']}")
            print(f"  Confidence: {r['confidence']:.0%} | {r['updated_at'][:10]}")

    if prefs:
        print(f"\n## 用户偏好")
        for r in prefs[:8]:
            print(f"- [{r['category']}] {r['subject']}: {r['predicate']}")
            print(f"  {r['object'][:80]}")

    if procs:
        print(f"\n## 工作流约定")
        for r in procs[:5]:
            print(f"- **{r['subject']}**: {r['predicate']}")
            print(f"  {r['object'][:80]}")

    if epis:
        print(f"\n## 重要事件")
        for r in epis[:3]:
            print(f"- [{r['updated_at'][:10]}] {r['subject']}: {r['object'][:80]}")

    print(f"\n## 快速恢复命令")
    print(f"```bash")
    print(f"python3 memory_tool.py list --scope {scope}")
    print(f"python3 memory_tool.py search \"关键词\"")
    print(f"python3 memory_tool.py handoff --scope {scope}")
    print(f"```")


# ─── CLI ────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="codex-memory v2.0 — SQLite+FTS5")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化数据库")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("save", help="写入记忆")
    p.add_argument("--type",  choices=["episodic","semantic","procedural"])
    p.add_argument("--scope", default="global")
    p.add_argument("--subject")
    p.add_argument("--predicate")
    p.add_argument("--object")
    p.add_argument("--body",   default="")
    p.add_argument("--confidence", type=float, default=1.0)
    p.add_argument("--category",   default="general")
    p.add_argument("--tags",   nargs="*", default=[])
    p.add_argument("--derived-from", dest="derived_from", default="explicit")
    p.add_argument("--json",  dest="json_data", default=None)
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("search", help="BM25 全文检索")
    p.add_argument("query")
    p.add_argument("--scope")
    p.add_argument("--type",  choices=["episodic","semantic","procedural"])
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("list", help="列出记忆")
    p.add_argument("--scope")
    p.add_argument("--type",  choices=["episodic","semantic","procedural"])
    p.add_argument("--tag")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("get", help="获取单条")
    p.add_argument("id")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("retire", help="标记废弃")
    p.add_argument("id"); p.add_argument("--reason", default="用户主动废弃")
    p.set_defaults(func=cmd_retire)

    p = sub.add_parser("stats",  help="统计"); p.set_defaults(func=cmd_stats)
    p = sub.add_parser("dump",   help="导出 JSON"); p.set_defaults(func=cmd_dump)

    p = sub.add_parser("handoff", help="生成交接文档")
    p.add_argument("--scope", default="global"); p.set_defaults(func=cmd_handoff)

    args = parser.parse_args()

    if args.cmd in ("save","search","list","get","retire","stats","dump","handoff"):
        conn = _conn()
        try:    args.func(conn, args)
        finally: conn.close()
    else:
        args.func(args)

if __name__ == "__main__":
    main()
