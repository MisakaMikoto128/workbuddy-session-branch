#!/usr/bin/env python3
"""真实后端 API 回归测试。

前置：先在另一终端运行 `python src/serve.py --port 8777`。
也可通过环境变量 WB_TEST_BASE 指定地址。
"""

import json
import os
import sys
import urllib.request

BASE = os.environ.get("WB_TEST_BASE", "http://127.0.0.1:8777")


def api(name, *args):
    data = json.dumps({"args": list(args)}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/api/{name}", data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("  " + detail if detail else ""))
    return cond


def main():
    ok = True
    print(f"== 真实后端 API 测试 ({BASE}) ==")

    r = api("version")
    ok &= check("version 返回成功", r.get("ok") is True)

    r = api("list_sessions")
    ok &= check("list_sessions 返回成功", r.get("ok") is True)
    sessions = r.get("data", [])
    ok &= check("会话数 > 0", len(sessions) > 0, f"共 {len(sessions)} 条")
    if not sessions:
        return 1
    ok &= check("会话含消息数统计", "count" in sessions[0])

    target = sessions[0]["id"]
    r = api("list_messages", target)
    ok &= check("list_messages 返回成功", r.get("ok") is True)
    msgs = r.get("data", [])
    ok &= check("消息数 > 0", len(msgs) > 0, f"共 {len(msgs)} 条")
    if not msgs:
        return 1

    at = msgs[min(4, len(msgs) - 1)]["id"]
    r = api("preview_branch", target, at, "测试分支")
    ok &= check("preview_branch 返回成功", r.get("ok") is True)
    ok &= check("截断消息数正确", r.get("keptMessages") == min(4, len(msgs) - 1) + 1,
                f"{r.get('srcMessages')} -> {r.get('keptMessages')}")

    print()
    print("== 前端页面检查 ==")
    with urllib.request.urlopen(BASE + "/", timeout=10) as resp:
        html = resp.read().decode("utf-8")
    ok &= check("页面标题正确", "会话分支管理器" in html)
    ok &= check("pywebview shim 已注入", "window.pywebview = {api: api}" in html)
    ok &= check("三步流程存在", all(f"st{i}" in html for i in (1, 2, 3)))
    ok &= check("明暗主题支持", 'data-theme="light"' in html and 'data-theme="dark"' in html)

    print()
    print("全部通过" if ok else "存在失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
