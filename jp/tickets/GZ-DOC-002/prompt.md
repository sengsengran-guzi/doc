---
ticket: GZ-DOC-002
track: SYS
phase: D0
size: S
req_refs: [REQ-FULFILL-003, REQ-FULFILL-004, REQ-FULFILL-005]
depends_on: []
touches:
  - doc/_adr/**
blueprint_refs:
  - FLOW:F-JP-03.step3
  - FLOW:F-JP-04.step2
  - FIELD:gz_jp_order_item.tracking_no
  - FIELD:gz_jp_order_item.fulfill_status
accept:
  - name: ADR 写明「不建包裹表」的理由与代价
    form: API
    run: |
      F=doc/_adr/0020-jp-batch-order-fulfillment-model.md; \
      test -f "$F" && grep -qE '包裹表|package' "$F" && grep -q 'tracking_no' "$F" && \
      grep -qE '(Accepted|已接受)' "$F"
  - name: 行级状态与行级退款两个决策都在（防只写一半）
    form: API
    run: |
      F=doc/_adr/0020-jp-batch-order-fulfillment-model.md; \
      grep -q 'order_item' "$F" && grep -qE '部分退款|行级退款' "$F" && \
      grep -qE 'partial_refunded' "$F"
---

# GZ-DOC-002 ADR-0020 日本拼团履约模型

## §0 状态自检

1. 确认 0020 编号未占用（GZ-DOC-001 占 0019）。

## What

本域有三个反直觉的建模决策，都需要留下出处：

**决策一：履约状态挂在订单商品行，不是订单上**
甲方原话「每一款商品都显示状态」+「一个客人买了 30 款，我们发货了 20 款」。
一单内各款进度天然不同，状态放订单级根本表达不了。

**决策二：不建包裹表**
甲方的实际操作是「勾一批 → 填一个顺丰单号 → 这 20 款都显示这个单号」。
**运单号本身就是包裹标识**，按 `tracking_no` 天然聚合即可。
代价：查不到「一个包裹里有哪些货」这种反查——但甲方不需要（客人不感知包裹，
后台按客人聚合看）。真需要时按 `tracking_no` group by 即可，不必预先建表。

> 演进记录：第一版设计曾建三层（订单/商品行/包裹），甲方 2026-08-05 的答复
> 说明包裹是隐式的，退回两层。

**决策三：退款是行级的部分退款**
因为状态粒度是行，退款必须跟着走行：30 款里 2 款没抢到只退这 2 款。
走微信部分退款，订单状态 rollup 为 `partial_refunded`（部分）/ `refunded`（全部）。
~~★ 实施前须硬查 `PayRefundController` 支持指定金额，不支持则 STOP。~~ **（已于 D0 执行完毕：不支持；路线已定为 jp 域独立退款入口，见 ADR-0020 §3。本卡已 close，此行仅存档）**

**附带口径**：「购买失败」不是异常而是常走的路（别人先买走 / 卖家取消 / 商品下架），
这条链路健壮性等同主链路。

## AC

- 落 `doc/_adr/0020-jp-batch-order-fulfillment-model.md`，状态 Accepted
- 三个决策各一段，每段写「为什么这么定 + 代价是什么 + 什么情况下要推翻」
