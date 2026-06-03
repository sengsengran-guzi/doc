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
