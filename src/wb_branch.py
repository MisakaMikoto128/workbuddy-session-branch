#!/usr/bin/env python3
"""WorkBuddy 会话分支工具。

功能：把某个本地会话从指定消息处复制成一条新会话，旧会话保持不变。
注意：执行前必须完全退出 WorkBuddy；脚本会先备份数据库再写入。
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
import uuid
from pathlib import Path

WB = Path(os.path.expanduser("~")) / ".workbuddy-ai"
DB = WB / "workbuddy.db"
PROJ = WB / "projects"

KEEP_META = {"session-meta", "ai-title"}


def now_ms():
    return int(time.time() * 1000)


def find_jsonl(session_id):
    hits = list(PROJ.glob(f"*/{session_id}.jsonl"))
    if not hits:
        raise SystemExit(f"找不到会话文件: {session_id}.jsonl（在 {PROJ} 下）")
    return hits[0]


def load(path):
    recs = []
    for i, line in enumerate(path.open(encoding="utf-8")):
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"跳过损坏行 {i+1}", file=sys.stderr)
    return recs


def messages(recs):
    return [r for r in recs if r.get("type") == "message"]


def preview(rec):
    c = rec.get("content")
    if isinstance(c, list):
        for it in c:
            if isinstance(it, dict) and it.get("text"):
                return it["text"].replace("\n", " ")[:70]
    return str(c)[:70]


def list_sessions():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id,title,custom_title,status,cwd,updated_at from sessions "
        "where deleted_at is null order by updated_at desc"
    ).fetchall()
    for r in rows:
        name = r["custom_title"] or r["title"] or "(无标题)"
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime((r["updated_at"] or 0) / 1000))
        print(f"{r['id']}  [{r['status']}] {ts}  {name}")
        print(f"    {r['cwd']}")


def list_messages(session_id):
    recs = load(find_jsonl(session_id))
    ms = messages(recs)
    print(f"会话 {session_id} 共 {len(ms)} 条消息：")
    for i, m in enumerate(ms):
        print(f"[{i:3}] {m.get('role','?'):9} id={m.get('id')}")
        print(f"         parent={m.get('parentId')}  ::  {preview(m)}")


def build_branch(recs, at_id):
    """保留 at 消息及其全部祖先；保留分支路径上的工具记录与产物快照。"""
    by_id = {r.get("id"): r for r in recs if r.get("id")}
    ms = messages(recs)

    target = None
    if at_id:
        for m in ms:
            if m.get("id", "").startswith(at_id) or at_id in preview(m):
                target = m
                break
        if not target:
            raise SystemExit(f"找不到分支点消息: {at_id}")

    # 祖先消息集合
    keep_ids = set()
    if target:
        cur = target
        while cur:
            keep_ids.add(cur.get("id"))
            pid = cur.get("parentId")
            cur = by_id.get(pid) if pid else None

    # 工具记录：parentId 落在保留集合内（或其父链最终落入）即保留
    out = []
    for r in recs:
        t = r.get("type")
        if t in KEEP_META:
            out.append(r)
            continue
        if t == "message":
            if not target or r.get("id") in keep_ids:
                out.append(r)
            continue
        if t == "file-history-snapshot":
            if not target or r.get("messageId") in keep_ids:
                out.append(r)
            continue
        # reasoning / function_call / function_call_result
        if not target:
            out.append(r)
            continue
        pid = r.get("parentId")
        seen = set()
        while pid and pid not in seen:
            if pid in keep_ids:
                out.append(r)
                break
            seen.add(pid)
            parent = by_id.get(pid)
            pid = parent.get("parentId") if parent else None
    return out


def branch(session_id, at_id, title, dry_run):
    src_path = find_jsonl(session_id)
    recs = load(src_path)
    kept = build_branch(recs, at_id)
    new_id = str(uuid.uuid4())

    print(f"源会话   : {session_id}")
    print(f"源文件   : {src_path}")
    print(f"分支点   : {at_id or '(整会话复制)'}")
    print(f"消息数   : {len(messages(recs))} -> {len(messages(kept))}")
    print(f"记录数   : {len(recs)} -> {len(kept)}")
    print(f"新会话ID : {new_id}")

    if dry_run:
        print("\n[DRY-RUN] 未写入任何数据。")
        return

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    src = con.execute("select * from sessions where id=?", (session_id,)).fetchone()
    if not src:
        raise SystemExit("源会话不在 sessions 表中")

    # 备份数据库（含 WAL 一致性）
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = WB / f"workbuddy.db.bak-branch-{stamp}"
    bk = sqlite3.connect(str(backup))
    con.backup(bk)
    bk.close()
    print(f"数据库备份: {backup}")

    cols = [d[1] for d in con.execute("PRAGMA table_info(sessions)")]
    row = dict(zip(cols, tuple(src)))
    row["id"] = new_id
    row["title"] = title
    row["custom_title"] = title
    row["created_at"] = now_ms()
    row["updated_at"] = now_ms()
    row["last_activity_at"] = now_ms()
    row["status"] = "completed"
    row["deleted_at"] = None
    row["unread"] = 0
    row["agent_dirty"] = 0
    row["buddy_snapshot_id"] = None
    con.execute(
        f"insert into sessions ({','.join(cols)}) values ({','.join('?' * len(cols))})",
        [row[c] for c in cols],
    )

    usage = con.execute(
        "select used,size,credit_json from session_usage where session_id=?",
        (session_id,),
    ).fetchone()
    if usage:
        con.execute(
            "insert or replace into session_usage(session_id,used,size,updated_at,credit_json) "
            "values (?,?,?,?,?)",
            (new_id, usage["used"], usage["size"], now_ms(), usage["credit_json"]),
        )

    dst_path = src_path.with_name(f"{new_id}.jsonl")
    with dst_path.open("w", encoding="utf-8", newline="\n") as f:
        for r in kept:
            r["sessionId"] = new_id
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    con.commit()
    con.close()
    print(f"新会话文件: {dst_path}")
    print("完成。重新启动 WorkBuddy，侧边栏会出现新任务。")


def main():
    p = argparse.ArgumentParser(description="WorkBuddy 会话分支工具")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="列出所有会话")
    g.add_argument("--msgs", metavar="SESSION", help="列出某会话的消息及 ID")
    g.add_argument("--branch", metavar="SESSION", help="要分支的源会话 ID")
    p.add_argument("--at", help="分支点消息 ID 前缀或内容关键词；不填=整会话复制")
    p.add_argument("--title", default="(分支)", help="新会话标题")
    p.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    a = p.parse_args()

    if a.list:
        list_sessions()
    elif a.msgs:
        list_messages(a.msgs)
    else:
        branch(a.branch, a.at, a.title, a.dry_run)


if __name__ == "__main__":
    main()
