---
ticket: GZ-SNAP-502
track: SNAP-MP
phase: D12
size: M
req_refs: [REQ-SNAP-016, REQ-SNAP-021, REQ-SNAP-025, REQ-SNAP-035]
depends_on: [GZ-SNAP-501]
touches:
  - code/main/miniapp-jp/src/pages.json
  - code/main/miniapp-jp/src/pages/snap/**
  - code/main/miniapp-jp/src/api/gz-jp/**
  - code/main/miniapp-jp/src/locale/**
  - code/main/miniapp-jp/src/components/biz/**
  - code/main/miniapp-jp/test/e2e/flows/**
blueprint_refs:
  - UI:mp.snap_detail
  - UI:mp.snap_detail.price
  - UI:mp.snap_detail.gate
  - UI:mp.snap_detail.cta
accept:
  - name: 模拟器 E2E：详情渲染到手价 + 煤炉原价、价格说明三行之和=到手价、三种准入态按钮形态正确
    form: API
    run: cd code/main/miniapp-jp && node test/e2e/run.mjs snap-detail
    counterfeit: 价格说明抽屉三行相加不等于到手价，或 blocked 商品按钮仍可点 → flow 红
  - name: 详情页源码不出现汇率与加价比例（方案 A）
    form: API
    run: |
      F1=code/main/miniapp-jp/src/pages/snap/detail.vue; F2=code/main/miniapp-jp/src/locale/snap.zh-CN.ts; \
      test -f "$F1" && test -f "$F2" && \
      ! grep -nwiE 'rate|markup|markupRatio|ratePer100Jpy' "$F1" && ! grep -nE '汇率|加价' "$F1" "$F2"
    counterfeit: 价格说明里加一行「汇率 4.8」或「服务费率 10%」→ grep 命中红
---

# GZ-SNAP-502 mp 代切商品详情

## §0 状态自检

1. GZ-SNAP-303 的详情接口返回准入三态 + 报价（mp 侧不含 rate / markupRatio）。
2. 读 `UI:mp.snap_detail` 及三个区块、`mp-snap-detail.md`（方案 A）、`design-options/README.md` 二期设计权威节。

## What

`pages/snap/detail.vue`（二级页）：
1. 进入即调详情接口（实时）；顶部「实时价格 · x 秒前」（由 `fetchedAt` 算）。
2. 图片轮播 → 中文标题（可展开日文原文）→ 价格区：到手价大字 +「煤炉原价 ¥x 円」小字 +「价格说明」→ 抽屉三行（商品价 / 代切服务费 / 到付预估运费 + 「多退少不补」说明）。
3. 成色 / 运费承担 / 描述（机翻，可看原文）。
4. 准入提示条三态（文案走 locale）：auto 不显示；manual「需日本员工先和卖家确认，付款后人工处理，谈不成全额退款」；
   blocked / 非在售：按钮置灰 + 原因（按 gate_reason 映射：卖家不接受代购 / 该商品已被预定 / 暂不支持该分类 / 已售出 …）。
5. 报价过期：下拉刷新或重新进入重报；底部固定条「立即购买」→ 下单确认页 snap 模式（带 quoteId）。不出现「加入购物车」。
6. E2E flow `snap-detail.mjs`：用日本服务回放样本集里的 auto、manual（到付 / コメント必須）、blocked（拒代购 / 専用）商品（经接口取，不造库数据），
   断言 blocked 的拒代购件显示「卖家不接受代购」。

## AC

- 两条 accept 绿；新页首版视觉进 Kevin 人验列。
