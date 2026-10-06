---
ticket: GZ-SNAP-305
track: SNAP
phase: D10
size: L
req_refs: [REQ-SNAP-026, REQ-SNAP-027, REQ-SNAP-028, REQ-SNAP-029, REQ-SNAP-030, REQ-SNAP-036, REQ-SNAP-039, REQ-SNAP-043]
depends_on: [GZ-SNAP-304]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - doc/jp/_accept/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application-dev.yml
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/enums/GzFileUsageType.java
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/service/impl/GzFileServiceImpl.java
blueprint_refs:
  - FLOW:F-JP-07.step1
  - FLOW:F-JP-07.step2
  - FLOW:F-JP-07.step3
  - FLOW:F-JP-07.step4
  - FLOW:F-JP-07.step5
  - FLOW:F-JP-07.step6
  - FLOW:F-JP-12.step5
  - FLOW:F-JP-12.step6
  - FIELD:gz_jp_snap_purchase.manual_reason
  - FIELD:gz_jp_snap_purchase.reconcile_count
  - FIELD:gz_jp_snap_purchase.next_action_at
  - FIELD:gz_jp_snap_purchase.evidence_file_ids
  - FIELD:gz_jp_snap_account.today_count
  - OWN:mercari_purchase_fact
  - OWN:gz_jp_snap_purchase
  - OWN:snap_evidence
accept:
  - name: 对账只会自动得出成功：查不到（不论是否已售出）只排下一轮、满 3 轮转人工且不退款；第 2 轮才查到的按成功；不明期间绝不再下单
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapReconcileTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapReconcileTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapReconcileTest.xml
    counterfeit: 把「not_found + sold_out」判 failed 并退款、第一轮查不到就转人工（用例「第 2 轮查到 → success」红）、或对账失败后重新 POST /v1/purchases → 红
  - name: 账号选择：冷却中=留在队列等；无健康账号 / 都到日限=转人工；风控信号=停号+关总开关+queued 全转人工
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapExecutorTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapExecutorTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapExecutorTest.xml
    counterfeit: 单账号冷却 60s 内的第二单直接转人工、failed(shipping_changed / account_unpayable) 被当成失败退款、或余额不足关了全局总开关 → 红
  - name: 故障注入（真 HTTP 打 fake 驱动）：断网 / 超时 / 进程重启下，每单至多点一次购买，不明单零退款
    form: DATA
    run: bash doc/jp/_accept/snap-fault-injection.sh
    counterfeit: 超时后调度把 executing 任务重置为 queued 重跑 → fake 账本里同一 order_no 点击 2 次；或超时直接判 failed 退款 → 脚本对账两侧（fake 账本 vs gz_jp_refund）红
---

# GZ-SNAP-305 自动下单调度 + 结果三态 + 对账 + 风控熔断

## §0 状态自检

1. GZ-SNAP-304 完工；GZ-SNAP-301 的风控熔断方法与 `snapPurchaseExecutor` 线程池可直接复用。
2. **逐字读** `FLOW:F-JP-07.step1~6` 与 REQ-SNAP-029 note（对账口径 Kevin 2026-10-03 改过：只会自动得出成功）。
3. GZ-JP-107 行级退款入口（`mark-failed` 背后的 service 方法）——失败退款必须走它，不另写退款。
4. 日本服务本地以 fake 驱动跑（`GATEWAY_DRIVER=fake`），`/v1/_fake/script` 与 `/v1/_fake/ledger` 可用。

## What

1. 调度（每 5s，`gz.local-scheduler.enabled`）：取 `queued` 且到点的任务 → 选账号（`admin_enabled=1` + `healthy` + `pause_reason` 为空 + 未超日限 + 过冷却）：
   - 有健康账号仅冷却中 → 留 queued，`next_action_at` = 最早冷却结束；
   - 无健康账号或都到日限 → `manual_pending` + `no_account`；
   - 选中 → 条件更新抢任务（`WHERE purchase_status='queued' AND version=?`）置 `executing` + `account_code` + `executed_at`，`today_count+1`（按 Asia/Tokyo 换日清零）、`last_purchase_at`。
   自动下单总开关关闭时不取任务（已 queued 的由熔断批量转人工）。
2. 执行（线程池内）：`POST /v1/purchases`，`expect_shipping_payer` 取快照；结果映射：
   - success → step3（`trade_status=await_ship`、行 `await_seller_ship`、`actual_price_jpy`、`mercari_txn_id`、`result_at`）；
   - failed(sold_out / deleted / price_up) → step4（GZ-JP-107 退款、`releaseSnapLock`、`result_at`）；
   - failed(shipping_changed) → `manual_pending` + `shipping_changed`，不退款；
   - failed(account_unpayable) → `manual_pending` + `account_unpayable`，不退款；该账号 `admin_enabled` 不动、`pause_reason` 写明并视为不可派单（直到 admin 处理），
     error 日志；**不关全局总开关**（其他健康账号继续）；
   - unknown / 超时 / 任何异常 → `unknown`、`next_action_at=+30s`；`risk_signal=true` 另触发熔断。
   连续 3 次非业务失败（unknown 非 risk）同账号 → 熔断。
3. 对账（同调度取 `unknown` 且到点）：`GET /reconcile` → found → 成功出口；
   not_found（不论 `item_status`）/ 对账调用失败 → `reconcile_count+1`，下次 +2min / +10min；满 3 轮仍未 found → `manual_pending`，
   最后一次看到 `item_status≠on_sale` → `reconcile_sold`，否则 `reconcile_exhausted`（纸面推演 P5：最常见的不明是「点了购买、超时、其实买到了」，要给购买记录留刷新时间）。
   ★ 对账路径里**没有**任何调用 `POST /v1/purchases` 的代码，也没有任何发起退款的代码。
4. 重启恢复：应用启动时把 `executing` 且 `executed_at` 超过 60s 的任务改为 `unknown`（进对账），**不是**改回 queued。
5. 证据：响应里的 evidence 存 `gz_file_object(usage_type=snap_evidence)`，id 逗号串写 `evidence_file_ids`；存证失败不影响结果落库（error 日志）。
6. 故障注入脚本 `doc/jp/_accept/snap-fault-injection.sh`：起 fake 驱动 → 用 304 的提交 + 模拟支付回调造 3 单，分别脚本化为
   「点击后超时」「点击后断开连接」「执行中重启后端」→ 等调度与对账跑完 → 断言 ① fake 账本每个 order_no 点击次数 ≤1 ② 三单均无 `gz_jp_refund` 记录
   ③ 三单状态 ∈ {success, manual_pending}。脚本前置反 stale（8080 jar = 当前 commit）。

## AC

- 三条 accept 绿；REQ-SNAP-038 的「1 分钟」在 fake 驱动 success 场景下，`result_at - paid_time` < 60s（脚本顺带打印）。
- 不明状态下零重复下单、零退款（REQ-SNAP-039）。
