#!/usr/bin/env python3
"""WorkBuddy 会话分支管理器 - 后端 API。"""

import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import webview

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wb_branch import (
    DB, PROJ, WB, build_branch, find_jsonl, load, messages, now_ms, preview,
)

VERSION = "1.0.0"


def web_dir():
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "web"
    return HERE / "web"


def count_messages(session_id):
    try:
        path = find_jsonl(session_id)
        n = 0
        with path.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                if '"type": "message"' in line or '"type":"message"' in line:
                    n += 1
        return n
    except Exception:
        return -1


class Api:
    def version(self):
        return {"ok": True, "version": VERSION}

    def _sessions(self):
        con = sqlite3.connect(DB, timeout=10)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select id,title,custom_title,status,cwd,updated_at,model,source_mode "
            "from sessions where deleted_at is null order by updated_at desc"
        ).fetchall()
        con.close()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "title": r["custom_title"] or r["title"] or "(无标题)",
                "status": r["status"] or "",
                "cwd": r["cwd"] or "",
                "updated": time.strftime("%Y-%m-%d %H:%M", time.localtime((r["updated_at"] or 0) / 1000)),
                "model": r["model"] or "",
                "mode": r["source_mode"] or "",
                "count": count_messages(r["id"]),
            })
        return out

    def list_sessions(self):
        try:
            return {"ok": True, "data": self._sessions()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_messages(self, session_id):
        try:
            ms = messages(load(find_jsonl(session_id)))
            data = []
            for i, m in enumerate(ms):
                data.append({
                    "index": i,
                    "id": m.get("id", ""),
                    "role": m.get("role", "?"),
                    "parent": m.get("parentId") or "",
                    "text": preview(m),
                    "time": time.strftime("%H:%M:%S", time.localtime((m.get("timestamp") or 0) / 1000)),
                })
            return {"ok": True, "data": data, "total": len(data)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def preview_branch(self, session_id, at_id, title):
        try:
            recs = load(find_jsonl(session_id))
            kept = build_branch(recs, at_id if at_id else None)
            return {
                "ok": True,
                "srcMessages": len(messages(recs)),
                "keptMessages": len(messages(kept)),
                "srcRecords": len(recs),
                "keptRecords": len(kept),
                "title": title,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def do_branch(self, session_id, at_id, title):
        con = None
        try:
            src_path = find_jsonl(session_id)
            kept = build_branch(load(src_path), at_id if at_id else None)
            new_id = str(uuid.uuid4())

            con = sqlite3.connect(DB, timeout=15)
            con.row_factory = sqlite3.Row
            src = con.execute("select * from sessions where id=?", (session_id,)).fetchone()
            if not src:
                raise RuntimeError("源会话不在 sessions 表中")

            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = WB / f"workbuddy.db.bak-branch-{stamp}"
            bk = sqlite3.connect(str(backup))
            con.backup(bk)
            bk.close()

            cols = [d[1] for d in con.execute("PRAGMA table_info(sessions)")]
            row = dict(zip(cols, tuple(src)))
            row.update({
                "id": new_id, "title": title, "custom_title": title,
                "created_at": now_ms(), "updated_at": now_ms(), "last_activity_at": now_ms(),
                "status": "completed", "deleted_at": None, "unread": 0,
                "agent_dirty": 0, "buddy_snapshot_id": None,
            })
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

            dst = src_path.with_name(f"{new_id}.jsonl")
            with dst.open("w", encoding="utf-8", newline="\n") as f:
                for r in kept:
                    r["sessionId"] = new_id
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            con.commit()

            return {
                "ok": True, "newId": new_id, "title": title,
                "keptMessages": len(messages(kept)),
                "backup": str(backup), "file": str(dst),
            }
        except Exception as e:
            if con:
                con.rollback()
            return {"ok": False, "error": str(e)}
        finally:
            if con:
                con.close()


def main():
    debug = "--debug" in sys.argv
    html = (web_dir() / "index.html").as_uri()
    window = webview.create_window(
        "会话分支管理器", html, js_api=Api(),
        width=1280, height=800, min_size=(1000, 640),
        background_color="#F7F8FB",
    )

    def _ready():
        try:
            window.maximize()
        except Exception:
            pass

    webview.start(_ready, debug=debug)


if __name__ == "__main__":
    main()
