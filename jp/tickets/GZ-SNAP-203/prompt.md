---
ticket: GZ-SNAP-203
track: SNAP-GW
phase: D14
size: L
system: mercari-gateway
req_refs: [REQ-SNAP-006, REQ-SNAP-026, REQ-SNAP-027, REQ-SNAP-030, REQ-SNAP-043]
depends_on: [GZ-SNAP-001, GZ-SNAP-201]
touches:
  - code/main/mercari-gateway/**
blueprint_refs:
  - FLOW:F-JP-07.step2
  - FLOW:F-JP-12.step5
  - OWN:mercari_account_session
  - OWN:snap_evidence
accept:
  - name: 下单结果判定：用技术验证录下的页面样本，点击前停下的情况才可能是 failed，点击后拿不到交易页一律 unknown
    form: STATE
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_purchase_classify.py
    counterfeit: 点击「購入する」后页面超时被判成 failed（会触发退款，但其实可能已买到），或余额不足页被判成 unknown → 红
  - name: 真驱动幂等与前置核价：同 order_no 不二次点击；涨价 / 运费改到付时不点击
    form: STATE
    run: cd code/main/mercari-gateway && .venv/bin/pytest -q tests/test_real_driver_guards.py
    counterfeit: 前置核价漏比较 expect_shipping_payer，或幂等表在进程重启后丢失（内存实现）→ 红
---

# GZ-SNAP-203 日本服务真下单驱动（Playwright）

## ★ 分支

先看 ADR-0025 §3 的 S0 结论：
- **no-go** → 本卡关闭不做：在本文件末尾写「S0 no-go，关闭」，确认部署环境 `GATEWAY_DRIVER=disabled`，accept 记 N/A。
- **go** → 按下文做。

## §0 状态自检

1. `doc/jp/_spike/s0/REPORT.md` 与 `evidence/` 的页面样本（用作判定测试的 fixture）。
2. 逐字读 `FLOW:F-JP-07.step2` 的 ①~⑦ 与 ADR-0025 §4 风险边界。

## What

`app/drivers/real.py` 的 `purchases`：
1. 本地幂等表（SQLite 持久化，进程重启不丢）：命中直接返回首次结果。
2. 查购买记录里已有该商品 → success（不再点）。
3. 打开商品页核对：在售 / 当前价 ≤ `max_price_jpy` / 运费承担 = `expect_shipping_payer`；不满足 → 对应 failed reason，**不点击**。
4. 进购买页确认默认付款方式与收货地址（与配置的转运仓地址比对，不一致 → unknown + risk_signal，不点击）；
   购买页显示余额不足 / 付款方式不可用 → `failed(account_unpayable)`，不点击（纸面推演 P6）→ 否则点「購入する」。
5. 判结果：交易页出现 → success（交易号、成交价）；其他一律 unknown。点击之后的任何失败都不允许返回 failed。
6. 每步截图 + 页面 HTML 快照随响应回传；本地留 7 天。
7. 任一页面出现验证码 / 登录验证 / 短信验证 → 立即停，unknown + `risk_signal=true`，该账号本地标 challenge（health 返回 challenge）。
8. 每账号一个常驻浏览器上下文、串行执行（同账号并发请求排队）；出口走 ISP 代理（环境变量）。

## AC

- 两条 accept 绿；首次真下单在 GZ-SNAP-601 演练里由 Kevin 在场时执行。
- 不引入任何验证码识别、指纹伪装类依赖。
