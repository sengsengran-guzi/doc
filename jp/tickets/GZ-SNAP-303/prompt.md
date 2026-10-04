---
ticket: GZ-SNAP-303
track: SNAP
phase: D9
size: L
req_refs: [REQ-SNAP-020, REQ-SNAP-021, REQ-SNAP-022, REQ-SNAP-023, REQ-SNAP-024, REQ-SNAP-025, REQ-SNAP-048, REQ-SNAP-061]
depends_on: [GZ-SNAP-302]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FLOW:F-JP-05.step5
  - FLOW:F-JP-12.step3b
  - FLOW:F-JP-06.step1
  - FLOW:F-JP-11.step1
  - FIELD:gz_jp_snap_item.gate_result
  - FIELD:gz_jp_snap_item.gate_reason
  - FIELD:gz_jp_fx_rate.rate_per_100jpy
  - FIELD:gz_jp_fx_rate.fetched_at
  - UI:mp.snap_detail.price
accept:
  - name: 准入按序判：専用 / 拒代购（标题、描述、卖家简介）→blocked 且先于转人工；留言必须 / 到付→manual；非在售不可下单；其余 auto
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapGateTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapGateTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapGateTest.xml
    counterfeit: 转人工词只扫标题不扫描述、「様専用」被判 manual、或描述同时含「代行業者は即購入不可…必ずコメント」时被判成 manual 而不是 blocked → 红
  - name: 报价公式与拒报价条件（参数未配 / 汇率超 6 小时 / 报价过期）
    form: DATA
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapQuoteTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapQuoteTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapQuoteTest.xml
    counterfeit: 预估运费也乘了加价比例、进位用四舍五入而非向上取整、或定价参数为空时按 0 报价 → 红
  - name: 小程序详情响应不含汇率与加价比例（设计方案 A）
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapDetailContractTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapDetailContractTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapDetailContractTest.xml
    counterfeit: mp 详情 VO 里带了 rate / markupRatio 字段（前端不显示也算泄漏）→ 序列化后的 JSON 键断言红
---

# GZ-SNAP-303 准入判定 + 汇率抓取 + 报价

## §0 状态自检

1. GZ-SNAP-302 完工，详情接口能落 `gz_jp_snap_item`。
2. 读 `FLOW:F-JP-06.step1`（公式、Redis 结构、拒报价条件）、`FLOW:F-JP-11.step1`（汇率）、REQ-SNAP-020~025 的 note。
3. 中国银行外汇牌价页面结构：先手动抓一次确认「日元 现汇卖出价」所在列与单位（每 100 日元），解析写死列名而不是列序号。

## What

1. 准入（`GzJpSnapGate`）：规则读 `gz.jp.snap.gate` + `gz.jp.snap.filter`，**按顺序判、先命中先定**：
   - blocked：标题含 blockKeywords（専用 / 様専用 / さん専用）、分类 / 黑名单不过、Shops 商品；
     **卖家拒绝代购**（REQ-SNAP-048）：标题、描述、卖家个人简介任一命中 proxyRefuseKeywords → `gate_reason=proxy_refuse:<词>@<位置>`，mp 提示「卖家不接受代购」。
     卖家简介经 gateway `GET /v1/sellers/{id}` 取，Redis 按卖家缓存 24 小时；取不到只按商品判、不阻断。
     ★ 必须先于 manual 判（实测原文：「越境取引代行業者は即購入不可…必ずコメントして下さい」——不先判就会落成转人工）；
   - manual：标题或描述含 manualKeywords，或 `shipping_payer=buyer`；
   - 其余 auto；`item_status≠on_sale` 时无论哪态都不可下单（单独字段 `purchasable=false` + 原因）。
   结果写 `gate_result` / `gate_reason`。
2. 汇率任务（每 30 分钟）抓中国银行日元现汇卖出价写 `gz_jp_fx_rate(source=boc)`；失败保留上一条并 warn；
   admin 手动录入接口 `POST /system/gz/jp/snap/fx`（`source=manual`），报价取最新一条；最新一条超过 6 小时 → 拒报价 + error 日志。
3. 报价器：`total = ceil(price_jpy × rate/100 × (1+markupRatio) × 100 分) + fixedFeeCent [+ estShippingCent，仅 gate=manual 且到付]`；
   报价存 Redis `quote:{quoteId}` TTL=quoteTtlSec，字段照 `FLOW:F-JP-06.step1`；`pricing` 三项任一为空 → 拒报价（错误码 `SNAP_PRICING_UNSET`）。
4. 详情接口叠加：准入三态 + 报价（mp 侧只给 `goodsCent`（含加价的商品价）/ `fixedFeeCent` / `estShippingCent` / `totalCent` / `priceJpy` / `quoteId` / `expiresAt`），
   **不下发 rate 与 markupRatio**；搜索列表的人民币参考价用同一公式现算、不生成 quoteId。

## AC

- 三条 accept 绿。
- 报价三行之和恒等于 totalCent（`UI:mp.snap_detail.price` 抽屉三行之和 = 到手价）。
- 汇率与加价比例只出现在 admin 接口与订单快照里，不出现在任何 mp 接口响应中。
