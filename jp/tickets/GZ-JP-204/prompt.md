---
ticket: GZ-JP-204
track: ORDER
phase: D4
size: M
req_refs: [REQ-ORDER-003, REQ-ORDER-004, REQ-ORDER-006]
depends_on: [GZ-JP-203, GZ-JP-105]
touches:
  - code/main/miniapp-jp/src/pages/order/**
  - code/main/miniapp-jp/src/composables/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.order_confirm
  - UI:mp.order_confirm.summary
  - FLOW:F-JP-02.step3
  - FLOW:F-JP-02.step5
accept:
  - name: 下单确认到支付调起全流程（dev mock 支付）
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs checkout
  - name: 金额区只有商品合计与实付两行，无运费
    form: API
    run: |
      ! grep -qE '运费|freight|shipping.?fee' code/main/miniapp-jp/src/pages/order/confirm.vue
---

# GZ-JP-204 小程序下单确认 + 支付

## §0 状态自检

1. GZ-JP-105 下单接口可调；GZ-SYS-022 支付多 appid 已 merge。
2. dev 环境 `VITE_MOCK_PAY` 与后端 mock 支付通道对齐（dev 走
   `/app/gz/test/pay/simulate-callback` 驱动结算，**用户自助版不是 admin 版**）。

## What

收货地址（选择/新增）→ 商品清单（只读）→ 备注 → 合计 →「提交订单」→ 拉起微信支付 → 支付结果轮询页。

★ 金额区**只有「商品合计」与「实付」两行，无运费行**。

提交前后端复校（场 open / 商品 on_shelf / 价格未变），不一致则退回购物车并提示具体哪件失效。

## AC

- 地址必选，未选不可提交
- 提交后拉起微信支付；dev 下可用 mock 通道走完结算
- 支付成功跳订单详情，失败/取消回到订单列表待支付 tab
