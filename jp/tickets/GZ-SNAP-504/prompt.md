---
ticket: GZ-SNAP-504
track: SNAP-MP
phase: D12
size: M
req_refs: [REQ-SNAP-031, REQ-SNAP-033, REQ-SNAP-038]
depends_on: [GZ-SNAP-503]
touches:
  - code/main/miniapp-jp/src/pages/order/**
  - code/main/miniapp-jp/src/api/gz-jp/**
  - code/main/miniapp-jp/src/locale/**
  - code/main/miniapp-jp/test/e2e/flows/**
  - code/main/miniapp-jp/test/e2e/run.mjs
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - UI:mp.order_detail.snap
  - UI:mp.order_list
  - FIELD:gz_jp_snap_purchase.purchase_status
  - FIELD:gz_jp_snap_purchase.trade_status
accept:
  - name: 代切状态映射单测：executing / unknown 统一「抢购中」、不暴露「结果不明」；运费差价行只在有已退 shipping_diff 时出现
    form: STATE
    run: cd code/main/miniapp-jp && npx vitest run src/pages/order/detail.snap.logic.test.ts
    counterfeit: unknown 显示成「结果不明 / 对账中」，或差价行把 refunding 中的退款也算进去 → 红
  - name: 模拟器 E2E：付款后订单详情抢购中轮询，fake 驱动 success 后 60 秒内变「已抢到」；failed 变「未抢到·已退款」
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs snap-order
    counterfeit: 只在进入页面时取一次状态不轮询，或轮询无上限 → flow 红
---

# GZ-SNAP-504 mp 订单列表 / 详情的代切状态

## §0 状态自检

1. GZ-SNAP-305~307 完工；一期 `pages/order/detail.vue` + `detail.logic.ts` 结构。
2. 读 `UI:mp.order_detail.snap`、REQ-SNAP-038 note（「1 分钟」只算自动通道）。

## What

1. 后端 mp 订单详情 / 列表接口给 snap 行补：`snapStatus`（映射后的展示态，不下发原始 purchase_status）、`snapTradeStatus`、已退运费差价 `shippingDiffRefundedCent`。
2. 详情：snap 行在一期履约状态前多一段代切状态：抢购中 → 已抢到 / 未抢到·已退款 / 人工处理中 → 等待卖家发货 → 卖家已发货 → 已到日本仓 → 验货通过（之后接一期状态）。
   抢购中每 3s 轮询、最多 60s，之后显示「刷新」按钮。金额区「运费差价已退 ¥x」。
   抢到之后交易被取消（卖家取消 / 丢件 / 事务局取消）或验货不通过：显示「交易取消·已退款」/「验货未通过·已退款」，与「未抢到·已退款」区分开。
3. 列表：代切单卡片加「代切」标签与当前代切展示态。
4. 映射逻辑放 `detail.snap.logic.ts` + 单测；E2E flow `snap-order.mjs`（fake 驱动脚本化 success / failed 两单）。

## AC

- 两条 accept 绿；一期 orders flow 不回归。
