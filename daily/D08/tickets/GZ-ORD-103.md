# GZ-ORD-103 — mp 商品详情 + 下单确认

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §用户操作流程 步骤 3-5 + §异常分支
**关联拆解**: doc/02-需求拆解.md §3.2 第 701-711 行
**关联 mockup**: design/mockup/preorder-detail.html + order-confirm.html（仅布局参考；视觉以 C 系统为准，doc/13）
**关联 ADR**: —
**依赖**: GZ-ORD-101 + GZ-USER-003 ✅（V1.0 已建用户收货地址 gz_user_address）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §6 V1.1 演进流 §6.5 预购下单流（从详情进入到确认订单页 — 实施前如缺写补）
- **字段表**：doc/11-字段权威表.md §6.1 gz_ord_product + §6.2 gz_ord_sku + §2.5 gz_user_address（地址 snapshot 字段来源）
- **UI 参考**：mp `preorder-detail.html`（轮播 + 富文本 + 规格选择 + 底部 CTA "立即购买"）+ `order-confirm.html`（地址 + 金额 + 不支持退款勾选）+ doc/12 §MP-ORD-PREORDER-DETAIL / §MP-ORD-CONFIRM

## What

mp 端两个页面 + 一个加购校验逻辑：

1. **商品详情页**：主图轮播 / 名称 / 起始价 / 截止倒计时 / 到货日 / 富文本描述（rich-text）/ 规格选择 panel（SKU 列表，选中后显示该 SKU 实际价 / 剩余库存）/ 底部 CTA「立即购买」
2. **加购校验**（点 CTA 时）：
   - 校验登录（未登 → 跳 SYS-002 登录流程后回跳）
   - 校验 deadline_at 未过 + 商品 status='on'（已过 / 已下架 → 拦截 + toast「该商品已截止」+ 跳回列表）
   - 校验 SKU 库存（stock_init NOT NULL 时 stock_left > 0）
3. **确认订单页**：商品 + 规格 snapshot 展示 / 数量 stepper / 收货地址（默认地址，可改）/ 金额计算 / 「我已阅读并接受预购商品不支持退款」勾选框（不勾不允许提交）/ 底部「提交订单」CTA → 跳 ORD-104

本 ticket 仅做 UI 流程 + 确认订单页校验，**不调起支付**（支付在 ORD-104 接入）。

## AC（验收标准）

- [ ] **AC 1**：mp `GET /app/gz/ord/product/{id}` 接口：
  - 返回商品所有字段 + SKU 列表（id / 规格名 / 价格 / 剩余库存）
  - **附加返回 server_now**（前端校准倒计时）
  - 调用同时 `UPDATE gz_ord_product SET view_count = view_count + 1 WHERE id=?`（ORD-102 加的字段，本 ticket 接入）
- [ ] **AC 2**：mp 端 `pages/ord/preorder-detail.vue` 页面：
  - 顶部 `<wd-swiper>` 轮播主图 + banner_imgs
  - 名称 / 起始价 / 倒计时（useCountdown 复用 ORD-102 composable）/ 到货日
  - 富文本 `<rich-text :nodes="description">`（uni 原生组件支持白名单标签）
  - 规格选择 `<wd-cell-group>` 列表 → 点 SKU 项选中 → 顶部价格 + 库存提示更新
  - 底部 fixed CTA「立即购买」按钮（业务组件 BizPrimaryButton）
- [ ] **AC 3**：加购校验逻辑（点 CTA 时）`useAddToConfirm(productId, skuId)`：
  - 未登 → 调 useAuth 触发登录 → 登录成功后回跳本动作
  - `POST /app/gz/ord/product/validate-purchase`（参数 productId + skuId + quantity）后端校验
    - product status='on' + deadline_at > NOW() → 否则返回 errCode=`PRODUCT_OFF` + 「该商品已截止，请重选」
    - SKU 存在 + stock_init IS NULL（无限）OR stock_left >= quantity → 否则 errCode=`SKU_OUT_OF_STOCK`
  - 校验通过 → 跳确认订单页 `/pages/ord/order-confirm?productId=&skuId=&quantity=`
- [ ] **AC 4**：mp 端 `pages/ord/order-confirm.vue` 页面：
  - 顶部展示 商品主图 + 名称 + 选中规格 + 数量 stepper（默认 1）
  - 地址区：默认显示用户默认地址（GZ-USER-003 已有 gz_user_address.is_default=1 行）；点击 → 跳地址选择页（USER-003 已实现）；如无地址 → 显示「请添加收货地址」CTA → 跳新增地址页
  - 金额计算：`SKU 单价 × 数量`（前端实时算）
  - **「我已阅读并接受预购商品不支持退款」勾选框**（默认未勾，未勾时底部「提交订单」按钮 disabled）
  - 底部「提交订单」CTA → 调 ORD-104 接口（本 ticket 占位 console.log + toast「待 ORD-104 接入」，不真实提交）
- [ ] **AC 5**：未勾不支持退款 → 提交按钮 disabled + 灰色置灰 UI 反馈
- [ ] **AC 6**：单测（vitest）：
  - 加购校验逻辑（mock api 返回不同 errCode 时跳转 / toast 行为）
  - 金额计算（单价 × 数量）
  - 未勾退款条款时 disabled 状态
  - 共 ≥ 3 个测试方法
- [ ] **AC 7**：i18n 所有可见字符串

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`
  - `controller/applet/GzOrdProductMpController.java` 加 `getDetail(id)` + `validatePurchase(req)` 方法
  - `service/IGzOrdProductService.java` 增 `getDetailForMp(id)` + `validatePurchase(req)`
  - `domain/dto/applet/ValidatePurchaseReq.java` + `vo/applet/OrdProductDetailVO.java`
  - 错误码枚举 `OrdErrCodeEnum`（PRODUCT_OFF / SKU_OUT_OF_STOCK / PRODUCT_NOT_FOUND）
- **小程序**：`code/main/miniapp/src/`
  - `pages/ord/preorder-detail.vue` + `pages/ord/order-confirm.vue`
  - `composables/useAddToConfirm.ts` + 复用 `useCountdown` + `useAuth`
  - `components/biz/BizSkuSelector.vue` + `BizAddressBar.vue`（复用 USER-003 已有的地址组件如有）
  - `api/gz-ord.ts` 加 `getPreorderDetail / validatePurchase`
  - `pages.json` 加两个页面路由 + navigationBar 标题
  - i18n 字典扩展
- **测试**：vitest + 微信开发者工具走一遍详情 → 确认订单流程

## 备注

### 强约束

1. **deadline 校验在加购点强制**（doc/02 §3.2 AC 3 锚定）— 即使商品已加车（V1.0 无车，V1.1 也无车），提交时仍校验
2. **不支持退款勾选** — 合同 §4.5 + 防止客户后续投诉
3. **地址 snapshot 由 ORD-104 落库**（本 ticket 仅 UI 展示当前默认地址）— 用户改默认地址不影响已提交订单
4. **rich-text 渲染**（uni 原生组件）支持有限标签白名单 — admin 端富文本编辑器使用前要校验输出 HTML 合规
5. **业务组件包一层**（BizSkuSelector / BizPrimaryButton / BizAddressBar — CLAUDE.md §7.5）
6. **i18n 强制**
7. **本 ticket 不接入支付** — 提交按钮占位，真实提交在 ORD-104

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 加购校验独立接口 validate-purchase | 提交订单（ORD-104）会再校验一次，本接口主要为 UX —— 点 CTA 即时反馈，不延迟到下一页 |
| D2 | server_now 同接口返回（不单独接口） | 减少 RTT |
| D3 | 数量 stepper 默认 1 + 上限 SKU 剩余库存 | 防止用户手滑超买 |
| D4 | 不支持退款勾选放在确认订单页（不是详情页） | 详情页是浏览阶段，确认页才是承诺阶段 |
| D5 | 富文本 description 用 uni rich-text 不是 webview | webview 性能差且需上下文切换；rich-text 满足谷子预购富文本展示需求 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 用户点立即购买到点提交订单的窗口期商品下架 | ORD-104 提交时再校验（双重防线）；本 ticket 占位逻辑不动 |
| R2 | 用户无收货地址直接提交 → ORD-104 拒收 | 本 ticket 确认页 UI 强制显示「请添加收货地址」CTA，无地址按钮 disabled |
| R3 | SKU 库存信息 mp 端显示不实时（其他用户已购但本用户未刷新） | 详情接口每次进入实时拉取 stock_left；商品列表不展示库存 |
| R4 | 富文本图片懒加载导致首屏空白 | uni rich-text 不支持懒加载，依赖图片本身 CDN 性能；后端富文本编辑时引导运营压缩图片 |
| R5 | i18n 字典遗漏 — 「请添加收货地址」「该商品已截止」等场景文案 | testing-human 检查清单必查每个文案是否走 t() |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
