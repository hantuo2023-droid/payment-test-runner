# Payment Test Runner 0.2.0 验收报告

日期：2026-09-28。通过验证的实现提交：`6b2bb16`。基于已验证 0.1.0 增量修改，无重写核心模块。

## 实际执行计数

所有业务结果来自真实 Playwright Chromium 的 Fill / Submit / 页面解析；未用 API 或数据库写入成功结果代替浏览器执行。数据使用本地合成 fixtures；100 条测试记录通过不同的有效期生成独立记录。

| 场景 | 选择数据 | RunItems | 实际登录 | Fill | Submit | Results | Browser launches |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 account + 5 test data + Direct | 5 | 5 | 1 | 5 | 5 | 5 | 1 |
| 1 account + 10 test data + Direct | 10 | 10 | 1 | 10 | 10 | 10 | 1 |
| 3 accounts + 12 test data + 2 HTTP nodes | 12 | 12 | — | 12 | 12 | 12 | — |
| 100 条新增记录，选择其中 17 条 | 17 | 17 | — | 17 | 17 | 17 | — |

多资源场景：Duplicate Test Data Execution = **NO**。两个真实本机 HTTP 代理各转发 6 次提交；每条结果的账号/节点来自选定池。表中“—”表示该项没有作为计数验收指标。

## 功能结果

| 验收项 | 结果 | 实际范围 / 证据 |
|---|---|---|
| Account batch import / export | PASS | 两种文本分隔符、CSV、规范化、去重、错误预览和安全字段导出 |
| Test Data batch import / export | PASS | 文本/CSV、去重、遮罩；通用导入接受五 fixtures 以外的官方测试数据；Local Adapter 单独限制 |
| Node batch import / export | PASS | HTTP/SOCKS5 URL、六列 CSV、去重、安全预览/导出；不支持的 SOCKS5 认证提前拒绝 |
| Accounts individual / multi / select-all / deselect-all | PASS | 真实前端点击、持久化检查、START 实际账号 ID 核对 |
| Test Data individual / multi / select-all / deselect-all | PASS | 真实前端点击、START 结果 ID 集合与所选数据完全一致 |
| Nodes individual / multi / select-all / deselect-all | PASS | 真实前端点击、实际节点来自选择；取消全部阻止 START |
| Imported resources default selected | PASS | 三池导入后直接自动检查；真实 UI 默认 START 生成 3 条，单选生成 1 条，多选生成 2 条 |
| Session / Browser Context reuse | PASS | 1+5、1+10 各只登录一次、启动一个浏览器；失效 cookie 自动重新登录 |
| Used test data reselect | PASS | 主动重选在新 Run 再次执行，use_count 递增到 2 |
| Immediate Success | PASS | 可见 BOUND 后才保存结果 |
| Spinner → Success | PASS | 等待 processing 结束并识别 BOUND |
| Spinner → Declined | PASS | FAIL / DECLINED |
| Spinner → 3DS | PASS | FAIL / 3DS_REQUIRED |
| Redirect → Success | PASS | 经空白过渡页面后最终 BOUND |
| Multiple Redirect → Success | PASS | 两次过渡跳转后最终 BOUND |
| Delayed Redirect → Success | PASS | 1.3 秒空白过渡后最终 BOUND |
| Visible 3DS iframe | PASS | 验证 iframe 已加载、可见，保存完整页面验证证据；不完成验证 |
| Unknown Result Timeout | PASS | 实际等待完整超时，ERROR / UNKNOWN_RESULT，记录明确 reason |
| Blank Screenshot Regression | PASS | 用 Pillow 读取保存 PNG，检查最终页面特定颜色区域 > 10,000 像素；不是仅检查文件存在 |
| Navigation Transient Regression | PASS | 真实导航销毁尚未结束的 execution context；等待器恢复并识别真实 BOUND，日志记录 transient |
| Final result log | PASS | FINAL_STATE_DETECTED 时间早于 EVIDENCE_SAVED；RESULT 包含分类与原因 |
| Sequential final-before-next | PASS | 5 / 10 / 12 / 17 条逐项检查上一项结束时间不晚于下一项开始时间 |
| Batch STOP | PASS | 至少 2 项完成后在 processing 中停止；已完成保留、当前取消、排队 NOT_EXECUTED，未开始数据 use_count=0 |
| Bad account isolation | PASS | BAD_CREDENTIALS 后移除坏账号，其他账号继续；全部不可用时 NO_AVAILABLE_ACCOUNT |
| Bad node isolation | PASS | preflight 失败节点排除；运行期间节点失效后继续使用剩余所选节点 |
| NO_AVAILABLE_NETWORK | PASS | 最后一节点真实断开，首项 NETWORK_ERROR，其余明确未执行 |
| HTTP 429 after Submit | PASS | 真实代理返回 429；记录 ACCESS_BLOCKED，后续项目停止，未在另一节点提交 |
| Run Isolation | PASS | 独立快照、结果和文件；后续 Run / 删除不改变已有 Run |
| TXT / CSV Export | PASS | 实际账号、节点、Task 版本、原因、最终 URL 和时间；不含密码、完整卡号 |
| Production UI boundary | PASS | 受控本地 Production 任务只打开 Add Card，UI_VERIFIED；无 FILLING / SUBMITTING |
| Core 0.1 regression | PASS | BOUND / DECLINED / 3DS_REQUIRED / INVALID_DATA / UNKNOWN_RESULT / BAD_CREDENTIALS / LOGIN_TIMEOUT、Session、证据、删除、STOP |
| UI filters / six menus / download | PASS | 真实账号与节点筛选、下载 CSV、六菜单；pageerror 数量 0 |
| Backend tests | PASS | **13 pytest**，包括 001 → 002 带数据迁移和密文保留 |
| Frontend lint | PASS | ESLint 退出码 0 |
| Frontend build | PASS | Next.js 生产构建成功 |
| Real Chromium E2E | PASS | e2e_live、e2e_pools、e2e_faults、e2e_ui 四套实际运行 |
| Local 0.2 runtime health | PASS | 3000 前端/代理、8000 Backend、8080 Sandbox HTTP 200；版本 0.2.0、DB/Worker/Disk 正常 |
| Docker | NOT TESTED | 当前机器无 Docker |
| VPS | NOT TESTED | 未提供 Linux Docker 主机 |

## 环境与复现

Windows，Python 3.12，Node 24.19.0，Next 16.3.6，React 19.3.0，Playwright Python 1.63.0，真实 Chromium 153.0.8010.12。测试使用独立数据目录和不同 Sandbox 端口，不污染正式 data。此次无全新依赖重装，使用现有锁文件和已安装依赖。

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider
$env:PLAYWRIGHT_BROWSERS_PATH="$PWD\test-output\browsers"
.\.venv\Scripts\python.exe -m backend.tests.e2e_live
.\.venv\Scripts\python.exe -m backend.tests.e2e_pools
.\.venv\Scripts\python.exe -m backend.tests.e2e_faults
.\.venv\Scripts\python.exe -m backend.tests.e2e_ui
cd frontend
pnpm lint
pnpm build
```

保存的汇总：[资源池和终态回归](docs/acceptance-pools.json)、[真实界面测试](docs/acceptance-ui.json)、[资源失效及 429](docs/acceptance-faults.json)、[原有核心回归](docs/acceptance-live.json)。

界面证据：[首页](docs/screenshots/home.png)、[结果](docs/screenshots/results.png)、[平板](docs/screenshots/tablet.png)。原始截图/Trace/日志在 test-output 的独立目录，未上传敏感运行目录。正式本机数据库已在 backups/before-v02-* 中备份后升级，备份未进入 Git。

## NOT TESTED / Known Limitations

- Docker build/runtime、VPS 安装、Linux 脚本实跑、容器重启、部署升级回滚与备份恢复未测。迁移单元测试和本机升级不代表这些部署项目通过。
- 真实 Preply 登录/UI 未测，未提供账号。Production 边界在受控本地站点验证。
- 外部 HTTP、SOCKS5 连通和认证代理未测；本机无认证 HTTP 代理真实转发已验证。
- 任意自定义授权站点绑定未测，需要内部 Adapter 符合该环境页面协议及官方测试数据。导入格式通过不等于任意站点适配成功。
- 非 Production 同源请求边界保留；跨域支付 iframe 需要专用适配器。不完成 3DS、OTP 或 CAPTCHA。
- 单管理员、单 worker、串行执行。有效旧 Session 可以恢复；不自动恢复可能已提交的中断项目。
- Trace 脱敏并关闭网络/DOM 快照，诊断信息少于完整 Trace。截图保留验证 iframe 的可见内容，并遮罩所有输入框。
- TestClient 有一条 httpx 弃用提示；13 项测试通过。
- 本机管理员尚未初始化，按 README 初始化后使用自己的密码登录。

## GitHub 交付

已上传至 [hantuo2023-droid/payment-test-runner](https://github.com/hantuo2023-droid/payment-test-runner)，可见性 Private，分支 master，包含本地完整提交历史。data、test-output、backups、secret.key 和环境文件没有进入仓库。
