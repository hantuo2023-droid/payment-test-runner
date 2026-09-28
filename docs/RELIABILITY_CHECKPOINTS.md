==================================================
执行规则：节省用量、允许中断后继续
==================================================

当前用户 Codex 用量有限。

本任务允许分阶段完成。

不要因为无法一次完成全部内容而：
- 重写项目
- 回滚已经完成的正确修改
- 重新克隆仓库
- 从头重新分析整个项目
- 重新执行已经有可靠结果的验收
- 创建第二套实现

必须基于当前仓库继续修改。

当前原始基线已经确认：

backend:
13 passed

请保留所有当前已通过功能。

--------------------------------------------------
一、仓库状态已知，不要额外验证
--------------------------------------------------

原 GitHub 仓库已经是 Public。

这是用户明确确认的事实。

不要为了确认这一点执行：

GitHub API 查询
gh repo view
网页访问 GitHub
仓库权限探测
重新 clone
重新配置 remote
重新配置 GitHub authentication

如果 TASK_STATE.md / README 中仍然写：

“私有仓库”

可以直接更正为：

“公开仓库”

或者删除“私有/公开”这种无关运行逻辑的描述。

不需要再联网验证。

--------------------------------------------------
二、不要做与这次修复无关的工作
--------------------------------------------------

不要：

重新设计 UI
更换技术栈
升级 Next.js
升级 React
升级 FastAPI
升级 Playwright
替换 SQLite
重建 Docker 架构
改变导航结构
重新实现 Session 系统
重新实现 Result 系统
重新设计 RunItem 模型
增加 Mock
增加半自动模式
增加账号与测试数据固定 1:1 配对
增加每账号最大测试数据数量
增加 Cartesian product

除非本次明确问题真正需要，否则：

不要创建数据库 migration。

当前问题大部分可以在现有 schema 上解决。

只有代码实现确实无法在现有 schema 完成时，
才允许增加 migration，并说明原因。

--------------------------------------------------
三、不要重复修改已经正确的功能
--------------------------------------------------

以下已经存在并且方向正确：

1 Account + N Test Data = N RunItems

资源池

Session reuse

Spinner waiting

Redirect waiting

multiple redirect

final-state detection

UNKNOWN_RESULT timeout

3DS detection

STOP

Run isolation

Screenshot / Trace / Log

TXT / CSV Result export

结果导出的：

status
code
reason
step
final_url
duration

这些都不要重新设计。

尤其：

结果导出已经有状态。

不要再新增：

passed
failed
result_status
test_status

等重复字段。

现有：

status + code + reason

继续保留并做回归测试即可。

--------------------------------------------------
四、内部年份字段保持兼容
--------------------------------------------------

当前 secret 内部使用：

month
year
cvc

不要为了本次修改强行把：

year

重命名为：

year_full

避免旧数据迁移和不必要数据库修改。

内部继续：

year = "2035"

需要两位年份时：

year[-2:]
→ "35"

需要 MM/YY：

month + "/" + year[-2:]

需要四位：

year

--------------------------------------------------
五、不要重新验证已经完成的 VPS 工作
--------------------------------------------------

这次是代码修复。

不要为了本任务：

SSH 用户 VPS
重新部署公网服务器
重新配置 GCP firewall
重新开放 3000
重新配置域名
重新测试公网 IP
重新测试 GitHub Public
重新安装 Docker

这些不是本次代码修复必要步骤。

最终代码全部完成后：

只需要在开发环境执行一次最终 Docker build / compose 验证。

不需要每修一个问题就重新 build Docker。

--------------------------------------------------
六、不要进行第三方 Production 实卡测试
--------------------------------------------------

不要为了验收：

登录真实 Preply 账号
向 Preply Production 填写测试数据
提交真实银行卡
测试真实 3DS
寻找真实 Production 支付页面

当前 Production UI-only 边界继续保留。

真正 Fill / Submit 的回归测试：

使用项目 Local Sandbox
或者明确授权的 QA / Staging / Internal fixture。

--------------------------------------------------
七、测试采用“最小必要测试”
--------------------------------------------------

修改某一个阶段时：

只运行该阶段相关测试。

例如：

修改 Import Normalizer：

先运行 importer tests。

修改 Network：

先运行 network tests。

修改 Runner：

先运行 runner / e2e pool tests。

不要每修改一个文件都：

backend 全测
frontend build
Docker build

全部功能完成以后，
再统一执行一次完整回归：

backend pytest
frontend lint
frontend build
必要 Browser E2E
Docker build/compose health

这样减少重复耗时和用量。

--------------------------------------------------
八、必须分 checkpoint
--------------------------------------------------

按照下面顺序工作。

CHECKPOINT 1

Import Normalizer
+
Expiry normalization
+
过期测试数据 WARNING
+
实际脏数据格式兼容

完成后：

运行相关 tests。

通过后：

git commit

建议：

fix: normalize imported resource data

然后再进入下一阶段。

--------------------------------------------------

CHECKPOINT 2

Network：

authenticated SOCKS5
network editing
credential change
Direct 默认选择修正

完成后：

运行 network 相关 tests。

通过后：

git commit

建议：

fix: support authenticated network resources

--------------------------------------------------

CHECKPOINT 3

Runner：

pre-submit resource failure
不能消耗 Test Data

Bad Account → Good Account

Bad Node → Good Node

Submit started 后禁止自动重新 Submit

完成后：

运行 runner/e2e 相关 tests。

通过后：

git commit

建议：

fix: preserve test data across resource failures

--------------------------------------------------

CHECKPOINT 4

Authorized origin allowlist

Import Preview UI

使用说明

已知文档错误

Result export 回归验证

然后执行最终完整测试。

通过后：

git commit

建议：

finish: complete runner reliability fixes

--------------------------------------------------
九、如果用量即将不足
--------------------------------------------------

如果预计剩余用量不足以完成下一个完整 checkpoint：

不要开始下一个大型修改。

停在当前已经通过测试的 checkpoint。

最后明确输出：

COMPLETED CHECKPOINT:
例如 1/4

LAST COMMIT:
commit hash

TESTS:
具体通过结果

NEXT:
下一步从哪个 checkpoint 开始

UNCOMMITTED CHANGES:
YES / NO

不要为了“看起来全部完成”仓促修改剩余代码。

--------------------------------------------------
十、如果用量突然中断在修改过程中
--------------------------------------------------

下次继续时：

先执行：

git status
git diff

检查当前留下的修改。

不要：

git reset --hard
重新 clone
重新开始
覆盖现有修改

如果已有上一阶段 commit：

直接从该 commit 后继续。

如果存在未提交修改：

先理解这些 diff 属于哪个未完成 checkpoint，
继续完成该 checkpoint。

不能把它们当垃圾直接删除。

--------------------------------------------------
十一、不要浪费用量 Push / GitHub 配置
--------------------------------------------------

每个 checkpoint 本地 commit 即可作为恢复点。

如果当前环境已经具备正常 push 能力，
且原工作流本来就会 push：

可以正常 push。

但如果没有：

不要为了 push 单独：

配置 token
配置 SSH key
重新登录 GitHub
检查 Public 权限

代码修改和测试优先。

最终再按当前已有仓库工作流处理。

--------------------------------------------------
十二、最终验收只做一次
--------------------------------------------------

四个 checkpoint 全部完成以后才进行：

1. backend full pytest

要求：
原 13 个基线测试不能减少
+
新增测试全部 PASS

2. frontend lint

3. frontend build

4. 必要的真实 Chromium Local Sandbox E2E

5. docker compose build / up / health

以上最终完整验证只运行一次。

如果某个外部环境没有提供：

例如真实 authenticated SOCKS5 upstream

不要寻找陌生公网代理来浪费用量。

可以：

使用本地受控测试 fixture

或者明确记录：

NOT TESTED

不能虚假写 PASS。

==================================================
最重要：
==================================================

优先修改代码，
不要花大量时间再次证明已经知道的事情。

已确认的信息直接使用。

已有正确实现直接保留。

只修改当前已经确认存在的问题。

用量不足时：

安全停在 checkpoint

而不是重新开始。

下次继续：

从最后 checkpoint 接着做。