---
ticket: GZ-JP-205
track: FULFILL
phase: D5
size: M
req_refs: [REQ-FULFILL-001, REQ-FULFILL-002, REQ-FULFILL-003, REQ-FULFILL-004, REQ-FULFILL-005, REQ-FULFILL-006]
depends_on: [GZ-JP-204, GZ-JP-106, GZ-JP-107]
touches:
  - code/main/miniapp-jp/src/pages/order/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.order_list
  - UI:mp.order_detail
  - UI:mp.order_detail.status_group
  - UI:mp.order_detail.item_row
  - UI:mp.order_detail.failed_group
accept:
  - name: 订单列表到详情可达且状态分组渲染
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs orders
  - name: 同一运单号在详情页只出现一次（分组的核心收益）
    form: API
    run: cd code/main/miniapp-jp && pnpm vitest run src/pages/order/detail.logic.test.ts
  - name: 页面不出现「包裹」字样
    form: API
    run: |
      ! grep -qE '包裹|package' code/main/miniapp-jp/src/pages/order/detail.vue
---

# GZ-JP-205 小程序订单列表 + 详情（按状态分组）

## §0 状态自检

1. GZ-JP-106/107 已 merge，dev 库有跨多状态的订单行可渲染。

## What

**列表**：按状态分 tab（全部 / 待支付 / 进行中 / 已完成）。卡片显示订单号 + 下单时间 +
前 N 个商品缩略图 + 款数 + 实付 + 订单状态。

**详情**：Kevin 已拍板走**按履约状态分组**（不是平铺）。

组按状态链顺序排：发货完毕 → 国内分拣中 → 清关中 → 日本仓库已发货 → 等待官方发货 →
购买中 → 购买失败。组头 = 「<状态> N 款」。

★ **已发货组的组头下方紧跟快递中文名 + 运单号 + 复制按钮，同一包裹只显示一次** ——
这是分组相对平铺的主要收益（30 款平铺时同一单号会重复十几次）。
同一状态但运单号不同时，按运单号再分子组。

购买失败组排最后，每行标「已退款 ¥xx」。

★ **全页不出现「包裹」二字** —— 客人不感知打包方式（REQ-FULFILL-006）。

## AC

- 30 款的订单在详情页可读（分组后不超过 7 个组）
- 单号复制走 `uni.setClipboardData`，**不引外部库**
- 已退款行金额显示正确
