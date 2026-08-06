---
ticket: GZ-JP-203
track: ORDER
phase: D4
size: M
req_refs: [REQ-ORDER-005, REQ-ORDER-004]
depends_on: [GZ-JP-202, GZ-JP-104]
touches:
  - code/main/miniapp-jp/src/pages/cart/**
  - code/main/miniapp-jp/src/api/gz-jp/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.cart
  - UI:mp.cart.group
  - UI:mp.cart.summary
accept:
  - name: 加购到结算全流程可走通
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs cart
  - name: 底部合计区无运费行（全包邮）
    form: API
    run: |
      ! grep -qE '运费|freight|shipping.?fee' code/main/miniapp-jp/src/pages/cart/index.vue
---

# GZ-JP-203 小程序购物车

## §0 状态自检

1. GZ-JP-104 接口可调。

## What

按场分组列出购物车项：商品图 + 名 + 单价 + 数量 stepper + 删除 + 单选框。
底部固定条：全选 + 合计（标注「已包邮」）+「去结算」。

失效项（场已结束 / 商品已下架）置灰标「已失效」，不计入合计、不可勾选。

★ 底部只有**商品合计**一行，**不出现运费行** —— 全包邮。

## AC

- 跨场商品同车共存，按场分组显示
- 改数量实时刷新合计
- 失效项不可勾选且不计入合计
- 未勾选任何项时「去结算」置灰
