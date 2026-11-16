# 会话分支管理器

WorkBuddy 本地会话的分叉工具。**从对话中间任意一条消息复制出一条独立新会话，原会话完整保留。**

> **Rust + Tauri 构建** · Windows x64 单文件 exe 仅 ~4 MB · 原生性能 · 全本地处理
> [下载最新版](https://github.com/MisakaMikoto128/workbuddy-session-branch/releases/latest) · [在线主页](https://misakamikoto128.github.io/workbuddy-session-branch/)

WorkBuddy 的对话在底层是一棵以 `parentId` 串联的消息树，但界面只沿当前叶子回溯显示一条链，没有暴露 Branch 按钮。内置的消息悬停「回退 / 编辑 / 刷新」会覆盖当前视图，旧分支切不回来。这个工具直接操作本地数据，把某条消息之前的上下文复制成一个全新的会话，两条线在侧边栏并存、可随时切换。

<p align="center">
  <img src="docs/screenshots/01-overview.png" alt="界面总览" width="860">
</p>
<p align="center"><sub>三步式流程：选择会话 → 设定分支点 → 确认创建，进度始终可见</sub></p>

## 为什么需要它

做长任务时，经常聊到一半想换一个方向试——但 WorkBuddy 没有 Branch 按钮，内置回退会把当前对话改掉，旧路走不回来。这个工具给你真正的选择：**保留已走的路，同时从任意节点开一条新路。**

- 原会话一字不改，新会话带着分支点之前的完整上下文
- 工具调用、推理过程、产物快照随分支点一起保留
- 写库前自动备份 `workbuddy.db`，失败自动回滚

## 三步完成分叉

### 1 · 选择会话

会话列表带状态徽章（进行中 / 已完成 / 异常）和消息条数，支持关键词搜索和状态筛选。选中后右侧加载完整消息时间线。

<p align="center">
  <img src="docs/screenshots/02-session-selected.png" alt="选择会话" width="860">
</p>

### 2 · 设定分支点

在时间线上点任意一条消息，即刻设为分支点：该行高亮并打上标记，底部**当场显示「保留 N 条」**，不用等预览就知道结果。新标题自动从该消息内容生成，可直接改。

<p align="center">
  <img src="docs/screenshots/03-fork-point.png" alt="设定分支点" width="860">
</p>

### 3 · 预览并确认

创建前弹出对照：原会话多少条、新会话保留多少条、记录数变化、最终标题。确认后才真正写入。

<p align="center">
  <img src="docs/screenshots/04-preview.png" alt="分支预览" width="720">
</p>

创建完成后重启 WorkBuddy，新会话就出现在侧边栏，可以和原会话随时切换。

## 更多界面

<details>
<summary><b>明暗主题</b> — 浅色默认，一键切换深色</summary>

<p align="center">
  <img src="docs/screenshots/05-dark-theme.png" alt="深色主题" width="860">
</p>
</details>

<details>
<summary><b>搜索与筛选</b> — 会话按状态过滤，消息按角色过滤</summary>

<p align="center">
  <img src="docs/screenshots/06-filters.png" alt="筛选功能" width="860">
</p>
</details>

> 以上截图全部来自**虚构演示数据**，不含任何真实会话、路径或用户名。见下方「隐私与演示模式」。

## 功能一览

- 三步流程，进度始终可见
- 会话搜索 / 状态筛选，消息按角色过滤
- 选分支点即时显示保留数
- 创建前自动备份数据库，失败回滚
- 明暗主题、键盘操作（`/` 搜索、`Ctrl+Enter` 创建、`Esc` 关闭）
- 完整空状态 / 加载骨架 / 错误态，WCAG AA 对比、焦点可见、减少动效偏好

## 安装与运行

需要 Python 3.10+。

```bash
pip install -r requirements.txt
python src/app.py
```

Windows 用户可双击根目录的 `启动界面.bat`（按其中说明配置 Python 路径，或直接使用打包版 exe）。

**执行前请完全退出 WorkBuddy**，避免写入时与桌面端缓存冲突；创建完成后重启即可看到新会话。

## 隐私与演示模式

工具只读取并复制本机 WorkBuddy 数据，不联网、不上传。README 的所有截图都来自一个隔离的**演示模式**：会话、路径、消息全部虚构（`demo-` 前缀），`do_branch` 在演示模式下为纯内存操作，**绝不接触真实数据库**。

```bash
python src/serve.py --port 8777 --demo
# 浏览器打开 http://127.0.0.1:8777/
```

不带 `--demo` 则是真实后端，会连本机的 `~/.workbuddy-ai` 数据——本地开发/测试时请注意区分。两种模式的前端代码完全相同。

浏览器直连的实现原理：PyWebView 桌面端通过 `chrome.webview.postMessage` 桥接 API（浏览器无此对象），`serve.py` 复用同一个 `Api` 后端，用标准库 HTTP 暴露接口并在返回页面时注入兼容 shim，前端零改动，Playwright 打到的就是真实后端（或演示后端）。

## 测试

```bash
python src/serve.py --port 8777        # 或 --demo
python tests/test_ui.py                # 另开终端
```

## Windows 自动编译

`.github/workflows/build-windows.yml` 在推送 `v*` tag 或手动触发时，用 PyInstaller 在 `windows-latest` 上打包单文件 exe，上传为 Actions artifact，并附着到对应 Release。

```bash
git tag v1.0.2
git push origin v1.0.2
```

本地打包：`pyinstaller scripts/build.spec`，产物在 `dist/`。

从 [Releases](https://github.com/MisakaMikoto128/workbuddy-session-branch/releases) 下载 `wb-session-branch-windows.exe` 即可直接运行。

## 项目结构

```
src/
  wb_branch.py   核心分支逻辑（逆向 WorkBuddy 会话存储）
  app.py         PyWebView 后端 API
  serve.py       浏览器直连测试/演示服务
  demo_data.py   虚构演示数据（隐私隔离）
  web/index.html 前端界面（设计 token + 三步流程）
tests/
  test_ui.py     真实后端回归测试
docs/screenshots/ README 配图（全部演示数据）
scripts/         打包配置
.impeccable.md   设计上下文与设计原则
```

## License

MIT — 详见 [LICENSE](LICENSE)。
