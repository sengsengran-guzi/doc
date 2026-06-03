# GZ-ORD-103 — mp 商品详情 + 下单确认 完工报告

## §0 状态自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（harness 跟踪文件状态，非 git 仓库） |
| 上游依赖 merge — gz_ord_product / gz_ord_sku（ORD-101） | ✅ V202606060900；DDL grep 确认 `gallery_image_ids` / `description_html` / `deadline_time` / `stock_total` / `stock_remain` / `status` / `price_cent` / `enabled` 全在 |
| 上游依赖 merge — gz_user_address（USER-003） | ✅ V202606031100；mp api `UserAddressVO` 含 `recipientName` / `mobile` / 省市区 / `detail` / `tag` / `isDefault` |
| ORD-102 已建 Controller / api / useCountdown | ✅ `GzOrdProductMpController`（/list + /ip-tags）/ `api/gz-ord.ts`（getPreorderList/getPreorderIpTags）/ `composables/useCountdown.ts` 全在；本卡在同文件追加 |
| ORD-102 列表→详情跳转 | ✅ `list.vue` goDetail 已跳 `/pages/ord/preorder-detail?id=`，命名对齐，Tier 2 无需临时入口 |
| 编译通过（后端 gz-ord，无 -am 并行安全） | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-ord -o` 无输出（成功） |
| migration 最大版本 | V202606061100；本卡无 DDL（零 schema 变更，决策 D6） |
| ADR 已读 | 任务卡「关联 ADR: —」无相关；跨层契约 #1 ID string / #2 业务码 已遵循 |

## 实现摘要

### 改动文件（相对 `code/main/`）

**后端 `RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`（追加，不改 ORD-101/102 既有逻辑）**
- 新增 `.../enums/OrdErrCodeEnum.java`（OK / PRODUCT_OFF / SKU_OUT_OF_STOCK / PRODUCT_NOT_FOUND，字符串 errCode，供 ORD-104 复用）
- 新增 `.../domain/dto/applet/ValidatePurchaseReq.java`（productId / skuId / quantity + @Valid 校验）
- 新增 `.../domain/vo/applet/ValidatePurchaseVO.java`（ok + errCode，静态工厂 ok()/of()）
- 新增 `.../domain/vo/applet/OrdSkuMpVO.java`（详情 SKU 子 VO；id ToString；stockRemain NULL=无限）
- 新增 `.../domain/vo/applet/OrdProductDetailVO.java`（含 mainImageUrl/galleryImageUrls/descriptionHtml/skus[]/serverNow；不返裸 file_id、无 view_count）
- 改 `.../service/IGzOrdProductService.java`（+getDetailForMp / validatePurchase 接口）
- 改 `.../service/impl/GzOrdProductServiceImpl.java`（+两方法实现 + resolveGalleryUrls / listSkuMpVO / toSkuMpVO 辅助；复用既有 resolveImageUrl / formatDeliveryText）
- 改 `.../controller/applet/GzOrdProductMpController.java`（+GET /{id} + POST /validate-purchase）
- 新增 `.../test/.../GzOrdProductMpDetailTest.java`（10 个单测）

**mp `miniapp/src/`**
- 改 `api/gz-ord.ts`（+OrdProductDetailVO/OrdSkuMpVO/ValidatePurchaseReq/VO/OrdErrCode 类型 + getPreorderDetail / validatePurchase）
- 改 `locale/ord.zh-CN.ts`（+`ord.detail.*` + `ord.confirm.*` 命名空间 zh/en，t() 路由扩展）
- 新增 `composables/usePurchaseGuard.ts`（登录引导 + validate + errCode 分流 + 跳转）
- 新增 `pages/ord/detail.logic.ts`（formatPriceCent/startPriceCent/calcAmountCent/quantityMax/isSubmitDisabled/formatStock 纯逻辑）
- 新增 `pages/ord/preorder-detail.vue`（swiper 轮播 + 价/倒计时/到货日 + BizSkuSelector + rich-text + BizFixedCta 立即购买）
- 新增 `pages/ord/order-confirm.vue`（商品块+stepper + BizAddressBar + 金额 + 不支持退款勾选 + 提交占位）
- 新增 `components/biz/BizSkuSelector.vue`（规格 chip，停用/售罄置灰，选中朱红）
- 新增 `components/biz/BizAddressBar.vue`（默认地址 / 无地址 CTA，复用 UserAddressVO）
- 新增 `components/biz/BizCountdownText.vue`（倒计时文案子件，v-if 挂载后建 useCountdown，归零 emit expired）
- 新增 `composables/usePurchaseGuard.test.ts`（5 个单测）+ `pages/ord/detail.logic.test.ts`（16 个单测）

### 关键设计点
- **validate-purchase 始终 R.ok 包裹**（HTTP 200 + 业务 code=200 + data.errCode），不抛异常 → 不触发 mp http 拦截器通用 toast，由 usePurchaseGuard 按 errCode 差异化 UX（PRODUCT_OFF 拦截退列表 / SKU_OUT_OF_STOCK 停页提示刷新）。
- **errCode 双码体系**：`OrdErrCodeEnum`（字符串，mp 校验结果分流）与既有 `GzOrdErrorCode`（int + ServiceException 抛错，如 detail 404）并存，职责清晰。
- **详情不做在售强约束**：下架商品旧链接仍可看详情，由 validate-purchase 在点 CTA 时拦截（决策 D1，避免用户进详情就 404）。
- **倒计时归零置灰**：BizCountdownText 在 detail 加载后才挂载（v-if），useCountdown 拿到真 deadline + serverNow；归零回调置 isExpired → CTA 灰显。

## AI 自测（Tier 1A）

### 后端编译 + 单测（无 -am，并行安全；PAY-102 同波次改 gz-common 不受影响）
```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-ord -o
[INFO] Tests run: 4,  Failures: 0, Errors: 0, Skipped: 0 -- OrdProductSortEnumTest
[INFO] Tests run: 6,  Failures: 0, Errors: 0, Skipped: 0 -- GzOrdSkuServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdProductMpDetailTest   ← 本卡新增
[INFO] Tests run: 6,  Failures: 0, Errors: 0, Skipped: 0 -- GzOrdProductServiceImplTest
[INFO] Tests run: 26, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
GzOrdProductMpDetailTest 10 例覆盖：OK / 无限库存放行 / PRODUCT_OFF（下架）/ PRODUCT_OFF（截止已过）/ SKU_OUT_OF_STOCK（库存不足）/ SKU_OUT_OF_STOCK（停用）/ PRODUCT_NOT_FOUND（商品不存在）/ PRODUCT_NOT_FOUND（SKU 不存在）/ detail null / detail 下架仍可读含 serverNow。

### mp vitest（本卡 2 个新文件 21 例）
```
$ npx vitest run src/composables/usePurchaseGuard.test.ts src/pages/ord/detail.logic.test.ts
 ✓ src/pages/ord/detail.logic.test.ts (16 tests) 3ms
 ✓ src/composables/usePurchaseGuard.test.ts (5 tests) 4ms
 Test Files  2 passed (2)
      Tests  21 passed (21)
```
- usePurchaseGuard 5 例（AC7）：未登录取消→cancelled / OK→navigated（确认页参数断言）/ PRODUCT_OFF→blocked+toast+navigateBack / SKU_OUT_OF_STOCK→blocked+toast 停页 / PRODUCT_NOT_FOUND→blocked+navigateBack。
- detail.logic 16 例：金额 priceCent×quantity（含数量变更）/ 起始价 enabled MIN / 提交 disabled 三分支+全满足 / quantityMax 无限 undefined / formatStock。

### mp 全量 vitest（回归）
```
 Test Files  1 failed | 20 passed (21)
      Tests  1 failed | 150 passed (151)

 FAIL  src/api/gz-bean.test.ts > bindMobile 透传 ...
   expected data { mobile: ... } but received { code: ... }
```
**该 1 例失败是预存（pre-existing），与本卡无关**：`gz-bean.ts` 的 `bindMobile` 实现已发 `{ code }`（对齐 wechat-real-integration 记忆：手机号走 code+access_token），但 `gz-bean.test.ts` 仍断言旧的 `{ mobile }` —— BEAN-004 重构后测试未同步。本卡未触碰 gz-bean，留给 BEAN 域 ticket 修测（不在本卡 scope）。

### mp 构建（dist 产物 + 路由注册）
```
$ pnpm build:mp-weixin
DONE  Build complete.
（尾部唤 wechat devtools cli 假挂起，dist 已生成，pkill cli 后 exit 0 — 见 mem）

$ grep pages/ord dist/build/mp-weixin/app.json
pages/ord/index
pages/ord/list
pages/ord/order-confirm     ← 本卡新增，已注册
pages/ord/preorder-detail   ← 本卡新增，已注册
```

### TS type-check
```
$ pnpm type-check
（error TS 总数 = 0；ORD-103 全部文件无类型错误，无 any）
```

### detail 接口 mock 返回示例（契约）
```jsonc
GET /app/gz/ord/product/12  →  R.ok:
{
  "code": 200, "msg": "操作成功",
  "data": {
    "id": "12", "name": "CHIIKAWA 公仔", "mainImageUrl": "https://cos.../m.png",
    "galleryImageUrls": ["https://cos.../g1.png", "https://cos.../g2.png"],
    "descriptionHtml": "<p>正版授权...</p>", "ipTag": "CHIIKAWA",
    "deadlineTime": "2026-08-20T23:59:59", "deliveryText": "2026-09-15",
    "status": "on_shelf", "salesCount": 42,
    "skus": [
      {"id":"100","specName":"标准款","priceCent":12900,"stockRemain":50,"enabled":1},
      {"id":"101","specName":"豪华版","priceCent":19900,"stockRemain":null,"enabled":1}
    ],
    "serverNow": "2026-06-03T16:05:00"
  }
}

POST /app/gz/ord/product/validate-purchase  body {"productId":"12","skuId":"100","quantity":2}
  →  R.ok { "code":200, "data": { "ok":true, "errCode":"OK" } }
  失败 data 形态： {"ok":false,"errCode":"PRODUCT_OFF"} / "SKU_OUT_OF_STOCK" / "PRODUCT_NOT_FOUND"
```

## Tier 2 可达路径（AC9）

`pages/ord/list`（ORD-102 预购列表，已上线）→ 点商品卡 1 次 → `pages/ord/preorder-detail?id=`（本卡）→ 选规格 + 点「立即购买」1 次 → usePurchaseGuard 校验通过 → `pages/ord/order-confirm?productId=&skuId=&quantity=`（本卡）。
- **无需临时入口**：ORD-102 列表→详情跳转 §0 已确认接好（list.vue goDetail），命名对齐 `preorder-detail`。
- 确认页地址区可跳 `pages/me/address/list` / `pages/me/address/edit`（USER-003 已建，§0 确认存在）。

## 风险提示 / 已知 issue

- **R1**：`gz-bean.test.ts > bindMobile` 1 例预存失败（断言 `{mobile}` vs 实现 `{code}`），非本卡引入，建议 BEAN 域下个 ticket 修测同步。
- **R2**：用户「立即购买」→「提交订单」窗口期商品可能下架/截止 → 提交占位不真实下单，真实校验+乐观锁扣减在 ORD-104（双重防线）。
- **R3**：富文本 `rich-text` 不支持图片懒加载，首屏依赖 COS 图本身性能（admin 富文本编辑引导压缩图）。
- **R4**：detail 接口对每张图集图各调一次 `getPresignedUrl`（无批量接口）；谷子商品图集通常 ≤ 5 张，可接受。COS 批量预签如成瓶颈，后续在 gz-common 加批量方法。
- **待 Kevin 批量人验关注（mp 端）**：① 列表→详情→确认页全链路可达 happy path；② 详情轮播滑动 + 规格切换价格/库存联动；③ 倒计时归零置灰；④ 确认页未勾退款/无地址/数量=0 时提交按钮灰显不可点；⑤ 「提交订单」点击 toast「待 GZ-ORD-104 接入」（占位不下单）；⑥ 「如需退款请联系客服」文案存在、无任何退款按钮。

## 对 GZ-ORD-104 接力提示

1. **复用 `OrdErrCodeEnum`**（PRODUCT_OFF / SKU_OUT_OF_STOCK / PRODUCT_NOT_FOUND）——提交时再校验一次（双重防线），可直接用本卡枚举或转 GzOrdErrorCode int 抛 ServiceException。
2. **确认页提交传参契约**（order-confirm.vue `onSubmit` 已 console.log 占位）：
   `{ productId, skuId, quantity, addressId, amountCent }` —— ORD-104 据此建单。
3. **snapshot 落库由 ORD-104**：商品名/规格/单价/地址（recipientName/mobile/省市区/detail）在下单时快照入 `gz_ord_order`，用户后续改默认地址不影响已提交订单（本卡仅 UI 展示当前默认地址）。
4. **库存扣减口径**：用 ORD-101 已建 `GzOrdSkuMapper.tryDeductStock(id, qty, version)`（乐观锁 + 无限库存 NULL 分支），影响行数 0 → 重试 ≤3 → SKU_OUT_OF_STOCK。
5. **微信支付通道**：本卡确认页不调支付；ORD-104 接 `business_type=preorder` 落 `gz_pay_transaction`（PAY 域），拿 prepay_id → mp `wx.requestPayment`。
6. **`gallery_image_ids` 解析方法**已抽 `resolveGalleryUrls`（service impl 私有），ORD-104 如需可提为复用辅助。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

> 注：本卡由主线程嵌套调用 kevin-coder 实施，无法 spawn kevin-qa（嵌套限制）。Tier 1A 已做扎实（后端 26 单测全过 + mp 21 新单测全过 + 全量回归 150/151（1 预存失败）+ 构建路由注册 + type-check 0 error）。Tier 1B（admin Playwright N/A — 本卡纯 mp + 后端 / 后端集成测试 / mp 端到端）由主线程接管。
