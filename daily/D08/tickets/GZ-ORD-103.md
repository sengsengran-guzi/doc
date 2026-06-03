# GZ-ORD-103 — mp 商品详情 + 下单确认

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §用户操作流程 步骤 3-5 + §异常分支
**关联拆解**: doc/02-需求拆解.md §3.2（GZ-ORD-103 微信端商品详情 + 下单确认）
**关联 mockup**: design/mockup/preorder-detail.html + design/mockup/order-confirm.html（仅布局参考；视觉以 C 日漫海报浓墨系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-ORD-101（预购商品 + SKU 数据模型）+ GZ-USER-003 ✅（V1.0 已交付收货地址 gz_user_address）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆。

- **业务流**：doc/10-业务流权威图.md **§7 预定货品全流程**（V1.1）——
  - §7 关键节点 N3（进商品详情）/ N4（选规格 + 数量 + 校验 SKU 库存）/ N5（确认订单页：选地址 / 看金额 / 勾选「已阅读不支持退款」）
  - §7 异常分支 E1（截止日已过下单）/ E2（SKU 库存不足）/ E3（商品已下架）
  - 跨境物流默认态见 doc/10 **§9**（本卡不触物流，仅 ORD-104 下单时落 `logistics_status='in_japan'`，详 §9.L1）
- **字段表**：doc/11-字段权威表.md
  - **§6.1 gz_ord_product**（展示字段：`name` / `main_image_id` / `gallery_image_ids` / `description_html` / `ip_tag` / `deadline_time` / `delivery_date_text` / `delivery_date_exact` / `status` / `sales_count` / `version`）
  - **§6.2 gz_ord_sku**（`spec_name` / `price_cent` / `stock_total` / `stock_remain` / `enabled` / `version`）
  - **§2.2 gz_user_address**（确认页选地址来源：`recipient_name` / `mobile` / `province` / `city` / `district` / `detail` / `tag` / `is_default`）
- **UI 参考**（V1.0 设计冻结期，仅布局参考不强求逐像素）：mp `preorder-detail.html`（轮播 + 富文本 + 规格选择 + 底部 CTA「立即购买」）+ `order-confirm.html`（地址 + 金额 + 不支持退款勾选）+ doc/12 §MP-ORD-PREORDER-DETAIL / §MP-ORD-CONFIRM

## What

mp 端两页 + 一段下单前校验逻辑：①商品详情页（轮播 / 价格 / 截止倒计时 / 到货日 / 富文本 / 规格选择）；②点「立即购买」时的下单前校验（登录 + 商品在售 + 截止未过 + SKU 库存）；③确认订单页（选 gz_user_address 地址 / 实时算金额 / 勾选「已阅读并接受不支持退款」才可提交）。本卡只到「提交订单」按钮触发为止，**不调起支付、不落订单**（出单 + snapshot 落库 + 跨域事务在 GZ-ORD-104）。

## AC（验收标准）

- [ ] **AC 1**：mp 商品详情接口 `GET /app/gz/ord/product/{id}` 返回 `OrdProductDetailVO`：
  - 商品字段：`id` / `name` / `mainImageUrl`（`main_image_id` 经 gz_file_object 解析为可访问 url）/ `galleryImageUrls`（`gallery_image_ids` 逗号分隔逐个解析为 url 数组）/ `descriptionHtml`（`description_html` 原文，前端用 `rich-text` 渲染）/ `ipTag` / `deadlineTime`（ISO8601）/ `deliveryText`（`delivery_date_exact` 优先格式化 `yyyy-MM-dd`，否则取 `delivery_date_text`，都空则空串）/ `status` / `salesCount`
  - SKU 列表 `skus[]`：每项 `id` / `specName` / `priceCent` / `stockRemain`（`stock_total IS NULL` → 返回 `null` 表无限，前端不显示库存数字）/ `enabled`
  - 外层附加 `serverNow`（服务器当前时间 ISO8601，供前端校准倒计时，复用 ORD-102 已有口径）
  - **不返回裸 url 列、不新增 view_count 字段、不做浏览量埋点**（§6.1 无该字段）
- [ ] **AC 2**：mp `pages/ord/preorder-detail.vue`：
  - 顶部 swiper 轮播 `mainImageUrl` + `galleryImageUrls`（功能性 `<wd-swiper>` 外观套 C token，不裸用）
  - 名称 / 起始价（取 `enabled=1` SKU 的 `priceCent` MIN，选中 SKU 后切到该 SKU 实价）/ 截止倒计时（复用 ORD-102 `composables/useCountdown.ts`，以 `serverNow` 校准；归零显示「已截止」）/ 到货日（`deliveryText`）
  - 富文本 `<rich-text :nodes="descriptionHtml">`（uni 原生组件，不用 webview）
  - 规格选择 `BizSkuSelector`：点 SKU 项选中 → 顶部价格切到该 SKU `priceCent`，并提示该 SKU `stockRemain`（无限则不显示数字）
  - 底部 fixed CTA「立即购买」走业务组件 `BizFixedCta` + `BizButton`（C token，不裸 `<wd-button>`）
- [ ] **AC 3**：下单前校验 `composables/usePurchaseGuard.ts`（点 CTA 时，参数 productId + skuId + quantity）：
  - 未登录 → 调 ORD-102/SYS-002 已有 `useAuth` 触发微信登录 → 登录成功后回跳本动作
  - 调 `POST /app/gz/ord/product/validate-purchase`（body：productId + skuId + quantity）后端校验：
    - 商品存在 + `status = 'on_shelf'` + `deadline_time > NOW()` → 否则 `errCode=PRODUCT_OFF`，文案「该商品已截止，请重选」（`status` 为 `off_shelf` / `auto_off` 或截止已过均归此码）
    - SKU 存在 + `enabled=1` + (`stock_remain IS NULL` 无限 OR `stock_remain >= quantity`) → 否则 `errCode=SKU_OUT_OF_STOCK`，文案「库存不足，请刷新」
    - 商品/ SKU 不存在 → `errCode=PRODUCT_NOT_FOUND`
  - `errCode=PRODUCT_OFF` → toast 文案 + 拦截（不跳确认页）+ 返回列表（用户须重选商品）
  - 校验通过 → 跳确认订单页 `/pages/ord/order-confirm?productId=&skuId=&quantity=`
- [ ] **AC 4**：mp `pages/ord/order-confirm.vue`：
  - 顶部商品块：主图 + 名称 + 选中规格名 + 数量 stepper（默认 1，上限 = 选中 SKU `stockRemain`；无限时不设上限）
  - 地址区（`BizAddressBar`）：默认读用户默认地址（gz_user_address `is_default=1`）；点击 → 跳 GZ-USER-003 已实现的地址选择页；无任何地址 → 显示「请添加收货地址」CTA → 跳新增地址页
  - 金额：`选中 SKU priceCent × quantity`（前端实时算，元 + ¥ 展示）
  - 「我已阅读并接受预购商品不支持退款」勾选框（默认未勾）
  - 底部「提交订单」CTA（`BizFixedCta` + `BizButton`）：本卡占位 `console.log` + toast「待 GZ-ORD-104 接入」，**不真实提交、不调支付**
- [ ] **AC 5**：「提交订单」按钮 disabled 条件（任一不满足即灰显不可点）：未勾不支持退款 ∥ 无收货地址 ∥ quantity ≤ 0。disabled 时 C token 置灰反馈。
- [ ] **AC 6**：C 端确认页**无退款入口**——仅「不支持退款」勾选文案；如需退款的引导文案统一为「如需退款请联系客服」（与合同 §2.3 / §4.5 一致，C 端不放任何退款按钮）。
- [ ] **AC 7**：单测（vitest）≥ 3 个：
  - `usePurchaseGuard` mock api 三种 errCode（PRODUCT_OFF / SKU_OUT_OF_STOCK / PRODUCT_NOT_FOUND）各断言一次跳转 / toast 行为；以及成功跳确认页
  - 金额计算（`priceCent × quantity`，含 quantity 变更）
  - 「提交订单」disabled 状态（未勾 / 无地址 / quantity=0 三分支）
- [ ] **AC 8**：i18n 所有可见字符串走 `t()` + zh_CN / en_US（含「立即购买」「该商品已截止，请重选」「库存不足，请刷新」「请添加收货地址」「我已阅读并接受预购商品不支持退款」「如需退款请联系客服」「待 GZ-ORD-104 接入」等），不混 emoji。
- [ ] **AC 9: Tier 2 入口可达**（mp ticket 强制，CLAUDE.md §8.3）— Kevin 从 ORD-102 已建的预购商品列表页 `pages/ord/list`（或首页预购卡片）点商品卡 1 次 → 进本详情页；详情页点「立即购买」1 次 → 进确认订单页。**本卡上游 ORD-102 列表入口已建，无需加临时入口**；若 §0 自检发现 ORD-102 列表→详情跳转未接，则在 `pages/index/index.vue` 加临时入口（注释 `<!-- TODO(Tier2-entry-temp): GZ-ORD-103, remove when GZ-ORD-102 list-to-detail merged -->`），由 ORD-102 清理者替换为真入口。

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`（包名 `org.dromara.gz.ord.{controller,service,domain,dto}`）
  - `controller/applet/GzOrdProductMpController.java` 加 `getDetail(Long id)` + `validatePurchase(ValidatePurchaseReq req)`
  - `service/IGzOrdProductService.java` 增 `getDetailForMp(id)` + `validatePurchase(req)`；impl 复用 GZ-ORD-101 已建 mapper / domain（**本卡不新增表、不改 schema**）
  - `domain/dto/applet/ValidatePurchaseReq.java`（productId / skuId / quantity）+ `domain/vo/applet/OrdProductDetailVO.java`（含 `serverNow` + `skus[]`）
  - 错误码枚举 `OrdErrCodeEnum`：`PRODUCT_OFF` / `SKU_OUT_OF_STOCK` / `PRODUCT_NOT_FOUND`（供 ORD-104 复用）
  - **无 DDL**：详情读取 + 下单前校验全部基于 ORD-101 已建 `gz_ord_product` / `gz_ord_sku` 与 USER-003 已建 `gz_user_address`。**若 §0 自检发现缺字段 → STOP 报 Kevin 回 ORD-101 补，不在本卡 ALTER**（避免 schema 双写撞）。
- **小程序**：`code/main/miniapp/src/`
  - `pages/ord/preorder-detail.vue` + `pages/ord/order-confirm.vue`（`pages.json` 加路由 + navigationBar 标题）
  - `composables/usePurchaseGuard.ts` + 复用 `composables/useCountdown.ts`（ORD-102）+ `useAuth`（SYS-002）
  - `components/biz/BizSkuSelector.vue` + `components/biz/BizAddressBar.vue`（复用 USER-003 已有地址组件如有；业务组件统一包一层放 `components/biz/`，前缀 `Biz`，套 `var(--c-*)` token，**不直接撒 `<wd-*>`**，CLAUDE.md §7.5）
  - `api/gz-ord.ts` 加 `getPreorderDetail / validatePurchase`
  - i18n 字典 zh_CN / en_US 扩展
- **测试**：vitest（AC 7）+ 微信开发者工具走「列表 → 详情 → 确认订单」一遍（Tier 2 留 Kevin 真机批量验）

## 备注

### 强约束（字段 / 命名锚定 doc/11，旧卡错误一并修正）

1. **字段名锚定 doc/11 §6.1 / §6.2**：截止 = `deadline_time`（**非 `deadline_at`**）；轮播图 = `gallery_image_ids` FK gz_file_object（**非 `banner_imgs` / 裸 url**）；富文本 = `description_html`（**非 `description`**）；库存 = `stock_total` / `stock_remain`（**非 `stock_init` / `stock_left`**）；价格 = `price_cent`（**非 `price_fen`**）；状态枚举 = `on_shelf` / `off_shelf` / `auto_off`（**非 `'on'` / `archived`**）。
2. **截止 + 在售双重校验在下单点强制**（doc/10 §7.E1 / E3）：`validate-purchase` 后端硬校验 `status='on_shelf' AND deadline_time > NOW()`，不靠 mp 端过滤；ORD-104 提交时会再校验一次（双重防线，本卡为 UX 即时反馈）。
3. **截止已过 / 已下架统一返 `PRODUCT_OFF` 并拦截重选**（不跳确认页）——对齐任务定制要点。
4. **地址 / 商品 / SKU snapshot 由 GZ-ORD-104 落库**（本卡仅 UI 展示当前默认地址 + 实时算金额）；用户改默认地址不影响已提交订单（snapshot 在 ORD-104）。
5. **C 端无退款入口**（合同 §2.3 / §4.5）：确认页仅「不支持退款」勾选 + 「如需退款请联系客服」文案，禁放任何退款按钮。
6. **本卡不接支付、不落订单**：「提交订单」占位，真实出单 + 跨域事务 + `business_type=preorder` 落 `gz_pay_transaction` 全在 GZ-ORD-104。
7. **富文本 rich-text 白名单**：`description_html` 由 admin 富文本编辑器产出（复用 GZ-NEWS-003 白名单），uni `rich-text` 仅渲染白名单标签；超出标签静默忽略。
8. **i18n 强制 + 不混 emoji**；mp 视觉走 C token（doc/13 / doc/tokens.md），mockup 仅布局参考。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 下单前校验独立接口 `validate-purchase`（不复用列表接口） | 点 CTA 即时反馈，不延迟到确认页；ORD-104 提交时会再校验，本接口主要为 UX |
| D2 | `serverNow` 随详情接口外层返回（不单独接口） | 减少 RTT；与 ORD-102 列表接口口径一致，倒计时校准复用 `useCountdown` |
| D3 | 数量 stepper 默认 1 + 上限 = 选中 SKU `stockRemain`（无限不设上限） | 防手滑超买；最终库存以 ORD-104 乐观锁扣减为准 |
| D4 | 「不支持退款」勾选放确认页（不放详情页） | 详情页是浏览阶段，确认页才是承诺阶段（合同 §4.5 防客诉） |
| D5 | 富文本用 uni `rich-text` 不用 webview | webview 性能差且需上下文切换；rich-text 满足谷子预购富文本展示 |
| D6 | 本卡零 DDL，复用 ORD-101 / USER-003 已建表 | 详情读取 + 校验无需新字段；缺字段回 ORD-101 补，避免双写撞 schema |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **§0 自检须 grep migration 目录确认上游表实际存在**（gz-ord 曾是空脚手架，不假设上游已建） | §0 自检 `ls code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/ \| grep GZ-ORD-101` + 连库 `SHOW COLUMNS FROM gz_ord_product` / `gz_ord_sku` 确认 `gallery_image_ids` / `description_html` / `deadline_time` / `stock_total` / `stock_remain` / `status` 全在；`SHOW COLUMNS FROM gz_user_address`（USER-003）确认 `recipient_name` / `is_default` 在；缺 → STOP 报 Kevin 回上游补，不在本卡 ALTER |
| R2 | 用户从「立即购买」到「提交订单」窗口期商品下架 / 截止 | ORD-104 提交时再校验（双重防线）；本卡校验只在点 CTA 时做 |
| R3 | 用户无收货地址直接提交 → ORD-104 拒收 | 本卡确认页强制：无地址显示「请添加收货地址」CTA + 「提交订单」disabled（AC 5） |
| R4 | SKU 库存 mp 端显示不实时（他人已购本用户未刷新） | 详情每次进入实时拉 `stock_remain`；ORD-102 列表不展示库存；最终以 ORD-104 乐观锁为准 |
| R5 | 富文本图片懒加载首屏空白 | uni `rich-text` 不支持懒加载，依赖图片本身 CDN 性能；admin 富文本编辑引导运营压缩图 |
| R6 | i18n 字典遗漏场景文案（「该商品已截止，请重选」「请添加收货地址」等） | testing-human 检查清单逐条核对每个文案走 `t()`（AC 8 列举） |
| R7 | 旧卡 `view_count` 自增 / `banner_imgs` / `stock_init/left` / `deadline_at` 字段不存在 → 误用撞 schema | 本卡明确删除 view_count 埋点；字段名全部锚定 doc/11 §6.1/§6.2（强约束 #1）；本卡零 DDL |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
