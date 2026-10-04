---
ticket: GZ-SNAP-306
track: SNAP
phase: D10
size: M
req_refs: [REQ-SNAP-023, REQ-SNAP-024, REQ-SNAP-025, REQ-SNAP-031]
depends_on: [GZ-SNAP-305, GZ-JP-111]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FLOW:F-JP-08.step1
  - FLOW:F-JP-08.step2
  - FLOW:F-JP-08.step3
  - FLOW:F-JP-09.step2
  - FIELD:gz_jp_refund.refund_type
  - FIELD:gz_jp_snap_purchase.actual_shipping_jpy
  - FIELD:gz_jp_snap_purchase.manual_operator
  - OWN:snap_money
accept:
  - name: 退款服务按类型分支：差价退款金额 = 预估 − 实际换算（向上取整）、≤0 不退、回调不改订单行且订单仍 paid；之后的失败退款扣掉已退差价
    form: DATA
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpShippingDiffRefundTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpShippingDiffRefundTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpShippingDiffRefundTest.xml
    counterfeit: shipping_diff 回调沿用一期落账（写行 refund_status=refunded + rollup）→ 一单一件的订单被汇总成 refunded；或卖家取消时按 amount_cent 全额再退（超退）→ 红
  - name: 人工填结果只能从 manual_pending 出发；填成功必须带煤炉交易号且实际价不高于锁定价；填失败走全额退款并释放锁
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapManualTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapManualTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapManualTest.xml
    counterfeit: 允许对 success 的任务再「填失败」（已买到又退款），或实际价高于锁定价也能填成功（与自动下单涨价口径不一致）→ 红
---

# GZ-SNAP-306 人工代买 API + 退款服务按类型分支（到付差价）

## §0 状态自检

1. GZ-SNAP-305 / GZ-JP-111 完工。
2. 读 `FLOW:F-JP-08` 全部三步、`FIELD:gz_jp_refund.refund_type` 注释（只有 purchase_failed 参与行状态与 rollup）。
3. `GzJpRefundServiceImpl` 的发起与回调落账两个方法 —— 本卡在它们里面按 `refund_type` 分支，不另起一套退款服务。

## What

admin 接口（`/system/gz/jp/snap/purchase`，权限串 `gz:jp:snap:purchase:*`，菜单在 GZ-SNAP-401 建）：

1. `GET /manual-list`：`manual_pending` 按付款时间升序，含入队原因、商品原链接、锁定日元价、到付预估运费、证据缩略图 id。
2. `POST /{id}/manual-success {mercariTxnId, actualPriceJpy}`：出口与自动成功同一方法。
   `actualPriceJpy > locked_price_jpy` → 拒（业务码 `SNAP_MANUAL_PRICE_UP`，提示改填失败·涨价），与自动下单的涨价口径一致（纸面推演 P13）。
   **不在这一步填到付运费**：着払い是货到转运仓时才付、才知道金额，由 GZ-SNAP-307 的「已到仓」接口收运费并调用下面的差价退款（纸面推演 P3）。
3. `POST /{id}/manual-fail {failReason, note}`：出口与自动失败同一方法（全额退款 + `releaseSnapLock`）。
4. 退款服务按 `refund_type` 分支（提供 `refundShippingDiff(orderItemId, actualShippingJpy)` 给 307 调用：按快照锁定汇率算 `diff = estShippingCent − ceil(actualShippingJpy × rate/100 × 100)`，>0 才发起）：
   - `shipping_diff`：发起与回调都**不写**订单行 `refund_status` / `refund_amount_cent` / `fulfill_status`，**不做** rollup；
   - `purchase_failed`：退款额 = `amount_cent − 该行已成功的 shipping_diff 金额`（为 GZ-SNAP-307 卖家取消 / 验货不通过准备）。
5. 写操作记 `manual_operator` / `manual_note`；对 success / failed 终态的任务再提交一律拒（409 业务码）。

## AC

- 两条 accept 绿；一期退款单测（`GzJpRefundStatusRollupTest` / `GzJpRefundCallbackIdempotentTest`）照旧绿。
- 同一行所有非失败退款单金额之和 ≤ `amount_cent`（QA 门用 SQL 对账）。
