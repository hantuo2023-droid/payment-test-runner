从零开发一个全新的 Web 工具。

项目名称：
Payment Test Runner

目标非常明确：

做一个稳定、操作简单、方便管理的浏览器自动化测试工具。

用户最常用的流程只有：

导入账号
→ 导入测试数据
→ 自动整理格式
→ 自动去重
→ 选择账号
→ 选择任务
→ 选择网络
→ START
→ 真实 Chromium 自动执行
→ 查看 SUCCESS / FAIL / ERROR
→ 查看具体原因
→ TXT / CSV 导出
→ 删除没用的数据

不要把它做成复杂 QA 平台。

不要加入：
Workflow Builder
Page Mapping
Case Builder
Selector Editor
复杂 Environment 管理
其他普通用户根本不需要理解的功能。

==================================================
1. 已知真实目标站点
==================================================

内置一个 Preply 页面任务。

真实站点：

https://preply.com

主要目标页面：

https://preply.com/en/settings/payments

程序应该优先直接访问：

https://preply.com/en/settings/payments

如果账号没有登录，网站可能正常跳转到类似：

https://preply.com/en/login?next=/en/settings/payments

不要把完整动态 login URL 当成唯一固定入口。

正确逻辑：

打开：
https://preply.com/en/settings/payments

如果已经登录：
→ 进入 Payment Methods

如果跳转到登录：
→ 识别 Login 页面

登录页面至少识别：

Email
Password
Log In

登录成功以后：

再次进入：
https://preply.com/en/settings/payments

然后识别：

Payment methods
Add card

可以打开：

Add card

并确认：

Save a payment card

弹窗/表单正常出现。

这个真实 Preply Production Task 用于：
登录
页面导航
Payment Methods
Add Card UI 验证

不要把真实 Production 网站拿来自动提交真实银行卡。

完整 Card Binding：
填写测试卡
→ Submit
→ 判断结果

必须在用户明确授权的：
Sandbox
QA
Staging
Internal

测试环境执行。

==================================================
2. 工具必须支持完整 Card Binding 测试
==================================================

这是工具的重要能力。

在授权测试环境中必须真正执行：

登录账号
→ 打开目标支付页面
→ Add Card
→ 等待卡片表单
→ 填写测试卡号
→ 填写有效期
→ 填写 CVC
→ Submit
→ 等待测试环境返回
→ 判断结果

不能只：

打开 Add Card
→ PASS

不能：

发现输入框
→ PASS

不能：

代码没有异常
→ PASS

完整任务必须真正完成：

FILL
+
SUBMIT
+
WAIT RESULT
+
PARSE RESULT

才能结束。

结果至少支持：

SUCCESS / BOUND

FAIL / DECLINED

FAIL / 3DS_REQUIRED

FAIL / INVALID_DATA

ERROR / BAD_CREDENTIALS

ERROR / LOGIN_TIMEOUT

ERROR / NETWORK_ERROR

ERROR / TARGET_NOT_FOUND

ERROR / UNKNOWN_RESULT

如果无法判断结果：

必须：

ERROR / UNKNOWN_RESULT

绝不能默认 SUCCESS。

==================================================
3. 测试地址必须可以自己添加和修改
==================================================

除了内置 Preply Task，

用户必须可以在后台：

新增任务
修改任务
启用
停用
测试地址

任务页面提供：

[新增任务]

字段：

任务名称

任务说明

环境类型：
Production
Sandbox
QA
Staging
Internal

Base URL

Login URL

Target URL

状态：
启用 / 停用

每个字段必须明确告诉用户：

这个字段是什么
是否必填
正确格式
示例

例如：

Target URL

用途：
登录成功后需要进入的目标测试页面

格式：
完整 URL

示例：
https://preply.com/en/settings/payments

必填：
是

提供：

[测试地址]
[保存]

用户选择哪个 Task：

本次 Run 就只使用这个 Task 的配置。

绝不能：

当前 Task 缺少 URL
→ 自动使用其他 Task 的 URL

绝不能：

配置错误
→ 随机找一个可用配置继续运行

缺少必要信息：

START 直接禁止。

==================================================
4. 不需要先知道支付商
==================================================

不要要求用户先配置：

Stripe
Adyen
某个支付商

才能使用软件。

这是浏览器自动化测试工具。

用户主要需要知道：

账号
测试数据
目标 URL
任务
网络

如果某个具体测试环境以后需要特殊支付页面解析：

由该 Task 内部实现。

不要把支付商配置暴露成普通用户必须理解的复杂步骤。

==================================================
5. 首页必须非常简单
==================================================

一级菜单只允许：

首页
账号
测试数据
运行记录
任务
设置

首页：

Payment Test Runner

版本：
x.x.x

运行模式：
LIVE

系统状态：

Backend       ✓
Database      ✓
Worker        ✓
Chromium      ✓
Network       ✓
Disk          ✓

然后：

① 账号

已导入：100
已选择：20

[导入账号]
[选择账号]

② 测试数据

可用：20
已选择：20

[导入测试数据]

③ 任务

[任务 ▼]

显示：

任务名称
目标地址
简单说明

④ 网络

[Direct ▼]

⑤ 准备状态

账号          ✓
测试数据      ✓
任务          ✓
目标地址      ✓
Chromium      ✓
网络          ✓

[ START ]

缺任何必要条件：

START 必须 disabled。

直接显示原因。

例如：

请先选择账号

测试数据不足

Task 缺少 Target URL

网络连接测试失败

不要开始后才报错。

==================================================
6. 账号导入
==================================================

账号页面必须明显提供：

[粘贴导入]
[TXT 导入]
[CSV 导入]
[导出]
[删除选中]
[清空]
[搜索]
[筛选]

至少支持：

email@example.com|password

以及：

email@example.com----password

文本解析必须自动：

忽略空行
去除前后空格
清理分隔符附近多余空格
识别支持的分隔符
规范成统一内部格式
检测重复
检测明显错误

例如：

   test@example.com   |   abc123

自动整理成：

test@example.com|abc123

能确定的格式问题：

自动修正。

不能确定：

不要猜。

标记错误。

导入前必须 Preview：

总数：110
有效：100
重复：8
错误：2

错误数据必须显示：

行号
原始内容
错误原因

例如：

第 18 行
缺少密码

第 35 行
邮箱格式错误

用户点击：

[确认导入]

之后才写数据库。

重复账号默认不要重复保存。

==================================================
7. 账号管理
==================================================

账号列表至少显示：

Email

状态

Session

上次结果

创建时间

支持：

搜索

筛选

多选

删除选中

清空

导出

重新测试

清除 Session

密码必须安全存储。

不能出现在：

普通列表
运行日志
结果导出
错误信息

==================================================
8. Session 自动处理
==================================================

普通用户不需要理解 storage_state。

账号只显示：

NONE

VALID

EXPIRED

逻辑：

NONE

→ 正常登录
→ 成功后保存 Session

VALID

→ 优先使用 Session
→ 尝试直接进入 Target URL

EXPIRED

→ 自动重新登录
→ 更新 Session

账号操作只提供：

[清除 Session]

[重新登录]

==================================================
9. 测试数据导入
==================================================

必须有独立：

测试数据

页面。

明显提供：

[粘贴导入]
[TXT 导入]
[CSV 导入]
[导出安全字段]
[删除选中]
[清空]
[搜索]
[筛选]

测试支付数据用于授权测试环境。

导入流程和账号一样：

文本解析
→ 格式整理
→ 去重
→ 错误检测
→ Preview
→ 确认导入

显示：

总数

有效

重复

错误

已使用

未使用

敏感数据显示必须遮罩。

例如：

**** **** **** 4242

敏感认证字段：

不能显示在普通列表

不能写普通日志

不能出现在普通结果导出

==================================================
10. 数据配对
==================================================

第一版保持简单。

默认：

1 个账号
对应
1 条测试数据

开始前明确显示：

账号：20

测试数据：20

可执行：20

如果：

账号：20

测试数据：8

显示：

本次最多执行 8 条。

不要在同一个 Run 内偷偷重复使用测试数据。

==================================================
11. 真实 Chromium
==================================================

正常运行默认：

LIVE

LIVE 必须代表：

真实 Playwright

真实 Chromium

真实网页操作

真实 Screenshot

真实 Trace

Mock 仅用于开发自动化测试。

如果进入 Mock：

前端必须醒目显示：

MOCK MODE

模拟结果，不是真实浏览器运行。

严格禁止：

LIVE 出错
→ 自动切换 Mock
→ 返回成功

真实运行失败：

就显示真实 ERROR。

==================================================
12. 页面状态必须稳定判断
==================================================

不要实现：

page.goto
→ 马上检测一次
→ 找不到
→ PAGE_ERROR

必须实现页面状态等待。

建议状态：

QUEUED

STARTING_BROWSER

NAVIGATING

WAITING_PAGE

AUTH_REQUIRED

AUTHENTICATING

AUTH_SUCCESS

TARGET_LOADING

TARGET_READY

FORM_OPEN

FILLING

SUBMITTING

WAITING_RESULT

COMPLETED

ERROR

CANCELLED

页面发生正常 redirect/navigation：

不能马上 ERROR。

以前已经出现过典型问题：

页面 DOMContentLoaded
→ 客户端稍后跳转
→ 程序检测太快
→ 错误 PAGE_ERROR
→ 截到白屏

新工具必须避免。

Playwright 如果在正常导航期间出现：

Execution context was destroyed because of navigation

应该视为 navigation transient state。

继续等待页面稳定并重新判断。

真正超时后才 ERROR。

==================================================
13. START 后的界面
==================================================

点击 START：

创建新的 Run ID。

例如：

Run #102

显示：

任务：

目标：

网络：

开始时间：

进度：

8 / 20

当前账号：

test@example.com

当前步骤：

正在提交测试数据

统计：

SUCCESS

FAIL

ERROR

RUNNING

WAITING

CANCELLED

实时日志例如：

Chromium started

Opening target page

Login required

Login form detected

Filling credentials

Login successful

Opening Payment Methods

Add Card opened

Filling test data

Submitting

Waiting result

DECLINED

提供明显：

[ STOP ]

==================================================
14. STOP
==================================================

点击 STOP：

安全停止任务。

已经完成的数据：

保留结果。

正在执行的项目：

安全结束。

尚未执行：

CANCELLED。

Chromium：

正确关闭。

Trace：

正确结束。

日志：

正确保存。

==================================================
15. 结果必须一眼看懂
==================================================

运行结果例如：

账号                  数据          结果       原因

a@example.com         ****4242      SUCCESS    BOUND

b@example.com         ****4000      FAIL       DECLINED

c@example.com         ****3220      FAIL       3DS_REQUIRED

d@example.com         ****1111      ERROR      LOGIN_TIMEOUT

支持：

搜索

SUCCESS

FAIL

ERROR

日期筛选

提供明显按钮：

[导出 TXT]

[导出 CSV]

[删除选中]

[删除本次 Run]

==================================================
16. 3DS
==================================================

完整 Card Binding Test 中：

如果检测到 3DS：

立即停止当前测试项。

不继续自动处理 3DS。

记录：

FAIL

3DS_REQUIRED

保存：

Screenshot

Trace

Log

然后继续下一项。

==================================================
17. Run 必须完全分开
==================================================

每次 START：

产生新的：

Run ID

例如：

Run #101

Run #102

Run #103

一次 Run 的：

账号

测试数据

任务

Task Version

网络

结果

日志

截图

Trace

开始时间

结束时间

全部关联到该 Run。

不同 Run 不能混在一起。

运行记录页面：

Run ID

Task

数量

SUCCESS

FAIL

ERROR

时间

耗时

点击某一个 Run：

只显示这一批结果。

==================================================
18. 导出
==================================================

导入和导出按钮必须明显。

不能藏起来。

账号页：

[导入]

[导出]

测试数据：

[导入]

[导出安全字段]

Results：

[导出 TXT]

[导出 CSV]

结果导出至少包含：

Run ID

账号

遮罩测试数据

结果

结果代码

时间

耗时

不能导出：

密码

敏感认证字段

==================================================
19. 删除和数据管理
==================================================

这是核心功能。

用户不能为了清理数据去 SSH 或 SQLite。

设置中必须有：

数据管理

显示：

账号数量

测试数据数量

Runs 数量

Results 数量

Screenshots 占用

Traces 占用

Logs 占用

Sessions 数量

磁盘占用

提供：

账号：

[删除选中]

[清空]

测试数据：

[删除选中]

[清空]

Run：

[删除选中 Run]

[清理历史 Run]

Artifacts：

[清理 Screenshots]

[清理 Trace]

[清理 Logs]

Session：

[清理失效 Session]

历史数据支持：

7 天以前

30 天以前

全部

危险删除：

必须二次确认。

删除 Run：

删除该 Run 的：

Results

Screenshots

Trace

Logs

但：

不要删除账号本身。

==================================================
20. Screenshot / Trace / Logs
==================================================

LIVE 运行必须保存真实调试证据。

至少：

错误 Screenshot

最终结果 Screenshot

Playwright Trace

运行日志

结果详情直接：

[查看截图]

[下载 Trace]

[查看日志]

不要要求用户 SSH 找路径。

日志至少包含：

Run ID

账号

步骤

URL

动作

结果

错误

日志不能记录：

密码

CVC

其他不必要的敏感字段

==================================================
21. 网络
==================================================

默认：

Direct

用户也可以添加：

HTTP

SOCKS5

网络设置字段：

名称

协议

Host

Port

Username（可选）

Password（可选）

必须提供：

[测试连接]

显示：

Connected

Latency

或者：

Connection failed

并给出原因。

测试失败的网络：

START 禁止。

正常网络错误可以有限重试。

不要实现：

CAPTCHA

Rate Limit

Login Block

出现以后自动轮换 IP 继续规避限制。

==================================================
22. 所有需要填写的位置都必须有说明
==================================================

硬性要求。

任何输入框都必须告诉用户：

名称

用途

是否必填

格式

示例

例如：

SOCKS5 Host

用途：
测试代理服务器地址

格式：
IP 或 Domain

示例：
192.0.2.10

必填：
是

不要只放一个：

Host [ ]

中文说明必须完整。

可同时支持英文。

==================================================
23. Task 内部实现
==================================================

普通用户不管理 Workflow / Selector。

Task 可以内部模块化。

例如：

tasks/
  preply_ui/
  local_sandbox_binding/

Task 内部负责：

登录识别

目标页面识别

Add Card

表单定位

Submit

Result parsing

主 Runner 负责：

Browser

Session

Network

状态机

Timeout

Retry

Logs

Screenshot

Trace

STOP

Result persistence

Task 必须有版本号。

Run 保存：

Task ID

Task Version

==================================================
24. 必须自带本地完整 Sandbox
==================================================

项目必须自带完全受控的本地测试站点。

建议 Docker Service：

sandbox

内部地址：

http://sandbox:8080

页面：

http://sandbox:8080/login

http://sandbox:8080/settings/payments

包含：

Login

Payment Methods

Add Card

Card Form

Submit

并能模拟：

BOUND

DECLINED

3DS_REQUIRED

INVALID_DATA

DELAYED_REDIRECT

TIMEOUT

Codex 必须用真实 Playwright Chromium执行：

Login

→ Payment Methods

→ Add Card

→ Fill

→ Submit

→ Result

分别测试：

BOUND

DECLINED

3DS_REQUIRED

INVALID_DATA

Delayed Redirect

不能只做 API Test。

==================================================
25. 技术方案
==================================================

优先：

简单

稳定

容易维护

建议：

Frontend：
Next.js

Backend：
FastAPI

Browser：
Playwright Python

Database：
SQLite

Migration：
Alembic

Deployment：
Docker Compose

第一版不要为了架构高级加入：

Redis

Kafka

复杂消息队列

微服务

除非核心功能确实必须。

==================================================
26. 安装
==================================================

新 VPS 应支持一键安装：

curl -fsSL <installer> | sudo bash

自动完成：

检查系统

安装 Docker

创建目录

创建配置

生成 Secret

数据库初始化

Alembic migration

Docker build

启动

Chromium health

整体 Health Check

安装结束必须明确显示：

Payment Test Runner installed

Frontend        Healthy

Backend         Healthy

Worker          Healthy

Database        Healthy

Chromium        Healthy

Mode            LIVE

Web URL:
...

==================================================
27. 更新 / 备份
==================================================

提供：

update.sh

backup.sh

restore.sh

status.sh

logs.sh

restart.sh

更新必须：

Backup

→ Pull

→ Migration

→ Build

→ Restart

→ Health Check

如果失败：

明确停止并报告。

不要留下半升级状态。

==================================================
28. Codex 用量控制
==================================================

用户非常在意 Codex 用量。

不要重复分析已经明确的需求。

不要反复重构已经测试通过的部分。

项目开始时创建：

AGENTS.md

TASK_SPEC.md

TASK_STATE.md

AGENTS.md：

只保存最必要、长期有效的开发规则。

TASK_SPEC.md：

保存本需求基线。

TASK_STATE.md：

保存：

当前 Phase

已完成

已测试

未完成

已知问题

下一步

最后稳定 Commit

开发分阶段完成。

建议：

Phase 1
项目骨架 / DB / Admin / Health

Phase 2
账号 Import / Preview / Normalize / Dedup / Delete / Export

Phase 3
Test Data Import / Normalize / Dedup / Delete

Phase 4
Task / Preply Target / Custom URL / Local Sandbox

Phase 5
Playwright Runner / State Machine / Session

Phase 6
Fill / Submit / Result Parser

Phase 7
Live Run UI / STOP

Phase 8
Results / TXT CSV Export

Phase 9
Screenshot / Trace / Logs

Phase 10
Data Management

Phase 11
Network Profiles

Phase 12
Install / Update / Backup

Phase 13
Full Acceptance

每完成一个阶段：

运行该阶段必要测试。

通过：

commit。

更新 TASK_STATE.md。

再继续。

不要每改一个小文件都完整 Docker rebuild。

完整 Build / Runtime / E2E：

放在里程碑或最终验收。

==================================================
29. Codex 用量不足时
==================================================

如果当前用量或执行资源快不足：

不要草率宣布完成。

先：

完成当前最小完整修改

运行相关测试

Commit

更新 TASK_STATE.md

写清楚：

完成到哪里

哪些测试 PASS

哪些还没有做

下一步是什么

最后稳定 Commit

然后安全暂停。

用户恢复用量后：

读取：

AGENTS.md

TASK_SPEC.md

TASK_STATE.md

检查：

git status

git log

然后：

从上次断点继续。

不要重新从头分析。

不要重新实现已经通过测试的功能。

==================================================
30. 最终验收
==================================================

必须 fresh clone 验证。

Backend tests：
PASS

Frontend lint：
PASS

Frontend build：
PASS

Docker build：
PASS

Docker runtime：
PASS

Health：
PASS

Account text import：
PASS

Whitespace normalization：
PASS

email|password：
PASS

email----password：
PASS

Duplicate detection：
PASS

Invalid format Preview：
PASS

Test Data Import：
PASS

Test Data Dedup：
PASS

Custom Task Create：
PASS

Custom URL Edit：
PASS

Preply Target：
PASS

Network Test：
PASS

Real Chromium：
PASS

Local Sandbox Login：
PASS

Payment Page：
PASS

Add Card：
PASS

Fill：
PASS

Submit：
PASS

BOUND：
PASS

DECLINED：
PASS

3DS_REQUIRED：
PASS

INVALID_DATA：
PASS

Delayed Redirect：
PASS

Run Isolation：
PASS

STOP：
PASS

TXT Export：
PASS

CSV Export：
PASS

Delete Selected：
PASS

Delete Run：
PASS

Screenshot Cleanup：
PASS

Trace Cleanup：
PASS

Restart Persistence：
PASS

LIVE never falls back to MOCK：
PASS

没有真正测试的项目：

必须：

NOT TESTED

不能为了交付写 PASS。

==================================================
31. 最终交付
==================================================

最后只需要输出清晰报告：

Version

Commit

安装命令

Web 地址

管理员初始化方法

已完成功能

测试结果

Backend

Frontend

Docker

Chromium

Local Sandbox E2E

Import / Dedup

Export

Delete / Cleanup

已知限制

NOT TESTED

不要输出大量重复开发过程。

==================================================
32. 最终产品原则
==================================================

这个工具本来就应该简单。

最重要：

稳定

操作简单

文本直接导入

自动整理格式

自动去重

错误行能看出来

测试地址用户自己能添加修改

真实 Chromium 执行

授权测试环境真正 Fill + Submit + Result

结果清楚

每次 Run 数据分开

TXT / CSV 直接导出

没用的数据直接删除

方便管理

发生问题直接看到：

原因
Screenshot
Trace
Log

不要做成复杂 QA 平台。

如果实现方案有多种：

优先选择：

最简单

最稳定

最少配置

最容易使用

最容易维护

不要自行增加会改变产品核心使用方式的功能。