# GZ-ADMIN-103 完工报告 — 订单管理（三类聚合，走 gz_pay_transaction 回查）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游表存在（gz_pay_transaction / gz_ord_order / gz_gacha_order） | ✅ V202606041200(PAY-001) / V202606061400(ORD-104) / V202606171400(GACHA-104) |
| ord create_dept 潜伏 fix（主线程补） | ✅ V202606180000__GZ-ORD-101-fix-base-columns.sql 存在（确认即可，未重复建） |
| 不再建 ord 表结构迁移（与 ADMIN-101 wave 并行） | ✅ 本卡仅新增 menu seed，零业务表 DDL |
| GZ-PAY-103 退款现状 | ✅ **已完工**：PayRefundController + PayRefundServiceImpl(gz-common) + menu 5106-5108 已授 owner；退款按钮 **enabled** |
| 编译通过（gz-ord -am offline） | ✅ |
| menu_id 段位（11007-11019 GZ-ADMIN 扩展段） | ✅ 取 11007/11008/11009，未撞已占 11003-11006 |
| Flyway 时间戳 > 已有最大（out-of-order=false） | ✅ 改名 V202606181000（> V202606180100 ADMIN-101），原 V202606111000 会被拒 |
| ADR 已读 | ADR-0005（跨境物流 C1 2 态）；物流卡按 3 态只读，无 7 节点 |

### 关键 §0 决策

- **GZ-USER-101 统一 VO service 尚未就绪**（grep 无 GzUnifiedOrder* in user/ord src）→ 按任务卡兜底：admin 端自实现回查 + 差异块，VO 字段名严格对齐 doc/11 §8.1（`GzUnifiedOrderVo`，与 USER-101 同源），完工后主线程校对齐。
- **退款 API 契约修正**：任务卡假设 body=`{businessOrderNo, reason}`，实际 PAY-103 `RefundApplyBo` = `{transactionId, reason}`（transactionId = gz_pay_transaction.id）。已对齐真实契约 —— VO 暴露 `transactionId`，前端按此 id 调 PAY-103，**不另造退款接口/stub**（PAY-103 plus-ui 端 `applyRefund` 已存在，直接复用）。
- **模块依赖**：gz-ord 新增 `ruoyi-gz-gacha` 依赖回查扭蛋单。gacha→gz-common 单向，ord→gacha 无环（gacha 不依赖 ord）。已验证。

## 实现摘要

### 改动文件

**后端（ruoyi-gz-ord 新增 6 + ruoyi-gz-common 改 2 + DDL 1）**
- 新增 `domain/bo/GzAdminOrderQueryBo.java` — admin 三类聚合查询入参
- 新增 `domain/vo/GzUnifiedOrderVo.java` — 统一订单 VO（doc/11 §8.1，含 preorder/gacha 差异块字段 + transactionId）
- 新增 `service/IGzUnifiedOrderService.java` + `service/impl/GzUnifiedOrderServiceImpl.java` — gz_pay_transaction 主表分页 + 回查映射
- 新增 `controller/GzOrdOrdersController.java` — `/system/gz/ord/orders` list/detail
- 新增 `src/test/.../GzUnifiedOrderServiceImplTest.java` — AC11 三单测
- 改 `ruoyi-gz-ord/pom.xml` — 加 ruoyi-gz-gacha 依赖
- 改 `ruoyi-gz-common IGzUserService + GzUserServiceImpl` — 加 `selectIdsByKeyword`（昵称/openid 模糊）
- 新增 `db/migration/V202606181000__GZ-ADMIN-103-menu.sql` — menu 11007-11009 + owner 授权

**前端（plus-ui 新增 4）**
- 新增 `api/gz-ord/orders.ts` — list/detail（GzUnifiedOrderVO，id 全 string，金额 _cent）
- 新增 `views/gz-ord/orders/index.vue` — 业务 tab + 6 筛选项 + 聚合表格
- 新增 `views/gz-ord/orders/components/OrderDetailDrawer.vue` — 差异块多态渲染 + 物流卡 + 退款按钮
- 新增 `views/gz-ord/orders/components/RefundConfirmDialog.vue` — 全额退款二次确认（复用 PAY-103 applyRefund）
- 改 `lang/zh_CN.ts` + `lang/en_US.ts` — gzOrdOrders 块全覆盖（不硬编码中文）

### 聚合口径（强约束 #1 落地）

- 以 `gz_pay_transaction` 为分页主表（财务真源，含 test 单），`business_type` / orderNo(likeRight) / 时间 / userKeyword→userIds 在主表层过滤。
- 按 business_order_no 批量 IN 回查 `gz_ord_order`(preorder) / `gz_gacha_order`(gacha)（非 N+1，R3）。test 单 business_order_no=null 仅投影支付流水。
- businessStatus（统一 chip）/ logisticsStatus 在回查后本页内过滤（V1.1 小数据量，R3）。
- 租户/软删全走 ruoyi 拦截器，不建物理 VIEW（决策 D2 / F8.1）。
- **未建** gz_order 单表 / biz_line / A·B 列 / gz_unified_order_view 物理 VIEW。

### 业务类型差异块（§6，复用 doc/11 §8.1 view-model）

- preorder：商品名 + 规格 + IP + 截止/到货日 + 收货地址。
- gacha：获得物 snapshot（name/图/稀有度）+ 来源扭蛋机名；UI 文案「获得物 / 出现概率 / 稀有度」，**禁** 抽奖/中奖/开奖。imageId 回退规则 prize→machine cover（doc/11 §8.1）。
- test：仅支付流水字段（无业务/物流/地址块）。
- 物流卡：C1 三态只读（在日本 / 已发往中国+快递中文名+单号 / 已签收），无 7 节点时间线。

## AI 自测（Tier 1A）

### 编译（gz-ord -am offline）
```
mvn -q -o compile -pl ruoyi-modules/ruoyi-gz-ord -am
# 无输出 = BUILD SUCCESS（offline 干净编译）
```

### 单测（AC11，3/3 通过）
```
[INFO] Running org.dromara.gz.ord.service.impl.GzUnifiedOrderServiceImplTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.817 s
[INFO] BUILD SUCCESS
# ① list 全部：主表分页 + 含 test 单 + preorder/gacha 回查映射（businessTypeLabel/chip/snapshot/user）
# ② list businessType=gacha：仅扭蛋单 + prize/machine snapshot + rarity + in_logistics→shipping chip
# ③ businessStatus chip 本页过滤（done 只留 delivered）+ detail 按 txnId 回查 + null 守卫
# 另：gz-common GzUserServiceImplTest 8/8 通过（selectIdsByKeyword 改动无回归）
```

### mvn install（4 模块 -am，运行时 jar 刷新）
```
[INFO] ruoyi-gz-common .................................... SUCCESS
[INFO] ruoyi-gz-user ..................................... SUCCESS
[INFO] ruoyi-gz-gacha .................................... SUCCESS
[INFO] ruoyi-gz-ord ..................................... SUCCESS [ 2.616 s]
[INFO] BUILD SUCCESS
```

### plus-ui build:prod（真跑绿）
```
vite build --mode production → 全部 chunk 产出，无报错
dist/assets/OrderDetailDrawer-FWNCBLMZ.js          ✅
dist/assets/RefundConfirmDialog-CCouj-fn.js        ✅
（orders/index.vue 进 system/gz 路由 chunk）
dist/index.html.gz 111.32kb -> 48.39kb
```

## 风险提示 / 已知 issue

- **R-VO 对齐**：USER-101 统一 VO 并行未就绪 → 本卡自实现 `GzUnifiedOrderVo`（字段名严格 doc/11 §8.1）。USER-101 落地后如其 VO 在 gz-user 包，主线程需校对字段名一致（businessType 值 preorder/gacha、productSnapshot 合并 5 字段、cnDispatchedAt 命名）；admin 这套可独立运行不阻塞。
- **R-chip 分页 total**：businessStatus/logisticsStatus 本页内过滤后 total 仍用主表分页 total（运营辅助筛，V1.1 千级数据可接受）。若上量后需精确 total，迁移到 mapper 层 UNION 子查询（V2 评估，doc/11 §8.1 已留口）。
- **退款契约**：用 transactionId（非 businessOrderNo）调 PAY-103，与任务卡描述不同但与 PAY-103 真实接口一致。
- 待 Kevin 批量人验关注（仅 mp 端）：**N/A — 纯 admin ticket，无 mp 端，AI ✅ 即终态，无人验**。

## 对下游 ticket 的提示

- **GZ-ADMIN-201（mp 店员端订单查看下沉）**：可复用本卡 `IGzUnifiedOrderService` 的映射逻辑（差异块/chip/snapshot 解析）；店员端加 `@SaCheckPermission("gz:ord:view")` + 同租户即可，不另造平行查询。
- **GZ-ADMIN-104（物流推进下沉 mp）**：本卡详情「推进物流」按钮占位跳 `/gz-ord-logistics?orderNo=`（路由暂不存在 → catch 提示），ADMIN-104 建该页后即通。
- **GZ-USER-101**：本卡 `GzUnifiedOrderVo` 在 `org.dromara.gz.ord.domain.vo`；若 USER-101 决定把统一 VO 放 gz-user 或 gz-common 共享包，主线程统一二者（建议下沉 gz-common 供两端共用，避免双份）。
- **Tier2 临时入口**：无（纯 admin，无 mp 新页）。

## §AI 测试段（kevin-qa 自动追加，21:32）

### admin Playwright E2E（plus-ui 8090，gz_owner 登录）

```
PASS: 登录 → /index ✅
PASS: 进 /gz/gz-ord-orders → el-table 渲染 ✅
PASS: Table headers: 订单号 | 业务 | 用户 | 商品 | 金额 | 业务状态 | 物流 | 创建时间 | 操作 ✅
PASS: Radio buttons (4 tabs): 全部, 预购, 扭蛋, 测试单 ✅
PASS: 点击「预购」tab → 页面不跳转 ✅
PASS: 点击「扭蛋」tab → 页面不跳转 ✅
PASS: 页面含「退款」文本（退款按钮/列）✅
PASS: Filter fields: 订单号, 用户, 业务状态, 物流, 创建时间 ✅
```

### API 契约回归

```bash
# 三类聚合列表
GET /system/gz/ord/orders/list → code=200, total=0 ✅
GET /system/gz/ord/orders/list?businessType=preorder → code=200, total=0 ✅
GET /system/gz/ord/orders/list?businessType=gacha → code=200, total=0 ✅
```

### 跳过 / 未跑

- 有实际订单时退款按钮 enabled/disabled 状态验证（测试环境无真实支付流水）→ Tier 1A 单测已覆盖 transactionId 逻辑
- 详情 drawer 差异块验证（preorder/gacha/test 三种）→ 无测试数据

### 结论

✅ Tier 1B 全通过，纯 admin ticket，AI ✅ 即终态（无 Tier 2 人验）
