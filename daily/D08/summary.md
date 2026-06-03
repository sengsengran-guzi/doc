# GZ-ORD-101 完工报告 — 预购商品 + SKU 数据模型 + admin CRUD + 截止下架 SnailJob

> V1.1 波次1。从零建立预购业务上游配置数据模型（gz_ord_product / gz_ord_sku）+ admin CRUD（plus-ui 从零建）+ SKU 库存乐观锁扣减 service + 截止下架 SnailJob executor。

## §0 自检结果（grep 代码 + migration 实证）

| 检查项 | 结果 |
|---|---|
| git | N/A（非 git repo，环境说明已注明） |
| migration 最大版本 | `V202606051200`（实证 `ls db/migration/ \| sort \| tail`）；本 ticket DDL `V202606060900` + menu `V202606060901` 均 > 之 ✅ |
| `gz_ord_*` 表存在性 | `grep gz_ord_ migration/` = **0 命中** → 从零落表 ✅ |
| `gz_file_object` 存在 | ✅（`V202605281100__GZ-SYS-005`，image_id FK 语义目标，不加 DB 外键） |
| gz-ord 脚手架状态 | 仅 `controller/OrdHelloController.java`，无任何业务类 → 从零建 ✅ |
| gz-ord pom `ruoyi-common-job` | 原**缺**（空脚手架）→ 本 ticket 新增（+ jsoup 1.17.2 + spring-boot-starter-test，镜像 gz-news pom） ✅ |
| 编译 | `mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-ord`（无 -am，并行安全）EXIT 0 ✅ |
| ADR | 无相关（预购数据模型层无 ADR；snapshot 契约写 doc/11 §6.3） |

**构建纪律遵守**：与 PAY-101 同波次并行；PAY-101 改 gz-common，本 ticket 改 gz-ord。全程 `mvn ... -pl ruoyi-modules/ruoyi-gz-ord`（**无 -am**），不触碰 gz-common 重建。

## 实现摘要

### 改动 / 新增文件（相对 `code/main/`）

**后端 ruoyi-gz-ord（从零建）**
- `RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/pom.xml`（改：+ ruoyi-common-job / jsoup 1.17.2 / spring-boot-starter-test）
- `.../ord/enums/OrdProductStatusEnum.java`（on_shelf/off_shelf/auto_off + isManualTarget 守卫）
- `.../ord/exception/GzOrdErrorCode.java`（SKU_OUT_OF_STOCK 7001 等 7 个业务码）
- `.../ord/domain/entity/GzOrdProduct.java` + `GzOrdSku.java`（@TableLogic del_flag / @Version version）
- `.../ord/domain/bo/GzOrdProductBo.java`（含嵌套 @Valid SkuList）+ `GzOrdSkuBo.java` + `GzOrdProductQueryBo.java`
- `.../ord/domain/vo/GzOrdProductAdminVO.java`（含 skuList；id/mainImageId ToStringSerializer）+ `GzOrdSkuVO.java`
- `.../ord/mapper/GzOrdProductMapper.java`（autoOffExpiredProducts / increaseSalesCount）+ `GzOrdSkuMapper.java`（tryDeductStock / returnStock 自定义 SQL）
- `.../ord/service/IGzOrdProductService.java` + `impl/GzOrdProductServiceImpl.java`（CRUD + SKU diff + 业务码生成 + 到货日校验 + changeStatus + autoOff）
- `.../ord/service/IGzOrdSkuService.java` + `impl/GzOrdSkuServiceImpl.java`（tryDeductStock 重试 ≤3 抛 SKU_OUT_OF_STOCK）
- `.../ord/service/internal/OrdHtmlSanitizer.java`（jsoup 白名单，策略对齐 gz-news §5，不跨模块依赖）
- `.../ord/controller/GzOrdProductController.java`（`/system/gz/ord/product` 6 端点 + @SaCheckPermission 9100 段 perm）
- `.../ord/job/OrdProductDeadlineJob.java`（SnailJob @JobExecutor 薄壳 → 委托 service）
- 单测：`.../ord/service/impl/GzOrdSkuServiceImplTest.java`（6）+ `GzOrdProductServiceImplTest.java`（6）

**DDL（Flyway 自动跑）**
- `RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/db/migration/V202606060900__GZ-ORD-101-create-gz_ord_product-and-sku.sql`（两表一文件）
- `.../db/migration/V202606060901__GZ-ORD-101-menu.sql`（menu_id 9100-9104 + owner role 100 授权）

**Admin plus-ui（从零建）**
- `plus-ui/src/api/gz-ord/product.ts`（VO/Form/Query + 6 个请求；id 全 string）
- `plus-ui/src/views/gz-ord/product/index.vue`（BizTable 风列表 + 搜索 + SKU 子表可编辑行 元↔分 + 到货日二选一 + 富文本）
- `plus-ui/src/views/gz-news/article/components/NewsEditor.vue`（改：+ `usageType` prop，默认 news_inline；预购传 preorder_product_image，非破坏复用）
- `plus-ui/src/lang/zh_CN.ts` + `en_US.ts`（+ `gzOrdProduct` i18n 块）

**doc**
- `doc/11-字段权威表.md §6.3`（+ snapshot 字段清单 product_snapshot_json 7 项 / sku_snapshot_json 4 项，AC 8 / ORD-104 落单契约）

## AI 自测（Tier 1A）

### 编译 + install（gz-ord only，无 -am）
```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-ord -q
=== INSTALL EXIT: 0 ===
```

### 单测（12 通过 / 0 失败）
```
[INFO] Running org.dromara.gz.ord.service.impl.GzOrdSkuServiceImplTest
14:26:39 WARN  [gz-ord-sku] DEDUCT miss skuId=10 qty=1 version=0 remain=5 attempt=1/3
14:26:39 INFO  [gz-ord-sku] DEDUCT ok skuId=10 qty=1 fromVersion=1 attempt=2
14:26:39 WARN  [gz-ord-sku] DEDUCT miss ... attempt=1/3 ... 2/3 ... 3/3   (库存不足重试耗尽)
14:26:39 INFO  [gz-ord-sku] DEDUCT ok skuId=10 qty=100 fromVersion=0 attempt=1  (无限库存)
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdSkuServiceImplTest
[INFO] Running org.dromara.gz.ord.service.impl.GzOrdProductServiceImplTest
14:26:39 INFO  [gz-ord-cron] auto-off expired products count=3
14:26:39 INFO  [gz-ord-product] CHANGE-STATUS id=1 off_shelf → on_shelf
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdProductServiceImplTest
[INFO] Results: Tests run: 12, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖 AC 7：① 有限扣减成功 ② version 冲突影响 0 重试后成功 ③ 无限库存 NULL 不耗尽 ④ 库存不足重试 3 次耗尽抛 SKU_OUT_OF_STOCK ⑤ SKU 不存在 ⑥ qty≤0；product 侧：⑤ 截止下架 service / D5 auto_off 拒绝 / changeStatus 合法 / F6.1 到货日二选一（都空+都填）/ D1 SKU 非空。

### DDL + 核心 SQL 真 MySQL 验证（throwaway db，零影响 dev 数据）
```
=== DESC gz_ord_product / gz_ord_sku ===  (全字段类型/默认值正确，UNIQUE 含 tenant_id)
uk_product_no    → tenant_id, product_no       ✅
idx_status_deadline → tenant_id, status, deadline_time
idx_ip_status    → tenant_id, ip_tag, status   (ORD-102 筛选索引)
uk_sku_no        → tenant_id, sku_no           ✅
idx_product      → tenant_id, product_id

=== tryDeductStock SQL 行为（doc/11 §6.2 逐字 SQL）===
tag          affected  stock_remain  version
① 有限扣2      1         3             1     (5→3, v0→1)
② 无限扣100    1         NULL          1     (NULL-100=NULL 不耗尽)
③ 不足扣5      0         1             0     (1<5 影响0 不变)
④ version冲突  0         3             1     (旧v0 vs 现v1 影响0)

=== 截止下架 SQL（on_shelf 过期 → auto_off）===
PRD-EXPIRED  auto_off   (on_shelf + 截止1h前 → 转)
PRD-FUTURE   on_shelf   (未到期不动)
PRD-OFF      off_shelf  (非 on_shelf 不动)
throwaway db dropped
```

### plus-ui 类型检查 + 生产构建
```
$ npx vue-tsc --noEmit   (gz-ord 新文件 0 错)  EXIT 0
$ pnpm build:prod        BUILD EXIT: 0  (无 error/fail；gz-ord 引用入打包 dist/assets/index-CAKqXt0n.js)
```

## SnailJob 控制台注册清单（人工 — 禁 Flyway INSERT sys_job）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-ORD-PRODUCT-DEADLINE |
| 执行器路由（executor_info） | `ordProductDeadlineJob`（= `@JobExecutor(name)`） |
| 触发类型 / CRON | CRON `0 0 * * * ?`（每小时整点，时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD） |
| 组 | `ruoyi_group` |

> 双重防线（R4）：cron 每小时粒度 → 边界 1h 内仍可能显示 on_shelf；ORD-103/104 下单时再 hard check `deadline_time`。本任务仅负责状态展示态自动转 auto_off（D5：auto_off 唯一写入路径）。

## snapshot 字段清单（AC 8 — 供 ORD-104 落单，已写 doc/11 §6.3）

**product_snapshot_json**（7 项）：`product_id` / `product_no` / `name` / `main_image_id`（不存裸 url）/ `ip_tag` / `delivery_date_text` / `delivery_date_exact`
**sku_snapshot_json**（4 项）：`sku_id` / `sku_no` / `spec_name` / `price_cent`（下单锁价乘数）
ORD-104 落单：tryDeductStock 扣库存（乐观锁）+ 同事务序列化两组 snapshot 进 JSON 列（不散列）+ 调 PAY-101 建 transaction（business_type=preorder）。

## 风险提示 / 已知 issue

- **商品引用检查 hook 当前恒 false**：`isReferencedByOrder` / `isSkuReferencedByOrder` 因 `gz_ord_order` 尚未建（ORD-104）→ 本 ticket 软删 / SKU diff 删除暂不触发拒删分支。**ORD-104 实施时必须填实**：`SELECT EXISTS(SELECT 1 FROM gz_ord_order WHERE product_id=? / sku_id=?)`（决策 D4 / R3）。已在 service 内注释标注。
- **OrdHtmlSanitizer 与 gz-news HtmlSanitizer 各落一份**：gz-ord 与 gz-news 同级（都仅依赖 gz-common），不引入跨模块依赖；策略（jsoup Safelist.relaxed + img data-file-id + 外链 nofollow）完全一致。如未来要统一可下沉 gz-common（当前两处各 ~110 行，复制成本可接受）。
- **NewsEditor 加了 usageType prop**：非破坏（默认 news_inline，gz-news 调用不传 = 行为不变）；gz-ord 传 preorder_product_image。已 vue-tsc + build 全绿。
- 待 Kevin 批量人验关注：**N/A — 纯后端 + admin ticket**（Tech 段无 miniapp/ + AC 无微信原生能力，CLAUDE.md §8.2 例外，AI ✅ 即终态无人验）。

## 对下游 ticket 的提示

- **ORD-102（mp 商品列表 + 筛选）**：筛选字段 `ip_tag` 索引已建（`idx_ip_status (tenant_id, ip_tag, status)`）+ `idx_status_deadline`；mp 列表查 `status='on_shelf'`。实施前 grep migration 确认字段（R6 已闭环：字段 + 索引都在）。mp 端 controller 走 `/app/gz/ord/...`（与 admin `/system/gz/ord/product` 区分）。
- **ORD-103（mp 商品详情 + 下单确认）**：详情含 SKU 列表（`selectAdminById` 已返 skuList，mp 另写只读 VO）；description_html mp 渲染前再兜底 sanitize（R5，ORD-103 负责）；下单前 hard check `deadline_time`（双重防线 R4）。
- **ORD-104（预购下单跨域事务）**：① 库存扣减调 `IGzOrdSkuService.tryDeductStock(skuId, qty)`（已定义 + 单测，本 ticket 仅定义未接入）；② snapshot 按 doc/11 §6.3 清单序列化（11 项）；③ 销量累加调 `GzOrdProductMapper.increaseSalesCount(id, qty)`（已预置原子 UPDATE）；④ 填实 `isReferencedByOrder` / `isSkuReferencedByOrder` hook；⑤ 库存归还调 `GzOrdSkuMapper.returnStock`（已预置，退款/取消用）。
- **menu_id 9100 段已用 9100-9104**；ORD-104/105 订单 admin / 物流推进（D10）用 9105-9199。

## §AI 测试段（kevin-qa 完工后追加）

> kevin-coder 作为 subagent，Agent 工具不可用 → 本 ticket 不 spawn kevin-qa（主线程指示）。Tier 1A 已做扎实（编译 + 12 单测 + 真 MySQL DDL/SQL 验证 + plus-ui build）。Tier 1B（admin Playwright E2E + 后端集成）由主线程波次结束统一接管。
# GZ-ORD-102 完工报告 — mp 预购商品列表 + 筛选 + 排序（接真数据，解 ComingSoon）

> V1.1 D08 波次2 · mp ticket · 与 GZ-PAY-104 同子波次并行（PAY-104 改 gz-common，本卡改 gz-ord + miniapp）

---

## §0 状态自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本目录非 git 仓库，环境约定 "Is directory a git repo: No"） |
| 上游依赖 ORD-101 merge | ✅ migration `V202606060900__GZ-ORD-101-create-gz_ord_product-and-sku.sql` 已落 + gz-ord 模块文件齐 |
| 关键表/字段存在 | ✅ grep migration 确认（见下） |
| 编译/单测通过 | ✅ 后端 16 testcase 0 fail；mp ord vitest 16 pass |
| 关联 ADR | 任务卡标 `—`（无相关 ADR） |
| 构建纪律（无 -am） | ✅ 后端只 `-pl ruoyi-gz-ord` 不带 -am；未触碰 gz-common（PAY-104 占用） |

### grep migration 确认 gz_ord_product 展示字段（R1 风险闭环）

`V202606060900` 内字段全部命中任务卡锚定口径：
- `name` VARCHAR(128) ✅
- `main_image_id` BIGINT UNSIGNED（FK 语义→gz_file_object.id，禁裸 url）✅
- `ip_tag` VARCHAR(64) ✅
- `deadline_time` DATETIME(3)（**非 deadline_at**）✅
- `delivery_date_text` VARCHAR(64) / `delivery_date_exact` DATE（**非 arrival_***）✅
- `status` VARCHAR(16) DEFAULT 'off_shelf'，枚举 `on_shelf`/`off_shelf`/`auto_off` ✅
- `sales_count` BIGINT UNSIGNED（**热度复用，无 view_count**）✅
- `sort_no` INT ✅
- 索引 `idx_ip_status (tenant_id, ip_tag, status)` ✅
- `gz_ord_sku.price_cent` BIGINT（**非 price_fen**）/ `enabled` TINYINT ✅

**结论：零缺字段，本卡零 DDL（符合任务卡强约束 8 + R6）。当前 migration 最大版本 V202606061100（PAY-104），本卡未新增。**

### grep gz_file_object url 解析用法（复用 V1.0 机制）

- `org.dromara.gz.common.service.IGzFileService#getPresignedUrl(Long fileId)` → 返回 `GzFileObjectVO`（`.getUrl()` 带 1h 过期签名 URL，URL 不存裸串）。
- gz-news NEWS-001 同模式（cover 经 fileId 解析）。本卡 `GzOrdProductServiceImpl#resolveImageUrl(mainImageId)` 复用：NULL / 解析失败 → 占位图 `/static/images/mock-product.png`（R4 闭环，不返空串）。

---

## 实现摘要

> **重要发现**：本卡的后端（list/ip-tags 全链路）+ mp 前端（list.vue / BizPreorderCard / useCountdown / api/gz-ord.ts / i18n / 首页 teaser / pages.json / 两组 vitest）在我接手前已由上一轮落地（ORD-101 一并预建了 mp Controller 骨架，控制器注释即标 GZ-ORD-102）。本轮我执行了**完整代码审查（逐文件比对 8 个 AC + 强约束 1-8 + 决策 D1-D5 + 风险 R1-R6）+ Tier 1A 全量自测验证**，确认实现正确且 AC 全覆盖，未发现需返工项。

### 涉及文件（相对 `code/main/`）

**后端 ruoyi-gz-ord**（包 `org.dromara.gz.ord`）：
- `controller/applet/GzOrdProductMpController.java` — 基路径 `/app/gz/ord/product`，`@SaIgnore`（C 端浏览不挂权限）；端点 `GET /list` + `GET /ip-tags`（ORD-103 在本类追加 getDetail/validatePurchase）
- `service/IGzOrdProductService.java` + `service/impl/GzOrdProductServiceImpl.java` — `listForMp(req)` / `listOnSaleIpTags()`
- `domain/dto/applet/OrdProductListReq.java`（pageNum/pageSize=20/sortBy/ipTags）
- `domain/vo/applet/OrdProductCardVO.java`（id ToString / name / mainImageUrl / startPriceCent / ipTag / deadlineTime ISO8601 / deliveryText / salesCount）
- `domain/vo/applet/OrdProductMpListVO.java`（rows / total / serverNow 外层）
- `enums/OrdProductSortEnum.java`（ARRIVAL_ASC / HOT / DEADLINE_ASC + `ofCodeOrDefault` 非法兜底）
- `mapper/GzOrdSkuMapper.java#selectMinPriceByProductIds`（批量 GROUP BY MIN 价，免 N+1）

**mp miniapp**（相对 `miniapp/src/`）：
- `pages/ord/list.vue`（definePage 注册 `pages/ord/list`，navbar「预购日谷」）
- `pages/ord/list.logic.ts`（排序 tab 定义 + formatPriceCent / formatCountdown / formatDelivery 纯逻辑抽出供单测）
- `components/biz/BizPreorderCard.vue`（业务卡组件，BizPanel 包一层，不裸撒 wd-*）
- `composables/useCountdown.ts`（serverNow 校准 + onUnmounted clearInterval + computeRemaining 纯计算抽出）
- `api/gz-ord.ts`（getPreorderList / getPreorderIpTags + OrdProductCardVO/OrdPreorderListResult 类型）
- `locale/ord.zh-CN.ts`（ord.list.* zh + en 同文件，不混 emoji）
- `pages/index/index.vue`（「日谷预购」teaser url → `/pages/ord/list` + 去 soon，解 ComingSoon）
- `pages.json`（声明 pages/ord/list；tabBar 不动维持 3 tab；ord/index 占位页保留）

**测试**：
- `pages/ord/list.logic.test.ts`（9 testcase）
- `composables/useCountdown.test.ts`（7 testcase）
- 后端 `enums/OrdProductSortEnumTest.java`（4 testcase，排序映射 + 非法兜底）

---

## AI 自测（Tier 1A）

### 1. mp vitest — 本卡 ORD-102 相关文件（AC7）

```
 RUN  v2.1.9 .../miniapp
 ✓ src/pages/ord/list.logic.test.ts (9 tests) 3ms
 ✓ src/composables/useCountdown.test.ts (7 tests) 2ms
 Test Files  2 passed (2)
      Tests  16 passed (16)
   Duration  380ms
```

- `computeRemaining`：正常拆分天时分秒 / 不足一天省天段 / **归零分支（diff<=0 → expired 全 0）** / serverNow 校准语义 / parseIsoMs 边界 ✅
- `formatPriceCent`：整元省小数（12900→¥129）/ 角分保留 2 位（12990→¥129.90）/ null→价格待定 ✅
- `formatCountdown`：归零→已截止 / 有剩余天 / 不足一天省天段 ✅
- `ORD_SORT_TABS`：3 tab + 首项 = 默认 deadline_asc（对齐后端兜底）✅

> 全套 `pnpm test` 跑 130 testcase，**唯一 fail = `gz-bean.test.ts > bindMobile`（GZ-BEAN-004，期望 `mobile` 实际发 `code`）—— 非本卡引入的预存失败，与 ORD-102 无关**。本卡 ord 16 testcase 隔离运行全绿。

### 2. 后端单测 gz-ord（无 -am，并行安全；AC7②）

```
[INFO] Running org.dromara.gz.ord.enums.OrdProductSortEnumTest
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0 -- OrdProductSortEnumTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdSkuServiceImplTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- GzOrdProductServiceImplTest
[INFO] Tests run: 16, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

- OrdProductSortEnumTest 钉死 3 枚举 → ORDER BY 子句映射 + 非法/空/null 兜底 DEADLINE_ASC ✅

### 3. mp 构建 build:mp-weixin（验证 app.json 含 pages/ord/list）

```
DONE  Build complete.
Run method: open Weixin Mini Program Devtools, import dist/build/mp-weixin run.

# app.json pages（grep dist/build/mp-weixin/app.json）：
pages/bean/index
pages/index/index
pages/me/index
pages/ord/index          ← 占位页保留（路由不断）
pages/ord/list           ← 本卡新页 ✅

# pages/ord/ 编译产物：list.js / list.json / list.wxml / list.wxss / list.logic.js ✅

# tabBar 仍 3 tab：pages/index/index | pages/bean/index | pages/me/index ✅（未加第 5 tab）
```

> mem 已知：build 尾部唤 wechat devtools cli 假挂起，dist 实际已生成（"DONE Build complete"），手动 kill cli 进程（已清理，无残留）。build 模式产物在 `dist/build/mp-weixin`（非 dev）。

### 4. list 接口契约 mock 返回（任务卡要求贴）

`GET /app/gz/ord/product/list?pageNum=1&pageSize=20&sortBy=deadline_asc&ipTags=CHIIKAWA`
后端 `R<OrdProductMpListVO>`：

```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "rows": [
      {
        "id": "12",
        "name": "CHIIKAWA 毛绒挂件预购",
        "mainImageUrl": "https://cos.../presigned?...   (NULL → /static/images/mock-product.png)",
        "startPriceCent": 12900,
        "ipTag": "CHIIKAWA",
        "deadlineTime": "2026-08-20T23:59:59",
        "deliveryText": "2026-09-15",
        "salesCount": 42
      }
    ],
    "total": 8,
    "serverNow": "2026-06-03T15:37:00"
  }
}
```

mp http 封装解包：最外层 R 无 rows/total（http.ts L109 判断 false）→ 走 L112 `return responseData.data` → 前端 `getPreorderList` 收 `{rows,total,serverNow}` = `OrdPreorderListResult`。契约对齐 ✅
`GET /ip-tags` 返回 `R<List<String>>` = `{code,msg,data:["CHIIKAWA","海贼王"]}` → 解包返回数组 ✅

---

## AC 逐条核对

| AC | 状态 | 证据 |
|---|---|---|
| AC1 list 强约束 + 排序 + ipTags | ✅ | `listForMp` eq(status,on_shelf)+gt(deadline,now)+@TableLogic 软删；排序走枚举白名单 ORDER BY；ipTags 截断 10+warn |
| AC2 VO 字段 + serverNow | ✅ | OrdProductCardVO 8 字段 + OrdProductMpListVO.serverNow；起始价 batch MIN；图片解析+占位 |
| AC3 ip-tags 接口 | ✅ | `listOnSaleIpTags` DISTINCT ip_tag WHERE on_shelf+未截止+非空 |
| AC4 page UI（排序/chip/卡/下拉上拉/倒计时） | ✅ | list.vue + BizPreorderCard（C token，选中 var(--c-red)）+ onPullDownRefresh/onReachBottom + useCountdown 归零置灰禁点 |
| AC5 点卡跳详情 | ✅ | `goDetail` → `/pages/ord/preorder-detail?id=`（**对齐 ORD-103 实际命名**，非任务卡字面的 detail，见下游提示） |
| AC6 i18n zh+en 不混 emoji | ✅ | locale/ord.zh-CN.ts 全 key 双语 |
| AC7 vitest ≥2 | ✅ | 16 testcase（含倒计时归零 + 排序映射非法兜底）后端 4 + 前端 16 |
| AC8 Tier2 入口可达 | ✅ | 首页 teaser「预购」+「日谷预购」卡 → `/pages/ord/list`（去 soon，1 次点达；tabBar 不动；ord/index 保留） |

---

## 风险提示 / 已知 issue

- **R3 翻页跳号**（分页中商品被截止下架）：预购品类少、概率低，接受；卡片倒计时归零本地置灰兜底。
- **R4 主图占位**：`main_image_id` NULL / 解析失败 → `/static/images/mock-product.png`（C 系统 MOCK 水印占位，待甲方正版 IP 商品图替换，CLAUDE.md §7.5）。
- **gz-bean.test.ts 预存失败**（与本卡无关）：`bindMobile` 期望 `mobile` 字段实际发 `code`，属 GZ-BEAN-004 域。建议主线程派给 bean 域 ticket 闭环，不在本卡修。
- **待 Kevin 批量人验关注**（mp 端）：
  1. 首页「预购」teaser / 「日谷预购」卡点击 1 次 → 落预购列表页（不再 ComingSoon）
  2. 三态排序切换（截止紧迫默认 / 到货近 / 热度）列表正确重拉
  3. IP chip 横滑多选 + 「全部」清空，列表筛选生效
  4. 下拉刷新 + 上拉加载分页
  5. 卡片倒计时每秒走动；截止商品置灰 + 「已截止」+ 点击无跳转
  6. 点未截止卡 → 跳 `/pages/ord/preorder-detail`（ORD-103 落地前报"页面不存在"属预期）

---

## 对下游 ORD-103 的接力提示

1. **`GzOrdProductMpController` 已建**（`controller/applet/`，基路径 `/app/gz/ord/product`，`@SaIgnore`）→ ORD-103 在**同一个类追加** `GET /{id}`（getDetail）+ `POST /{id}/validate-purchase`（validatePurchase）。注释里已留 ul 占位。
2. **`api/gz-ord.ts` 已建**（mp 侧）→ ORD-103 在同文件追加 `getPreorderDetail(id)` / `validatePurchase(...)`，复用 `OrdProductCardVO` 风格 + ID string 契约。
3. **`composables/useCountdown.ts` 可直接复用**（详情页同样要截止倒计时；`useCountdown(deadlineIso, serverNowIso)` + `computeRemaining` 纯函数）。
4. **页面命名对齐（重要）**：列表→详情跳转用的是 **`/pages/ord/preorder-detail?id=`**（非任务卡 AC5 字面写的 `/pages/ord/detail`）—— 因 ORD-103 详情页实际命名为 `preorder-detail`。ORD-103 落地详情页时必须 `definePage` 注册路由名 `pages/ord/preorder-detail`，否则点卡跳转 404。
5. **起始价/图片解析机制可复用**：`GzOrdProductServiceImpl#resolveImageUrl` + `batchMinPrice`（详情单商品取 SKU 列表，可改用 `selectList` + 各 SKU enabled MIN，或直接展示全 SKU）。
6. **gallery_image_ids**（图集，逗号分隔 file_id）字段已在 schema，详情页轮播解析时同 `resolveImageUrl` 逐个解析。

---

## §AI 测试段（kevin-qa 完工后追加）

> 本卡运行于 subagent 嵌套限制下，无法 spawn kevin-qa。Tier 1A 已做扎实（vitest 16 + 后端 16 + build app.json 验证 + 接口契约核对）。**Tier 1B（mp 端 E2E / 后端集成 / 可达性验证）交主线程接管。**
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
# GZ-ORD-104 完工报告 — 预购下单跨域事务

> V1.1 第一个跨域事务：扣 SKU 库存 + INSERT gz_ord_order(snapshot) + 调 PAY-101 写 gz_pay_transaction（同事务），
> 支付回调按 PREORD- 前缀 SPI 路由到下沉 gz-ord 的 preorder handler → 订单 created→paid；物流默认 in_japan。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（sensenran 项目目录非独立 git 仓库，`git rev-parse` 无 toplevel；不 commit，符合 ticket 收尾要求） |
| 上游 gz_ord_product/gz_ord_sku（ORD-101 V202606060900） | ✅ grep 确认存在 + stock_total/stock_remain 字段（NULL=无限） |
| 上游 gz_pay_transaction business_type/fee_cent/version（PAY-001 V202606041200） | ✅ grep 确认 70/77/84 行 |
| 上游 gz_user_address（USER-003 V202606031100） | ✅ migration 存在；IGzUserAddressService.getByIdForUser 非本人返回 null |
| gz_user.openid（GzUserVO.openid） | ✅ 第 36 行 |
| 当前 migration 最大版本 | V202606061301（PAY-103 menu）；本卡 DDL = V202606061400（> 1301 ✅） |
| ADR-0005 已读（C1 物流 2 态） | ✅ logistics_status 仅 3 字段 + 默认 in_japan，无 node 表 |
| 编译基线 | ✅ mvn compile gz-common+gz-ord 通过 |
| 删占位后无重复 preorder handler | ✅ gz-common spi/handler 目录已删；启动 fail-fast 校验通过（gz-common 98 单测绿，SPI 路由表 "已注册 1 个 handler：[preorder]"） |

## 架构变更说明（ticket ⭐⭐ 必做 5 步）

gz-common 不能依赖 gz-ord（反向 = 循环依赖），故真实业务 handler 下沉 gz-ord：

1. ✅ **新建** `org.dromara.gz.ord.service.callback.PreorderPayCallbackHandler`（@Component implements gz-common `PayCallbackHandler`，supportedBusinessType=preorder，onPaid 委托 `IGzOrdOrderService.onPaid` 推进 created→paid）
2. ✅ **删除** gz-common 占位 `org.dromara.gz.common.pay.service.spi.handler.PreorderPayCallbackHandler`
3. ✅ **新建** `org.dromara.gz.ord.service.callback.PreorderRefundCallbackHandler`（implements `IRefundCallbackHandler`，onRefunded → gz_ord_order paid→refunded，**SKU 库存不归还**）
4. ✅ **删除** gz-common 占位 `PreorderRefundCallbackHandler`（整个 `spi/handler/` 目录已移除）
5. ✅ **删前修引用**：`GzPayBusinessFullChainMockTest`（PAY-101）+ `PayRefundServiceImplTest`（PAY-103）原 `new PreorderXxxHandler()` → 改用**测试内联匿名 handler**（implements 接口，supportedBusinessType=preorder）。**gz-common 98 单测仍绿**（关键验证：删占位 + 内联 handler 后无重复注册、SPI 路由命中不变）。

pom：gz-ord 新增 `ruoyi-gz-user` 依赖（取地址 snapshot + 归属校验；gz-user→gz-common 单向，无循环）。

## 实现摘要

**后端 gz-ord（新增）**：
- DDL `V202606061400__GZ-ORD-104-create-gz_ord_order.sql`（逐字段对齐 doc/11 §6.3）
- entity `GzOrdOrder` / mapper `GzOrdOrderMapper`（行锁 selectByOrderNo/IdForUpdate + 状态守卫 markPaid/markCancelled/markRefunded）
- service `IGzOrdOrderService` + `GzOrdOrderServiceImpl`（submit 跨域事务 / cancel / getDetail / onPaid / onRefunded）
- 2 callback handler（下沉，见架构变更）
- enums `OrdBusinessStatusEnum`（无 closed）+ `LogisticsStatusEnum`（C1 2 态+终态）
- DTO `SubmitOrderReq` / `OrdSnapshot`（3 段 snapshot POJO）；VO `SubmitOrderVO` / `OrdOrderDetailVO`
- MP controller `GzOrdOrderMpController`（`@SaCheckLogin` /app/gz/ord/order：submit / cancel/{id} / {id}）
- 扩 `GzOrdErrorCode`（ADDRESS_INVALID 7008 / PRODUCT_OFF 7009 / ORDER_NOT_CANCELLABLE 7010 / ORDER_NOT_FOUND 7011）
- 扩 `IGzOrdSkuService.restoreStock`（取消回滚库存，无限库存跳过）

**后端 gz-common（删 + 改）**：删 2 占位 handler；改 2 测试用内联 handler。

**mp**：
- `api/gz-ord.ts` +submitOrder/cancelOrder/getOrderDetail + 类型（SubmitOrderReq/VO/OrdOrderDetailVO/snapshot）
- `composables/useOrderSubmit.ts`（submit→requestPayment→跳 pay-result；取消/失败保 created）
- `pages/ord/order-confirm.vue`（接真 submit，去占位 console.log）
- `pages/ord/pay-result.vue` + `pay-result.logic.ts`（C 系统 Biz* + var(--c-*)，3s×10 轮询）
- `locale/ord.zh-CN.ts` +`ord.payResult.*`（zh-CN + en，无 emoji）

**关键决策落地**：
- **order_no = gz_pay_transaction.business_order_no**：gz-ord 用 PayOrderNoGenerator 生成 PREORD- 号作 order_no，传 PAY-101 当 businessOrderNo；回调 SPI 据 business_order_no 反查订单。
- **pay_transaction_id（微信交易号）建单时 NULL，回调 onPaid 回填**（doc/11 §6.3；微信侧交易号下单时不存在，故 AC2 的"submit 阶段 UPDATE pay_transaction_id"落到 AC3 onPaid，已与字段语义对齐 —— 见风险段说明）。
- **金额后端重算**（不信任前端）：total = sku.price_cent × qty。
- **snapshot 用注入 ObjectMapper 序列化**（不用 JsonUtils 静态，避免 SpringUtils 静态依赖破坏单测；Spring 运行时由 JacksonConfig 提供 ObjectMapper bean）。

## AI 自测（Tier 1A）

### 编译 + install（删占位后全链路 install）
```
$ mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-ord -am
BUILD SUCCESS
（gz-common 删 2 占位 handler + 改 2 测试 → 编译通过；gz-ord 新增全部产物 → 编译通过）
```

### 单测 — gz-ord（GzOrdOrderServiceImplTest 9 个 + AC8 全链路 1 个 + 既有）
```
[INFO] Tests run: 9, Failures: 0, Errors: 0 -- GzOrdOrderServiceImplTest
  ① happy path：扣库存→INSERT created(snapshot+in_japan)→调 PAY(preorder)→返回 5 参
  ② onPaid：created→paid + paid_time + pay_transaction_id 回填 + 累加销量
  ③ 库存不足：tryDeductStock 抛 SKU_OUT_OF_STOCK → 不 INSERT order、不调 PAY（整事务回滚）
  ④ 商品下架 PRODUCT_OFF / ④b 截止过期 → 扣库存前拦截，不落 order
  ⑤ 地址非本人 ADDRESS_INVALID → 扣库存前拦截
  ⑥ 重复回调 onPaid markPaid affected=0 → 幂等不二次推进、不二次累加销量
  ⑦ cancel created→cancelled+回滚库存 / ⑦b cancel paid→ORDER_NOT_CANCELLABLE 不回滚库存
[INFO] Tests run: 1, Failures: 0, Errors: 0 -- PreorderFullChainMockTest（AC8）
[INFO] BUILD SUCCESS  ——  gz-ord 合计 Tests run: 36, Failures: 0, Errors: 0
```

### mock 全链路（AC8，gz.pay.client.mode=mock）— createOrder→mock V3 回调→PREORD- SPI 路由→订单 paid
```
[AC8] 建单 out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-20260603-000001 订单初态=created
16:54:58 INFO GzOrdOrderServiceImpl -- [gz-ord-order] onPaid ok orderNo=PREORD-20260603-000001 ordOrderId=8001 → paid transaction_id=mock_wx_txn_PREORD-20260603-000001 paid_time=2026-06-03T16:54:58.143
[AC8] 回调后 gz_ord_order business_status=paid logistics_status=in_japan pay_transaction_id=mock_wx_txn_PREORD-20260603-000001
[AC8] 重复回调幂等 OK，销量仅累加 1 次，callback_logs=4
```
验证链路：PAY createBusinessOrder(preorder) → MockWechatPayClient.buildMockCallbackBody(AES-GCM) → handlePaymentNotify 乐观锁 pending→paid → PayCallbackDispatcher 按 business_type=preorder 路由到**真实下沉的 gz-ord PreorderPayCallbackHandler** → GzOrdOrderService.onPaid 行锁定位订单 → markPaid。
终态断言全过：`gz_ord_order.business_status='paid'` + `logistics_status='in_japan'` + `pay_transaction_id` 回填 + `gz_pay_transaction.business_type='preorder'`；重复回调双层幂等（PAY 侧 duplicated + ord 侧 markPaid affected=0），销量仅累加 1 次。

### 单测 — gz-common（删占位关键验证：仍绿）
```
[INFO] Tests run: 98, Failures: 0, Errors: 0  -- ruoyi-gz-common  BUILD SUCCESS
（含 GzPayBusinessFullChainMockTest 改内联 preorder handler 后仍绿；
  RefundCallbackDispatcher "退款回调 SPI 路由表就绪，已注册 1 个 handler：[preorder]" —— 无重复注册、无 fail-fast）
```

### mp vitest + type-check + build
```
$ pnpm test
 ✓ src/pages/ord/pay-result.logic.test.ts (11 tests)   — phase 映射 + 轮询判定
 ✓ src/composables/useOrderSubmit.test.ts (3 tests)    — 支付成功/取消/submit失败三分支
 ✓ src/pages/ord/detail.logic.test.ts (16 tests)
 Tests  1 failed | 164 passed (165)
   → 唯一失败 = src/api/gz-bean.test.ts bindMobile（code vs mobile 字段，GZ-BEAN-004 既有 case，与本卡无关，未触碰该文件）

$ pnpm type-check    （vue-tsc --noEmit）→ 0 error（pay-result.vue / useOrderSubmit.ts / order-confirm.vue / gz-ord.ts 全 clean）

$ pnpm build:mp-weixin → DONE Build complete.（尾部唤 devtools cli 已 pkill -o cli；dist 已生成）
   dist/build/mp-weixin/pages/ord/ 含 pay-result.js/.wxml/.wxss + pay-result.logic.js + order-confirm.js(4472B，含真 submit)
```

## Tier 2 可达（AC9）

现成路径全程可达，**无需新增临时入口**：
`首页 pages/index/index（预购 teaser + 网格④ → /pages/ord/list）→ 列表 list.vue（点卡 → preorder-detail?id=）→ 详情 preorder-detail.vue（立即购买 → usePurchaseGuard → order-confirm）→ 确认页 order-confirm.vue（提交订单 → useOrderSubmit submit → requestPayment → redirectTo pay-result?orderId=）→ pay-result.vue`。
确认页是 ORD-103 已建现成入口；本卡只把「提交订单」从 console.log 占位接到真跨域事务 + 支付。

## 风险提示 / 已知 issue

- **R8 真实端到端（外部前置）**：本卡 DoD 仅 mock 全链路（gz.pay.client.mode=mock）。真实微信支付商户号 / cert / apiV3Key 依赖甲方挂号 + V1.0 验收，**列外部前置风险，不当默认就绪**。
- **AC2 文案 vs AC3 字段语义对齐**：ticket AC2 写"调 PAY 拿 transaction_id → UPDATE gz_ord_order.pay_transaction_id"，但 `gz_pay_transaction.transaction_id`（微信侧交易号）在建单（createBusinessOrder）时为 NULL，仅支付回调才有值（doc/11 §4.2）。故实现按 AC3 在 **onPaid 时回填 pay_transaction_id**（与字段权威 doc/11 §6.3 "FK→transaction_id"语义一致）。submit 阶段订单与支付的关联靠 `gz_pay_transaction.business_order_no = gz_ord_order.order_no`（回调 SPI 据此反查）。无契约违背，仅 AC2 描述顺序与字段生命周期对齐说明。
- **支付超时（E7）订单自动取消未实现**：PAY-102 超时把 gz_pay_transaction 标 timeout，但本卡未实现"超时→订单 created→cancelled+回滚库存"的联动（无超时 SPI / cron）。当前行为 = 订单停 created，用户可重进继续支付或主动 cancel（R1 缓解）。**留 V1.1 后续 ticket**（建议 PAY-102 超时关单时发事件 / 加 OrdTimeoutCancelJob 扫 created+对应 timeout 交易行）。
- **gz-bean.test.ts bindMobile 既有失败**：与本卡无关（未触碰该文件 / API），D08 既有 case，不计本卡回归。
- **pages/index/index.vue 存 PAY-001 Tier2-entry-temp 临时入口**（注释 "remove when GZ-PAY-101 merged"）：本卡未触碰，属 PAY-101 清理责任。

## 对 ORD-105 的提示

- **gz_ord_order 表已建** + 全字段就绪（snapshot / 物流 / 时间）；**`getOrderDetail(id, userId)` 已建**（GET /app/gz/ord/order/{id}，snapshot 还原 + 归属校验，可直接复用为详情）。
- ORD-105 增量：① **list**（按 user_id 分页，建议 ORDER BY paid_time DESC + 软删 / 业务态过滤；snapshot 反序列化复用 `OrdSnapshot` POJO + `readJson`）；② **admin 只读列表**（business_type 分流真源仍在 gz_pay_transaction，admin 看 gz_ord_order + JOIN 语义靠 business_order_no）；③ **时间线**（C1 物流 2 态：paid → in_logistics(cn_dispatched_at) → delivered；订单时间线用 paid_time/cn_dispatched_at/delivered_time）。
- **C 端无退款入口**（合同 §2.3/§4.5）：ORD-105 订单详情仅文案「如需退款请联系客服」，禁退款按钮。
- **snapshot 即真源**：ORD-105 展示历史订单全部读 snapshot（不反查 gz_ord_product/sku/address —— 商品下架/改名/调价后仍显原貌）。
- **物流字段（cn_carrier_code/cn_tracking_no/cn_dispatched_at）本卡建表即落，未写值**：admin 推进（GZ-ADMIN-104 D10）才写；ORD-105 详情展示这几个字段（NULL 时不显物流模块）。

## §AI 测试段（kevin-qa Tier 1B）

> 本次为嵌套 subagent 调用，无法 spawn kevin-qa（嵌套限制）。Tier 1A 已做扎实（gz-ord 36 单测 + gz-common 98 单测 + AC8 mock 全链路 + mp 14 新单测 + type-check + build:mp-weixin）。
> 待主线程 / Kevin 触发 kevin-qa 跑 Tier 1B（admin 无新页 → 主要是 mp vitest 回归 + 后端集成 + 可达性确认）后追写于此。
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
# GZ-PAY-101 完工报告 — 业务统一支付服务（V3 / business_type 分流 / SPI 回调路由 / 回调幂等）

> 波次 1 · ruoyi-gz-common · 后端 service 底座（无新表）· mock 全链路自测通过

## §0 自检结果

| 检查项 | 结果 | 实证 |
|---|---|---|
| git 状态 | N/A | 当前目录非 git repo（环境提示 `Is directory a git repo: No`）；按 ticket 收尾约定本 ticket 不 commit |
| 上游 PAY-001 已交付 | ✅ | grep `pay/` 子包：`IWechatPayClient`(`MockWechatPayClient`/`WechatPayV3ClientImpl`) / `PayOrderNoGenerator` / `PayBusinessType` / `PayStatus` / `GzPayTransaction` 实体 + `GzPayTransactionServiceImpl` / `WechatPayNotifyController`(`/api/pay/v3/notify`) / `GzPayTestController` 全部实证存在 |
| 关键表 schema 齐全 | ✅ | grep `V202606041200`：`gz_pay_transaction` 已含 `business_type`/`business_order_no`/`fee_cent`/`amount_cent`/`out_trade_no`/`transaction_id`/`version` + `uk_tenant_out_trade_no` + `uk_tenant_transaction_id` + `idx_business_type_status`；`gz_pay_callback_log` 含 `callback_type`/`process_status` → **本 ticket 无需新建迁移** |
| migration 最大版本 | ✅ | `V202606051200`（本 ticket 不新增迁移，故无需 > 它） |
| 编译通过 | ✅ | `mvn compile -pl ruoyi-modules/ruoyi-gz-common`（无 -am）EXIT=0 |
| ADR 已读 | ✅ | ADR-0003（实际文件名 `0003-wechat-pay-channel-mock-degradation.md`）：mock+real 双实现 profile 切换 / 官方 SDK / SnailJob 调度 / 真实端到端=外部前置风险 —— 沿用不改选型 |
| 权威蓝图引用 | ✅ | doc/10 §2（V3 通道 N1~N9）+ §6（业务支付 N1~N10 + 状态机 + E1 幂等/E2 业务回调失败回滚）；doc/11 §4.2 gz_pay_transaction + §4.3 callback_log + §4.6 4% 分成（business_type+fee_cent 分别核算）已 Read 摘录 |

**权威约束摘录（落地依据）**：
- doc/10 §6.N6：「业务回调：根据 out_trade_no 前缀 / business_type 分发到业务回调」→ 落地为 SPI 按 `business_type` 路由（非前缀字符串匹配，更稳）。
- doc/10 §6.E2：业务回调事务异常 → 整笔回滚 + 微信重试 + PAY-102 补单兜底 → 落地为 handler 异常向上透传致 `@Transactional` 回滚 + callback 返失败。
- doc/11 §4.2：`fee_cent` 回调中提取「W → S」，但 F4.3 已裁定 V3 回调 body 不含通道费，由 PAY-104 拉 `/v3/bill/fundflowbill` 回写 → 本 ticket 建单 `fee_cent` 留 NULL（强约束 #7）。
- doc/11 §4.6：分流真源只在 `gz_pay_transaction.business_type`，业务订单表禁加 biz_line/A-B 列。

## 实现摘要

**新增（6 文件）**：
- `pay/service/spi/PayCallbackHandler.java` — SPI 接口（`supportedBusinessType()` + `onPaid(GzPayTransaction)`），含 key 空间约定（支付按 business_type / 退款 PAY-103 独立 key）+ 事务/幂等契约文档。
- `pay/service/spi/PayCallbackDispatcher.java` — 注册中心：构造注入 `List<PayCallbackHandler>` → `@PostConstruct validate()` 建 `Map<businessType, handler>` 路由表 + fail-fast（同 type 多 handler 抛 `IllegalStateException`）；`dispatch(txn)` 按 business_type 取 handler，无 handler（test 单）跳过不报错，handler 异常向上透传。**无 switch-case**。
- `pay/service/spi/handler/PreorderPayCallbackHandler.java` — preorder 占位 handler（`@Component`，命中即日志 + 带说明 TODO `// ORD-104 填实现`）。
- `pay/domain/bo/CreateOrderBo.java` — 通用建单入参（businessType/businessOrderNo/amountCent/openid/userId/description + 校验注解）。
- `(test) pay/service/spi/PayCallbackDispatcherTest.java` — 6 测：fail-fast / 正常建表 / 路由命中 / test 无 handler 跳过 / handler 异常透传 / 空列表。
- `(test) pay/service/GzPayBusinessFullChainMockTest.java` — 2 测：preorder 全链路（建单→mock 调起→mock V3 回调→真 SPI 路由真 PreorderPayCallbackHandler→paid→重复幂等）+ test 单全链路（无 handler 跳过仍 paid）。in-memory mapper 模拟 DB UNIQUE + 乐观锁。

**改动（4 文件）**：
- `pay/service/IGzPayTransactionService.java` — `+ createBusinessOrder(CreateOrderBo)`。
- `pay/service/impl/GzPayTransactionServiceImpl.java` — ① 抽 `createOrderInternal(...)` 通用建单底层（`createTestOrder` 改为薄壳调它，决策 D3：test 单=业务单特例，**不重写**底层）；② `+ createBusinessOrder`；③ `handlePaymentNotify` 在 markPaid affected=1 后、callback_log processed 前接入 `callbackDispatcher.dispatch(tx)`（同事务 REQUIRED）；幂等两道防线（已 paid SELECT / 乐观锁 affected=0）均 **不进入分发** → onPaid 至多一次；④ 注入 `PayCallbackDispatcher`。
- `pay/controller/GzPayTestController.java` — `+ /create-business-order`（`@SaCheckPermission("gz:pay:test")`，AC 10 mock 全链路驱动入口；prod 关 perm）。
- `(test) pay/service/GzPayTransactionServiceImplTest.java` — 构造器 +1 mock(`callbackDispatcher`) + 改 3 个旧回调测加 dispatch 断言（happy=1 次 / duplicated=0 / 乐观锁冲突=0）+ 4 新测（业务建单 happy + 未知 type 失败 + SPI 路由命中传 paid 行 + handler 异常透传致回滚）。

**无新建迁移**（表已齐全）。**AC 8 选型**：业务下单走「业务模块在自己跨域事务内注入 service 调 `createBusinessOrder`」（ticket AC 8「或」分支），不暴露通用 mp 建单端点（避免任意 business_order_no 越权建单）；mp 调起 5 参由 `MpPayParamsVO` 提供，ORD-104 接入。

## AI 自测（Tier 1A）

### 1. 编译（gz-common only，无 -am）

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
COMPILE_EXIT=0   （无 error 输出）
```

### 2. 单测（service 10 + dispatcher 6 + 全链路 2 = 18，全 gz-common 73 全绿）

```
[INFO] Running org.dromara.gz.common.pay.service.GzPayBusinessFullChainMockTest
[INFO] Tests run: 2, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.common.pay.service.GzPayTransactionServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.common.pay.service.spi.PayCallbackDispatcherTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
...（其余 gz-common 测试 47 个全绿）
[INFO] Tests run: 73, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

AC 9 五项单测覆盖确认：
- happy path（建单 created→pending + 回调 paid + SPI 命中 1 次）→ `createBusinessOrder_preorder_happyPath` + `handlePaymentNotify_preorder_spiDispatched`
- SPI 路由（preorder 回调只命中 preorder handler，gacha 0 次）→ `PayCallbackDispatcherTest.dispatch_routesToCorrectHandler`
- 幂等（同回调二次 → onPaid 仅 1 次 + duplicated）→ `handlePaymentNotify_duplicated_alreadyPaid`/`_optimisticLockConflict`（dispatch never）+ 全链路测重复回调断言 markPaid times(1)
- handler 异常回滚（交易行保 pending / 异常透传）→ `handlePaymentNotify_handlerThrows_propagatesForRollback`（processed 日志未写）+ `dispatch_handlerThrows_propagates`
- fail-fast（同 business_type 2 handler 启动抛 IllegalStateException）→ `PayCallbackDispatcherTest.validate_duplicateBusinessType_failFast`

### 3. AC 10 mock 全链路 raw log（preorder 端到端 + 重复幂等）

```
[gz-pay-mock] createJsapiOrder out_trade_no=PREORD-20260603-000001 amount=9900 → prepay_id=mock_prepay_PREORD-20260603-000001
[gz-pay] 建单成功 business_type=preorder out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-ORDER-20260604-001 amount=9900 prepay_id=mock_prepay_PREORD-20260603-000001
[gz-pay] SPI 分发支付回调 business_type=preorder → PreorderPayCallbackHandler out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-ORDER-20260604-001
[gz-pay] PreorderPayCallbackHandler.onPaid 命中（占位）out_trade_no=PREORD-20260603-000001 business_order_no=PREORD-ORDER-20260604-001 amount_cent=9900 —— 实际出单逻辑待 ORD-104 填实现
[gz-pay] 回调处理成功 out_trade_no=PREORD-20260603-000001 business_type=preorder → paid transaction_id=mock_wx_txn_PREORD-20260603-000001
[gz-pay] 重复回调（已 paid）out_trade_no=PREORD-20260603-000001          ← 第二次回调幂等
```

**断言（全链路测内）**：建单后 status=pending + business_type=preorder + business_order_no 写入 + fee_cent=NULL + prepay_id=mock_prepay_* + packageVal 一致；回调后 status=paid + transaction_id 写入 + callback_log [received, processed]；重复回调后 status 仍 paid + callback_log 追加 [received, duplicated] + markPaid 仅调 1 次。test 单链路：无 handler dispatch 跳过仍 paid。

### 4. 强约束反例自查（应全空 → 已确认空）

```
$ grep -rn "gz_pay_order\|amount_fen\|/api/wxpay\|api-key\|switch.*business" pay/service/spi/ pay/domain/bo/CreateOrderBo.java
(空 — 无违反：无新表 / 无 _fen / 无 V2 端点 / SPI 无硬编码 switch)
```

### 5. 落 .m2（并行安全，无 -am）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common
Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/.../ruoyi-gz-common-5.6.1.jar
BUILD SUCCESS
```

## 风险提示 / 已知 issue

- **R1【外部前置风险】真实 0.01 元端到端未跑**：本 ticket DoD = mock 全链路（`gz.pay.client.mode=mock`）。真实商户号/cert/apiV3Key 就绪后切 real profile 在 staging 跑（ADR-0003 §2 四步），不当默认就绪。
- **DB 真链路 SQL 未跑**：单测用 in-memory mapper 模拟 DB（UNIQUE + 乐观锁语义），未起真实 MySQL 跑 INSERT/UPDATE。乐观锁 SQL（`markPaid` WHERE version + status）+ UNIQUE 约束在 PAY-001 已经真链路验过，本 ticket 复用未改 mapper SQL，风险低；Tier 1B 主线程集成可起库验真 SQL。
- **PreorderPayCallbackHandler 占位归属待 ORD-104 定**：当前占位 Bean 在 gz-common（让 PAY-101 本身可验 preorder 路由命中）。ORD-104 接手时二选一：(a) 在本类注入 `IGzOrdOrderService` 填实现；(b) 把本类移到 ruoyi-gz-ord 模块 + 删 gz-common 占位（dispatcher 自动收新 Bean，零改 PAY-101）。**推荐 (a)**（保留 gz-common 单一支付域，handler 跨模块注入 ord service 即可）。注意：方案 (b) 移走后 gz-common 内 `GzPayBusinessFullChainMockTest` 仍 new PreorderPayCallbackHandler 直测，会编译失败 → 届时该测改用匿名 handler。
- 待 Kevin 批量人验关注：**N/A — 纯后端 service 底座，无 mp 页面、无微信原生能力**（Tech 段无 `miniapp/` 路径），按 CLAUDE.md §8.2「纯后端 ticket 无人验」，AI Tier 1A+1B 全 ✅ 即终态 close。

## 对下游 ticket 的提示（SPI 契约 + 路由 key 空间）

### 给 ORD-104（预购下单跨域事务，波次 3）— 最关键

1. **建单契约**：在 ORD-104 下单事务内注入 `IGzPayTransactionService`，调
   ```java
   MpPayParamsVO params = payService.createBusinessOrder(CreateOrderBo.builder()
       .businessType(PayBusinessType.PREORDER)
       .businessOrderNo(ordOrder.getOrderNo())   // gz_ord_order.order_no
       .amountCent(totalCent)
       .openid(openid).userId(userId)
       .description("谷子宇宙预购：" + productName)
       .build());
   ```
   `createBusinessOrder` 是 `@Transactional(REQUIRED)` → 与 ORD-104「建 gz_ord_order + 扣 sku.stock_remain（乐观锁）+ 调本方法」**同一事务**，任一失败整体回滚（R4）。`params` 含 out_trade_no + 5 参签名返 mp `uni.requestPayment`。
2. **出单契约（填 PreorderPayCallbackHandler.onPaid）**：支付成功回调由 PAY-101 在自己事务内调 `onPaid(GzPayTransaction txn)`。ORD-104 在 `onPaid` 内用 `txn.getBusinessOrderNo()` 定位 `gz_ord_order` → created→paid（建议带 `WHERE business_status='created'` 守卫防御）。**onPaid 至多调一次**（PAY-101 已保证幂等，无需自己再做支付幂等）。**抛异常 = 整笔回调事务回滚 → 微信重试 + PAY-102 补单**，故 onPaid 内只更新订单状态，不调外部不可回滚操作。
3. **占位 handler 归属**：见上「已知 issue」，推荐方案 (a) 本类注入 ord service。

### 给 PAY-104（fundflowbill 回写笔费）

- `fee_cent` 建单时已留 NULL（本 ticket 不回写）。PAY-104 SnailJob 按 `transaction_id` 拉 `/v3/bill/fundflowbill` 回写 `gz_pay_transaction.fee_cent`。无需改 PAY-101 任何代码。

### 给 PAY-102（主动查单补单）

- 查到 paid 但本地 pending 时，复用本 ticket 的 `handlePaymentNotify` 链路（构造等价 NotifyContext）即可走同一套乐观锁 + SPI 分发，自动幂等。或直接调内部推进 + `callbackDispatcher.dispatch(tx)`（建议走 handlePaymentNotify 保持单一真源）。

### 给 PAY-103（退款，独立 key 空间 — R3 核心）

- **支付回调 SPI 路由 key = `business_type`**（preorder/gacha/...），由 `PayCallbackHandler` + `PayCallbackDispatcher` 承载。
- **退款回调走独立 SPI key 空间**：`gz_pay_callback_log.callback_type='refund'` 区分，**新建独立的 RefundCallbackHandler + RefundCallbackDispatcher**（或同一 dispatcher 加 `callback_type` 维度），**不要复用本 `PayCallbackHandler`**（避免支付/退款路由 key 撞）。PAY-103 落地后主线程串行 review 一次路由表（R2）。
- 退款会用到 PayStatus.REFUNDING/REFUNDED 常量（本 ticket 未加，PAY-103 加到 `PayStatus`）。

### SPI 契约摘要（供主线程派 ORD-104）

```
接口  org.dromara.gz.common.pay.service.spi.PayCallbackHandler
      String supportedBusinessType();          // 路由 key，取 PayBusinessType 常量
      void   onPaid(GzPayTransaction txn);      // PAY-101 回调事务内调用，至多一次
注册  实现 @Component 即自动被 PayCallbackDispatcher 收集（List 注入 + @PostConstruct 建表 + fail-fast）
路由  支付成功回调 → 按 txn.businessType 取 handler.onPaid；test 单无 handler 跳过不报错
事务  onPaid 同 handlePaymentNotify 事务（REQUIRED）；抛异常 → 整笔回滚 → 微信重试 + PAY-102 兜底
建单  IGzPayTransactionService.createBusinessOrder(CreateOrderBo) → MpPayParamsVO（out_trade_no + 5 参）
key 空间  支付回调=business_type；退款回调（PAY-103）=独立 key（callback_type=refund），二者不混
```

## §AI 测试段（kevin-qa Tier 1B / 主线程集成接管）

> kevin-coder 作为 subagent 时 Agent 工具不可用（嵌套限制）→ 本 ticket 未 spawn kevin-qa。
> Tier 1A 已做扎实（编译 + 18 单测 + mock 全链路 raw log + 强约束反例自查 + .m2 install）。
> Tier 1B（起真实 MySQL 跑集成验真 SQL / 全量 `mvn install -am` 集成编译）由主线程在波次结束统一接管。
# GZ-PAY-102 完工报告 — 主动查单 + 补单

> SnailJob 每分钟扫 pending → 微信 V3 查单 → SUCCESS 走 PAY-101 同一幂等补单路径补单 / NOTPAY 超 30min 关单 / CLOSED→closed / PAYERROR→failed。
> V1.1 D08 波次2 · 复杂度 S · 模块 ruoyi-gz-common · 包 org.dromara.gz.common.pay

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 仓库非 git（`git rev-parse` 报 not a repository） |
| 上游依赖 PAY-101 已交付 | ✅ grep 确认 spi/{PayCallbackHandler,PayCallbackDispatcher,handler/PreorderPayCallbackHandler} + GzPayTransactionServiceImpl.handlePaymentNotify（含 SELECT + 状态判定 + markPaid 乐观锁 + dispatch + callback_log）全在位 |
| 包名实证 | ✅ 实际 `org.dromara.gz.common.pay`（任务卡行50 `org.dromara.gz.pay` 是笔误，已按主线程修正落位） |
| gz-common pom 含 ruoyi-common-job | ✅ GzPayExpireOrderJob / PayFundflowBillJob 在用 `@JobExecutor`，无需改 pom |
| 复用 PAY-101 补单核心（非另写） | ✅ 抽出 `applyPaid()` 私有单点，回调（行230）+ 查单 reconcilePaid（行301）两个调用点共用 |
| 状态枚举存在（doc/11 §4.2） | ✅ PayStatus.{PAID,TIMEOUT,CLOSED,FAILED,PENDING} 齐全，未新造别名 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-modules/ruoyi-gz-common` BUILD SUCCESS |
| migration 最大版本 | ✅ V202606061100（PAY-104），本卡**无新 DDL**（AC10），未编辑已应用迁移 |
| ADR | N/A（任务卡标 N/A，无相关 ADR） |
| 违禁项（Quartz/sys_job INSERT/_fen/新造状态） | ✅ grep 全空（仅 javadoc 说明文字提及"不通过 INSERT sys_job"） |
| 并行安全（与 ORD-103 同波次） | ✅ 仅改 gz-common；install 用 `-pl ruoyi-modules/ruoyi-gz-common`（不加 -am） |

## 实现摘要

### 改动 / 新增文件（相对 code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/）

**新增（4）**
- `main/.../pay/service/IPayOrderQueryService.java` — 查单服务接口 + `ReconcileResult` 统计 record
- `main/.../pay/service/impl/PayOrderQueryServiceImpl.java` — 扫描循环 + 逐单查单 + 状态分发（SUCCESS→reconcilePaid / NOTPAY<30min 保持 / NOTPAY>30min closeOrder+timeout / CLOSED|REVOKED→closed / PAYERROR→failed / USERPAYING 保持 / 单条异常隔离）
- `main/.../pay/job/PayOrderQueryJobExecutor.java` — SnailJob 薄壳（`@Component` + `@JobExecutor(name="payOrderQueryJob")`，仅调 scanAndReconcile）
- `test/.../pay/service/PayOrderQueryServiceImplTest.java` — 7 个测试（覆盖 AC9 五条 + 并发跳过 + 单条异常隔离）

**修改（5）**
- `main/.../pay/service/internal/IWechatPayClient.java` — 加 `queryByOutTradeNo` / `closeOrder` 接口方法 + `QueryResult` record
- `main/.../pay/service/internal/MockWechatPayClient.java` — 实现查单（可配置 trade_state + payerTotal）/ 关单（计数）+ 测试注入 setter
- `main/.../pay/service/internal/WechatPayV3ClientImpl.java` — 实现 real 查单/关单（SDK `JsapiServiceExtension.queryOrderByOutTradeNo` / `closeOrder`）
- `main/.../pay/service/IGzPayTransactionService.java` — 加 `reconcilePaid()` 补单单点入口 + `ReconcileOutcome` 枚举
- `main/.../pay/service/impl/GzPayTransactionServiceImpl.java` — **抽出 `applyPaid()` 幂等补单单点**（回调 ④⑤⑥ 与查单共用）+ 新增 `reconcilePaid()`（SELECT FOR UPDATE + 状态判定 + applyPaid）
- `main/.../pay/mapper/GzPayTransactionMapper.java` — 加 `selectReconcilePendingIds`（5min-24h+LIMIT100）/ `selectByIdForUpdate`（FOR UPDATE）/ `markClosed` / `markFailed`
- `test/.../pay/service/GzPayTransactionServiceImplTest.java` — 加 3 个 reconcilePaid 单点测试（10→13 方法）

### 复用 PAY-101 补单路径（类 + 方法名）

被动回调 `GzPayTransactionServiceImpl.handlePaymentNotify` 原内联的「markPaid 乐观锁 + SPI dispatch + callback_log processed」（步骤 ④⑤⑥）抽成私有方法：

```
GzPayTransactionServiceImpl#applyPaid(GzPayTransaction tx, String transactionId,
    Long feeCent, String outTradeNo, String rawBody, String signature) : boolean
```

- 被动回调 `handlePaymentNotify` 验签 + SELECT byOutTradeNo + 已 paid 判定后 → 调 `applyPaid(...)`
- 主动查单 `reconcilePaid(txId, transactionId, feeCent, rawBody)` → `selectByIdForUpdate` 行锁 + 非 pending 跳过后 → 调**同一个** `applyPaid(...)`（signature 传 null，rawBody = 查单报文）

→ markPaid 乐观锁 / SPI `PayCallbackDispatcher.dispatch` / callback_log 写入**单点维护**，主动补单与被动回调绝无两套 paid 推进逻辑（强约束 #1 / 决策 D4）。

## AI 自测（Tier 1A）

### 编译

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
BUILD SUCCESS
（首轮报 illegal character → 踩坑：javadoc 内 CRON `0 */1` 的 `*/` 提前闭合 /** */ 块注释。改 `0 0/1` + HTML 实体 *&#47;1 修复，见下方踩坑）
```

### 单测（gz-common 全量）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common
[INFO] Running org.dromara.gz.common.pay.service.PayOrderQueryServiceImplTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.028 s
[INFO] Running org.dromara.gz.common.pay.service.GzPayTransactionServiceImplTest
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.116 s
...
[INFO] Tests run: 93, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

> 日志里 `ERROR ... 主动查单单条失败 id=1001` 是 `scan_singleException_isolated` 测试**故意注入**查单异常验证单条隔离（风险 R2），是预期断言路径，该测试通过。

### 新增测试方法清单（10 个，覆盖 AC9 五条 + 扩展）

PayOrderQueryServiceImplTest（7）：
```
scan_success_delegatesReconcilePaid          AC4 SUCCESS → 委托 reconcilePaid 补单单点 + 不另写 paid 推进
scan_idempotent_secondRoundSkipped           AC5 同笔连扫两轮 → 第二轮 SKIPPED_TERMINAL，补单仅计一次
scan_notpay_under30min_keepsPending          AC6 NOTPAY<30min → 保持 pending，不关单不补单
scan_notpay_over30min_closeAndTimeout        AC8 NOTPAY>30min → closeOrder + markTimeout
scan_closed_payerror_userpaying_branches     AC7 CLOSED→closed / PAYERROR→failed / USERPAYING→保持
scan_alreadyTerminal_skips                   AC5 并发 selectById 已 paid → 跳过不查单
scan_singleException_isolated                R2 单条查单异常 → 隔离不卡整批
```
GzPayTransactionServiceImplTest 新增（3）：
```
reconcilePaid_pending_marksPaidAndDispatchOnce   AC4 行锁 pending → markPaid+dispatch 一次+processed 日志
reconcilePaid_alreadyPaid_idempotentSkip         AC5 行锁已 paid → SKIPPED_TERMINAL，不二次 markPaid/dispatch
reconcilePaid_optimisticConflict_duplicated      AC5 行锁内 markPaid affected=0 → SKIPPED_TERMINAL（duplicated 审计）
```

### install 到 m2（仅 gz-common，并行安全）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common
[INFO] Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/.../ruoyi-gz-common-5.6.1.jar
[INFO] BUILD SUCCESS
```

## SnailJob 待注册清单（人工在控制台注册，禁 Flyway INSERT sys_job）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-ORDER-QUERY |
| 执行器路由 executor_info | `payOrderQueryJob`（= `@JobExecutor(name)`） |
| 触发类型 | CRON |
| CRON 表达式 | `0 0/1 * * * ?`（每分钟，等价 `0 */1 * * * ?`，决策 D1；容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃 DISCARD（上轮未跑完不叠加） |
| 组 | ruoyi_group |

## 是否新增 SPI 路由 key

**否。** 复用 PAY-101 既有 `payment` SPI 分发（`PayCallbackDispatcher` 按 business_type 路由），主动查单补单与被动回调走同一 `applyPaid` → `dispatch`。callback_log `callback_type` 仍恒为 `payment`，靠 raw_body 来源（查单报文 `"source":"query"` vs 解密通知报文）区分主动/被动，不新增列（决策 D5）。

## 对「PAY 三票 SPI 路由 review」的输入（R4）

- **本卡复用的路由段**：`PayCallbackDispatcher.dispatch(GzPayTransaction)` → `resolve(business_type)` → `PayCallbackHandler.onPaid`，key 空间 = business_type（preorder/gacha），callback_type = `payment`。
- **本卡未新增任何 handler / 路由 key**：查单补单不注册新 handler，完全走 PAY-101 既有 payment 分发。
- **三票交集点**：PAY-102（主动查单补单，payment key）/ PAY-103（退款，独立 callback_type=`refund` key 空间）/ PAY-104（对账批，不走 SPI 直接回写 fee_cent）。三者落地后 review 确认 payment（PAY-101/102 共用）与 refund（PAY-103）两套 key 空间不混用即可，**本卡不引入撞 key 风险**。

## 风险提示 / 已知 issue

- **R-真实端到端（外部前置风险）**：真实微信 V3 查单 `GET /v3/pay/transactions/out-trade-no/{no}` + 关单 `POST .../close` 依赖甲方商户号 + cert + apiV3Key（申请中）。`WechatPayV3ClientImpl` 已用官方 SDK 0.2.17（`JsapiServiceExtension.queryOrderByOutTradeNo` / `closeOrder`）实现，但**未做真实端到端联调**。本日 DoD = mock 全链路（Kevin 决策 1），real 联调列 buffer 期补打。
- **R2 已缓解**：handler 异常 → reconcilePaid 整笔事务回滚（保持 pending）→ 下轮重扫重试；单条查单异常被扫描循环隔离不卡整批。连续失败由 callback_log `process_status` / 应用日志 ERROR 暴露，运维介入。
- **关单非事务保护**（AC8）：`closeOrder`（微信）+ `markTimeout`（本地）两步非原子。若关单成功但 markTimeout affected=0（并发已变）→ 下轮重扫，微信关单幂等，安全。
- **30min 关单时间基准**：用 `create_time`（BaseEntity，java.util.Date）+ 30min < now 判定（不用 expire_time，expire_time = create+5min 是回调超时用途，语义不同）。

## 对下游 ticket 的提示

- **PAY 三票 SPI review（主线程接管）**：本卡复用 payment key，无撞 key；review 时确认 refund（PAY-103）独立 key 空间即可。
- **PAY-103 退款**：退款回调请走**独立 callback_type=refund + 独立 SPI key 空间**（PayCallbackHandler 仅服务支付成功 payment，不要复用本卡 payment 路由）。
- **集成测试（Tier 1B 主线程接管）**：可用 `gz.pay.client.mode=mock` + `MockWechatPayClient.setQueryTradeState(...)` 注入各 trade_state，INSERT 一条 `create_time=NOW()-INTERVAL 10 MINUTE` + `status='pending'` 的 gz_pay_transaction（业务类型 preorder + 已注册 PreorderPayCallbackHandler）→ 调 `scanAndReconcile()` 验证推进 paid + handler 出单 + callback_log 落 raw_body=查单报文。
- **真实端到端**：商户配置就绪后切 `real` profile，注入 env（WECHAT_PAY_MCH_ID 等），用 0.01 元单验证查单/关单/补单全链路。

## 踩坑记录（learnings 候选）

**javadoc 块注释内含 CRON `*/N` 提前闭合 `/** */`**：`@JobExecutor` javadoc 写 CRON 表达式 `0 */1 * * * ?` 时，`*/` 序列把 `/** ... */` 块注释提前闭合，后续中文字符全被当代码体非法字符（`illegal character: '，'` 误导成"编码问题"，实为注释提前结束）。修复：javadoc 内 CRON 改 `0 0/1`（功能等价无 `*/`）或用 HTML 实体 `*&#47;1`。任何 java 块注释里写含 `*/` 的字面量（CRON / 正则 / 路径）都会触发，注意。

## §AI 测试段（Tier 1B — kevin-qa / 主线程接管追加）

（占位。本卡 kevin-coder 嵌套限制无法 spawn kevin-qa；Tier 1A 已做扎实，Tier 1B 集成测试由主线程接管追写到此。）
# GZ-PAY-103 完工报告 — 退款服务（仅全额 / @SaCheckPermission / V3 退款回调 / gz_pay_refund）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态 | code/main 非 git 仓库（项目从零起，符合约定）；不 commit |
| 上游 PAY-101 已落 | ✅ `gz_pay_transaction` / `gz_pay_callback_log` 已建（V202606041200）；支付 SPI `PayCallbackHandler`/`PayCallbackDispatcher`/`PreorderPayCallbackHandler` 已存在 |
| 关键类/表存在 | ✅ `IWechatPayClient`/`MockWechatPayClient`/`WechatPayV3ClientImpl`/`PayOrderNoGenerator`/`GzPayCallbackLogMapper` 均在 |
| 包名实证 | ✅ 实际 `org.dromara.gz.common.pay.*`（任务卡行77 `org.dromara.gz.pay` 是笔误，已按实际包名落地） |
| migration 时间戳 | ✅ 现最大 V202606061100（PAY-104）；本卡用 V202606061300（建表）+ V202606061301（菜单），均 > 最大值 |
| menu_id 5100 段占用 | ✅ grep 确认 5100-5105 已用（PAY-001）；本卡用 5106/5107/5108 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-common` EXIT 0 |
| ADR 已读 | ADR-0004（mp+admin 权限底座，本卡 admin 走 @SaCheckPermission） |

### 支付 SPI 现状硬探（grep 实证）

PAY-101 支付 SPI：`PayCallbackHandler`（key=business_type，`onPaid`）+ `PayCallbackDispatcher`（payment 注册中心，启动 fail-fast）+ `PreorderPayCallbackHandler`（占位）。callback_log `callback_type='payment'`。`PayCallbackHandler` javadoc §key 空间约定 R3 已明示「退款回调走独立 SPI key 空间」——本卡严格遵循。

## 退款 SPI 路由 key 空间说明（供 PAY 三票串行 review，README R2）

| 维度 | 支付（PAY-101/102） | 退款（PAY-103，本卡） | 隔离确认 |
|---|---|---|---|
| SPI 接口 | `PayCallbackHandler.onPaid` | `IRefundCallbackHandler.onRefunded` | 不同接口 |
| 注册中心 | `PayCallbackDispatcher`（payment 路由表） | `RefundCallbackDispatcher`（refund 路由表） | **独立 Bean，路由表完全隔离** |
| 路由 key | business_type（preorder/gacha） | business_type（preorder/gacha） | 取值同，但**各自 dispatcher 各自命中**，不撞 |
| callback_log.callback_type | `'payment'` | `'refund'` | **DB 层隔离** |
| 回调 endpoint | `/api/pay/v3/notify` | `/api/pay/v3/refund-notify` | **独立 endpoint** |
| 占位 handler | `PreorderPayCallbackHandler` | `PreorderRefundCallbackHandler` | 不同类 |

结论：退款 SPI 与支付 SPI **完全平行、零交叉**，同 business_type 在两个 dispatcher 各自路由，绝不混淆。

## 实现摘要

### 新增产物（后端 ruoyi-gz-common，包 org.dromara.gz.common.pay）

- `domain/entity/GzPayRefund.java` — 退款单 entity（含非持久化 `transientTransactionRowId`）
- `domain/bo/RefundApplyBo.java` — 申请入参（仅 `transactionId`+`reason`，**无 amountCent**）
- `domain/vo/GzPayRefundVO.java` — VO（id String 化，refund_no 业务码）
- `mapper/GzPayRefundMapper.java` — countActiveByTransactionId / selectByRefundNoForUpdate / markRefunded / markFailed / selectMaxDailySeq
- `service/IPayRefundService.java` + `service/impl/PayRefundServiceImpl.java` — apply / handleRefundNotify / selectPageList
- `service/internal/PayRefundTxService.java` — 退款 DB 事务原子操作（独立 Bean，规避 self-invocation 事务失效）
- `service/spi/IRefundCallbackHandler.java` + `service/spi/RefundCallbackDispatcher.java` + `service/spi/handler/PreorderRefundCallbackHandler.java` — 退款 SPI（独立 key 空间）
- `controller/PayRefundController.java` — `POST /system/gz/pay/refund/apply`（@SaCheckPermission + @Log OTHER）+ `GET .../list`
- `controller/external/WechatPayRefundNotifyController.java` — `POST /api/pay/v3/refund-notify`（@SaIgnore）

### 改动的既有文件（后端）

- `enums/PayStatus.java` — 加 `REFUNDING`/`REFUNDED` 常量
- `service/internal/IWechatPayClient.java` — 加 `refund()` / `parseAndVerifyRefundNotify()` + records（RefundRequest/RefundResult/RefundCallbackResult）
- `service/internal/MockWechatPayClient.java` — 实现退款 / 退款回调 mock + `buildMockRefundCallbackBody` + `setRefundAcceptFail`
- `service/internal/WechatPayV3ClientImpl.java` — real 退款（SDK RefundService.create）+ 退款回调（NotificationParser parse RefundNotification，复用同套 AES-GCM）
- `service/internal/PayOrderNoGenerator.java` — 加 `generateRefundNo()`（前缀 RF，查 refund 表序号空间）+ 注入 GzPayRefundMapper
- `config/WechatPayProperties.java` — 加 `refundNotifyUrl`
- `mapper/GzPayTransactionMapper.java` — 加 markRefunding / markRefunded / rollbackRefundingToPaid（状态机守卫 UPDATE）
- `test/.../GzPayBusinessFullChainMockTest.java` — 适配 PayOrderNoGenerator 新构造参数（加 refundMapper mock）

### 新增产物（admin plus-ui）

- `src/api/gz-pay/refund.ts` — applyRefund / listRefund + 类型（id String）
- `src/views/gz-pay/refund/index.vue` — 退款记录 el-table + 「申请退款」disabled 占位（订单看板未完工）
- `src/views/gz-pay/refund/RefundApplyDialog.vue` — 退款弹窗（只读全额金额 + reason textarea 必填≤255 + v-hasPermi）
- `src/lang/zh_CN.ts` / `src/lang/en_US.ts` — `gzRefund` i18n 段（zh/en）

### DDL（Flyway）

- `V202606061300__GZ-PAY-103-create-gz_pay_refund.sql` — 建表
- `V202606061301__GZ-PAY-103-menu.sql` — 菜单 5106/5107/5108 + owner(100) 授权

#### gz_pay_refund 表/字段（严格对齐 doc/11 §4.4）

| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT UNSIGNED PK | 不暴露前端 |
| refund_no | VARCHAR(64) NOT NULL | RF-yyyyMMdd-6位 |
| transaction_id | VARCHAR(64) NOT NULL | FK 微信交易号 |
| out_trade_no | VARCHAR(64) NOT NULL | 原业务订单号 |
| wechat_refund_id | VARCHAR(64) NULL | 微信退款单号 |
| **refund_amount_cent** | BIGINT NOT NULL | 分（**非 _fen**），全额=原单 amount_cent |
| reason | VARCHAR(255) NOT NULL | 退款原因 |
| status | VARCHAR(16) DEFAULT 'refunding' | refunding/refunded/failed |
| triggered_by | VARCHAR(64) NOT NULL | username（**非 operator_id**） |
| triggered_time | DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) | |
| refunded_time | DATETIME(3) NULL | |
| + 公共字段 | | tenant_id DEFAULT '1001' / del_flag 2 值 |

约束：`UNIQUE(tenant_id, refund_no)` / `UNIQUE(tenant_id, wechat_refund_id)`（NULL 并存）/ IDX(tenant_id,transaction_id)、(tenant_id,status)、(tenant_id,out_trade_no)。**未建 gz_pay_order，未在 gz_pay_transaction 加 refund_fen 累计列**。

### 退款回调 endpoint

`POST /api/pay/v3/refund-notify`（@SaIgnore，与 PAY-001 `/api/pay/v3/notify` 分离），复用 V3 NotificationParser AES-GCM。

## AI 自测（Tier 1A）

### 编译 + install

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
COMPILE_EXIT=0

$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -q
INSTALL_EXIT=0
```

### 单测（AC9 ≥ 4，本卡 5 个）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -Dtest=PayRefundServiceImplTest
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.743 s -- in PayRefundServiceImplTest
[INFO] BUILD SUCCESS
```

5 个测试方法（覆盖 AC9 全部分支）：
1. happy path：paid → apply → mock 受理成功 → V3 退款回调 SUCCESS → refund=refunded + transaction=refunded + 退款 SPI 命中 preorder（callback_type='refund'）
2. 非 paid（pending）不允许退 → ServiceException「仅已支付」
3. 重复退拦截：同 transaction 已 refunding → ServiceException「已有进行中或已完成的退款」
4. 回调幂等：已 refunded 二次回调 → duplicated，不重复变更
5. 受理失败回滚：mock 受理失败 → refund=failed + transaction 回 paid + ServiceException

退款 SPI 命中日志（happy path raw）：
```
RefundCallbackDispatcher -- [gz-pay] 退款回调 SPI 路由表就绪，已注册 1 个 handler：[preorder]
MockWechatPayClient -- [gz-pay-mock] refund ... → 受理成功 refund_id=mock_refund_id_RF-... (PROCESSING)
RefundCallbackDispatcher -- [gz-pay] 退款 SPI 分发 business_type=preorder → PreorderRefundCallbackHandler refund_no=RF-...
PreorderRefundCallbackHandler -- [gz-pay] PreorderRefundCallbackHandler.onRefunded 命中（占位）... SKU 库存不归还 待 ORD-104 填实现
```

### pay 包全量回归（确认未破坏上游 PAY-001/101/102/104 测试）

```
$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -Dtest='org.dromara.gz.common.pay.**'
GzPayBusinessFullChainMockTest      Tests run: 2  ✅（已适配 PayOrderNoGenerator 新构造）
GzPayTransactionServiceImplTest     Tests run: 13 ✅
PayFundflowBillServiceImplTest      Tests run: 10 ✅
PayOrderQueryServiceImplTest        Tests run: 7  ✅
PayCallbackDispatcherTest           Tests run: 6  ✅
PayRefundServiceImplTest            Tests run: 5  ✅
[INFO] Tests run: 43, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### admin build（plus-ui）

```
$ npx vue-tsc --noEmit  → refund 相关文件 0 新增类型错误
$ pnpm build:prod        → 构建成功，emit dist/assets/RefundApplyDialog-C1Mq_ijz.js（+ refund/index 进 index-* chunk）
```

## 风险提示 / 已知 issue

- R1 真实退款端到端 = **外部前置风险**（商户号 + apiV3Key + 商户私钥未到位，Kevin 决策 1）。本卡 DoD = mock 全链路自测；real 路径已实现（SDK RefundService.create + NotificationParser parse RefundNotification）但**未做真实联调**。staging/prod 切 real 需注入 `gz.pay.refund-notify-url`（完整域名 URL）。
- R3 真实退款 API 失败（余额不足/网络）→ status 卡 refunding。本卡：受理失败已回滚 paid；回调返 ABNORMAL/CLOSED → failed 留人工（doc/10 §6.E4）。admin 退款记录列表可见 failed 态供人工介入；refunding 态重试退款入口待订单看板（ADMIN-103）落地后接通。
- 受理成功返回的 refund_id 暂不落库（以异步回调写 wechat_refund_id 为准，避免半态写入）；若需「受理后即展示微信退款单号」可在 D1x 增量补。
- 「申请退款」按钮当前 disabled 占位（订单详情看板 ADMIN-103 未完工）。RefundApplyDialog 已就绪并 `defineExpose({ open })`，看板落地后直接 `dialogRef.open(txId, outTradeNo, amountCent)` 接通，本卡不依赖看板。

## 对下游 ticket 的提示

- **GZ-ORD-104（预购退款 handler 填实现）**：把 `PreorderRefundCallbackHandler.onRefunded` 填实——注入 IGzOrdOrderService 把 out_trade_no/business_order_no 对应的 `gz_ord_order` paid→refunded（同 PAY-103 退款回调事务 REQUIRED）。**强约束（doc/10 §6.N10 / §7.N13）：退款 SKU 库存不归还**（货已采购），仅推进订单状态，不回写 gz_ord_sku.stock。可二选一：把该 handler 移到 ruoyi-gz-ord 模块，或在本类注入 ord service（§0 自检定）。
- **GZ-ORD-105 / GACHA 订单详情（mp）**：C 端**绝对无退款入口**（合同 §4.5 / 强约束 #5）。订单详情页仅展示文案「如需退款请联系客服」+ 客服入口（GZ-SYS-004 已实现）。§0 自检 grep 确认无「申请退款」按钮，Kevin 批量人验必查。
- **GACHA 退款 handler**：扭蛋退款需自行实现 `IRefundCallbackHandler`（supportedBusinessType=gacha），退款回滚策略（是否回收奖品/库存）由扭蛋域决策。
- **ADMIN-103 订单看板**：退款按钮接通点 = `dialogRef.open(交易行 id, out_trade_no, amount_cent)`；退款记录可复用 `/system/gz/pay/refund/list?outTradeNo=`。

## 收尾说明

- 退款 admin ticket（纯 admin/后端，C 端无退款入口、无 mp 人验面）→ **跳过 Tier 2 入口可达**（CLAUDE.md §8.2 例外：Tech 段无 miniapp/ + AC 无微信原生能力）。AI Tier 1A 全 ✅ 即终态。
- 嵌套限制无法 spawn kevin-qa；Tier 1A 已做扎实（编译 + install + 5 退款单测 + 43 pay 全量回归 + admin build）。
- 未 commit（按要求）。

## §AI 测试段（kevin-qa 完工后追加）

（本卡纯 admin/后端，无 mp 人验面；如需 Tier 1B 由 Kevin 主线程 spawn kevin-qa 跑 admin Playwright + 后端集成）
# GZ-PAY-104 完工报告 — 业务通道账单对账批

> 每日 SnailJob 拉前一业务日微信资金账单（/v3/bill/fundflowbill），解析 CSV 按 transaction_id
> 覆盖式回写 gz_pay_transaction.fee_cent（fee 唯一真源）。纯后端跑批，无 mp / admin 页面 → 无人验。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A — 项目目录非 git 仓库（`git rev-parse` fatal not a repository），按约定不 commit |
| 上游依赖 GZ-PAY-101 merge | ✅ `pay/service/spi/`（PayCallbackHandler / PayCallbackDispatcher / PreorderPayCallbackHandler）已存在 |
| 支付模块定位（任务卡 Tech 笔误修正） | ✅ 模块=`ruoyi-gz-common` 包=`org.dromara.gz.common.pay.*`（无 `ruoyi-gz-pay` 模块），按主线程实证修正落地 |
| `gz_pay_transaction.fee_cent` 列存在 | ✅ V202606041200 行 77：`fee_cent BIGINT NULL`（仅 UPDATE 不 ALTER） |
| `gz_pay_transaction.transaction_id` 列存在 | ✅ V202606041200 行 80：`transaction_id VARCHAR(64) NULL` + `uk_tenant_transaction_id` |
| `gz_pay_transaction.status='paid'` 可过滤 | ✅ V202606041200 行 78：status 含 paid 态 |
| gz-common pom 有 `ruoyi-common-job` | ✅ pom.xml 行 87（SnailJob @JobExecutor 无需改 pom） |
| 编译基线（写前） | ✅ `mvn compile -pl ruoyi-gz-common` exit 0 |
| migration 时间戳 > 当前最大 | ✅ V202606061100 > V202606060901（GZ-ORD-101-menu） |
| 未注册任何 SPI handler（R2） | ✅ spi/handler/ 仅 PreorderPayCallbackHandler（PAY-101 的），我 3 个新文件无 Handler/onPaid/SPI 引用 |

### 权威蓝图引用摘录（§0 强制）

- **doc/10 §10 E6**：系统按 transaction 级实际 fee 字段汇总，**不依赖固定费率** → 本卡是其数据准备前置，把真实笔费灌进 `fee_cent`。
- **doc/11 §4.2**：回写目标 `fee_cent`（分）/ 关联键 `transaction_id` / 过滤 `status='paid'`。
- **doc/11 F4.3 / F9.2**：V3 回调 body **不含 fee** → 唯一来源 = 每日拉 `/v3/bill/fundflowbill`。本卡落地这条裁定。
- **doc/11 §9.1**：`gz_recon_daily.system_fee_cent = SUM(fee_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)` → 本卡是其上游唯一数据源（不回写 → D11 对账"通道费"列恒 0）。

## 实现摘要

> DDL + entity + mapper + CSV 解析器/构造器/row + IWechatPayClient.downloadFundFlowBill + MockWechatPayClient
> 由前序 partial 落地（已就位且齐全）。本次补齐缺的两块：**service（可单测核心）+ SnailJob 薄壳**，并写齐单测。

新增文件（本次）：

| 文件 | 行数 | 作用 |
|---|---|---|
| `pay/service/PayFundflowBillService.java` | 69 | service 接口 + `ReconcileResult` record（billTotal/matched/transactionNotFound/paidNoBill，AC5 可断言） |
| `pay/service/impl/PayFundflowBillServiceImpl.java` | 120 | 核心：拉账单→sha1 校验→解析→幂等 upsert→覆盖式回写→缺账/孤儿告警（AC3-6） |
| `pay/job/PayFundflowBillJob.java` | 70 | SnailJob 薄壳 `@JobExecutor(name="gzPayFundflowBillJob")`，仅取 bizDate=前一日→调 service→返结果 |
| `pay/service/PayFundflowBillServiceImplTest.java`（test） | 332 | 10 个单测，覆盖 CSV 解析/回写/AC5 两计数/AC6 幂等/hash 失败 |

已就位（前序 partial，本卡读取复用，未改）：
- DDL `V202606061100__GZ-PAY-104-pay-bill-fundflow.sql`（建 `gz_pay_bill_fundflow`）
- `domain/entity/GzPayBillFundflow.java` / `mapper/GzPayBillFundflowMapper.java`（upsertBill / updateFeeCentByTransactionId / selectPaidTransactionIdsByDate / countByBillDate）
- `service/internal/bill/{FundFlowBillCsvParser,FundFlowBillCsvBuilder,FundFlowBillRow}.java`
- `service/internal/IWechatPayClient.java`（扩 `downloadFundFlowBill(LocalDate)` + `FundFlowBill` record）+ `MockWechatPayClient`（setOverrideBillCsv/HashValue 注入钩子）

### DDL 表/字段（gz_pay_bill_fundflow）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK AUTO | 主键（不暴露前端） |
| bill_date | DATE NOT NULL | 账单业务日 |
| transaction_id | VARCHAR(64) NOT NULL | 微信交易号（关联回写键） |
| out_trade_no | VARCHAR(64) NULL | 业务订单号（冗余追溯） |
| fee_cent | BIGINT NOT NULL | 该笔真实通道手续费（分） |
| raw_line | TEXT NULL | 原始 CSV 行（争议追溯） |
| tenant_id | VARCHAR(20) NOT NULL DEFAULT '1001' | 多租户（INSERT 不显式赋，拦截器注入） |
| del_flag | CHAR(1) '0'/'1' | 软删 2 值 |
| + create/update_dept/by/time + remark | | 公共字段 |

约束：`UNIQUE uk_tenant_bill_date_transaction_id (tenant_id, bill_date, transaction_id)`（AC6 幂等基础）+ idx_bill_date + idx_transaction_id。**未改 gz_pay_transaction 结构**（仅 UPDATE）。

## AI 自测（Tier 1A）

### 1. 编译（写后，gz-common 单模块，无 -am）

```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -q
EXIT=0   （无 error 输出）
```

### 2. 单测 — PayFundflowBillServiceImplTest（10 用例全过）

```
[INFO] Running org.dromara.gz.common.pay.service.PayFundflowBillServiceImplTest
15:47:23 WARN  ...PayFundflowBillServiceImpl -- [gz-pay-bill] 孤儿账单行（账单有但系统无 paid 交易）bill_date=2026-06-05 count=1 txnIds=[4200WX_ORPHAN]
15:47:23 WARN  ...PayFundflowBillServiceImpl -- [gz-pay-bill] 缺账（系统当日 paid 交易账单缺其行）bill_date=2026-06-05 count=1 txnIds=[4200WX_MISSING]
15:47:23 INFO  ...PayFundflowBillServiceImpl -- [gz-pay-bill] 对账完成 bill_date=2026-06-05 billTotal=2 matched=1 transactionNotFound=1 paidNoBill=1
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.647 s -- in PayFundflowBillServiceImplTest
[INFO] BUILD SUCCESS
```

用例清单（AC 映射）：
1. happy path 2 笔全匹配回写（元→分换算断言：0.01→1 / 0.59→59）— AC3/AC4
2. 覆盖式回写 — 同交易号 2 个手续费行聚合 59 分一次性回写（非两次累加）— AC4
3. 孤儿账单 — 回写 affected=0 → transactionNotFound=1（明细列表）— AC5 ①
4. 缺账 — 系统 paid 但账单缺 → paidNoBill=1（明细列表）— AC5 ②
5. 孤儿+缺账同时触发（mock AC7 全链路）→ 两计数均 >0 — AC5/AC7
6. 同日重跑幂等 — upsert 调用对称、同笔 fee 始终 1（不累加）— AC6
7. hash 校验失败 → ServiceException + 不 upsert 不回写 — AC3
8. CSV 缺关键列（业务类型）→ 解析抛错 — AC3
9. 明细段中段空行 → 跳过容错、正常笔仍解析 — CSV 健壮性
10. bizDate=null → 早失败、不拉账单不回写 — 入参校验

### 3. 全模块回归（83 用例，0 失败）

```
[INFO] Tests run: 83, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
（含 PAY-001/101 既有 12 用例 + dashboard/wechat/staff 等，未被本卡影响。GzDashboardServiceImplTest 的单条 ERROR 日志是其自身异常路径断言，该测试 4/4 绿。）

### 4. 落 .m2（并行安全，仅 gz-common，无 -am）

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common
[INFO] Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/.../ruoyi-gz-common-5.6.1.jar
[INFO] BUILD SUCCESS
```

## mock 全链路结论（AC7 = 本日 DoD）

`gz.pay.client.mode=mock`（matchIfMissing=true）→ `MockWechatPayClient.downloadFundFlowBill` 返回
`FundFlowBillCsvBuilder` 构造的可控 CSV（默认 2 笔 / 单测注入「正常+孤儿+缺账」）+ 自匹配 sha1。
单测驱动 AC3（解析+hash 校验）→ AC4（覆盖式回写）→ AC5（两类计数被触发，WARN 含明细 txnId 列表）→
AC6（幂等）全链路通过。**真实账单拉取 = 外部前置风险 R1（甲方商户配置滞后），不当默认就绪。**

## SnailJob 注册清单（人工在 SnailJob 控制台注册，不写迁移）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-PAY-FUNDFLOW-BILL |
| 执行器路由 executor_info | `gzPayFundflowBillJob`（= `@JobExecutor(name)`） |
| 触发类型 / CRON | CRON `0 30 3 * * ?`（凌晨 3:30，账单 T+1 已生成，容器时区 Asia/Shanghai） |
| 阻塞策略 | 丢弃（DISCARD） |
| 组 | ruoyi_group |

bizDate 由壳取 `LocalDate.now().minusDays(1)`（前一业务日，账单 T+1 可用）。

## 是否注册 SPI handler

**否**（R2 遵守）：本卡是主动拉账单跑批，不注册支付/退款 SPI 回调 handler，不抢 PAY-102/103 的 SPI key。
spi/handler/ 仅含 PAY-101 的 PreorderPayCallbackHandler，本卡未新增。

## 风险提示 / 已知 issue

- **R1 外部前置（甲方商户配置）**：真实 `/v3/bill/fundflowbill` 需商户号 + cert + apiV3Key 就绪。本卡 DoD 仅认 mock 全链路；真实账单 CSV 列序/手续费列名以官方文档为准，真实端到端验证不当就绪 → 上线前需 real 模式回归。
- **多租户**：cron 用 `TenantHelper.ignore` + 常量 `TENANT_ID="1001"`（与 GzDashboardServiceImpl 同口径，V1.0 单租户）。未来多租户需改为遍历租户列表分批 —— 已在代码注释标注。
- **`updateFeeCentByTransactionId` affected 语义**：mapper 返回受影响行数，本卡用 `affected >= 1` 判命中。同一 transaction_id 在 gz_pay_transaction 至多 1 条 paid（uk_tenant_transaction_id 兜底），实际仅 0/1。
- 待 Kevin 批量人验关注：N/A — 纯后端 ticket，无 mp / admin 页面，AI Tier 1A ✅ 即终态（CLAUDE.md §8.2）。

## 对 D11 GZ-ADMIN-105 对账契约提示

- 本卡**只灌 `gz_pay_transaction.fee_cent`**（真实笔费），**不建 gz_recon_* 表、不算汇总、不做业务线 attribution** —— 那是 ADMIN-105 的范围。
- ADMIN-105 计算 `gz_recon_daily.system_fee_cent` 时直接 `SUM(gz_pay_transaction.fee_cent WHERE business_type=? AND status='paid' AND DATE(paid_time)=?)`（doc/11 §9.1）；本卡保证该列有真源。
- **fee_cent 可能为 NULL**（PAY-104 跑批未覆盖到的交易 / 账单缺该笔 = paidNoBill）→ ADMIN-105 SUM 时注意 `COALESCE(fee_cent,0)` 或 `WHERE fee_cent IS NOT NULL`，并把 paidNoBill 缺口体现在对账差异。
- `business_type='test'` 交易本卡照常回写 fee_cent（不预过滤）→ ADMIN-105 对账阶段才 exclude test 单（doc/10 §10 Q10.2 业务线 attribution）。
- 审计追溯：`gz_pay_bill_fundflow.raw_line` 存原始 CSV 行，对账争议时可回溯每笔 fee 来源。

## §AI 测试段（kevin-qa Tier 1B）

> 嵌套 spawn 限制 → 本 subagent 无法 spawn kevin-qa。Tier 1A 已做扎实（编译 + 10 单测 + 83 全模块回归 + mock 全链路 + .m2 install）。Tier 1B（集成 / 启动 Flyway 跑 DDL 真建表 + 真 DB upsert/回写）由主线程统一接管。
