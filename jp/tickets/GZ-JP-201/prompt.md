---
ticket: GZ-JP-201
track: EVENT
phase: D3
size: M
req_refs: [REQ-SYS-001, REQ-EVENT-001]
depends_on: [GZ-JP-002, GZ-JP-103]
touches:
  - code/main/miniapp-jp/src/pages/index/**
  - code/main/miniapp-jp/src/api/gz-jp/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.home
  - UI:mp.home.banner
  - UI:mp.home.event_card
  - UI:mp.home.order_entry
accept:
  - name: 首页三区块渲染且场卡片来自真后端
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs home
  - name: 无 banner 配置时降级为默认图，不出现空轮播
    form: API
    run: cd code/main/miniapp-jp && pnpm vitest run src/pages/index/index.logic.test.ts
---

# GZ-JP-201 小程序首页（聚合）

## §0 状态自检

1. GZ-JP-103 接口可调（`curl /app/gz/jp/event/list` 有数据）。
2. 确认 `sys_config` 里 banner 配置 key 的命名（沿用现有 miniapp 的 `gz.home.banners` 形态）。

## What

Kevin 已拍板首页做**聚合**（不是裸场列表）。自上而下三块：

1. **轮播 banner** —— 走 `sys_config` 后台可配。★ 一期无运营内容，
   **无配置时降级为单张默认图**，绝不显示空轮播或占位骨架
2. **进行中的场** —— 纵向卡片流，分「进行中 / 即将开始 / 已结束」三组，进行中置顶
3. **我的订单快捷入口** —— 带待收货款数角标

## AC

- 三区块齐、点场卡进场详情、点订单入口进订单列表
- banner 无配置时不塌陷
- E2E flow `home` 断言：场卡片文案来自后端真数据（不是前端 mock）
