---
ticket: GZ-SNAP-503
track: SNAP-MP
phase: D12
size: M
req_refs: [REQ-SNAP-036, REQ-SNAP-037]
depends_on: [GZ-SNAP-502]
touches:
  - code/main/miniapp-jp/src/pages/order/**
  - code/main/miniapp-jp/src/pages/agreement/**
  - code/main/miniapp-jp/src/api/gz-jp/**
  - code/main/miniapp-jp/src/locale/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.order_confirm.snap
  - UI:mp.order_confirm
  - UI:mp.agreement.snap
  - FLOW:F-JP-06.step2
accept:
  - name: 模拟器 E2E：snap 模式下单确认——未勾「抢到后不可取消」不能提交；勾选后提交生成订单并进支付（wxMOCK）
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs snap-checkout
    counterfeit: 默认勾选（微信审核会驳回「默认同意」）或未勾也能提交 → flow 红
  - name: 确认页逻辑单测：报价剩余时间倒计时、过期后按钮变「重新报价」；一期拼团确认页逻辑不变
    form: STATE
    run: cd code/main/miniapp-jp && npx vitest run src/pages/order/confirm.logic.test.ts src/pages/order/confirm.snap.logic.test.ts
    counterfeit: 过期后仍可提交（前端不拦，等后端报错）或改坏拼团模式金额计算 → 红
---

# GZ-SNAP-503 mp 下单确认 · 代切模式 + 用户协议代切条款

## §0 状态自检

1. GZ-SNAP-304 的提交接口可调；一期 `pages/order/confirm.vue` + `confirm.logic.ts` 的结构。
2. 读 `UI:mp.order_confirm.snap`、`UI:mp.agreement.snap`；memory「mp 隐私协议合规」：勾选框**默认不勾**。

## What

1. 确认页按入参 `mode=snap&quoteId=` 切代切模式：只一件商品；显示报价剩余时间（倒计时，过期 → 按钮「重新报价」回详情）；
   金额区展开报价构成（同详情抽屉三行）；提交按钮上方勾选「已知悉：抢到后不可取消；没抢到全额原路退款」，默认不勾、未勾不可提交；
   提交 → `POST /app/gz/jp/snap/order/submit` → 复用一期支付拉起与结果页。
2. snap 逻辑放 `confirm.snap.logic.ts` + 单测，不把分支塞进一期 logic。
3. 协议页补「代切服务」一节（抢到后不可取消、未抢到全额原路退款、到付预估运费多退少不补、商品信息来自煤炉卖家以实物为准、验货不通过退款）。
   文案标注「待甲方过目」（确认单第三部分 #7），定稿前可上 staging。
4. E2E flow `snap-checkout.mjs`。

## AC

- 两条 accept 绿；一期 checkout flow 不回归。
- 本卡碰真机微信原生支付：进 Kevin 人验列（真机支付在 GZ-SNAP-601 演练里一起跑）。
