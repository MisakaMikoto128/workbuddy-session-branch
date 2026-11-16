# 会话分支管理器

WorkBuddy 本地会话的分叉工具。**从对话中间任意一条消息复制出一条独立新会话，原会话完整保留。**

WorkBuddy 的对话在底层是一棵以 `parentId` 串联的消息树，但界面只沿当前叶子回溯显示一条链，没有暴露 Branch 按钮。内置的消息悬停「回退 / 编辑 / 刷新」会覆盖当前视图，旧分支切不回来。这个工具直接操作本地数据，把某条消息之前的上下文复制成一个全新的会话，两条线在侧边栏并存、可随时切换。

## 功能

- 三步流程：选择会话 → 设定分支点 → 确认创建，进度始终可见
- 会话列表支持搜索与状态筛选，消息时间线支持按角色过滤
- 选定分支点时即时显示「将保留 N 条」，无需等待预览
- 创建前自动备份 `workbuddy.db`，写入失败自动回滚
- 工具调用、推理、产物快照随分支点一并保留或截断
- 明暗主题、键盘操作（`/` 搜索、`Ctrl+Enter` 创建、`Esc` 关闭）、完整空/加载/错误态
- 两种运行方式：PyWebView 桌面窗口，或浏览器直连（便于自动化测试）

## 安装与运行

需要 Python 3.10+。

```bash
pip install -r requirements.txt
python src/app.py
```

Windows 用户可直接双击根目录的 `启动界面.bat`（需先按其中说明配置 Python 路径，或使用打包版 exe）。

## 浏览器模式 / 测试

PyWebView 在桌面端通过 `chrome.webview.postMessage` 桥接 API，浏览器里没有该对象。项目提供 `serve.py`，复用同一个 `Api` 后端，用标准库 HTTP 暴露接口，并在返回页面时注入兼容 shim——前端代码零改动，浏览器/Playwright 打到的就是真实后端。

```bash
python src/serve.py --port 8777
# 浏览器打开 http://127.0.0.1:8777/
```

另一个终端跑回归测试：

```bash
python tests/test_ui.py
```

## Windows 自动编译

`.github/workflows/build-windows.yml` 在推送 tag（如 `v1.0.0`）或手动触发时，用 PyInstaller 在 `windows-latest` 上打包单文件 exe，上传为 Actions artifact，并附着到对应 Release。

```bash
git tag v1.0.0
git push origin v1.0.0
```

本地打包：

```bash
pyinstaller build.spec
# 产物在 dist/会话分支管理器.exe
```

## 项目结构

```
src/
  wb_branch.py   核心分支逻辑（逆向 WorkBuddy 存储结构）
  app.py         PyWebView 后端 API
  serve.py       浏览器直连测试服务
  web/index.html 前端界面（设计 token + 三步流程）
tests/
  test_ui.py     真实后端回归测试
scripts/         打包辅助
.impeccable.md   设计上下文与设计原则
```

## 数据存储说明

工具只读取并复制本机 WorkBuddy 的数据，不联网、不上传：

- 元数据：`~/.workbuddy-ai/workbuddy.db` → `sessions` 表
- 消息体：`~/.workbuddy-ai/projects/<项目>/<sessionId>.jsonl`

**执行前请完全退出 WorkBuddy**，避免写入时与桌面端缓存冲突；创建完成后重启即可看到新会话。

## License

MIT — 详见 [LICENSE](LICENSE)。
