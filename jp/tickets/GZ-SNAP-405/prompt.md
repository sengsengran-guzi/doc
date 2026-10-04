---
ticket: GZ-SNAP-405
track: SNAP-ADMIN
phase: D11
size: S
req_refs: [REQ-SNAP-004, REQ-SNAP-033]
depends_on: [GZ-SNAP-404]
touches:
  - code/main/plus-ui/src/views/gz-jp/fulfill/**
  - code/main/plus-ui/src/api/gz-jp/**
  - code/main/plus-ui/src/lang/zh_CN.ts
  - code/main/plus-ui/src/lang/en_US.ts
  - code/main/plus-ui/e2e/gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - UI:admin.fulfill_board.snap
  - UI:admin.fulfill_board
  - FLOW:F-JP-09.step3
accept:
  - name: 履约看板代切行：带「代切」标签；未评价行不可勾选并提示；评价后与拼团行同一套推进；一期看板 E2E 不回归
    form: API
    run: |
      cd code/main/plus-ui && npx playwright test e2e/gz-jp/fulfill-board-snap.spec.ts e2e/gz-jp/fulfill-board.spec.ts --reporter=line
    counterfeit: 未评价代切行仍可勾选（靠后端守卫兜底报错但前端不提示）或改坏一期聚合视图 → spec 红
---

# GZ-SNAP-405 admin 履约看板 · 代切行

## §0 状态自检

1. GZ-SNAP-307 的后端守卫已生效；GZ-SNAP-102 已让看板查询容纳代切行（名称 / 图取快照）。
2. 读一期 `views/gz-jp/fulfill/` 与 `e2e/gz-jp/fulfill-board.spec.ts`。

## What

1. 看板列表接口补 `source`、`snapTradeStatus` 两个字段（后端只加字段，不改既有字段）。
2. 前端：代切行加「代切」来源标签（`el-tag`）；`snapTradeStatus≠rated` 的代切行勾选框置灰 + tooltip「验货评价后才能推进」；评价后与拼团行完全同一套推进 / 发货。
3. 新 E2E `fulfill-board-snap.spec.ts`；一期 `fulfill-board.spec.ts` 必须照旧绿。

## AC

- accept 绿。纯 admin，无人验。
