---
ticket: GZ-JP-202
track: PROD
phase: D3
size: M
req_refs: [REQ-PROD-003, REQ-PROD-004, REQ-PROD-005, REQ-ORDER-004]
depends_on: [GZ-JP-201]
touches:
  - code/main/miniapp-jp/src/pages/event/**
  - code/main/miniapp-jp/src/pages/product/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.event_detail
  - UI:mp.product_detail
  - UI:mp.product_detail.notice
accept:
  - name: 场详情商品网格渲染 + 商品详情可达
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs product
  - name: 注意事项区块默认展开且在 CTA 之上
    form: API
    run: |
      grep -q 'notice' code/main/miniapp-jp/src/pages/product/detail.vue && \
      ! grep -qE 'collapse|折叠' code/main/miniapp-jp/src/pages/product/detail.vue
---

# GZ-JP-202 小程序场详情 + 商品详情

## §0 状态自检

1. GZ-JP-201 已 merge，首页可进场。

## What

**场详情**：顶部场信息（封面/名称/倒计时或已结束提示）+ 商品两列网格 + 上拉加载。
一期不做筛选不做排序。场已结束时商品仍可浏览，加购入口置灰并提示「本场已结束」。

**商品详情**：主图轮播（主图+图集）→ 名称 → 价格（大字，**标注「包邮」**）→ 预计到货时间 →
★ **注意事项区块** → 底部固定 CTA（数量 stepper + 加入购物车）。

★ 注意事项必须**在 CTA 之上、默认展开不折叠、底色区分正文** —— 这是甲方明确要的下单前风险告知位，
折叠起来等于没有。

## AC

- 从首页两跳可达商品详情
- 价格旁有「包邮」标识（全包邮，REQ-ORDER-004）
- 场已结束时加购置灰
