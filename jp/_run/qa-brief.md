# 干净 QA subagent 通用任务书（GZ-JP 二期代切 · /zhixing 任务 QA 门）

## Kevin 最新执行授权（2026-10-06，优先于本文旧 STOP / 全量重复测试要求）

Kevin 已要求继续到 D12，减少不必要测试，遇到类似样本缺口、工具链或可兼容技术问题自行判断并调整，不因重复尝试次数单独停工。调整须记入报告；涉及蓝图则同步权威、impact 与 change-log。每期保留独立 QA，验证本期实际变更及关键权限、资金、幂等、并发不变量；已有有效证据可复用，避免重复全项目测试、无关 UI 回归与机械变异验证。真实煤炉请求预算、不 push、不合 staging、主 miniapp 只读等红线不变。QA / 返工 / E2E 不调用真实煤炉，202 live 命令不在 QA 重跑。


你是**全新上下文的独立 QA**，对一个任务（D<N>）做定向 L0–L3 验证，聚焦本期实际改动与关键不变量。项目根 = `/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi`。

## 干净纪律（硬性）
- **禁止读**实现方的解释：`doc/jp/tickets/*/report.md`、实现方 commit message 正文里的自评、主线程转述。你只看：ticket `prompt.md`（What / AC / accept）、权威蓝图、需求、ADR、phase-plan 的该任务「QA 范围」、以及**代码本身**。
- 看代码是允许且鼓励的：每个代码仓 `git -C <仓> diff feat/jp-snap...task/D<N>` 取改动面（返工轮尤其要看——修复引入新回归是高发项）。
- 你的结论只基于你亲手跑出的 raw output。

## 必读
1. `doc/jp/phase-plan.md`：「二期 · 代切」开头三条不变量 + 本任务 D<N> 节的「QA 范围」（**逐条都要覆盖**）+ 「二期执行口径」（外部替身白名单）。
2. 本任务所有 ticket 的 `doc/jp/tickets/<T>/prompt.md`。
3. 权威：`doc/jp/authority/*.yaml`（人读 `_rendered/*.md`）、`doc/jp/requirements.yaml`、`doc/_adr/0025-jp-snap-mercari-gateway.md`、`doc/jp/19-代切链路纸面推演.md`。
4. 项目铁律 `.claude/CLAUDE.md`；项目 QA 经验 `.claude/agents/kevin-qa.md`（E2E harness 用法、坑）；记忆索引 `~/.claude/projects/-Users-wkui-Project-profile-project-freelance-projects-sensenran-guzi/memory/MEMORY.md`。
5. L1 回归包原子：`doc/jp/verify.sh`（一期留下的反 stale 守卫 + 公共字段 + 跨表对账 + C 端契约），以及 `doc/jp/_accept/` 下已有脚本。

## 环境
- 本机共享restart脚本已改用专用launchd任务 `dev.sensenran-guzi.jp-snap.backend` 保活，工具会话结束不会清理8080；依然只用共享脚本启动/重启。运行选项只保存在权限600的 `/tmp/sensenran-run/backend-options.json`，不打印/提交。最终由主线程 `launchctl remove` 停自己的任务并检查8080。
- `rg` 当前不可用，直接用 `grep`/`find`；Docker准确路径 `/usr/local/bin/docker`。宿主审批timeout不算已执行，不无限重复；直接绝对工具命令可用。默认沙箱Mockito自附加失败可用已有mockito-core jar经JAVA_TOOL_OPTIONS加载agent，不引依赖。
- `export PATH=/opt/homebrew/bin:$PATH`。curl 打 localhost 一律 `--noproxy '*'`；Playwright / node 打 localhost 设 `NO_PROXY=localhost,127.0.0.1`。
- MySQL `docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue`；Redis `sensenran-dev-redis`（6380 / ruoyi123）。admin 账号 `gz_owner/gz_owner123!`（租户 1001）、`admin/admin123`。
- 后端 8080 共享单例：要让它跑当前 task 分支代码，**只用**共享重启脚本（带锁、clean install、清幽灵迁移、等启动成功）：
  `bash /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/_run/restart-backend.sh`
- plus-ui 若需起 dev server：`pnpm dev -- --port 8090`（后台起，结束时你自己关掉）。
- mp 模拟器 E2E只运行 `code/main/miniapp-jp/test/e2e/run.mjs`，各flow串行共享devtools。`code/main/miniapp`本轮全目录只读，不在该目录build/test或生成任何产物。每条flow按现有harness独立会话；devtools普通装置问题自行排查。
- 外部替身白名单：煤炉读 = 回放样本、煤炉写 = fake 驱动、翻译 = mock、微信支付 = mock 通道 + simulate-callback。**这些不算 mock 自证**，但业务数据必须真 seed + 真库对账（禁自造数据自证：断言要打在实现方没写过的数据上）。
- **绝不打真煤炉**，不写循环 / 批量外部请求。不跑 migration 之外的 destructive SQL；你造的测试数据用精确 WHERE 硬删清理。
- 不改产品代码。你可以新增测试资产（`regression/` 下的脚本、E2E flow / spec），放在对应代码仓的 task/D<N> 分支并 commit（消息 `test(jp-snap): D<N> QA ...` + 末行 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`），或放 `doc/jp/regression/D<N>/`（doc 仓不 commit）。

## 四级
| 级 | 要求 |
|---|---|
| L0 | 复用同一生产源码的已核实干净构建证据；代码变化后必要重建 + 本期关键单测（`-DskipTests=false`）+ plus-ui `pnpm build:prod`（如本任务改了 plus-ui）+ miniapp-jp 生产 build（如改了 mp）+ 迁移已 commit。**每个绿都带实际执行条数**（surefire tests/failures/errors/skipped 汇总），0 条或新增测试文件后条数没涨 = FAIL |
| L1 | 真 seed + 跨表对账 SQL；QA 范围里的 DDL / DATA / STATE 逐条；**并发形态**（任务里有先读后写同一行 / upsert / 计数器 / 外部写入点时强制）：至少一轮≥2独立连接真并发，断言打在DB不变量与外部副作用次数（不只看HTTP200）；不机械重复三轮或做锁/唯一键变异，仅实际失败或未解决风险需要时追加 |
| L2 | 端侧：admin Playwright（本任务改动页面及直接受影响的一期spec）、mp 模拟器 E2E（本任务改动flow及直接受影响的一期flow）。**反 stale**：先确认 8080 跑的是当前 task 分支 commit 构建的 jar、mp dist 是当前源码构建；**反空转**：每个 flow 至少一条「数据真来自后端」的证据 |
| L3 | 邪路：跨日期边界 / 非超管权限（用 gz_owner 或无权限角色）/ 空数据 / 同日区间 / 并发（同 L1 标准），每类至少 1 条，与本任务相关的都要做 |

## 报告
**若写 .md 被 hook 拦截（Claude Code 子 agent 常见）**：报告全文放在最终回复末尾（「==== 报告全文 ====」之后），主线程落盘到 `doc/jp/qa/D<N>-r<轮次>.md`。测试脚本 / spec 等非 md 资产照常写文件。**必答四项**（答不出 = 本轮作废）：
① 各级实际跑了多少条用例 / 断言（贴 raw）；
② 被测产物指纹由被测系统自报（如运行中后端的启动日志 / 某接口返回的 build 信息 / jar mtime 与 commit），与本次构建对得上；
③ 每类探针（SQL / HTTP / 选择器 / grep）本轮取到过的一个**确定存在**的锚（证明探针没瞎）；
④ 本轮的绿**不覆盖什么**：≤3 条，每条指名一个具体缺陷类。

另列：每条「QA 范围」条目 → PASS / FAIL + 证据位置；所有 FAIL 的复现步骤 + 失败用例**单独复跑**的结果（单跑也红 = 产品缺陷；单跑绿全跑红 = 未定，按产品缺陷报，除非能指出具体装置污染机制）。

## 收尾
- 关掉你自己起的所有进程（dev server、devtools 自动化会话等），8080 后端保留运行（若你重启过，它应在跑当前 task 分支代码）。
- 清理你造的测试数据（精确硬删），报告里列出清理 SQL。

## 最终回复格式（给主线程）
```
VERDICT: PASS | FAIL | VOID(装置问题，说明)
TASK: D<N>  ROUND: r<k>
REPORT: 见下方报告全文
COUNTS: L0 <n> / L1 <n> / L2 <n> / L3 <n>
FAILS:（每条一行：ID | 级 | 关联 ticket | 现象 | 单跑复现? | 涉及文件）
NOT_COVERED: ≤3 条
```
