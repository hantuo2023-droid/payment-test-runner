# Payment Test Runner 状态 · 0.2.0

更新时间：2026-09-28。继续工作前先读 AGENTS.md、TASK_SPEC.md 和本文件。

## 基线与范围
基线 5156a67（0.1.0 最终文档；已验证实现 37406b1）。保持 Next.js、FastAPI、SQLite/Alembic、真实 Playwright Chromium；六菜单、中文帮助、LIVE only。

## 已完成并验证
- 迁移 002：持久化 selected、使用计数、节点健康、加密资源快照、完整结果字段；保留 0.1 资源及密文。
- 三个资源池：导入默认选择、单选/多选/全选/取消、搜索、安全导出、删除；节点 TXT/CSV/URL 解析与去重。
- RunItems 仅取所选数据数量；账号和已连接节点确定性复用；同一 Run 每数据一次，可在新 Run 主动重选。
- 同账号/节点连续复用 Browser Context。坏账号/节点排除，耗尽标记 NO_AVAILABLE_*；403/429 不换 IP。
- 提交后持续等待终态，容忍导航瞬态；完整页面脱敏截图、Trace、日志在终态后保存；真实超时才 UNKNOWN_RESULT。
- 首页自动准备检查；复选框立即生效；进度、实际节点、结果原因/URL、账号/节点/日期筛选。
- 13 后端 pytest PASS。Frontend lint / production build PASS。
- 真实 Chromium 1+5：RunItems/Fill/Submit/Results 各 5，登录 1，浏览器 1；1+10 各 10，登录 1，浏览器 1。
- 3 账号/12 数据/2 真实 HTTP 代理：12 独立结果，代理各提交 6，无重复；100 条中选 17，执行 17。
- Immediate、Spinner success/decline/3DS、单/多/延迟跳转、可见 iframe、Timeout、截图像素、真实 context-destroy、批量 STOP PASS。
- 真实 UI 粘贴/CSV/TXT、三池全部勾选操作、默认 3 条/单选 1 条/多选 2 条实际 START、筛选、下载、六菜单 PASS；无 pageerror。
- 原有登录、Session 失效重登、结果代码、Production UI 不提交、Run 隔离、删除、证据脱敏回归 PASS。
- 坏账号继续、失败节点排除、NO_AVAILABLE_NETWORK、提交后 HTTP 429 不切换节点 PASS。

## 本机与 GitHub 交付
- 实现里程碑 6b2bb16；ACCEPTANCE.md 和 README.md 已同步。
- 正式本机 data 已备份至 backups/before-v02-* 后升级；三个服务已启动，http://127.0.0.1:3000 健康检查通过，版本 0.2.0。
- 正式库账号/测试数据/Run 均为空，管理员尚未初始化；按 README 运行 backend.cli init-admin 后登录。
- 服务进程记录 data/local-services.json，日志 data/*.log。
- GitHub 公开仓库（用户已明确确认，无需再次核验）：https://github.com/hantuo2023-droid/payment-test-runner 。完整 Git 历史已推送，origin/master 已关联；源码、文档和安全验收汇总在仓库中。
- 用户明确授权了 Git Credential Manager 的 GitHub 登录权限；凭据由系统凭据管理器保管，不写进项目。
- 本机运行数据、密码、Secret、原始测试目录与备份均未加入仓库。

## 限制 / NOT TESTED
- Docker build/runtime、VPS、Linux 安装、容器重启、升级回滚与部署备份恢复：没有 Docker/Linux 主机。
- 真实 Preply 登录/UI：未提供账号；Production 边界已在受控本地网站验证。
- 外部 HTTP/SOCKS5 成功连通及认证代理：未提供节点；本机真实无认证 HTTP 代理已测。
- 任意自定义授权站点实际绑定：需要内部 Adapter 符合其页面协议和官方测试数据，未提供环境。
- 单管理员、单 worker 串行；无 Workflow/Selector/配额编辑器；不完成 3DS/验证码。
- Trace 关闭 DOM/网络快照且脱敏；跨域支付 iframe 需专用适配器。
- TestClient 存在 httpx 弃用警告，不影响测试通过。

## 证据
见 docs/acceptance-pools.json、acceptance-ui.json、acceptance-faults.json、acceptance-live.json 和 docs/screenshots/。
测试数据库及完整证据位于忽略的 test-output/ 下，未进入 Git。


## Reliability Checkpoints · 当前恢复点

执行规则：docs/RELIABILITY_CHECKPOINTS.md。修复起点 83080dc；原后端 13 项测试保持，不重做已可靠通过的 0.2 验收。

### COMPLETED CHECKPOINT: 1/4
- Import Normalizer：处理行首 BOM、数值字段零宽字符、全角数值/分隔符、管道/CSV/Tab/分号/冒号及可明确拆分的空格格式。
- 账号按首个结构分隔符拆分，密码内的管道、逗号、---- 和 Unicode 字符不被改写；CSV 引号错误仍拒绝。
- 有效期支持 M/MM + YY/YYYY、MM/YY、MM/YYYY；两位年份明确映射 20YY。内部保留 month="07"、year="2035"、cvc，不引入 year_full。
- 规范化后去重；过期记录仍计入有效数据并可确认加密保存，Preview API 返回带行号和安全遮罩的 EXPIRED_TEST_DATA warnings。格式错误仍是 errors。
- TESTS：仅运行 test_importer.py + API 原导入确认测试 + 新过期记录预览/确认测试，11 passed（1 条原有 httpx 弃用提示）。新增共 5 个测试，原 13 个未删除。
- 未执行全量 pytest、lint/build、Browser E2E 或 Docker；这些统一留至 Checkpoint 4，当前不能据此声称新修改全量验收通过。
- 未新增 migration，未修改 Runner / Network 调度、Session 或 Result。
- LAST COMMIT：本节所在的 fix: normalize imported resource data 提交；用 git log -1 获取实际 hash。

### NEXT: CHECKPOINT 2
1. authenticated SOCKS5（Chromium 需受控转接方案）、节点编辑与凭据变更、Direct 默认选择；仅运行相关 network tests 后提交。
2. Checkpoint 3：提交前坏资源切换不得消耗数据；Submit started 后禁止自动重新提交。
3. Checkpoint 4：授权 origin allowlist、Preview 警告 UI/说明与其余文档修正、结果导出回归；最后一次完整验收。
4. 如有中断，先看 git status / git diff，保留当前修改，不重写/重克隆/重跑已可靠阶段验收。

### 仍待确认的输入
用户尚未提供具体失败的“脏数据”脱敏样例。目前只兼容上面有明确字段边界的格式；不猜测缺失列或把任意数字串当作完整数据。

### 交付状态
Checkpoint 1 为本地恢复点；本轮未 push。公开仓库信息仅按用户事实更正文档，没有执行任何 GitHub/网络权限查询或重新认证。
