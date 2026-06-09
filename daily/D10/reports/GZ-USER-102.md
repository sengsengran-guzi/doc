# GZ-USER-102 完工报告 — mp 订单详情统一页（预购 + 扭蛋多态）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游 USER-101 已就绪（统一 VO + 只读 mapper + service） | ✅ 读 reports/GZ-USER-101.md：GzUnifiedOrderVo 12 字段 + OrdOrderRow/GachaOrderRow 只读投影 + GzUnifiedOrderServiceImpl |
| 上游表 / snapshot 列存在（gz_ord_order / gz_gacha_order） | ✅ V202606061400(ORD-104) + V202606171400(GACHA-104)；列 product_snapshot_json / sku_snapshot_json / qty / prize_snapshot_json / machine_snapshot_json 实有 |
| snapshot JSON 形状核对（R2 缓解） | ✅ 比对源码 OrdSnapshot.java + GzOrdOrderServiceImpl.buildXxxSnapshot：preorder product={productId,productNo,name,mainImageId,ipTag,deliveryDateText,deliveryDateExact} / sku={skuId,skuNo,specName,priceCent}；gacha prize={name,imageId,rarity} / machine={name,coverImageId}（与 USER-101 service 读法一致） |
| 后端编译通过（gz-user -am offline） | ✅ |
| 单测通过 | ✅ 10/10（6 USER-101 原有 + 4 新增 USER-102 detail） |
| 全链 install（common/user） | ✅ BUILD SUCCESS |
| mp 构建到 dist | ✅ DONE Build complete + order-detail.{js,wxml,wxss,json} 生成 |
| vitest unit | ✅ order-detail.logic 8/8 + me 全域 36/36 无回归 |
| type-check（vue-tsc --noEmit） | ✅ 0 error |
| 鉴权模型 | C 端 @SaCheckLogin + user_id 归属（沿用 USER-101 偏差裁定，非 @SaCheckPermission 店员门） |
| ADR 已读 | ADR-0004（店员权限门，确认本卡是 C 端不挂 SaCheckPermission）/ ADR-0005（C1 物流，本卡物流占位） |

> 本仓库无 git（env 提示 "Is directory a git repo: No"），跳过 git status 项；用 ls / 文件清单替代 diff --stat。

### §0 关键蓝图引用摘录

- **doc/12 §MP-ORD-DETAIL**：统一布局五段顺序锚定（状态卡 → 商品 → 物流 2 态 → 订单信息 → 底部 CTA）；mockup order-detail.html 7 节点版作废，只参考结构。
- **doc/11 §8.1**：详情字段口径完全复用 USER-101 统一 VO；§6.3 gz_ord_order snapshot / §7.4 gz_gacha_order snapshot 字段来源。
- **doc/10 §9（C1 物流 2 态 + 终态）**：logistics_status ∈ in_japan / in_china_dispatching / delivered，独立于 business_status。
- **D10 README §6 + §8**：差异块复用同一份 view-model（ADMIN-103 也复用）；盲盒语义仅扭蛋，UI 用 获得物/获得时间/稀有度，禁 中奖/抽奖/开奖。

## 实现摘要

### 后端（ruoyi-gz-user，无新 DDL，消费 USER-101/D09 已建表）

| 文件 | 动作 | 作用 |
|---|---|---|
| `domain/vo/UnifiedOrderDetailVo.java` | 新增 | = USER-101 统一 12 字段 + 内嵌 GachaSnapshot(5 字段) / PreorderSnapshot(7 字段) 差异块 |
| `domain/entity/readonly/OrdOrderRow.java` | 加 2 列 | 补 skuSnapshotJson + qty（预购差异块需要） |
| `service/IGzUnifiedOrderService.java` | 加方法 | `getDetail(orderNo, userId)` |
| `service/impl/GzUnifiedOrderServiceImpl.java` | 加实现 | orderNo 前缀（PREORD-/GACHA-）判 businessType → 查只读 mapper → 归属校验 → 解 snapshot 拼差异块；复用 USER-101 的 mergeGachaProductSnapshot（统一字段口径一致） |
| `controller/applet/GzUserOrderMpController.java` | 加端点 | `GET /app/gz/user/orders/{orderNo}`（@SaCheckLogin + 非本人/不存在 → R.fail(403)） |
| `test/.../GzUnifiedOrderServiceImplTest.java` | 加 4 测 | 102a 预购 7 字段 / 102b 扭蛋 5 字段 + 合并 / 102c 非本人 null / 102d 非法前缀·查无·null |

**新增 detail 端点：是。** `GET /app/gz/user/orders/{orderNo}`（USER-101 报告已预判此需求并钉死纪律：用只读 mapper 镜像，**不注入 gz-ord/gacha service** 避免 Maven 环 —— 本卡严格遵守，全链 install 无环）。

### 小程序（miniapp）

| 文件 | 动作 |
|---|---|
| `pages/me/order-detail.vue` | 重写为统一多态页（原 GZ-ORD-105 preorder-only 时间线版被替换为 USER-101 统一 VO 消费版）|
| `pages/me/order-detail.logic.ts` | 新增（纯逻辑：状态映射 / 终态 / CTA / 地址解析 / 多态取图，供 vitest）|
| `pages/me/order-detail.logic.test.ts` | 新增（8 vitest）|
| `components/biz/BizOrderHeader.vue` | 新增（状态卡，tone red/green/muted）|
| `components/biz/BizProductSnapshot.vue` | 新增（商品块，businessType 多态：扭蛋获得物+稀有度边框 / 预购商品+SKU）|
| `components/biz/BizLogisticsCard.vue` | 新增（物流占位/最简 3 态，USER-103 实装内部 UX）|
| `api/gz-user.ts` | 加 UnifiedOrderDetailVO / UnifiedGachaSnapshot / UnifiedPreorderSnapshot 类型 + `getUnifiedOrderDetail(orderNo)` |
| `locale/user.zh-CN.ts` | 加 `order.detail.*` 双语命名空间（zh/en）+ isEn() |
| `pages/me/orders.vue` | 列表卡点击改携 `orderNo`（原携内部 id）→ 对齐统一详情按 orderNo 寻址 |

**统一布局五段顺序（强约束 #1，不可变）**：BizOrderHeader（状态卡）→ BizProductSnapshot（商品多态）→ BizLogisticsCard（物流占位）→ BizPanel（订单信息+地址）→ BizFixedCta（确认收货置灰，AC6）。退款仅纯文案，无按钮（铁律 #5）。

## AI 自测（≥ 3 代码 block）

### 后端编译 + 全链 install

```
$ mvn -q -o compile -pl ruoyi-modules/ruoyi-gz-user -am
（无错误输出 = 编译通过）

$ mvn -o install -Dmaven.test.skip=true -pl ...gz-common,...gz-user -am
[INFO] ruoyi-gz-common .................................... SUCCESS [  0.087 s]
[INFO] ruoyi-gz-user ..................................... SUCCESS [  0.065 s]
[INFO] BUILD SUCCESS
```

### 后端单测（10/10，含 4 个 USER-102 detail 多态验证）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-user -am \
    -Dtest=GzUnifiedOrderServiceImplTest -Dsurefire.failIfNoSpecifiedTests=false
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖：(102a) PREORD- → preorderSnapshot 恰好 7 字段（productName/productImageId/skuSpec/arrivalText/unitPriceCent/qty + 透传 totalAmountCent）+ 只查预购表 / (102b) GACHA- → gachaSnapshot 5 字段（prizeName/prizeImageId/rarity/machineName/paidTime）+ productSnapshotJson 仍合并 5 字段 + 只查扭蛋表 / (102c) 非本人订单 → null（controller 转 403）/ (102d) 非法前缀 TEST- / null orderNo / userId null / 查无 → 全 null 不误命中。

### mp 构建 + vitest + type-check

```
$ pnpm build:mp-weixin            # devtools cli 唤起属正常，已 pkill
DONE  Build complete.
$ ls dist/build/mp-weixin/pages/me/ | grep order
order-detail.js  order-detail.json  order-detail.wxml  order-detail.wxss  orders.*
$ ls dist/build/mp-weixin/components/biz/ | grep -E 'ProductSnapshot|OrderHeader|LogisticsCard'
BizLogisticsCard.*  BizOrderHeader.*  BizProductSnapshot.*

$ pnpm vitest run src/pages/me/
 ✓ src/pages/me/orders.logic.test.ts (3)
 ✓ src/pages/me/order-detail.logic.test.ts (8)
 ✓ src/pages/me/collection.logic.test.ts (25)
 Test Files  3 passed (3)    Tests  36 passed (36)

$ pnpm type-check     # vue-tsc --noEmit
（0 error）
```

### 多态渲染验证（vitest 断言摘要）

```
order-detail.logic — 业务态映射：created/paid/pending_ship/in_logistics → red；delivered → green；refunded/cancelled → muted；未知 → muted + label 原样回显 ✅
order-detail.logic — 稀有度色：SSR→--c-r-ssr / SR→--c-r-sr / R→--c-r-r / 其余→--c-r-n ✅
order-detail.logic — 终态(AC7)：delivered/refunded/cancelled/物流delivered → isTerminal=true ✅
order-detail.logic — 确认收货(AC6)：仅 in_china_dispatching 且非终态 → showConfirmReceipt=true ✅
order-detail.logic — pickImageId 多态：gacha→prizeImageId / preorder→productImageId ✅
order-detail.logic — 地址解析：正常拼行 / 空走兜底「中奖后补充地址」/ 脏 JSON 空串 ✅
```

## 风险提示 / 已知 issue

- **R1（鉴权口径偏差，沿用 USER-101 裁定）**：ticket AC1 写 sa-token-app；本卡用 @SaCheckLogin + user_id 归属（C 端模型，非店员 @SaCheckPermission 门）。与 USER-101 一致，待 product 在 doc/11 §8.1 回填修订源头。
- **R2（gacha 地址可空）**：开盒未补址时 addressSnapshotJson=null，前端兜底「中奖后补充地址」文案（盲盒语义内的"中奖"是兜底口语？— 已按 doc/12 §页面结构 5 原文采用；如需更严格盲盒化建议改 doc 源头文案为"开盒后补充地址"，本卡先遵循 doc/12 现文）。⚠️ 见下「对下游提示」。
- **R3（物流模块占位）**：BizLogisticsCard 仅最简 3 态文案，未做复制单号交互 / 快递 code→中文名映射 / 终态样式 —— 按强约束 #9 留给 USER-103 实装组件内部，本卡只接 props。
- **R4（确认收货置灰）**：AC6 要求 in_china_dispatching 态显示确认收货按钮，本卡 disabled + 点击 toast「确认收货功能即将上线」，USER-104 真实化。
- **R5（gz-ord PreorderFullChainMockTest 预存在 testCompile 失败）**：USER-101 报告已记录，与本卡无关，本卡未触碰 gz-ord 代码；跑测试仅针对 ruoyi-gz-user 模块。

## 对下游 ticket 的提示

1. **USER-103（物流 2 态实装）**：填 `BizLogisticsCard.vue` 内部 —— in_china_dispatching 态加 cnCarrierCode→中文名（字典 gz_express_carrier）+ 复制单号按钮（uni.setClipboardData，i18n key `order.detail.logiCopyTracking`/`logiCopied` 已备好）+ 终态样式。props 接入点已就位（logisticsStatus/cnCarrierCode/cnTrackingNo），不动 order-detail.vue 主体。
2. **USER-104（确认收货）**：order-detail.vue 的 `onConfirmReceipt()` 现仅 toast；真实化时调签收接口 + 刷新 detail，去掉 BizFixedCta 的 `primary-disabled`。
3. **统一 mp 订单列表（USER-101 mp 消费侧，尚未建）**：当前 `pages/me/orders.vue` 是 ORD-105 preorder-only 列表（gacha tab 占位），只拉预购真数据。**扭蛋详情分支可达性依赖统一列表落地** —— 详情端点本身按 orderNo 已可独立工作（curl 可验），但 Kevin 真机走 gacha 详情需有 gacha 订单进列表。建议排一张「mp 统一订单列表」ticket 用 USER-101 的 `GET /app/gz/user/orders` 替换 orders.vue 数据源（届时 3 tab 全真数据，gacha 详情即 N=1 可达）。
4. **ADMIN-103（admin 订单详情）**：可直接复用本卡的差异块字段语义（gachaSnapshot 5 / preorderSnapshot 7），后端 UnifiedOrderDetailVo 可作为 admin 端 view-model 参考（admin 多一个申请退款按钮）。
5. **doc 源头建议（§9.5 #1）**：doc/12 §MP-ORD-DETAIL §页面结构 5 的「中奖后补充地址」文案与盲盒语义（禁"中奖"）冲突，建议 product 改 doc 文案为「开盒后补充地址」，本卡先遵循 doc 现文以免擅自偏离权威。

## 风险提示 / 待 Kevin 批量人验关注（mp 端）

- 我的订单（会员中心「我的订单」cell → /pages/me/orders）→ 点预购订单卡 → 进统一详情页：状态卡 / 商品块（预购：图+名+规格+数量+单价）/ 物流占位 / 订单信息（订单号+时间+地址）/ 底部「如需退款请联系客服」纯文案。
- gacha 详情：暂需 curl 或等统一列表 ticket（见对下游 #3）；详情页本身扭蛋分支已实现（获得物图+稀有度边框+扭蛋机名+获得时间），盲盒语义已遵循。
- Tier 2 可达（AC10）：会员中心 →「我的订单」→ 点单卡 → 详情，预购订单 N=1 可达，无需临时入口（现成路径已通）。

## §AI 测试段（kevin-qa 自动追加，21:32）

### API 契约回归

```bash
# USER-102: GET /app/gz/user/orders/{orderNo} - 不存在/非本人 → 403
curl GET /app/gz/user/orders/PREORD-999999
# code=403 ✅（非本人/不存在统一 403，不泄露存在性）
```

### 后端单测（归 GZ-USER-101 报告，USER-102 新增 4 测）

```
[INFO] Tests run: 10, Failures: 0, Errors: 0 -- GzUnifiedOrderServiceImplTest
（含 102a 预购 7 字段 / 102b 扭蛋 5 字段 / 102c 非本人 null / 102d 非法前缀 null）
```

### mp vitest 回归

```
 ✓ src/pages/me/order-detail.logic.test.ts (8 tests)（含确认收货 CTA 门、终态、多态图 pick）
 ✓ 全域 34 files, 301 tests passed ✅
```

### Tier 2 可达性

会员中心→「我的订单」→点单卡→详情，N=1/2 可达 ✅（无临时入口）

### 跳过 / 未跑

- gacha 详情真机走查（依赖统一列表 mp 消费侧落地，真机 Tier 2 人验）
- 地址为 null 时「开盒后补充地址」文案语义（kevin 批量人验视觉判定）

### 结论

✅ Tier 1B 全通过，ticket 可 close；mp 进人验列
