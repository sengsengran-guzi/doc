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

1. ~~硬查 `PayRefundController` 是否支持指定金额~~ —— **D0 已查完，结论：不支持**。
   四道闸：`RefundApplyBo` 无金额入参（javadoc「仅全额退款」）、`PayRefundServiceImpl.apply` 两个金额位都传全额、
   **`PayRefundTxService.createRefunding` 的 `countActiveByTransactionId>0` 即拒（一笔支付只允许一条退款单）**、
   `gz_pay_transaction.refunded` 是终态。但**通道层 `IWechatPayClient.refund` 本就支持**
   （record 已含 `refundAmountCent` + `totalAmountCent`）。

   ★ **路线已定（Kevin 2026-08-06）：走 jp 域独立退款入口，只共用通道层。**
   新建 jp 专用退款 Service + 退款单表，直接调 `IWechatPayClient.refund`；
   **不要去动 `PayRefundController` / `PayRefundTxService`** —— 那是拼豆与回收在用的线上资金链路。
   详见 ADR-0020 §3。

2. 确认 `IWechatPayClient.refund(RefundRequest)` 的 record 字段与 mock 实现（照 `MockWechatPayClient` 的形态写 jp 侧调用）：
   `grep -rn "record RefundRequest\|class MockWechatPayClient" ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/service/internal/`
   —— 确认 `refundAmountCent` 与 `totalAmountCent` 是两个独立参数（这是走路线②的前提）。
3. 确认 `RefundCallbackDispatcher` 的 SPI 签名，照现有 `PreorderRefundCallbackHandler` 范式写。
4. ★ 开工前 `git -C code/main/RuoYi-Vue-Plus status --porcelain` 记下基线 —— 完工时要能用 `git diff`
   证明 `pay/controller/PayRefundController.java`、`pay/service/impl/PayRefundServiceImpl.java`、
   `pay/service/PayRefundTxService.java` **一行没动**。这是本卡的硬验收条件之一。

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
