---
ticket: GZ-SNAP-307
track: SNAP
phase: D10
size: L
req_refs: [REQ-SNAP-025, REQ-SNAP-032, REQ-SNAP-033, REQ-SNAP-034]
depends_on: [GZ-SNAP-306]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FLOW:F-JP-09.step1
  - FLOW:F-JP-09.step1b
  - FLOW:F-JP-09.step2
  - FLOW:F-JP-09.step3
  - FLOW:F-JP-09.step4
  - FLOW:F-JP-09.step5
  - FLOW:F-JP-12.step7
  - FIELD:gz_jp_snap_purchase.trade_status
  - FIELD:gz_jp_snap_purchase.rate_deadline_at
  - FIELD:gz_jp_snap_purchase.actual_shipping_jpy
  - UI:admin.fulfill_board.snap
accept:
  - name: 交易状态机：只能按序推进；交易取消只能从待发货 / 已发货出发；到付商品「已到仓」必须带实际运费并触发差价退款；取消 / 退货退款扣掉已退差价
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapTradeTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapTradeTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapTradeTest.xml
    counterfeit: 允许 await_ship 直接点「已评价」、已到仓后还能标交易取消、到付商品不填运费也能「已到仓」、或退货时按 amount_cent 全额再退（与已退差价叠加超退）→ 红
  - name: 履约看板后端守卫：未评价的代切行混进批量推进 / 发货 / 标失败，整批拒绝并指出行号
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpFulfillSnapGuardTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpFulfillSnapGuardTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpFulfillSnapGuardTest.xml
    counterfeit: 守卫只做在前端（接口仍放行）、静默跳过未评价行只推其余行、或守卫把系统自己的卖家取消 / 退货退款也拦了 → 红
---

# GZ-SNAP-307 交易巡检落账 + 到仓 / 验货 / 评价 / 退货 + 评价提醒 + 履约守卫

## §0 状态自检

1. GZ-SNAP-306 完工（`purchase_failed` 退款额已扣 shipping_diff）。
2. 读 `FLOW:F-JP-09` 全部步骤（含新增 step1b 手工通道）与 `FLOW:F-JP-12.step7`。
3. 一期 `GzJpFulfillController` 三个写接口 `/advance` `/ship` `/mark-failed` 背后的 service 方法——守卫加在 service 层。

## What

1. 巡检任务（间隔读 `gz.jp.snap.trade.patrolMinutes`，默认 20）：按账号 `GET /v1/trades` → 对 `trade_status ∈ {await_ship, shipped}` 的交易：
   卖家已发货 → `shipped`；卖家取消 → `cancelled` + `fail_reason=seller_cancel` → 订单行 `purchase_failed`（102 放开的转移）→ 退款 + `releaseSnapLock`。巡检失败只记日志。
2. admin 交易操作（`/system/gz/jp/snap/trade`）：
   - `POST /{id}/seller-shipped`（只允许从 `await_ship` 出发）、`POST /{id}/trade-cancel`（step1b，允许从 `await_ship` 或 `shipped` 出发——含已发货后丢件、事务局取消；幂等）；
   - `POST /{id}/arrived {actualShippingJpy?}`（`shipped→arrived`，写 `arrived_at`、`rate_deadline_at = arrived_at + rateDeadlineHours`）；
     到付商品（快照 `shippingPayer=buyer`）`actualShippingJpy` 必填 → 落 `actual_shipping_jpy` → 调 306 的 `refundShippingDiff`（纸面推演 P3）；
   - `POST /{id}/rated`（`arrived→rated`）；`POST /{id}/returned`（`arrived→returned` + `fail_reason=inspect_ng` → 行 `purchase_failed` → 退款）。
   - `GET /list?tradeStatus=`：默认按 `rate_deadline_at` 升序；`GET /reminder-count`：`rate_deadline_at` 在 12h 内且未评价的条数（菜单角标用）。
3. 履约守卫：一期批量推进 / 批量发货 / 标记购买失败三个 **admin 入口**，入参行里只要有 `source=snap` 且 `trade_status≠rated` 的行 → 整批拒绝，错误信息列出这些行 id。
   代切自己的系统路径（305 自动失败、本卡交易取消 / 退货完成）把行改 `purchase_failed` 时调用守卫之下的内部方法，不受守卫拦截（纸面推演 P10）。
4. 交易状态只进不退；非法转移返回业务错误码。

## AC

- 两条 accept 绿；一期履约状态机单测照旧绿。
- 卖家取消 / 验货不通过两条退款路径，退款额都 = 实付中尚未退的部分（不超退）。
