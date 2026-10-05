# 交接 · GZ-JP 二期代切 /zhixing 执行 —— 从 D8 续跑到 D12

> 写给接手的 AI。写于 2026-10-05 21:55。上一个会话跑完了 D7（QA 门通过并已合流），D8 第一张 ticket 做到一半时 API 限额中断。
> 读完本文即可接着跑，不需要上一个会话的聊天记录。**本文只覆盖执行现场**；需求、口径、铁律以下文列出的文件为准。

---

## 0. 你的任务（Kevin 原始指令，原样有效）

用 /zhixing 执行 GZ-JP 二期代切，**本轮只跑到 D12**：D12 的 QA 门通过后立即停，**不要派 D13**（GZ-SNAP-001 需要甲方的东京服务器、ISP 代理、煤炉账号，目前都没有）。

停下时交给 Kevin：
1. `task_state report` 进度表
2. 每个任务的 QA 报告路径与结论（D7 的已有，见 §2）
3. Tier 2 人验清单（GZ-SNAP-501 / 502 新页首版视觉、503 真机支付）
4. 全程所有 spec_conflict / blocked / 蓝图回流（authority_lint impact）汇总——**D7 已有一条，必须并进最终汇总**（见 §2）

## 1. 先读这些

| # | 文件 | 为什么 |
|---|---|---|
| 1 | `~/.claude/skills/zhixing/SKILL.md` + `templates/task-loop.md` | 执行方法论本体：任务档循环、QA 门 L0–L3、STOP 规则、返工血缘半径 |
| 2 | `.claude/CLAUDE.md`（项目根） | 项目铁律：不动 ruoyi 自带模块 / tenant_id / Flyway append-only 且时间戳取当下 / menu_id 先查活库与全部迁移 / i18n / 改 gz 模块后 mvn clean install 再重启 |
| 3 | `doc/jp/phase-plan.md` | 「二期 · 代切」三条不变量 + D8–D12 各任务的 ticket 与 **QA 范围** + 「交给 /zhixing 前的项目侧约定」（多仓拓扑 / **二期执行口径** / 外部替身白名单） |
| 4 | `doc/jp/_run/impl-brief.md` | **impl subagent 通用任务书**（上一会话打磨过，含已踩实的坑）。每个 impl subagent 都让它先读这份 |
| 5 | `doc/jp/_run/qa-brief.md` | **干净 QA subagent 通用任务书**（干净纪律、四级、必答四项、清理） |
| 6 | `doc/jp/qa/D7-r1.md`、`D7-r2.md`、`D7-rework-r1.md` | 看一遍 D7 的 QA 门长什么样、逮到了什么（并发 / RR 快照读） |
| 7 | 权威：`doc/jp/authority/*.yaml`（人读 `_rendered/`）、`doc/jp/requirements.yaml`、`doc/_adr/0025-jp-snap-mercari-gateway.md`、`doc/jp/19-代切链路纸面推演.md` | 派单与 QA 的依据 |

## 2. 当前进度（2026-10-05 21:55）

```
D0–D6  ✅ qa_passed（一期）
D7     ✅ qa_passed（QA r1 FAIL → 返工 → r2 PASS），已合进 feat/jp-snap
D8     ⬜ GZ-SNAP-201 pending（做了一半，见下）、GZ-SNAP-202 pending
D9–D12 ⬜ pending        D13–D15 ⬜ 不在本轮
```
权威状态：`doc/jp/waves/state.json`（**只用 sync，绝不 init**——init 会清掉进度）。

### D7 已产生、要并进最终汇总的事项
- **spec_conflict（已解决）**：GZ-SNAP-102 原要求「await_seller_ship→purchase_failed 仅对代切行放开、拼团行仍被拒」，与一期 GZ-JP-106 有意允许任意非终态→purchase_failed 矛盾。Kevin 2026-10-05 定**方案 A**：按来源判定入口，snap 允许，batch 与一期逐一相同。
- **蓝图回流**：`authority/flows.yaml` FLOW:F-JP-09.step1、`phase-plan.md` D7 QA 范围、`tickets/GZ-SNAP-102` What#5 + accept#0 已改；`change-log.md` 有记录；authority_lint impact 波及 102（已返工）/ 204 / 307（未开工、正文无旧口径）；快照已 `--force` 更新。
- **QA 返工**：FAIL-1（支付回调 vs 超时任务并发，RR 快照读把迟到付款记成 duplicated）+ O2（退款受理失败与回调竞态，从表无条件回写）已修，真库并发 + 变异验证。
- **跟进项（未修，非阻塞）**：
  - O-1：miniapp-jp `run.mjs all` 的 orders flow 偶发 `timeout waiting for automator response`（首个 gotoPage，单跑与同序重跑全绿），判装置抖动；**若再在同一位置复现，升级为产品缺陷排查**。
  - O-2：admin「重新发起退款」在回调已抢先落账时仍提示失败（钱已退，纯展示误报）；`markPurchaseFailedAndRefund` 守卫跳过时返回行显示 refund_failed。可放 D11 admin 或单独小卡，**需 Kevin 定**。
  - 现有小程序 `code/main/miniapp` 的 E2E 没有一条真把钱付完（kevin-check R6 tap 不命中）；D7 是靠 mp API 对真后端补测的。

### GZ-SNAP-201 断点
- 仓 `code/main/mercari-gateway/` 已建：`main`（ff4f57d 初始 .gitignore）→ `feat/jp-snap` → **`task/D8`**（abd1962：骨架、HMAC、health、fake/real/disabled 驱动、replay 读源、登录模式）。
- 中断时正在让 accept #2（docker compose 起容器 + 签名调 /v1/health）变绿，**6 个文件未提交**：`.env.example` `Dockerfile` `README.md` `docker-compose.yml` `docker/entrypoint.sh` `docker/login.sh`。`.env` 已存在（不进 git）。容器默认端口 **127.0.0.1:8700**。
- 续做：派一个新 impl subagent，告诉它上面这些事实，先 `git -C code/main/mercari-gateway diff` 看半成品，再从项目根用 `bash -c` 原样跑 201 的三条 accept，绿了 commit 到 task/D8。**本卡不访问真煤炉**。

### 下游提示（上一会话 impl 回报里的，派对应 ticket 时转告）
- **GZ-SNAP-304**：建 snap 订单行 insert 前调 `GzJpOrderItemSourceInvariant.check(item)`；报价写进 `JpOrderSnapshot.Product.snap`；锁释放加在 `GzJpUnpaidExpireTxService.cancelExpired` 同一 REQUIRES_NEW 事务内、仅 affected==1 时。**蓝图缺口**：FLOW:F-JP-06.step3 ⑥ 说「主图转存失败快照留原 URL 兜底」，但 field-ssot 的 snap 段没有 URL 字段——派 304 前要么先补 field-ssot（蓝图回流 + impact），要么让 impl 按 spec_conflict 报。
- **GZ-SNAP-306**：`GzJpRefundMapper.selectByOrderItemIds` 不区分 refund_type，有 shipping_diff 后 `createRefunds` 会误判「已退过」；shipping_diff 分支（不碰订单行、不参与 rollup）要加在 `applyRefundSuccess` / `applyRefundFailure` / `markAcceptFailed(IfRefunding)` 三处；从表写入必须看主单 affected。
- **GZ-SNAP-303**：准入结果枚举已叫 `GzJpSnapGateResult`，`GzJpSnapGate` 留给判定器。
- onPaid 扩展（304 写下单任务）：`replayPaid` 与 `reconcilePaid` 都会走到 `onPaid`，必须幂等、不调日本服务。
- 空号：jp 域错误码下一个 4117；字典 dict_id 9298 / dict_code 92866；sys_config config_id 14040006。
- `GzLocalJpScheduler` 已有开关 `gz.local-scheduler.enabled`（dev 缺省 false），新调度加 `@Scheduled` 方法即可。

## 3. 执行现场约定（上一会话踩出来的，照做）

**环境**
- `export PATH=/opt/homebrew/bin:$PATH`；python 用 `/opt/homebrew/bin/python3.11`（有 PyYAML）；pnpm 在 `~/.nvm/versions/node/v24.11.1/bin`。
- dev MySQL `docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue`（3307）；Redis `sensenran-dev-redis`（6380 / ruoyi123）。curl 打 localhost 必须 `--noproxy '*'`。
- **8080 后端现在是停的**（上一会话收尾停掉了）；日本服务容器也已 `docker compose stop`。开跑前：`bash doc/jp/_run/restart-backend.sh`（全量 clean install gz-* + 清迁移幽灵副本 + 起后端 + 等启动成功，带锁，日志 `/tmp/sensenran-run/backend.log`，输出带 commit 指纹，工作区脏时标 `+DIRTY-WORKTREE`）。D9 起日本服务 `cd code/main/mercari-gateway && docker compose up -d`（默认 replay + fake）。

**调度**
```bash
P=/opt/homebrew/bin/python3.11; T=~/claude-config/skills/zhixing/scripts/task_state.py; S=doc/jp/waves/state.json
$P $T --state $S next | report | set --ticket <T> --status running|done|failed|escalated|pending | set --phase <D> --status qa_running|qa_passed|qa_failed
```
- ⚠️ `next` **不检查与 running ticket 的 touches 冲突**：它会把与正在跑的 ticket 改同一模块的 ticket 也放进 spawn。派单前自己核一下，冲突就等。
- 每任务首次进 impl：把 accept.run 原样预跑一遍，必须红（依赖待产出脚本 / 测试类的记 N/A）。
- 三条 lint（开跑前已过，蓝图有变动时重跑）：`cd doc/jp` 后跑 coverage_lint / authority_lint check / dag_lint（命令见 phase-plan「lint 运行方式」）。已知不算红：coverage 3 条 clarify（REQ-SNAP-009/060/062）、dag 仅 C5 warning（exit 2）。蓝图改动后 `authority_lint diff → impact →` 处理受影响 ticket → `snapshot --force` → `render --out authority/_rendered`，并在 `change-log.md` 记一条。

**派单**
- impl：每 ticket 一个全新 subagent（项目 agent `kevin-coder`），prompt = 「先读 `doc/jp/_run/impl-brief.md`，再读 ticket」+ 上游事实 + 本卡特别注意。完工回报格式见 brief。
- QA：每任务末一个**干净** subagent（上一会话用 `general-purpose`），prompt = 「先读 `doc/jp/_run/qa-brief.md`」+ 任务范围 + Kevin 硬要求 + 并发形态点名。返工轮可读上一轮 QA 报告，**禁读 `D<N>-rework-*.md` 与 `tickets/*/report.md`**。返工轮必须全量重跑并重放 `doc/jp/regression/D<N>/` 资产。
- **子 agent 写 .md 会被 hook 拦截**：它们把报告全文放在最终回复里，由主线程落盘到 `doc/jp/tickets/<T>/report.md` / `doc/jp/qa/D<N>-r<k>.md` / `doc/jp/qa/D<N>-rework-r<k>.md`。
- 子 agent 被 API 限额 / 断连打断时（上一会话出现 3 次）：先查现场（各仓 git status、进程、DB 残留），再用 SendMessage 续它（保留上下文），不要新派一个从头来。

**已踩实的坑（brief 里已写，这里再点名）**
- 新 JUnit 测试类必须 `@Tag("dev")`（根 pom surefire `<groups>${profiles.active}</groups>`，否则 0 条、无报告、accept 的 grep 必红）。
- accept.run 一律 `bash -c` 跑（zsh 下 `rm -f *X*` 无匹配会 exit 1）。
- 守卫 UPDATE affected=0 后再 SELECT 区分原因 → 同事务一律 `FOR UPDATE` 当前读（MySQL RR）。两步写的从表一步必须看主单 affected。mock 单测照不出，QA 门靠真库双连接 + 摘守卫变异。
- impl 说某条要求不该做 → `escalated` + note `spec_conflict: ...`，**第一次就报 Kevin**（用提问工具给方案选项），不许跳过。同一环境障碍连续 2 次无进展 → `blocked` 报 Kevin。

**git（多仓）**
- 四个仓 `doc` / `RuoYi-Vue-Plus` / `plus-ui` / `miniapp-jp` 当前都在 `feat/jp-snap`、干净（RuoYi 有一个开工前就在的 `ruoyi-admin/logs/*.tmp`，忽略）。`mercari-gateway` 在 `task/D8`。
- 模型：`feat/jp-snap` 充当 integration；每任务在**受影响的代码仓**各建 `task/D<N>`（`git checkout -b task/D<N> feat/jp-snap`），impl / QA 资产 commit 在上面；QA 门过后按仓做 touches 对账（`git diff --name-only feat/jp-snap...task/D<N>` 对 front-matter touches，越界须是 impl 报告里声明过的），然后 `merge --no-ff` 回 `feat/jp-snap`，**后端先合、前端后合**。commit 末行 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。
- `doc` 仓直接在 `feat/jp-snap` 上由主线程提交（state、报告、蓝图回流）。**不 push、不合 staging**。
- `code/main/miniapp`（现有小程序）**只读不改**。

**外部依赖（硬性）**
- 煤炉读 = 回放样本（`GATEWAY_READ_SOURCE=replay`）；煤炉写 = fake 驱动；翻译 = mock；微信支付 = mock 通道 + simulate-callback。QA 不得判它们为 mock 自证，但业务数据必须真 seed + 真库对账。
- **真煤炉只允许 GZ-SNAP-202**：live 契约测试单次 ≤5 次请求、回放样本录制一次性 ≤15 次，出口是 Kevin 的个人代理 IP。建议给 202 的 impl 定死：live accept 最多跑 2 次、录制只跑 1 次，脚本内置计数上限。**QA 门、返工、E2E 任何环节都不准打真煤炉，不准写循环或批量请求**——D8 QA 跑 202 的测试时必须排除 `-m live`。

**E2E 串行**：mp 模拟器 E2E 与 admin Playwright 一律串行（devtools / 8080 共享单例），两个小程序的 E2E 也互相串行。

**收尾**：停下前关掉自己起的后台进程（8080 后端：`lsof -tnP -iTCP:8080 -sTCP:LISTEN` 杀掉；日本服务：`docker compose stop`；plus-ui dev server 等），然后交付 §0 的四样。

## 4. 各任务特别提醒

- **D8**（201、202）：Python 新仓，QA 范围见 phase-plan。202 依赖 201。202 的回放样本要覆盖下游需要的类别（拒代购描述 / 到付 / Shops / 已售出等，见 `doc/jp/_spike/mercari-probe/READ-PROBE-2026-10-03.md`），否则 D9 的 303 / D12 的 502 没法测。
- **D9**：QA 需要日本服务在本地跑；`_accept/snap-submit-race.sh` 由 304 产出，须自带反 stale 前置。一期拼团下单 / 支付回调回归。
- **D10**：二期最重的门（故障注入 `_accept/snap-fault-injection.sh`、对账只自动得出成功、风控熔断、到付差价退款不碰订单行）。注意 306 的提示（§2）。
- **D11**：admin 五页，菜单 14040–14089——**分配前查活库 sys_menu + grep 全部迁移**（本项目撞号 3 次）；配置保存要清 Caffeine + Redis 两级缓存；会触发退款的操作要二次确认。
- **D12**：mp 四页；token 只走 `c-tokens.scss`；详情页源码与文案不出现汇率与加价比例；501/502/503 进 Tier 2 人验清单。
