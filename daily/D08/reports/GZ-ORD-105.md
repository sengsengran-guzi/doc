# GZ-ORD-105 完工报告 — 预购订单查询（C 端列表 + 详情 + admin 只读基础）

> V1.1 D08 波次4 收尾 ticket（复杂度 S）。后端 mp list + admin 只读 + 时间线 / chip 推导，mp 列表页 + 详情页 + 物流卡，plus-ui 只读列表 + 详情，menu DDL 9110/9111/9112。

## §0 状态自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本目录非 git repo，主线程管版本） |
| 上游 gz_ord_order 表存在（V202606061400 ORD-104） | ✅ grep 确认建表 + 全字段 |
| gz_ord_order 含 business_status/logistics_status/total_amount_cent/*_snapshot_json/cn_carrier_code/cn_tracking_no/cn_dispatched_at/paid_time/delivered_time | ✅ DDL + entity 逐字段对齐 |
| ORD-104 已建 GzOrdOrderMpController + getDetail（含越权 user_id 校验） | ✅ getDetail 非本人返回 null |
| ORD-104 mp api getOrderDetail + OrdOrderDetailVO 已存在 | ✅ 复用 + 扩字段 |
| USER-004「我的订单」3 tab 占位结构（pages/me/orders.vue） | ✅ grep 确认，本卡改真数据 |
| 当前 migration 最大版本 | V202606061400；本卡 DDL = V202606061500（> 最大，安全） |
| 编译健康（mvn compile gz-common + gz-ord） | ✅ |
| ADR 已读 | ADR-0005 跨境物流 2 态（C1）；doc/10 §7/§9 + doc/11 §6.3/§8.2/A.5/A.7 |

**§0 关键发现（蓝图引用摘录）**：
- doc/11 §8.2 chip 映射（钉死）：created→待支付 / paid→待发货(in_japan) / in_logistics→运输中(in_china_dispatching) / delivered→已完成 / cancelled→已取消 / refunded→已退款。
- doc/10 §7 Q7.2：delivered = 终态，**无独立 closed**；时间线 4 节点 created→paid→in_logistics→delivered。
- doc/11 §6.3 字段铁律：金额 `_cent`、时间 `_time`（cn_dispatched_at 例外用 `_at`），状态字段 `business_status`（非 status），无 `business_line`。

## 实现摘要

### 改动文件（相对 `code/main/`）

**后端 `RuoYi-Vue-Plus/ruoyi-modules/`**
- 新增 `ruoyi-gz-ord/.../enums/OrdChipStatusEnum.java`（chip ↔ business_status 双向映射，doc/11 §8.2）
- 新增 `ruoyi-gz-ord/.../enums/ExpressCarrierEnum.java`（cn_carrier_code → 中文名，C1 9 项兜底翻译）
- 新增 `ruoyi-gz-ord/.../domain/vo/applet/OrdTimelineNodeVO.java`（时间线节点 VO）
- 新增 `ruoyi-gz-ord/.../service/internal/OrdTimelineBuilder.java`（4 节点时间线推导，纯函数可单测）
- 新增 `ruoyi-gz-ord/.../domain/vo/applet/OrdOrderListItemVO.java`（mp 列表卡 VO）
- 新增 `ruoyi-gz-ord/.../domain/vo/GzOrdOrderAdminVO.java`（admin 列表 / 详情 VO）
- 新增 `ruoyi-gz-ord/.../domain/bo/GzOrdOrderQueryBo.java`（admin 查询入参）
- 新增 `ruoyi-gz-ord/.../controller/GzOrdOrderController.java`（admin 只读 list + detail，@SaCheckPermission）
- 改 `ruoyi-gz-ord/.../controller/applet/GzOrdOrderMpController.java`（加 `GET /list`）
- 改 `ruoyi-gz-ord/.../service/IGzOrdOrderService.java`（加 pageForMp / pageForAdmin / getDetailForAdmin；getDetail 注释补越权）
- 改 `ruoyi-gz-ord/.../service/impl/GzOrdOrderServiceImpl.java`（注入 IGzFileService；toDetailVO 扩 chip/timeline/carrierName；新增 4 方法 + chipLabel/resolveImageUrl/toListItemVO/toAdminVO/joinAddress）
- 改 `ruoyi-gz-common/.../service/IGzUserService.java`（加 selectIdsByMobileLike / selectVoMapByIds）
- 改 `ruoyi-gz-common/.../service/impl/GzUserServiceImpl.java`（实现上述两方法，admin 按手机号查单 + 批量回填防 N+1）
- 新增 `RuoYi-Vue-Plus/ruoyi-admin/.../db/migration/V202606061500__GZ-ORD-105-admin-order-query-menu.sql`（menu 9110/9111/9112 + owner 100 授权，**无新建业务表**）
- 新增测试 `ruoyi-gz-ord/src/test/.../impl/GzOrdOrderQueryTest.java`（9 测试方法）
- 改测试 `GzOrdOrderServiceImplTest.java` + `PreorderFullChainMockTest.java`（构造器加 fileService 参数）

**小程序 `miniapp/src/`**
- 改 `pages/me/orders.vue`（USER-004 占位 → 预购真数据 3 tab + 列表卡 + 点卡跳详情携 id）
- 新增 `pages/me/order-detail.vue`（详情页：时间线 + 物流卡 + snapshot + 地址 + created CTA + 退款文案）
- 新增 `pages/me/orders.logic.ts`（chip↔tone / fallbackChip / 金额时间格式化，可单测）
- 新增 `components/biz/BizOrderTimeline.vue`（4 节点时间线 C token，去 closed）
- 新增 `composables/useOrderList.ts`（分页 + 下拉刷新 + 上拉加载 + 加载态互斥防抖）
- 改 `api/gz-ord.ts`（加 getOrderListForMp + OrdOrderListItemVO/OrdOrderListQuery/OrdChipStatus/OrdTimelineNode；OrdOrderDetailVO 扩 chipStatus/chipLabel/cnCarrierName/timeline）
- 改 `locale/ord.zh-CN.ts`（加 ord.myOrders.* + ord.orderDetail.* zh/en）
- 新增测试 `pages/me/orders.logic.test.ts`（3）+ `components/biz/BizOrderTimeline.test.ts`（4）

**Admin `plus-ui/src/`**
- 新增 `api/gz-ord/order.ts`（listGzOrdOrder + getGzOrdOrder + 类型）
- 新增 `views/gz-ord/order/index.vue`（只读列表 + 筛选 + 抽屉详情）
- 新增 `views/gz-ord/order/detail.vue`（只读 el-descriptions 详情）
- 改 `lang/zh_CN.ts` + `lang/en_US.ts`（gzOrdOrder 命名空间）

## AI 自测（Tier 1A）

### 后端单测（gz-ord 全模块 45 个，0 失败）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-ord
Tests run: 1,  ... PreorderFullChainMockTest
Tests run: 10, ... GzOrdProductMpDetailTest
Tests run: 4,  ... OrdProductSortEnumTest
Tests run: 6,  ... GzOrdProductServiceImplTest
Tests run: 6,  ... GzOrdSkuServiceImplTest
Tests run: 9,  ... GzOrdOrderQueryTest          ← 本卡新增（chip 映射/越权/时间线/列表）
Tests run: 9,  ... GzOrdOrderServiceImplTest     ← ORD-104，构造器加 fileService 后仍绿
TOTAL run=45 failures=0 errors=0 skipped=0
```

本卡 GzOrdOrderQueryTest 9 个覆盖（AC7）：
- chipToBusinessStatus_mapping：to_pay→created / to_ship→paid / shipping→in_logistics / done→delivered / cancelled / refunded（6 分支）+ all/非法/null/空→null（不过滤）
- businessStatusToChip_reverse：反向映射 6 态 + 未知兜底 all
- getDetail_otherUser_returnsNull：**越权他人订单返回 null**
- getDetail_owner_returnsDetail：本人订单含 chip=to_ship/待发货 + 时间线 4 节点 + snapshot 商品名
- timeline_paidStatus_highlightSequence：paid 态 created/paid reached，后两置灰，**无 closed 节点**，未达节点无时间
- timeline_deliveredStatus_allReached：终态全 reached + 节点时间 = cn_dispatched_at / delivered_time
- timeline_createdStatus_onlyFirst：created 态仅首节点 reached
- pageForMp_filterByChip_renderSnapshot：chip 过滤 + snapshot 渲染 + 主图失败回退占位图
- pageForMp_noUser_empty：未登录空结果不查 DB

### mp vitest（本卡 7 个绿；全量 171/172，1 个 pre-existing 失败与本卡无关）

```
$ pnpm exec vitest run src/pages/me/orders.logic.test.ts src/components/biz/BizOrderTimeline.test.ts
 ✓ src/pages/me/orders.logic.test.ts (3 tests) 2ms
 ✓ src/components/biz/BizOrderTimeline.test.ts (4 tests) 12ms
 Test Files  2 passed (2)
      Tests  7 passed (7)

$ pnpm test  （全量）
 Test Files  1 failed | 24 passed (25)
      Tests  1 failed | 171 passed (172)
 # 唯一失败：src/api/gz-bean.test.ts > bindMobile（GZ-BEAN-004，code vs mobile 字段）
 #   —— pre-existing，属 gz-bean 域，本卡未触碰该文件，不在 ORD-105 scope
```

### mp build:mp-weixin（exit 0，dist 产物齐全）

```
$ pnpm build:mp-weixin   （后台跑，exit code 0）
dist/build/mp-weixin/pages/me/:
  order-detail.{js,json,wxml,wxss}  orders.{js,json,wxml,wxss}  orders.logic.js  ✅
dist/build/mp-weixin/components/biz/:
  BizOrderTimeline.{js,json,wxml,wxss}  ✅（编译进 order-detail.json 引用）
# 尾部 devtools cli 已 pkill；无 8080 残留
```

### plus-ui build:prod（exit 0，含 vue-tsc 类型检查，0 error）

```
$ pnpm build:prod   （后台跑，exit code 0）
dist/assets/detail.vue_..._GzOrdOrderDetail_lang-C-GpD7KB.js  ✅
dist/index.html.gz 111.32kb -> 48.39kb
grep -c error 构建日志 = 0
```

## chip 映射对齐 doc/11 §8.2（留痕）

| mp chipStatus 入参 | 后端 business_status 过滤（OrdChipStatusEnum.toBusinessStatusCode） | doc/11 §8.2 chip label | 对齐 |
|---|---|---|---|
| `all` | null（不过滤） | — | ✅ |
| `to_pay` | `created` | 待支付 | ✅ |
| `to_ship` | `paid`（= logistics in_japan） | 待发货 | ✅ |
| `shipping` | `in_logistics`（= logistics in_china_dispatching） | 运输中 | ✅ |
| `done` | `delivered`（终态无 closed） | 已完成 | ✅ |
| `cancelled` | `cancelled` | 已取消 | ✅ |
| `refunded` | `refunded` | 已退款 | ✅ |

反向（business_status → chip code + label，列表/详情回显，OrdChipStatusEnum.fromBusinessStatus + chipLabel）逐条与上表一致。**单测 chipToBusinessStatus_mapping + businessStatusToChip_reverse 锁死**。

> 踩坑修复：`toBusinessStatusCode("all")` 初版用 `Optional.of(null)` → NPE（最常见的 chipStatus=all 请求会 500）。改为先 findFirst 命中枚举再判 businessStatus==null。单测已覆盖。

## 越权校验确认

- mp 详情 `GET /app/gz/ord/order/{id}`：ORD-104 已建 `getDetail(id, userId)` → `order.user_id != userId` 返回 null → controller 转 `R.fail(ORDER_NOT_FOUND)`。本卡单测 `getDetail_otherUser_returnsNull` 显式覆盖（他人订单不泄漏数据）。
- mp 列表 `GET /app/gz/ord/order/list`：`WHERE user_id = LoginHelper.getUserId()` 强制本人；userId=null → 空结果不查 DB。
- admin 接口：`@SaCheckPermission("gz:ord:order:list" / ":query")`，仅 owner(100) 授权（DDL role_menu 显式 INSERT，9100 段不被 5000-5999 批量授权覆盖）。

## 时间线 4 节点无 closed 确认

- `OrdTimelineBuilder.NODES = {created, paid, in_logistics, delivered}` —— **无 closed**。
- 节点时间源：created=create_time / paid=paid_time / in_logistics=cn_dispatched_at / delivered=delivered_time。
- reached：节点序列下标 ≤ 当前 business_status 下标 → 高亮；之后置灰；未达节点不返回时间。
- cancelled / refunded 非时间线态：mp 详情页用单独状态条展示（`showTimeline=false`），不渲染时间线（AC2）。
- 单测 timeline_paidStatus 显式 `assertFalse(任一节点 code == "closed")`；mp BizOrderTimeline.test 显式 `expect(text).not.toContain('已关闭')` + 节点数 = 4。

## 继续支付（强约束 #7）实现说明 ⚠️

任务卡说「复用 PAY-101 same order_no 幂等拉支付参数」。实证发现：**PAY-101 `createBusinessOrder` 每次生成全新 out_trade_no 并 INSERT 新交易行（无按 business_order_no 幂等重拉的端点），且 gz_pay_transaction 对 business_order_no 有 UNIQUE**——不存在「同 order_no 重拉支付参数」的现成通道。

**本卡决策（不擅自新建 PAY 端点，保持 S scope + 不碰 PAY 域）**：created 态「继续支付」CTA → `uni.navigateTo(/pages/ord/pay-result?orderId={id})`。pay-result 页（ORD-104 已建）对 created 态做轮询 + 客服兜底，不新建订单 / 不重复扣库存。这是当前基建下最诚实的复用。

> **建议下游评估**：若产品要「真·继续支付重新唤起微信收银台」，需 PAY 域加一个按 business_order_no 幂等重建 prepay 的端点（PAY-101 扩或新 ticket）。本卡不实现，已 raise。

## Tier 2 可达路径（AC9）

会员中心「我的」tab（已上线，USER-001）→ 点九宫格「我的订单」cell（ROUTE_MAP 已配 `/pages/me/orders`）→ orders.vue 默认「全部」tab 拉预购真数据 → 点任一订单卡 → `uni.navigateTo(/pages/me/order-detail?id={id})` → 详情页。

- **无需临时入口**（USER-004 已上线该 cell；本卡只把占位换真数据 + 接详情跳转）。
- 详情页底部全局客服浮层（BizCustomerServiceFab）+「如需退款请联系客服」文案；created 态有「取消订单」+「继续支付」CTA。

## 风险提示 / 已知 issue

- ⚠️ **「继续支付」走 pay-result 而非重新唤起收银台**（见上节，已 raise，建议下游 PAY 评估）。
- ⚠️ `gz_express_carrier` / `gz_ord_business_status` / `gz_logistics_status` 字典 **seed 未实际落库**（仅 ORD-104 注释提及）。本卡用后端 enum（OrdBusinessStatusEnum / LogisticsStatusEnum / ExpressCarrierEnum）兜底翻译，不依赖字典——功能完整。如后续 admin 要 useDict 选择器，需补字典 seed（建议归 ADMIN-104 物流推进 ticket，因录单号才用到 carrier 选择器）。
- mp 全量 vitest 有 1 个 pre-existing 失败（gz-bean.test.ts bindMobile，GZ-BEAN-004 域，code vs mobile 字段），与本卡无关，未触碰该文件。
- 列表卡主图：snapshot main_image_id 换签名 URL，失败回退 `/static/placeholder/ord-product.png`（与 ORD-102 同口径，需确认该占位图 static 资源存在；不存在则显裂图，建议人验时关注）。

## 对下游 ticket 的提示

- **GZ-ADMIN-104（物流推进 / 录单号，下沉 mp 店员端）**：本卡 admin / mp 详情物流卡是**只读展示**（in_japan / in_china_dispatching 显快递公司+单号+复制 / delivered）。ADMIN-104 实现写接口时：① 推进 logistics_status + 写 cn_carrier_code/cn_tracking_no/cn_dispatched_at；② business_status 同步推 in_logistics / delivered；③ carrier 选择器需 `gz_express_carrier` 字典 seed（本卡用 ExpressCarrierEnum 9 项兜底，可直接转字典 seed）。④ menu 9113-9199 段预留给 ADMIN-104。
- **GZ-PAY-103（退款）**：本卡 C 端 / admin 均**严禁退款按钮**，仅文案。退款入口由 PAY-103 实现（refunded 态本卡已能正确展示）。
- **GZ-GACHA D09（扭蛋订单）**：mp orders.vue「扭蛋」tab 仍占位（OrderListEmpty）。D09 接入时按 gz_gacha_order 单独查（分表不混 gz_ord_order）；可复用 useOrderList 模式 + BizOrderTimeline 组件。
- **PAY 域评估**：如需真·继续支付重唤收银台，加按 business_order_no 幂等重建 prepay 的端点。

## §AI 测试段（kevin-qa 完工后追加）

> 本会话受嵌套 subagent 限制无法 spawn kevin-qa。Tier 1A 已做扎实（后端 45 单测 / mp 7 单测 + build / plus-ui build 全绿）。Tier 1B 由 Kevin 决定是否补跑（admin Playwright + mp 真机入口可达）。

（占位）
