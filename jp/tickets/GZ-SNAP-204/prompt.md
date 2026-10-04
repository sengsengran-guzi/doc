---
ticket: GZ-SNAP-204
track: SNAP-GW
phase: D14
size: M
system: mercari-gateway
req_refs: [REQ-SNAP-029, REQ-SNAP-032]
depends_on: [GZ-SNAP-203]
touches:
  - code/main/mercari-gateway/**
blueprint_refs:
  - FLOW:F-JP-12.step6
  - FLOW:F-JP-12.step7
  - FLOW:F-JP-09.step1
  - OWN:mercari_purchase_fact
accept:
  - name: 对账只读：按商品 ID 查购买记录，found 带交易号；对账代码路径不可能触发购买
    form: STATE
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_reconcile_trades.py
    counterfeit: reconcile 在查不到时「顺手补下单」，或巡检把已完成交易报成 cancelled → 红
---

# GZ-SNAP-204 日本服务真对账 + 交易巡检

## ★ 分支

S0 no-go → 本卡关闭不做（与 203 同理），巡检由日本员工手工标记（FLOW:F-JP-09.step1b）。

## §0 状态自检

1. GZ-SNAP-203 完工；S0 报告第 6 项（购买记录可查、可见延迟）。

## What

1. `reconcile(order_no, external_id, account_code)`：先查本地幂等表，再查该账号购买记录 → `{found, mercari_txn_id, actual_price_jpy, item_status}`（item_status 用匿名详情接口取）。
2. `trades(account_code)`：抓「購入した商品」进行中 + 最近 7 天结束的交易 → 契约字段；煤炉状态到 `await_ship|shipped|cancelled|completed` 的映射写在 README。
3. 两个方法只读；页面解析失败 → 抛错（ruoyi 视为调用失败，进下一轮），绝不返回猜测值。
4. 测试用 S0 录下的购买记录页 / 交易页样本。

## AC

- accept 绿。
