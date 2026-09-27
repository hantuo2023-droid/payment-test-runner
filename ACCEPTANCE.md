# 0.1.0 本地验收报告

日期：2026-09-27。通过测试的实现版本：`37406b1`。后续文档提交不改变实现。

**本地核心流程已通过验证，尚未完成全部部署与真实站点验收。**

## 环境与方法

Windows；Python 3.12；Node 24.19.0；pnpm 11.19.0；Next 16.3.6；React 19.3.0；Playwright Python 1.63.0；真实 Chromium 153.0.8010.12。

独立克隆目录 `test-output/fresh-clone`：前端重新按锁文件安装，Python 与浏览器二进制复用已安装依赖，数据库和测试文件独立创建。初次完整验收版本 `8437c05`；最终 STOP/导航修改更新至 `c84cbf1` 并重跑后端和 Chromium 测试，其后 CSV 严格解析修复更新至 `37406b1` 并在独立克隆重跑 9 个后端测试；这两次修改均不涉及前端。

## 测试结果

| 项目 | 结果 | 范围 |
|---|---|---|
| Backend tests | PASS | 9 pytest，独立克隆 |
| Frontend install / lint / build | PASS | frozen-lockfile 安装；lint 无警告；生产构建成功 |
| 本机 Runtime / Health | PASS | Backend、Database、Worker、Disk；前端 HTTP 200 |
| Compose YAML 语法 | PASS | 仅语法解析，不等同于 Docker 验收 |
| Docker build / runtime | NOT TESTED | 当前机器没有 Docker |
| VPS 一键安装 / Linux 脚本运行 | NOT TESTED | 未提供 Linux Docker 主机 |
| 更新回滚 / 备份恢复 | NOT TESTED | 脚本已实现，尚未实机验收 |
| Account text import | PASS | API 和真实前端浏览器 |
| Whitespace normalization | PASS | 空白、空行、规范格式 |
| email\|password / email----password | PASS | 两种分隔符 |
| CSV account import | PASS | 标题、引号、含逗号密码 |
| Duplicate detection | PASS | 批内重复、重复提交预览令牌 |
| Invalid format Preview | PASS | 行号和原因，确认前不写账号库 |
| Test Data Import / Dedup | PASS | 合成卡、有效期和字段检查 |
| Custom Task Create / URL Edit | PASS | 新增、修改、版本递增，非法 URL 拒绝 |
| Preply Target 配置 | PASS | 固定目标地址，Production UI-only |
| 真实 Preply 登录 / UI | NOT TESTED | 没有真实账号，不能从本地测试推断适配成功 |
| Network Direct | PASS | 真实 Chromium 访问本地目标 |
| 失败网络阻止 START | PASS | 失效 HTTP 代理连接，缺少有效 proof 拒绝启动 |
| 外部 HTTP / SOCKS5 成功连接 | NOT TESTED | 未提供可用代理 |
| Real Chromium | PASS | 所有 E2E 使用真实浏览器 |
| Local Sandbox Login / Payment Page / Add Card | PASS | 真实输入和点击 |
| Fill / Submit / Result | PASS | 日志包含 FILLING、SUBMITTING、WAITING_RESULT |
| BOUND | PASS | SUCCESS / BOUND |
| DECLINED | PASS | FAIL / DECLINED |
| 3DS_REQUIRED | PASS | FAIL；不继续验证，继续下一项 |
| INVALID_DATA | PASS | FAIL / INVALID_DATA |
| Delayed Redirect | PASS | 初始 700ms 跳转，登录后 1.5s 跳转 |
| TIMEOUT / UNKNOWN_RESULT | PASS | 未检测到结果时 ERROR / UNKNOWN_RESULT |
| BAD_CREDENTIALS / LOGIN_TIMEOUT | PASS | 分别正确识别 |
| Session 复用 / 失效重登 | PASS | 有效 Session 跳过认证，无效 cookie 自动重新认证 |
| Production UI 不提交 | PASS | 本地 Production 任务 UI_VERIFIED，无 FILLING/SUBMITTING |
| Run Isolation | PASS | 后续运行、删除不影响先前 Run |
| STOP | PASS | 当前项 CANCELLED，排队项 NOT_EXECUTED，已完成结果保留 |
| TXT / CSV Export | PASS | 密码、完整卡号不出现 |
| UI CSV Download | PASS | 浏览器触发并保存文件 |
| Delete Selected | PASS | 账号选择删除；缺少确认被拒绝 |
| Delete Run | PASS | 删除结果和文件，保留账号 |
| Screenshot / Trace / Logs | PASS | 六种结果有真实截图、可读取 Trace ZIP、步骤日志 |
| Screenshot / Trace / Log Cleanup | PASS | API 清理选定时间范围 |
| Restart Persistence | PASS（有限范围） | SQLite 重初始化保留数据；worker 重启标记 INTERRUPTED；未测 Docker 重启 |
| LIVE never falls back to MOCK | PASS | 无运行时 Mock；失败及未知结果保留 ERROR |
| 六菜单 / 实时结果 | PASS | 真实 UI 点击，无 pageerror |
| 桌面 / 平板截图 | PASS | 截图生成，桌面首页和结果布局已人工查看 |

## 证据与限制

- [Chromium 验收输出](docs/acceptance-live.json)
- [首页截图](docs/screenshots/home.png)
- [结果与实时日志截图](docs/screenshots/results.png)
- 可重跑测试：`backend/tests/e2e_live.py`、`backend/tests/e2e_ui.py`。
- 自定义绑定站点必须满足 README 中的页面协议；跨域支付 iframe 和其他登录流程需专用 Task 适配器。
- 当前只接受五种合成测试卡，不接收真实银行卡。
- Trace 脱敏填写值，关闭 DOM/网络快照，诊断信息少于完整未脱敏 Trace。
- 第一版为单管理员、单 backend worker、串行执行。
- TestClient 有一条 httpx 弃用警告，9 个测试全部通过。
- 没有远端仓库或公开安装器地址，尚不能给出已发布的 curl 安装 URL。
