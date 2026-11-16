#!/usr/bin/env python3
"""演示数据：全部虚构，用于截图与文档，不含任何真实会话信息。

do_branch 在演示模式下为纯内存操作，绝不写入本机 WorkBuddy 数据库。
"""

SESSIONS = [
    {"id": "demo-a1e2-3c4d-5e6f", "title": "电商后台订单模块重构", "status": "working",
     "cwd": "/work/demo-shop/admin", "updated": "2026-11-16 18:42", "model": "assistant-pro", "mode": "craft", "count": 86},
    {"id": "demo-b2f3-4d5e-6f70", "title": "季度销售数据可视化", "status": "working",
     "cwd": "/work/demo-analytics/reports", "updated": "2026-11-16 17:20", "model": "assistant-pro", "mode": "craft", "count": 54},
    {"id": "demo-c304-5e6f-7081", "title": "移动端登录页适配", "status": "completed",
     "cwd": "/work/demo-shop/mobile", "updated": "2026-11-15 21:08", "model": "assistant-lite", "mode": "craft", "count": 132},
    {"id": "demo-d415-6f70-8192", "title": "接口文档自动生成方案", "status": "completed",
     "cwd": "/work/demo-tools/docs", "updated": "2026-11-14 15:36", "model": "assistant-pro", "mode": "ask", "count": 47},
    {"id": "demo-e526-7081-92a3", "title": "缓存策略性能对比", "status": "completed",
     "cwd": "/work/demo-infra/benchmark", "updated": "2026-11-13 11:12", "model": "assistant-pro", "mode": "craft", "count": 95},
    {"id": "demo-f637-8192-a3b4", "title": "构建脚本排查", "status": "error",
     "cwd": "/work/demo-tools/ci", "updated": "2026-11-12 09:48", "model": "assistant-lite", "mode": "craft", "count": 28},
    {"id": "demo-g748-92a3-b4c5", "title": "组件库设计规范整理", "status": "completed",
     "cwd": "/work/demo-design/system", "updated": "2026-11-10 16:30", "model": "assistant-lite", "mode": "craft", "count": 73},
    {"id": "demo-h859-a3b4-c5d6", "title": "日志分析小工具", "status": "completed",
     "cwd": "/work/demo-tools/logger", "updated": "2026-11-08 13:55", "model": "assistant-pro", "mode": "craft", "count": 39},
]

USER_LINES = [
    "订单列表的分页加载有点慢，帮我看看瓶颈在哪",
    "把状态筛选和关键词搜索合并成一个查询条件",
    "导出功能需要支持选中行，不只是全部导出",
    "这里的权限校验应该放在服务端还是前端？",
    "把重复的表单校验逻辑抽成一个公共方法",
    "加一个空状态提示，数据为空时别显示空白页",
    "帮我写一下这个接口的单元测试用例",
    "移动端上这个弹窗被键盘挡住了，怎么修",
    "把列表的接口换成批量查询，减少请求次数",
    "这个组件的 props 太多了，能拆一下吗",
]

ASSISTANT_LINES = [
    "我先看了下当前的查询逻辑，瓶颈主要在没有给筛选字段建索引。建议先加联合索引，再把分页改成游标方式。",
    "可以。把两个条件合成一个查询对象，服务端用同一个 where 拼装，前端只传一个 params。",
    "明白，我给表格加上行选择，导出时读取选中行的 id 列表，再调用批量导出接口。",
    "服务端必须校验，前端校验只是体验优化。两边都做，但以服务端结果为准。",
    "已经抽成公共方法了，放在校验工具模块里，两个表单都改成引用它。",
    "加了空状态插图和引导文案，数据为空时显示，加载中显示骨架屏。",
    "测试用例覆盖了正常、边界和异常三种情况，边界值单独列了一组。",
    "弹窗改成从底部滑入并监听键盘事件，输入时自动上移，避免被遮挡。",
    "改成批量查询后单次请求能拿到整页数据，请求数从每行的 N 次降到 1 次。",
    "拆成了基础展示、数据加载和交互控制三个组件，props 数量减少了一半。",
]


def messages_for(session_id):
    """生成一组稳定的虚构消息，按用户/助手交替。"""
    seed = sum(ord(c) for c in session_id)
    n = 18 + seed % 9
    out = []
    for i in range(n):
        is_user = i % 2 == 0
        role = "user" if is_user else "assistant"
        text = (USER_LINES if is_user else ASSISTANT_LINES)[(i // 2 + seed) % 10]
        out.append({
            "index": i,
            "id": f"demo-msg-{session_id[5:9]}-{i:04d}",
            "role": role,
            "parent": "" if i == 0 else f"demo-msg-{session_id[5:9]}-{i-1:04d}",
            "text": text,
            "time": f"{14 + (i // 4) % 6:02d}:{(i * 7) % 60:02d}:{(i * 11) % 60:02d}",
        })
    return out


class DemoApi:
    """与真实 Api 接口一致，但全部返回演示数据，无任何副作用。"""

    def version(self):
        return {"ok": True, "version": "1.0.0-demo"}

    def list_sessions(self):
        return {"ok": True, "data": [dict(s) for s in SESSIONS]}

    def list_messages(self, session_id):
        ms = messages_for(session_id)
        return {"ok": True, "data": ms, "total": len(ms)}

    def preview_branch(self, session_id, at_id, title):
        ms = messages_for(session_id)
        idx = next((i for i, m in enumerate(ms) if m["id"] == at_id), -1)
        kept = idx + 1 if idx >= 0 else len(ms)
        return {
            "ok": True,
            "srcMessages": len(ms),
            "keptMessages": kept,
            "srcRecords": len(ms) * 11 + 37,
            "keptRecords": kept * 11 + 37,
            "title": title,
        }

    def do_branch(self, session_id, at_id, title):
        ms = messages_for(session_id)
        idx = next((i for i, m in enumerate(ms) if m["id"] == at_id), -1)
        kept = idx + 1 if idx >= 0 else len(ms)
        return {
            "ok": True,
            "newId": "demo-9f8e-7d6c-5b4a-3210",
            "title": title,
            "keptMessages": kept,
            "backup": "/demo/backup/workbuddy.db.bak-branch-20261116-200000",
            "file": "/demo/projects/demo-9f8e-7d6c-5b4a-3210.jsonl",
        }
