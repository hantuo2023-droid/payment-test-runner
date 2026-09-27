# Payment Test Runner — 当前状态

Version: 0.1.0（本地验收版）
当前 Phase: 13，部分验收完成；Docker / VPS / Preply 真实登录仍未验收。
最后通过实际测试的实现 Commit: 37406b1。
需求基线：TASK_SPEC.md；逐项验收：ACCEPTANCE.md。

## 已完成
- Phase 1：FastAPI、SQLite、Alembic、管理员认证、加密与健康检查。
- Phase 2–3：账号/合成数据 Import、Preview、Normalize、Dedup、Confirm、Delete、Safe Export。
- Phase 4：Preply UI、本地 Sandbox、自定义任务、地址编辑、版本和授权检查。
- Phase 5–6：真实 Chromium、状态等待、Session、Fill / Submit / Parse Result。
- Phase 7–9：六菜单 Next.js UI、准备检查、Run 隔离、实时日志、STOP、TXT/CSV、真实截图和脱敏 Trace。
- Phase 10–11：数据管理、历史清理、Direct/HTTP/SOCKS5 配置、真实连接预检、失败阻止 START。
- Phase 12：Docker Compose、install/update/backup/restore/status/logs/restart、Windows dev.ps1 和使用文档已实现。

## 已测试
- 独立克隆：前端 frozen-lockfile 安装、lint 无警告、production build PASS。
- Backend：9 pytest PASS，包含认证保护、迁移、加密、导入、任务修改、删除、清理和重启恢复。
- 真实 Chromium：BOUND、DECLINED、3DS_REQUIRED、INVALID_DATA、延迟跳转、UNKNOWN_RESULT、BAD_CREDENTIALS、LOGIN_TIMEOUT PASS。
- Session 复用及失效重登、STOP 当前及排队项目、Run 隔离、TXT/CSV、删除 Run、脱敏证据 PASS。
- Direct 网络、失效代理阻止 START、Production UI 不填卡/提交 PASS。
- 真实前端点击：登录、预览与导入、选择、START、实时结果、CSV 下载、六菜单 PASS；无 pageerror。
- PowerShell 脚本语法和 Compose YAML 语法检查通过；不代表容器运行通过。

## 未完成 / NOT TESTED
- Docker build/runtime，全新 VPS 安装、更新回滚、备份恢复、容器重启持久性。
- Preply 真实登录和 UI（未提供账号）。
- 外部 HTTP/SOCKS5 成功连接（未提供可用代理）。
- 未适配站点的完整 Card Binding。
- 远端仓库、公开安装脚本 URL 和 VPS 部署未配置。

## 已知限制
- 自定义站点需满足 README 的内部页面协议；跨域支付表单需专用适配器。
- 仅五个合成测试卡号，不处理真实卡、3DS 或验证码。
- Secret 必须随数据库备份；Trace 脱敏并关闭 DOM/网络快照。
- TestClient 有 httpx 弃用提示，不影响已执行测试。

## 本机运行
- 当前预览：http://127.0.0.1:3000。仅监听 loopback。
- PID：data/local-services.json；服务日志：data/。
- 正式本机数据为空，管理员尚未初始化。
- 初始化：.\.venv\Scripts\python.exe -m backend.cli init-admin
- 重启电脑后可用 scripts/dev.ps1 启动；当前为本机进程，不是 Docker。

## 下一步
1. 在 Linux Docker 主机验证安装、健康、备份恢复、更新回滚和容器重启。
2. 提供 Preply 测试账号和可用代理后补齐对应验收。
3. 为其他授权站点实现内部 Task 适配，再做真实浏览器验收。
4. 继续前读取 AGENTS.md、TASK_SPEC.md、TASK_STATE.md，检查 git status / git log；不要重做已通过部分。
