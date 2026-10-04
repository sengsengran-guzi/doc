---
ticket: GZ-SNAP-601
track: SNAP
phase: D15
size: M
req_refs: [REQ-SNAP-001, REQ-SNAP-011, REQ-SNAP-038, REQ-SNAP-039]
depends_on: [GZ-SNAP-204, GZ-SNAP-504]
touches:
  - doc/jp/snap-rehearsal.md
  - doc/jp/_accept/**
  - doc/jp/GO-LIVE-CHECKLIST.md
blueprint_refs:
  - FLOW:F-JP-05
  - FLOW:F-JP-06
  - FLOW:F-JP-07
  - FLOW:F-JP-08
  - FLOW:F-JP-09
  - FLOW:F-JP-10
accept:
  - name: 全链路演练剧本每个场景都有 PASS 记录与证据
    form: API
    run: |
      F=doc/jp/snap-rehearsal.md; test -f "$F" && \
      for s in R1 R2 R3 R4 R5 R6 R7 R8; do grep -qE "^\| *$s *\|.*\| *PASS *\|" "$F" || { echo "not pass: $s"; exit 1; }; done
    counterfeit: 有场景标 SKIP / 待测，或真机支付场景用模拟器代替 → 红
  - name: 不明单零重复下单零退款（真环境复跑故障注入）+ 无失败迁移
    form: DATA
    run: |
      bash doc/jp/_accept/snap-fault-injection.sh && \
      docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "SELECT COUNT(*) FROM flyway_schema_history WHERE success=0" | grep -qx 0
    counterfeit: 任何一单在 fake 账本里点击 ≥2 次，或不明单出现退款记录 → 红
---

# GZ-SNAP-601 代切联调与全链路演练

## §0 状态自检

1. D7–D14 全部 `qa_passed`；S0 结论（go / no-go）决定演练里自动下单场景跑真驱动还是改为「全人工」版本。
2. 真机演练需要 Kevin 在场（真钱 / 真机微信原生能力）。

## What

写演练剧本 `doc/jp/snap-rehearsal.md`（表格：场景 | 步骤 | 期望 | 实际 | PASS/FAIL | 证据链接），逐条跑：

| # | 场景 |
|---|---|
| R1 | 真机：中文搜 → 详情 → 付 1 分钱级 / 最便宜商品 → 1 分钟内看到「已抢到」（no-go 时：看到「人工处理中」）|
| R2 | 被抢：报价后被买走 → 提交时被拦下（未付款）；付款后才被买走（fake sold_out）→ 「未抢到·已退款」，退款到账 |
| R3 | 人工代买：「コメント必須」商品 → 人工队列 → 填成功；到付商品到仓时填实际运费 → 差价退款到账、订单仍 paid |
| R4 | 交易取消：巡检或手工标记（含已发货后丢件）→ 全额退清、锁释放 |
| R5 | 验货不通过 → 退货完成 → 退款 |
| R6 | 风控：fake 驱动返回 risk → 账号停用 + 总开关关 + queued 全转人工 → admin 恢复 |
| R7 | 未付款 15 分钟关单：商品锁释放，另一用户可下单；关单后原支付单不可再付 |
| R8 | 故障注入：断网 / 超时 / 重启三场景（`snap-fault-injection.sh`）|

同时把代切上线卡点补进 `GO-LIVE-CHECKLIST.md` 桶 2：甲方书面确认封号风险 · 东京服务器与 ISP 代理 · 采购账号 + 付款方式 + 余额 ·
转运仓地址设为默认地址 · 图片 CDN 备案域名 · 定价三参数 · 代切协议条款过目 · 分类白名单与首批词表 · 自动下单总开关上线当天再开。

## AC

- 两条 accept 绿；`node test/e2e/run.mjs all`（miniapp-jp）与 plus-ui `e2e/gz-jp` 全绿；现有小程序 `code/main/miniapp` E2E 不回归（两个小程序串行跑）。
