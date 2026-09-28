# Payment Test Runner · 0.2.0

私有仓库：[https://github.com/hantuo2023-droid/payment-test-runner](https://github.com/hantuo2023-droid/payment-test-runner)。

简单的自托管浏览器测试工作台：导入账号、测试数据和可选节点 → 选择任务 → START → 查看结果、截图、Trace 和日志。

**运行模式只有 LIVE。** 使用 Playwright Python 和真实 Chromium，不提供运行时 Mock，也不会将未知结果当作成功。

## 快速启动（Windows 本机）

需要 Python 3.12、Node.js 24、pnpm 11.19.0。当前工作目录已经安装了 `.venv`、前端依赖和测试用 Chromium。

```powershell
# 首次安装依赖（已安装时跳过）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
cd frontend
pnpm install --frozen-lockfile
cd ..

# 初始化管理员并启动三个服务；按 Enter 停止
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

Web：<http://127.0.0.1:3000>。管理员密码在第一次启动时从终端输入，至少 12 位，不写入脚本或普通日志。

也可单独初始化：`.\.venv\Scripts\python.exe -m backend.cli init-admin`。初始化只允许一次，重复执行不会覆盖现有密码。

## Docker / VPS

仓库克隆到 Debian/Ubuntu VPS 后：

```bash
sudo bash scripts/install.sh
```

安装器检查 Linux、安装 Docker（如尚未安装）、生成加密 Secret、构建服务、执行 Alembic、交互初始化管理员、等待服务健康并启动一次 Chromium 访问本地 Sandbox。

仓库为 **Private**。先使用有权限的 GitHub 账号完成 Git 登录，再克隆：

```bash
git clone https://github.com/hantuo2023-droid/payment-test-runner.git
cd payment-test-runner
sudo bash scripts/install.sh
```

私有仓库不提供匿名公共 curl 安装地址。当前环境无 Docker，容器构建、运行和安装脚本尚未实机验收；参见 `ACCEPTANCE.md`。

默认只监听 VPS 的 `127.0.0.1:3000`。从自己的电脑访问：

```bash
ssh -L 3000:127.0.0.1:3000 user@your-vps
```

然后打开 <http://127.0.0.1:3000>。公网使用需配置 HTTPS 反向代理并设置 `PTR_SECURE_COOKIE=1`；请不要直接将明文 HTTP 后台暴露到公网。

手动 Compose：复制 `.env.example` 为 `.env`，设置有效 Fernet Secret，创建并赋予 UID 10001 对 data 目录的权限，然后执行 `docker compose build`、迁移、管理员初始化和 `docker compose up -d --wait`。请勿启动多个 backend worker，第一版使用单进程后台线程和 SQLite。

## 本地 Sandbox 测试

默认任务是 `Local Sandbox Binding`。本机 URL 为 `http://127.0.0.1:8080`，Compose 中为 `http://sandbox:8080`。

账号：任意格式正确的邮箱；密码固定 `sandbox-pass`。以 `delay` 开头的邮箱会在登录后延迟 1.5 秒跳转。其他密码返回 BAD_CREDENTIALS。该账号协议仅用于完全受控的本地 Sandbox。

账号导入示例：

```text
bound@example.com|sandbox-pass
declined@example.com----sandbox-pass
delay@example.com|sandbox-pass
```

CSV 支持 `email,password` 标题行和 CSV 引号。导入清理空白、忽略空行、大小写归一、去重；错误行显示行号和原因。为避免错误文本回显密码，原始敏感文本仅保留在浏览器本地的导入输入框；服务器预览返回安全摘要。

测试数据格式：`number|month|year|cvc`；也支持四列 CSV 标题 `number,month,year,cvc`。

| 合成卡号 | 本地 Sandbox 结果 |
|---|---|
| 4242424242424242 | SUCCESS / BOUND |
| 4000000000000002 | FAIL / DECLINED |
| 4000000000003220 | FAIL / 3DS_REQUIRED |
| 4000000000000069 | FAIL / INVALID_DATA |
| 4000000000009995 | 不返回结果，最终 ERROR / UNKNOWN_RESULT |

示例：`4242424242424242|12|2035|123`。**以上五种限制仅用于 Local Sandbox fixture。** 通用导入层接受符合格式的官方测试数据；明确授权的 Sandbox / QA / Staging / Internal 任务由内部 Adapter 检查和填写。不用于第三方 Production 真实银行卡验证。 去重依据卡号、月份、年份，不依据 CVC。导入后先预览，再确认保存。

## 三个资源池与自动执行

账号、测试数据、节点导入成功后默认勾选。列表复选框直接决定是否参加下一次 Run；支持单选、任意多选、全选、取消全选、搜索、导出安全字段、删除和清空。无需“标记已选”或逐条配对。

Card Binding 的 `RunItems = selected_test_data_count`。1 个账号 + 10 条数据生成 10 条任务和独立结果；账号和节点按 ID 升序循环复用，不产生笛卡尔积。首页自动进行真实 Chromium 准备检查，条件满足后可直接 START；失败会列出原因。默认没有代理时使用 Direct；不会悄悄以 Direct 替代用户只选的代理。

同一账号与节点连续执行复用当前 Browser Context；换账号或节点时使用加密 Session。每条数据先完成填写、提交、等待明确终态、保存证据和结果，再执行下一条。账号出现 BAD_CREDENTIALS / LOGIN_TIMEOUT 后在当前 Run 排除；连接错误节点同样排除，有剩余可用资源时继续。资源耗尽时剩余项目明确标记 NO_AVAILABLE_ACCOUNT / NO_AVAILABLE_NETWORK，保留未执行数据。

开始执行的数据记录 used、use_count、last_used_at、last_result，并取消默认勾选；排队未执行数据不消耗。已使用的数据可主动重新勾选，在新的 Run 再次测试。同一 Run 由唯一索引保证每条数据只创建一个项目。

### 节点批量管理

在“设置 → 节点池”导入文本、TXT 或 CSV：

```text
http://host:port
http://username:password@host:port
socks5://host:port
```

CSV 标题：`name,protocol,host,port,username,password`。按协议、Host、端口、用户名去重；密码加密，预览错误不回显凭据。Chromium 不支持 SOCKS5 用户名密码认证，导入预览即拒绝并解释。

新节点默认选中，START 前检查所选节点访问当前 Task 的能力。CONNECTED 才进入 Run 快照，FAILED 保留在列表但排除；可“批量 Test Connection”重测，列表显示状态、延迟和原因。延迟包含 Chromium 启动和目标访问时间。403 / 429 / CAPTCHA 等限制终止本次受影响运行，不换 IP 重试。

### 终态与证据

Submit 后持续观察 PROCESSING / WAITING_RESULT。加载、空白页、跳转和正常导航引起的 execution-context 销毁均继续等待。只有可见 Adapter 终态稳定后才记录 FINAL_STATE_DETECTED；随后生成完整页面截图、脱敏 Trace 和日志。3DS iframe 必须加载且可见，结果为 FAIL / 3DS_REQUIRED，不完成验证。真实超时才是 ERROR / UNKNOWN_RESULT。

每条结果保存实际账号、测试数据和节点 ID、Task 版本、原因、最终 URL、起止时间与耗时。运行记录可按 Run、结果状态、账号、节点和日期筛选，导出 TXT / CSV。STOP 关闭当前浏览器，保留已完成结果，将当前及未开始项目明确标记。

## 任务与适配边界

- 内置 Preply Production：优先打开 `https://preply.com/en/settings/payments`，等待目标页或登录表单；登录后再次访问目标；打开 Add card 并识别 Save a payment card。结果是 `SUCCESS / UI_VERIFIED`，不会填写或提交卡片。
- Production 类型的自定义任务同样仅做 UI 验证。
- Sandbox / QA / Staging / Internal 必须在任务编辑中确认授权；任务的三个 URL 必须同源。
- 每次保存增加版本号；Run 保存任务完整快照、任务版本及网络快照，旧记录不会随配置修改而变化。
- Login URL 保存登录入口；正常流程先访问 Target URL，再等待页面自身的登录跳转。当前适配器不强行跳转到登录页，以避免误判客户端导航。
- 非 Production 的所有浏览器 HTTP 请求都限制在任务站点同源范围内，避免测试数据随页面跳转发送给其他站点。

**任意支付网站不能只填 URL 就保证完整绑定。** 当前自定义绑定任务使用受控页面协议：

| 页面位置 | 内部适配协议 |
|---|---|
| 登录 | `input[name=email]`、密码输入框、名为 `Log In` 的按钮 |
| 目标页 | 可见 `Payment methods` 文本和 `Add card` 按钮 |
| 打开表单 | 可见 `Save a payment card` 文本 |
| 数据字段 | `input[name=card_number]`、`input[name=month]`、`input[name=year]`、`input[name=cvc]` |
| 提交 | 可访问名称严格为 `Submit` 的按钮 |
| 结果 | 可见元素的 `data-result` 为 `BOUND` / `DECLINED` / `3DS_REQUIRED` / `INVALID_DATA` |

特殊页面、跨域支付 iframe、不同登录形式需要在 `backend/tasks` 中增加专用适配器并进行真实浏览器验收。普通用户无需配置支付商、Selector 或 Workflow。未检测到明确结果一律 UNKNOWN_RESULT；检测到已加载且可见的 3DS 后保存验证页面证据，再结束该项目并继续下一项，不自动完成验证。

## Session、日志与数据保护

- 密码、测试卡、代理密码、预览内容和 Session 使用 Fernet 加密存储；管理员密码用 scrypt 哈希。
- 加密 Secret 从 `PTR_SECRET` 获取；本机开发无环境配置时生成 `data/secret.key`。备份必须同时保存数据库和 Secret；丢失 Secret 将无法解密。
- Session 按账号 + 任务 + 版本隔离。有效 Session 优先复用，登录重定向后自动重新登录；修改任务令已有 Session 失效。
- 账号和结果导出不含密码；测试数据只导出安全字段。CSV 对公式前缀进行转义。
- 完整页面截图遮罩主页面及所有 iframe 内的输入框和文本域，保留可见的验证提示。Trace 保存真实浏览器动作但关闭网络/DOM 快照、自动截图和源码；保存前移除填写值、认证字段和秘密文本。诊断细节少于完整未脱敏 Trace，这是有意的保护措施。
- 浏览器异常只保存归类错误，不直接记录可能含密码的 Playwright 原始异常。导航 URL 去掉查询字符串与片段。
- 普通错误不会切换 Mock；程序重启时将中断项目记为 INTERRUPTED，避免自动重复可能已提交的测试。
- 准备检查使用当前任务和网络真正启动 Chromium 并访问目标。凭证有效 120 秒，配置或选择变化后界面自动重新检查；START 验证同一份资源签名。
- SOCKS5 仅支持无认证，这是 Chromium 的限制；需要账号密码的代理请用 HTTP。
- 不绕过 CAPTCHA、限流、登录限制；不因这些限制更换节点。HTTP 403/429 会记录 ACCESS_BLOCKED 并停止本次 Run 的后续项目。

## 维护

```bash
bash scripts/status.sh
bash scripts/logs.sh
bash scripts/restart.sh
bash scripts/backup.sh
bash scripts/update.sh
bash scripts/restore.sh /absolute/path/to/ptr-backup.tar.gz
```

备份会暂时停止后台 worker，保存 data 和对应 `.env` 两个压缩包；恢复需要两者并输入 RESTORE 二次确认。更新保留旧镜像，在失败时尝试恢复之前代码、数据库、配置和镜像，并报告结果。部署脚本需要 Linux GNU 工具，尚未经过实际 Docker 验收。

后台“设置 → 数据管理”可清理 7 天前、30 天前或全部历史 Run / Screenshots / Traces / Logs，以及已失效 Session。删除 Run 不删除账号。运行期间禁止删除或修改核心数据，避免破坏当前 Run。

## 开发与验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider
# 如果浏览器安装在项目测试目录：
$env:PLAYWRIGHT_BROWSERS_PATH="$PWD\test-output\browsers"
.\.venv\Scripts\python.exe -m backend.tests.e2e_live
.\.venv\Scripts\python.exe -m backend.tests.e2e_pools
.\.venv\Scripts\python.exe -m backend.tests.e2e_faults
.\.venv\Scripts\python.exe -m backend.tests.e2e_ui
cd frontend
pnpm lint
pnpm build
```

测试只写 `test-output`，每次端到端执行使用独立目录。`e2e_pools` 验证资源池数量、真实代理、Session 复用、终态截图像素、导航异常恢复和批量停止。`e2e_live` 使用真实 Chromium 测试登录、Add Card、Fill、Submit、结果解析、STOP、Run 隔离和脱敏证据；`e2e_ui` 启动实际 Next.js / FastAPI / Sandbox，点击导入、预览、选择、START、导出，并生成桌面/平板截图。

参考：[Playwright Trace 配置](https://playwright.dev/python/docs/api/class-tracing)、[Next.js 安装文档](https://nextjs.org/docs/app/getting-started/installation)。
