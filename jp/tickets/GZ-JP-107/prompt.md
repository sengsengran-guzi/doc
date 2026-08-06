---
ticket: GZ-JP-107
track: FULFILL
phase: D5
size: L
req_refs: [REQ-FULFILL-005]
depends_on: [GZ-JP-106]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FLOW:F-JP-04.step1
  - FLOW:F-JP-04.step2
  - FLOW:F-JP-04.step3
  - FIELD:gz_jp_order_item.refund_status
  - FIELD:gz_jp_order.business_status
accept:
  - name: 退款金额等于该行金额，不是整单
    form: DATA
    run: |
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
        SELECT COUNT(*) FROM gz_jp_order_item
        WHERE refund_status='refunded' AND refund_amount_cent <> amount_cent AND del_flag='0'" | grep -qx 0
  - name: 部分行失败时订单转 partial_refunded，全失败才 refunded
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpRefundStatusRollupTest 2>&1 | tail -5
  - name: 退款回调幂等（重复回调不重复退）
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
        -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpRefundCallbackIdempotentTest 2>&1 | tail -5
---

# GZ-JP-107 行级退款（购买失败 → 微信部分退款）

## §0 状态自检（★ 本卡最关键的一步）

1. **硬查 `PayRefundController` 的 apply 接口是否支持指定退款金额**：
   `grep -n "refund" -r ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/controller/PayRefundController.java`
   以及其 BO 的字段。
   - 支持指定金额 → 按本卡设计做
   - **不支持（只能整单退）→ 立刻 STOP 报 Kevin**，改走「整单退 + 人工补差」或先扩展 PAY 侧能力。
     不要闷头实现，这是 doc/17 §6 R3 明确标出的风险点。
2. 确认 `RefundCallbackDispatcher` 的 SPI 签名，照现有 `PreorderRefundCallbackHandler` 范式写。

## What

因为状态粒度是商品行（REQ-FULFILL-003），退款也必须是**行级**：
一单 30 款里 2 款没抢到，**只退这 2 款的钱**，走微信部分退款。

- `POST /system/gz/jp/fulfill/mark-failed`，入参 `{itemIds: []}`（可批量）
- 每行置 `fulfill_status=purchase_failed` + `refund_status=refunding`
- 按 **该行 `amount_cent`** 发起微信退款（不是订单总额）
- 退款回调 → `refund_status=refunded` + `refund_amount_cent` 落值
- 订单状态 rollup：有失败行且非全部 → `partial_refunded`；全部行失败 → `refunded`

## AC

- 退款金额恒等于该行 `amount_cent`
- 订单状态 rollup 正确（部分 / 全部两种情形）
- 回调幂等
- 退款失败有明确落库状态（`refund_failed`）+ admin 可见，不静默吞

## ⚠️ 甲方口径

「购买失败」不是异常而是**常走的路**（别人先买走、卖家取消、商品下架都会导致）。
这条链路的健壮性等同主链路，不能按边缘 case 对待。
