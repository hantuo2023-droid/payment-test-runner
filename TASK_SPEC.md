# 当前增量修复规则

最新用户执行规则见 [docs/RELIABILITY_CHECKPOINTS.md](docs/RELIABILITY_CHECKPOINTS.md)，优先于下方 0.2.0 历史规格。
保留原 13 项测试与已通过功能，按四个 checkpoint 本地提交。仅阶段相关测试；四阶段完成后做一次最终完整回归。
GitHub 已由用户确认 Public，不再联网核验、重新 clone 或配置认证。不部署或验证用户 VPS。
内部 month/year/cvc 保持兼容，不创建非必要迁移。阶段状态与继续位置见 TASK_STATE.md。

---

请基于当前已经完成的 Payment Test Runner 0.1.0 继续修改。

不要从零重写。
不要重新设计已经验证正常的核心模块。
不要把项目重新做成复杂 QA 平台。

当前已验证实现版本：

37406b1

开始修改前请先阅读：

README.md
ACCEPTANCE.md
TASK_SPEC.md
TASK_STATE.md
当前代码和现有测试

本次是在现有 0.1.0 基础上修正产品核心使用逻辑，并建议版本升级为：

0.2.0

==================================================
一、不要重写已经验证正常的功能
==================================================

当前已经验证正常的能力包括：

真实 Playwright Chromium
LIVE only
Login
Session
Add Card
Fill
Submit
Result Parser
BOUND
DECLINED
3DS_REQUIRED
INVALID_DATA
UNKNOWN_RESULT
BAD_CREDENTIALS
LOGIN_TIMEOUT
STOP
Run Isolation
Screenshot
Trace
Logs
TXT / CSV Export
Cleanup

这些功能尽量保持现有实现。

只做实现下面新需求所必要的修改。

不要重新增加：

Workflow Builder
Page Mapping
Case Builder
Selector Editor
复杂 QA 配置
复杂 Scheduler 配置

==================================================
二、这个工具真正的目的
==================================================

这个工具最主要的目的：

减少用户重复人工输入测试数据。

正常使用流程应该非常简单：

批量导入账号
+
批量导入测试数据
+
批量导入节点
↓
选择 Task
↓
START
↓
真实 Chromium 全自动执行
↓
一直运行到本次待测试数据全部完成
↓
查看结果
↓
导出 / 删除 / 清理

不要让用户配置：

一个账号跑几条测试数据

一个节点跑几个任务

账号数量必须等于测试数据数量

1 个账号只能对应 1 条测试数据

每一条测试数据人工指定账号

每一条测试数据人工指定节点

不要设计这种额外工作。

==================================================
三、使用“三个资源池”
==================================================

系统主要有三个资源池：

账号池

测试数据池

节点池

三类资源都必须支持批量管理。

用户默认使用方式：

导入
→ START

如果用户不手工修改选择：

所有当前有效、可用、已选择的数据默认参与本次运行。

只有用户想排除某些数据时：

才去列表取消勾选。

==================================================
四、执行数量只由测试数据决定
==================================================

这是本次最重要的规则之一。

对于需要测试数据的 Card Binding Task：

本次选择多少条测试数据，

就必须执行多少条。

公式：

RunItems = selected_test_data_count

绝对不要再：

min(account_count, test_data_count)

绝对不要再：

1 account = 1 test data

例如：

1 个账号
+
10 条测试数据
+
1 个节点

必须：

RunItems = 10

Fill = 10

Submit = 10

Results = 10

例如：

3 个账号
+
100 条测试数据
+
5 个节点

必须：

RunItems = 100

最终：

100 条独立结果。

==================================================
五、每条测试数据在一个 Run 内只执行一次
==================================================

每一条本次选中的测试数据：

只创建一个 RunItem。

不要因为：

多个账号

多个节点

而形成笛卡尔积。

例如：

10 accounts
+
100 test data
+
10 nodes

不是：

10 × 100 × 10

而是：

100 RunItems

账号和节点：

属于可复用资源。

测试数据：

才是待执行任务。

==================================================
六、不要增加“每账号跑多少条”设置
==================================================

用户不需要设置：

Account A = 5 cards

Account B = 20 cards

Node A = 10 tasks

Node B = 30 tasks

这些设置全部不要。

账号和节点只要：

被本次 Run 选择

并且：

有效 / 可用

就可以由系统内部自动使用。

内部调度必须：

简单
确定
可预测

并在每条结果中记录：

实际使用的账号

实际使用的节点

不要随机分配。

不要让普通用户配置复杂调度规则。

==================================================
七、允许用户自己选择本次资源
==================================================

虽然默认使用全部有效资源，

但是用户必须能够自己决定本次 Run 使用哪些：

账号

测试数据

节点

例如数据库里有：

20 个账号

100 条测试数据

10 个节点

用户可以选择：

3 个账号

25 条测试数据

2 个节点

然后：

START

系统只能使用：

这 3 个账号

这 25 条测试数据

这 2 个节点

本次：

RunItems = 25

START 后：

仍然自动执行到底。

“自己搭配”指的是：

决定本次允许使用哪些资源。

不要要求用户逐条创建：

Account → Test Data → Node

Mapping。

==================================================
八、只保留全自动执行
==================================================

不要半自动模式。

不要：

提交前暂停

人工点击继续

人工操作浏览器

手动确认每一条

START 后必须全自动：

建立 Run
→ 建立 RunItems
→ 获取账号
→ 获取节点
→ Chromium
→ Login / Session
→ Target
→ Add Card
→ Fill
→ Submit
→ 等待最终结果
→ 保存结果
→ 下一条
→ 下一条
→ …
→ 队列清空
→ Run 完成

==================================================
九、账号必须支持完整批量导入 / 导出
==================================================

账号页面必须支持：

粘贴批量导入

TXT 导入

CSV 导入

批量导出

搜索

单选

任意多选

全选

取消全选

删除选中

清空

至少继续支持：

email@example.com|password

email@example.com----password

CSV：

email,password

导入自动：

忽略空行

Trim

整理分隔符

邮箱规范化

检测重复

检测错误

Preview：

总数

有效

重复

错误

错误显示：

行号

安全摘要

错误原因

不能把密码通过错误结果重新回显。

==================================================
十、账号选择不能再多一步
==================================================

账号列表中的 checkbox：

就是：

是否参加下一次 Run。

不要：

先 checkbox

然后还需要再点击：

“标记已选”

才真正生效。

必须支持：

单独选择

任意多选

全选

取消全选

导入成功且有效的新账号：

默认 selected = true

这样普通用户：

导入
→ START

不用重新手工全选一次。

==================================================
十一、测试数据必须支持完整批量管理
==================================================

测试数据支持：

粘贴批量导入

TXT

CSV

批量导出安全字段

搜索

单选

任意多选

全选

取消全选

删除选中

清空

继续支持：

格式整理

去重

Preview

错误检查

普通列表只显示遮罩数据。

例如：

****4242

CVC 等敏感字段：

不显示在普通列表

不写普通日志

不出现在普通导出

==================================================
十二、测试数据默认直接参加运行
==================================================

导入成功且有效的新测试数据：

默认 selected = true

例如用户导入：

100 条

首页直接显示：

本次待执行：

100

用户可以：

START

系统直接跑 100 条。

如果用户只需要其中 17 条：

取消其他数据

则：

selected = 17

START 后：

RunItems = 17

不要只能：

全选全部数据。

必须真正支持逐条选择和取消。

==================================================
十三、Local Sandbox 五种合成卡只限制 Sandbox
==================================================

当前 README 有：

“当前版本只接受五个合成卡号”

必须明确：

这个限制只属于：

Local Sandbox fixture

Local Sandbox 可以继续使用固定合成测试数据：

BOUND

DECLINED

3DS_REQUIRED

INVALID_DATA

UNKNOWN_RESULT

这是为了验证程序。

但是：

整个 Test Data 数据库和导入层

不能只允许这五条 fixture。

对于用户明确授权的：

Sandbox

QA

Staging

Internal

应该允许导入该测试环境官方允许的测试数据。

实际数据结构和填写规则：

由 Task / Adapter 决定。

不要支持或宣传第三方 Production 的真实银行卡验证。

==================================================
十四、节点升级为正式资源池
==================================================

节点也必须像账号和测试数据一样方便管理。

节点页面或：

设置 → 节点

必须容易找到。

支持：

Direct

HTTP

SOCKS5

以及：

批量粘贴导入

TXT

CSV

批量导出

格式解析

去重

搜索

单选

任意多选

全选

取消全选

删除选中

清空

批量连接测试

延迟显示

状态显示

==================================================
十五、节点导入格式
==================================================

至少支持：

http://host:port

http://username:password@host:port

socks5://host:port

CSV：

name,protocol,host,port,username,password

如果当前 Chromium / Playwright 对某种代理认证有限制：

必须在 UI 或 Preview 明确告诉用户。

不要等真正执行以后才突然失败。

导入 Preview：

总数

有效

重复

格式错误

节点导入后可以：

批量 Test Connection

显示：

CONNECTED

FAILED

LATENCY

节点密码：

不显示在普通列表

不写普通日志

不出现在普通导出

==================================================
十六、节点默认参与逻辑
==================================================

格式有效的新节点：

默认 selected = true

但是实际执行只能使用：

Healthy / Connected

节点。

FAILED 节点：

保留在列表

但不参加自动执行。

重新 Test Connection 成功后：

重新可用。

如果用户没有导入任何代理节点：

系统默认：

Direct

==================================================
十七、不要利用节点规避站点限制
==================================================

节点用于正常授权测试网络。

不要实现：

CAPTCHA 出现 → 自动换 IP

Rate Limit → 自动换 IP

Login Block → 自动换 IP

403 / 429 等情况：

按现有安全逻辑记录并停止对应项目。

==================================================
十八、首页必须做到“导入后直接 START”
==================================================

首页至少显示：

账号：

总数
可用
本次使用

测试数据：

总数
待执行
本次使用

节点：

总数
Healthy
本次使用

Task

Mode：

LIVE

以及：

本次预计执行：

N 条

例如：

Accounts:
3 selected

Test Data:
100 selected

Nodes:
5 selected / 4 healthy

Task:
Local Sandbox Binding

预计执行：

100

[ START ]

不要再增加：

每账号执行数量

每节点任务数量

卡片配额

==================================================
十九、Readiness 检查
==================================================

START 前检查：

Backend

Database

Worker

Chromium

Task

Target URL

至少一个有效账号

至少一条 selected 测试数据
（需要测试数据的 Task）

至少一个可用 Network
（Direct 也算）

不满足：

START disabled

并告诉用户具体原因。

==================================================
二十、Session 必须充分复用
==================================================

同一个账号连续处理多条数据时：

优先复用：

当前 Browser Context

Session

不要：

每测试一条
→ 重新登录一次

正常情况下：

1 account
+
10 test data

应该：

Login ≈ 1

Fill = 10

Submit = 10

Results = 10

只有：

Session expired

被退出

重新出现认证页

才重新登录。

==================================================
二十一、坏账号不能拖死整个 Run
==================================================

如果某个账号明确出现：

BAD_CREDENTIALS

登录失败

Session 无法恢复

应该：

记录账号不可用

保存对应错误

当前 Run 中暂时停止继续使用这个账号

如果还有其他可用账号：

继续处理剩余测试数据

如果：

所有账号都不可用

再停止剩余任务并明确：

NO_AVAILABLE_ACCOUNT

不要无限尝试坏账号。

==================================================
二十二、坏节点不能拖死整个 Run
==================================================

如果节点：

NETWORK_ERROR

Connection Failed

确认不可用

当前 Run 暂时停止使用。

如果还有其他已选择 Healthy 节点：

继续。

如果全部不可用：

明确结束并给出：

NO_AVAILABLE_NETWORK

不要无限重试。

==================================================
二十三、提交以后绝对不能马上给结果
==================================================

这是本次最重要的稳定性要求之一。

以前旧版本真实出现过：

Fill
→ Submit
→ 页面正在转圈 / redirect
→ 程序检查太快
→ 页面最终信息还没有出来
→ 程序已经给结果
→ Screenshot 甚至是空白页

新版本绝对不能再次出现。

点击 Submit：

绝对不代表当前测试已经完成。

==================================================
二十四、正确的提交后流程
==================================================

必须：

FILLING
↓
SUBMITTING
↓
WAITING_RESULT
↓
观察页面
↓
处理 Redirect
↓
处理 Spinner / Loading
↓
等待安全验证 / 3DS / 成功 / 失败等状态
↓
检测真正最终状态
↓
FINAL_STATE_DETECTED
↓
Screenshot / Trace / Log
↓
保存结果
↓
当前 RunItem 才结束

不能：

Submit click 成功
→ SUCCESS

不能：

没有异常
→ SUCCESS

不能：

页面跳转
→ SUCCESS

不能：

500ms 没看到内容
→ UNKNOWN_RESULT

==================================================
二十五、中间状态不能当最终结果
==================================================

以下都不是 Final Result：

Loading

Processing

Please wait

Spinner

Skeleton

按钮 Disabled

Submit 按钮暂时消失

页面空白过渡状态

页面正在 redirect

DOM 正在 reload

Execution context destroyed during navigation

这些状态：

只能继续等待。

不能直接：

SUCCESS

FAIL

ERROR

UNKNOWN_RESULT

==================================================
二十六、结果判断必须读取最终页面信息
==================================================

成功必须来自明确证据。

例如由当前 Adapter 定义：

BOUND

Payment method added

Saved successfully

明确成功提示

卡片出现在目标页面

或者该测试环境正式定义的 Success marker

不能：

“没有看到错误”
=
SUCCESS

失败也必须读取最终信息。

例如：

DECLINED

INVALID_DATA

Card rejected

Validation error

明确失败提示

然后才记录：

FAIL / 对应 Result Code

==================================================
二十七、Spinner / Loading 必须继续等
==================================================

如果 Submit 后出现：

转圈

Processing

Loading

Please wait

页面 skeleton

必须继续：

WAITING_RESULT

持续检测。

不能因为页面一两秒没有内容：

就截图

就 ERROR

就 UNKNOWN_RESULT

==================================================
二十八、Redirect 必须导航容错
==================================================

Submit 后可能：

Page A
→ intermediate blank page
→ Page B
→ processing
→ Page C
→ Final Result

不要只：

wait_for_load_state("domcontentloaded")

然后立即判断。

DOMContentLoaded：

不是业务完成状态。

如果 Playwright 出现：

Execution context was destroyed because of a navigation

如果发生在正常导航中：

视为 transient condition。

继续：

等待页面稳定

读取新 URL

重新检测页面

而不是：

PAGE_ERROR。

==================================================
二十九、3DS / Security Verification
==================================================

Submit 后如果进入：

3DS

3-D Secure

Security verification

Bank verification

Challenge page

验证 iframe

等状态，

必须先等到：

验证页面或 iframe 真正加载

有明确可见证据

然后才分类。

当前工具不自动完成或绕过：

3DS

OTP

Security Verification

CAPTCHA

如果 Adapter 判断为：

3DS_REQUIRED

则：

FAIL / 3DS_REQUIRED

并保存：

明确显示验证状态的 Screenshot

Final URL

Trace

Log

Reason

不能在验证页还没加载出来时：

截空白图
→ 直接返回 3DS。

==================================================
三十、WAITING_RESULT 必须持续轮询
==================================================

不能：

检测一次
→ 没找到
→ UNKNOWN_RESULT

应该在 Task / Adapter 的 result timeout 内持续观察。

每轮至少检查：

当前 URL

是否 Navigation

是否仍 Loading

是否 Processing

Success marker

Failure marker

3DS / Security marker

Validation error

Adapter Terminal State

直到：

Terminal State

或者真正 Timeout。

==================================================
三十一、只有真正超时才能 UNKNOWN_RESULT
==================================================

只有：

Submit 已完成

并且：

整个 Result Wait Timeout 已结束

仍然没有：

Success

Business Fail

3DS / Verification

明确 Technical Error

才允许：

ERROR / UNKNOWN_RESULT

Reason：

No recognized terminal result before timeout

不能：

刚提交
→ 没看到结果
→ UNKNOWN_RESULT

==================================================
三十二、最终结果检测属于 Adapter
==================================================

不同目标页面最终状态不同。

Task / Adapter 应负责定义：

success markers

failure markers

3ds/security markers

processing markers

terminal URL patterns（如果需要）

result timeout

主 Runner 负责：

等待

循环检测

Navigation 容错

Timeout

Screenshot

Trace

Logs

Result persistence

普通用户：

不要配置复杂 Selector。

==================================================
三十三、Screenshot 必须在正确时间生成
==================================================

这是之前真实出现过的问题。

最终 Screenshot：

必须在检测到最终状态以后再生成。

SUCCESS：

截最终成功页面。

DECLINED：

截最终拒绝页面。

INVALID：

截最终错误页面。

3DS_REQUIRED：

截明确的验证页面。

UNKNOWN_RESULT：

真正 Timeout 后：

等待当前页面稳定

再截图当前实际可见状态。

不要：

刚 click Submit
→ Screenshot

这样会再次得到空白图。

==================================================
三十四、日志必须把整个提交后过程写清楚
==================================================

日志例如：

SUBMITTING:
clicked submit

WAITING_RESULT:
waiting for terminal state

PROCESSING:
spinner detected

POST_SUBMIT_NAVIGATION:
URL changed

WAITING_RESULT:
still waiting

FINAL_STATE_DETECTED:
DECLINED

RESULT:
FAIL / DECLINED

Reason:
...

或者：

FINAL_STATE_DETECTED:
3DS_REQUIRED

RESULT:
FAIL / 3DS_REQUIRED

或者：

RESULT:
ERROR / UNKNOWN_RESULT

Reason:
No terminal state detected before timeout

不能：

WAITING_RESULT
→ Run finished

中间没有最终结果信息。

==================================================
三十五、每张测试数据必须等待自己的最终结果
==================================================

批量执行不能为了速度：

Submit Card 1
→ 不等结果
→ 直接 Card 2

必须：

Card 1
→ Fill
→ Submit
→ 等到 Card 1 Final Result
→ 保存 Card 1
→ 再 Card 2

这样才能保证：

结果不会错位。

==================================================
三十六、每条结果保存实际资源
==================================================

每个 RunItem 至少保存：

Run ID

Account ID

Account Email

Test Data ID

Masked Test Data

Network Profile ID

Network Name

Task ID

Task Version

Status

Result Code

Reason

Final Step

Final URL

Started At

Finished At

Duration

Screenshot

Trace

Logs

这样用户能知道：

哪条数据

用了哪个账号

哪个节点

最后是什么结果。

==================================================
三十七、结果页面
==================================================

例如：

Account          Test Data    Network    Result    Reason

a@example.com    ****4242     Node-01    SUCCESS   BOUND

b@example.com    ****0002     Node-02    FAIL      DECLINED

a@example.com    ****3220     Direct     FAIL      3DS_REQUIRED

支持：

搜索

SUCCESS

FAIL

ERROR

账号筛选

节点筛选

日期筛选

Run 筛选

明显按钮：

导出 TXT

导出 CSV

删除选中

删除 Run

==================================================
三十八、运行进度
==================================================

START 后：

Run ID

总任务：
100

已完成：
37

剩余：
63

SUCCESS：
20

FAIL：
14

ERROR：
3

RUNNING：
1

当前：

Account

Masked Test Data

Network

Step

例如：

FILLING

SUBMITTING

WAITING_RESULT

PROCESSING

每完成一个：

自动下一条。

直到：

Remaining = 0。

==================================================
三十九、STOP
==================================================

批量运行中的 STOP 必须继续正常。

例如：

100 条

完成：
37

正在执行：
第 38 条

用户 STOP：

前 37 条：

保留结果

第 38 条：

安全停止 / CANCELLED

剩余：

NOT_EXECUTED
或者现有明确未执行状态

不能：

删除前面已完成结果。

不能：

把未执行的数据全部标记成已使用。

==================================================
四十、“已使用”不能永久禁止再次测试
==================================================

测试数据可以记录：

last_used_at

use_count

last_result

但是：

已使用

不能代表：

以后永远不能再次主动测试。

规则：

同一个 Run 中：

同一条测试数据只执行一次。

不同 Run：

如果用户以后主动再次选择：

允许重新测试。

==================================================
四十一、Run Isolation 继续保留
==================================================

Run #101

Run #102

必须完全分开。

每个 Run 保存：

账号资源快照

测试数据

节点资源快照

Task Snapshot

Task Version

Results

Artifacts

删除 Run：

删除该 Run 的：

Results

Screenshots

Trace

Logs

但：

不删除账号

不删除测试数据

不删除节点资源。

==================================================
四十二、Production 边界继续保持
==================================================

当前 Preply Production：

https://preply.com/en/settings/payments

继续只做：

Login

Payment Methods

Add Card UI Verify

Production：

不要自动提交真实银行卡。

完整：

Fill
Submit
Final Result Parse

用于明确授权：

Sandbox

QA

Staging

Internal

不要因为批量功能修改：

破坏现有安全边界。

==================================================
四十三、界面必须有使用说明
==================================================

不要只靠 README。

首页增加简洁：

“使用说明”

例如：

1. 导入账号
2. 导入测试数据
3. 可选：导入节点
4. 选择 Task
5. 默认全部可用数据参与
6. 如需排除，在对应页面取消勾选
7. 点击 START
8. 系统自动运行到全部结束
9. 在运行记录查看 / 导出 / 删除结果

账号页面：

显示导入格式。

测试数据页面：

显示当前 Adapter 支持格式。

节点：

显示 HTTP / SOCKS5 示例。

结果页面：

解释：

SUCCESS
FAIL
ERROR

以及常见：

BOUND
DECLINED
3DS_REQUIRED
UNKNOWN_RESULT

所有用户输入字段继续保持：

用途

格式

示例

是否必填

==================================================
四十四、批量导出
==================================================

账号：

批量导出安全字段

不要密码。

测试数据：

批量导出安全字段

不要完整敏感认证信息

不要 CVC。

节点：

批量导出安全字段

不要代理密码。

Results：

TXT

CSV

至少包含：

Run ID

Account

Masked Test Data

Network

Result

Result Code

Reason

Time

Duration

==================================================
四十五、必须增加新的批量自动化测试
==================================================

这次绝对不能只验证一条。

至少真实测试：

A.

1 account
+
5 test data
+
Direct

必须：

RunItems = 5

Fill = 5

Submit = 5

Results = 5

B.

1 account
+
10 test data

必须：

RunItems = 10

Fill = 10

Submit = 10

Results = 10

C.

多个账号
+
多条 test data
+
多个节点

必须确认：

每条 selected test data

只执行一次。

不能形成笛卡尔积。

D.

只选部分数据：

例如数据库 100 条，
手动只选 17 条。

必须：

RunItems = 17。

==================================================
四十六、必须测试三类资源的选择
==================================================

Accounts：

Individual Select
PASS

Multi Select
PASS

Select All
PASS

Deselect All
PASS

Test Data：

Individual Select
PASS

Multi Select
PASS

Select All
PASS

Deselect All
PASS

Nodes：

Individual Select
PASS

Multi Select
PASS

Select All
PASS

Deselect All
PASS

不能只测试：

“页面上有 checkbox”。

必须真正确认：

START 使用的是选择后的数据。

==================================================
四十七、必须增加提交后状态回归测试
==================================================

Local Sandbox 必须增加或完善以下真实 Chromium 场景：

Immediate Success

Spinner → Success

Spinner → Declined

Spinner → 3DS_REQUIRED

Redirect → Success

Multiple Redirect → Success

Delayed Redirect → Success

No Result → UNKNOWN_RESULT

必须确认：

程序没有在中间状态提前结束。

==================================================
四十八、空白 Screenshot 回归测试
==================================================

这是以前真实发生过的问题。

增加明确测试：

Blank Screenshot Regression

测试场景：

Submit
→ Redirect
→ Intermediate blank/loading page
→ Final result

最终保存的 Screenshot：

必须是：

最终可见结果页面

而不是：

Redirect 中间的空白页。

如果截图仍然空白：

测试 FAIL。

==================================================
四十九、Navigation transient 回归测试
==================================================

专门验证：

Execution context was destroyed because of navigation

出现在正常页面跳转期间时：

不会马上 PAGE_ERROR。

必须：

继续等待

重新检测

最终识别真实结果。

验收：

Navigation Regression
PASS / FAIL

==================================================
五十、批量执行时每张数据必须等最终状态
==================================================

专门测试：

5 条测试数据连续运行。

必须证明：

Card 1 Final Result
→ Card 2 Start

Card 2 Final Result
→ Card 3 Start

不能：

Card 1 Submit
→ Card 2 已经 Fill
→ Card 1 Result 还没回来

禁止这种结果错位。

==================================================
五十一、不要为了这次修改重构整个项目
==================================================

本次重点只在：

批量资源管理

默认全自动执行

账号 / 测试数据 / 节点选择

批量节点导入导出

执行队列

提交后的 Final Result 等待

结果证据正确时间点

UI 使用说明

已经 PASS 的：

Browser
Session
Result Parser
STOP
Run Isolation
Evidence
Cleanup
LIVE only

尽量复用。

==================================================
五十二、文档必须同步
==================================================

修改：

README.md

TASK_SPEC.md

TASK_STATE.md

ACCEPTANCE.md

删除现有文档中的错误描述：

“1 个账号对应 1 条测试数据”

以及任何：

账号数量决定最多执行数量

的旧规则。

新文档必须明确：

本次执行数量 = selected test data count

账号和节点是可复用资源。

==================================================
五十三、完成以后不要只告诉我“已完成”
==================================================

最终必须给真实验收数字。

按照下面格式回复：

Version:

Commit:

Account batch import/export:
PASS / FAIL

Test Data batch import/export:
PASS / FAIL

Node batch import/export:
PASS / FAIL

Account individual/multi/select-all/deselect-all:
PASS / FAIL

Test Data individual/multi/select-all/deselect-all:
PASS / FAIL

Node individual/multi/select-all/deselect-all:
PASS / FAIL

Default imported resources auto-selected:
PASS / FAIL

1 account + 5 test data:
RunItems =
Login count =
Fill count =
Submit count =
Results =

1 account + 10 test data:
RunItems =
Login count =
Fill count =
Submit count =
Results =

Multiple accounts + multiple test data + multiple nodes:
Selected Test Data =
RunItems =
Duplicate Test Data Execution = YES / NO

Custom partial selection:
Selected =
RunItems =

Session reuse:
PASS / FAIL

Immediate Success:
PASS / FAIL

Spinner → Success:
PASS / FAIL

Spinner → Declined:
PASS / FAIL

Spinner → 3DS:
PASS / FAIL

Redirect → Success:
PASS / FAIL

Multiple Redirect → Success:
PASS / FAIL

Unknown Result Timeout:
PASS / FAIL

Blank Screenshot Regression:
PASS / FAIL

Navigation Transient Regression:
PASS / FAIL

Final result log:
PASS / FAIL

Batch STOP:
PASS / FAIL

Run Isolation:
PASS / FAIL

TXT / CSV Export:
PASS / FAIL

Backend tests:
实际数量 / PASS / FAIL

Frontend lint:
PASS / FAIL

Frontend build:
PASS / FAIL

Real Chromium E2E:
PASS / FAIL

Docker:
PASS / FAIL / NOT TESTED

VPS:
PASS / FAIL / NOT TESTED

NOT TESTED:
逐项列出

Known Limitations:
逐项列出

==================================================
五十四、验收纪律
==================================================

没有真实测试：

必须写：

NOT TESTED

不能写：

PASS

不能因为：

代码看起来正确

就写 PASS。

不能通过：

Mock

直接 API 修改结果

直接数据库写结果

跳过真实 Fill / Submit

来冒充浏览器测试。

需要 Browser E2E 的项目：

必须真实 Playwright Chromium。

==================================================
五十五、最终产品原则
==================================================

最终用户体验必须保持：

导入
→ START
→ 自动跑完
→ 看结果

需要精确控制：

勾选想使用的：

账号

测试数据

节点

→ START

→ 仍然自动跑完

不要再增加：

一个账号跑几张

一个节点跑几个

1:1 配对

手工逐条 Mapping

半自动

复杂 Workflow

复杂 Scheduler

复杂 Selector UI

最重要：

批量导入后能直接自动执行全部待测试数据。

并且：

每一条测试数据 Submit 后，
必须真正等到页面最终结果出现，
再给出结果和 Screenshot。

绝对不能：

刚 Submit
→ 页面还在转圈 / 跳转
→ 就提前给结果。

这两个目标是本次修改的最高优先级。