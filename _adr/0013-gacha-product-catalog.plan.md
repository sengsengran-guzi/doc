# 扭蛋产品库 + 投放线改造 实现计划（GZ-GACHA-112）

> **For agentic workers:** 本计划由主线程编排（ultracode）执行，按 Task 顺序推进，Task 间编译/自测 gate。
> 权威设计见 [ADR-0013](0013-gacha-product-catalog.md)。Steps 用 `- [ ]` 跟踪。

**Goal:** 把扭蛋「内联奖品」升级为「可复用产品库 `gz_gacha_product` + 机器×产品投放线 `gz_gacha_prize`」，admin 加产品库 CRUD + 奖品池改「选产品」，mp 单机详情只显示产品列表（去概率）。

**Architecture:** 产品固有属性（名/图/参考价）入新主表 `gz_gacha_product`；`gz_gacha_prize` 改为投放线（加 `product_id`，删内联列，保留 rarity/weight/stock/enabled 按机器独立）。抽奖事务/快照不变（快照隔离历史）。展示层运行时 join 产品库取值。

**Tech Stack:** RuoYi-Vue-Plus 5.5.x（MyBatis-Plus + Sa-Token + Flyway）· plus-ui（Vue3 + Element Plus）· miniapp（uni-app + wot-design-uni）。

## Global Constraints（ADR-0013 + CLAUDE.md 铁律，逐 Task 隐含）

- 业务表 `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`；INSERT 不显式赋（`InjectionMetaObjectHandler`）；UNIQUE 必含 tenant_id。
- 包名 `org.dromara.gz.gacha.{controller,service,mapper,domain,...}`。
- DDL 命名 `V<yyyyMMddHHmm>__<TICKET>-<desc>.sql`，放 `ruoyi-admin/src/main/resources/db/migration/`，时间戳 **> 当前最大 `V202606300001`**；已应用迁移不可改。
- menu_id GACHA 段 10000-10099：产品库页 `10005`，按钮 `10050-10054`。
- 金额一律 `_cent`（BIGINT，分）；id / imageId 出参 `@JsonSerialize(ToStringSerializer)`。
- 改 `ruoyi-gz-*` 模块代码后必须 `mvn CLEAN install`（见 [memory] mvn-clean-install-required）+ restart；重建库后 `FLUSHDB`。
- 不写 `any`（TS）/ 不吞异常 / 不留无说明 TODO；i18n 走 `t('xxx')` + zh/en。
- 测 admin 用 `gz_owner/gz_owner123!`（租户 1001），非 ruoyi 超管。
- 抽奖事务（`ProbabilityNormalizer`/`SecureRandomDrawer`/`SELECT FOR UPDATE`）**禁改逻辑**，只改快照「取值来源」。

---

## File Structure

**后端 `ruoyi-modules/ruoyi-gz-gacha/src/main/java/org/dromara/gz/gacha/`：**
- 新建产品域：`domain/entity/GzGachaProduct.java` · `domain/bo/GzGachaProductBo.java` · `domain/bo/GzGachaProductQueryBo.java` · `domain/vo/GzGachaProductVo.java` · `mapper/GzGachaProductMapper.java` · `service/IGzGachaProductService.java` · `service/impl/GzGachaProductServiceImpl.java` · `controller/GzGachaProductController.java`
- 改投放线：`domain/entity/GzGachaPrize.java` · `domain/bo/GzGachaPrizeBo.java` · `domain/vo/GzGachaPrizeVo.java` · `service/impl/GzGachaPrizeServiceImpl.java`（+ 接口 `IGzGachaPrizeService.java`）
- 改展示/快照 join：`service/impl/GzGachaDrawServiceImpl.java`（`buildPrizeSnapshot`）· `service/impl/GzGachaMachineServiceImpl.java`（mp detail）· `service/impl/GzGachaCollectionServiceImpl.java`（图鉴 cell）· `domain/vo/GzGachaPrizeDetailVo.java`（删 `normalizedProbability`）
- mapper XML（若有自定义 join）：`mapper/GzGachaProductMapper.xml` / 复用 LambdaQuery

**DDL：** `ruoyi-admin/src/main/resources/db/migration/V202606300002__GZ-GACHA-112-*.sql`

**Admin `plus-ui/src/`：**
- 新建：`views/gz-gacha/product/index.vue` · `api/gz-gacha/product.ts`
- 改：`views/gz-gacha/prize/index.vue`（选产品）· `api/gz-gacha/prize.ts` · `lang/zh_CN.ts` + `lang/en_US.ts`（gzGachaProduct + gzGachaPrize 调整）

**mp `miniapp/src/`：**
- 改：扭蛋单机详情页（`pages/gacha/detail.vue` 或同名）· 对应 api/类型 · 去概率公示组件引用

**Doc：** `doc/11-字段权威表.md` §7 · `doc/10-业务流权威图.md` §8

---

## Task 1: DDL — 产品库建表 + 投放线改造 + 数据迁移 + 菜单

**Files:**
- Create: `ruoyi-admin/src/main/resources/db/migration/V202606300002__GZ-GACHA-112-product-catalog.sql`

**Interfaces:**
- Produces: 表 `gz_gacha_product`（列见 ADR §1）；`gz_gacha_prize` 新列 `product_id BIGINT UNSIGNED NOT NULL` + uk `uk_gacha_prize_machine_product(tenant_id,machine_id,product_id)`，删列 `name/image_id/reference_value_cent`；菜单 10005 + 按钮 10050-10054 + owner(role 100) 授权。

- [ ] **Step 1: 写迁移文件**（一文件内顺序执行；幂等用 `IF NOT EXISTS` / 先查后插）

```sql
SET NAMES utf8mb4;

-- 1. 产品库主表
CREATE TABLE IF NOT EXISTS gz_gacha_product (
  id                    BIGINT UNSIGNED  NOT NULL AUTO_INCREMENT,
  tenant_id             VARCHAR(20)      NOT NULL DEFAULT '1001',
  product_no            VARCHAR(32)      NOT NULL COMMENT '业务码 GPRD-yyyyMMdd-6位序号',
  name                  VARCHAR(128)     NOT NULL,
  image_id              BIGINT UNSIGNED  NULL DEFAULT NULL COMMENT 'FK语义→gz_file_object.id',
  reference_value_cent  BIGINT           NULL DEFAULT NULL COMMENT '参考价(分)',
  ip_tag                VARCHAR(64)      NULL DEFAULT NULL,
  enabled               TINYINT          NOT NULL DEFAULT 1 COMMENT '1可投放/0停用',
  version               INT              NOT NULL DEFAULT 0,
  create_dept           BIGINT           NULL DEFAULT NULL,
  create_by             BIGINT           NULL DEFAULT NULL,
  create_time           DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  update_by             BIGINT           NULL DEFAULT NULL,
  update_time           DATETIME(3)      NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  del_flag              CHAR(1)          NOT NULL DEFAULT '0',
  remark                VARCHAR(500)     NULL DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_gacha_product_no (tenant_id, product_no),
  KEY idx_gacha_product_ip (tenant_id, ip_tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='GZ-GACHA 产品库（ADR-0013）';

-- 2. prize 加 product_id（先 nullable 便于回填）
ALTER TABLE gz_gacha_prize ADD COLUMN product_id BIGINT UNSIGNED NULL DEFAULT NULL COMMENT 'FK语义→gz_gacha_product.id' AFTER machine_id;

-- 3. 存量 1:1 迁移：每条 prize 建一条 product（product_no 用 GPRD-+旧id 保唯一），回填 product_id
INSERT INTO gz_gacha_product
  (tenant_id, product_no, name, image_id, reference_value_cent, ip_tag, enabled, version,
   create_dept, create_by, create_time, update_by, update_time, del_flag, remark)
SELECT p.tenant_id,
       CONCAT('GPRD-MIG-', p.id),
       p.name, p.image_id, p.reference_value_cent,
       (SELECT m.ip_tag FROM gz_gacha_machine m WHERE m.id = p.machine_id),
       1, 0, p.create_dept, p.create_by, p.create_time, p.update_by, p.update_time, '0',
       CONCAT('迁移自 prize#', p.id, ' (ADR-0013)')
FROM gz_gacha_prize p
WHERE p.del_flag = '0';

UPDATE gz_gacha_prize p
JOIN gz_gacha_product pr ON pr.product_no = CONCAT('GPRD-MIG-', p.id)
SET p.product_id = pr.id
WHERE p.del_flag = '0';

-- 软删的 prize 行也要满足 NOT NULL：指向一个占位/其自身迁移产品（保险：给所有剩余 NULL 建产品）
INSERT INTO gz_gacha_product
  (tenant_id, product_no, name, image_id, reference_value_cent, ip_tag, enabled, version,
   create_time, update_time, del_flag, remark)
SELECT p.tenant_id, CONCAT('GPRD-MIG-', p.id), p.name, p.image_id, p.reference_value_cent,
       NULL, 0, 0, p.create_time, p.update_time, '0', CONCAT('迁移自已删 prize#', p.id)
FROM gz_gacha_prize p WHERE p.product_id IS NULL;
UPDATE gz_gacha_prize p
JOIN gz_gacha_product pr ON pr.product_no = CONCAT('GPRD-MIG-', p.id)
SET p.product_id = pr.id WHERE p.product_id IS NULL;

-- 4. 收紧约束 + 删内联列
ALTER TABLE gz_gacha_prize MODIFY COLUMN product_id BIGINT UNSIGNED NOT NULL COMMENT 'FK语义→gz_gacha_product.id';
ALTER TABLE gz_gacha_prize ADD UNIQUE KEY uk_gacha_prize_machine_product (tenant_id, machine_id, product_id);
ALTER TABLE gz_gacha_prize DROP COLUMN name, DROP COLUMN image_id, DROP COLUMN reference_value_cent;

-- 5. 菜单：产品库页 10005 + 按钮 10050-10054（父=10000 扭蛋目录）+ owner 授权
INSERT IGNORE INTO sys_menu
  (menu_id, menu_name, parent_id, order_num, path, component, query_param,
   is_frame, is_cache, menu_type, visible, status, perms, icon, create_dept, create_by, create_time, remark)
VALUES
  (10005, '产品库', 10000, 0, 'product', 'gz-gacha/product/index', '',
   1, 0, 'C', '0', '0', 'gz:gacha:product:list', '#', 103, 1, NOW(), 'GZ-GACHA-112 产品库'),
  (10050, '产品列表', 10005, 1, '', '', '', 1, 0, 'F', '0', '0', 'gz:gacha:product:list',   '#', 103, 1, NOW(), ''),
  (10051, '产品详情', 10005, 2, '', '', '', 1, 0, 'F', '0', '0', 'gz:gacha:product:query',  '#', 103, 1, NOW(), ''),
  (10052, '产品新增', 10005, 3, '', '', '', 1, 0, 'F', '0', '0', 'gz:gacha:product:add',    '#', 103, 1, NOW(), ''),
  (10053, '产品编辑', 10005, 4, '', '', '', 1, 0, 'F', '0', '0', 'gz:gacha:product:edit',   '#', 103, 1, NOW(), ''),
  (10054, '产品删除', 10005, 5, '', '', '', 1, 0, 'F', '0', '0', 'gz:gacha:product:remove', '#', 103, 1, NOW(), '');
INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
SELECT 100, m FROM (SELECT 10005 m UNION SELECT 10050 UNION SELECT 10051 UNION SELECT 10052 UNION SELECT 10053 UNION SELECT 10054) t;
```

- [ ] **Step 2:** 应用启动跑 Flyway（`mvn spring-boot:run -pl ruoyi-admin`），看日志 `Migrating schema ... 202606300002`，无 checksum 错。
- [ ] **Step 3:** 校验：`DESC gz_gacha_product;`、`SHOW COLUMNS FROM gz_gacha_prize LIKE 'product_id';`（NOT NULL）、`SELECT COUNT(*) FROM gz_gacha_prize WHERE product_id IS NULL;`（=0）、`SHOW INDEX FROM gz_gacha_prize WHERE Key_name='uk_gacha_prize_machine_product';`。
- [ ] **Step 4:** `FLUSHDB`（重建/迁移后清字典缓存）。

---

## Task 2: 后端 — 产品库域 CRUD（gz_gacha_product）

**Files:** Create entity/bo/queryBo/vo/mapper/service/serviceImpl/controller（见 File Structure）。
**Interfaces:**
- Produces:
  - `GzGachaProduct`（entity，字段对齐 DDL；`@Version version`，`@TableLogic delFlag`）
  - `IGzGachaProductService`：`TableDataInfo<GzGachaProductVo> selectAdminPage(GzGachaProductQueryBo,PageQuery)` · `GzGachaProductVo selectAdminById(Long)` · `Long insertByBo(GzGachaProductBo)` · `boolean updateByBo(GzGachaProductBo)` · `boolean deleteByIds(List<Long>)` · `List<GzGachaProductVo> listOptions(String ipTag)`（奖品池选产品下拉用，仅 enabled=1）· `Map<Long,GzGachaProduct> mapByIds(Collection<Long>)`（展示 join 用）
  - Controller 路径 `/system/gz/gacha/product`，perms `gz:gacha:product:list/query/add/edit/remove` + `/options` 走 `list` 权。

- [ ] **Step 1: 写产品 CRUD service 单测（happy + 3 error）** — `GzGachaProductServiceImplTest`

```java
@Test void insertByBo_generatesProductNo_andPersists() { /* 建产品 → product_no GPRD- 前缀非空，查回字段一致 */ }
@Test void insertByBo_dupName_allowed_diffNo() { /* 同名允许（不去重），product_no 不同 */ }
@Test void deleteByIds_blockedWhenReferencedByPrize() { /* 产品被投放线引用 → 抛 ServiceException「产品已被机器投放，不能删除」*/ }
@Test void updateByBo_optimisticLock_orNotFound() { /* 不存在 id → false / 抛 */ }
@Test void listOptions_onlyEnabled() { /* enabled=0 不返回 */ }
```

- [ ] **Step 2:** 实现 entity/bo/queryBo/vo（仿 `GzGachaMachine*` 模式：bo 用 `@NotBlank/@Size/@Min` + AddGroup/EditGroup；vo 用 `ToStringSerializer` 转 id/imageId；`reference_value_cent` 分）。
- [ ] **Step 3:** 实现 mapper（`extends BaseMapperPlus<GzGachaProduct, GzGachaProductVo>`）。
- [ ] **Step 4:** 实现 serviceImpl：
  - `product_no` 生成「查当日 `GPRD-yyyyMMdd-` 最大序号 + 1」（仿 `GzGachaPrizeServiceImpl` 的 prize_no 生成）。
  - `deleteByIds`：先 `count gz_gacha_prize WHERE product_id IN ids AND del_flag='0'` > 0 → `throw new ServiceException("产品已被机器投放，请先从奖品池移除后再删除")`。
  - `listOptions(ipTag)`：`LambdaQuery enabled=1 [+ ipTag]`，按 create_time desc。
- [ ] **Step 5:** 实现 controller（仿 `GzGachaMachineController`，写操作 `@Log` + `@RepeatSubmit`；`/options` GET 返 `R<List<GzGachaProductVo>>`）。
- [ ] **Step 6:** `mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am` 绿。

---

## Task 3: 后端 — `gz_gacha_prize` 改造为投放线（选产品）

**Files:** Modify `GzGachaPrize.java`（删 name/imageId/referenceValueCent，加 `Long productId`）· `GzGachaPrizeBo.java`（删 name/imageId/referenceValueCent，加 `@NotNull(AddGroup) Long productId`）· `GzGachaPrizeVo.java`（加 `productId`(string) + 展示用 `productName`/`imageId`/`referenceValueCent`(来自 join)）· `IGzGachaPrizeService.java` + `GzGachaPrizeServiceImpl.java`。

**Interfaces:**
- Consumes: `IGzGachaProductService.mapByIds` / `listOptions`（Task 2）。
- Produces: `insertByBo`：校验「机器存在 + 产品存在且 enabled + (machine,product) 未投放过(uk 前置查)」→ 建投放线（rarity/weight/stock/enabled），`prize_no` 仍系统生成。`updateByBo`：只改 rarity/weight/stock/enabled（productId/machineId 不可改）。`selectAdminPage`/`selectAdminById`：join 产品库回填 productName/imageId/referenceValueCent。

- [ ] **Step 1: 改单测** `GzGachaPrizeServiceImplTest`：

```java
@Test void insertByBo_requiresExistingEnabledProduct() { /* product 不存在/停用 → 抛 */ }
@Test void insertByBo_rejectsDuplicateProductInSameMachine() { /* 同机器同产品再投放 → 抛「该产品已在本机奖品池」*/ }
@Test void insertByBo_persistsLineFields_andJoinsProductForVo() { /* 建线后查回：rarity/weight/stock 来自线，name/image 来自产品 */ }
@Test void updateByBo_ignoresProductIdChange() { /* 改 productId 不生效 */ }
```

- [ ] **Step 2:** 改 entity/bo/vo 字段（如上）。`GzGachaPrizeVo` 新增：`@JsonSerialize(ToStringSerializer) Long productId` · `String productName` · `@JsonSerialize(ToStringSerializer) Long imageId` · `Long referenceValueCent`（后三个 join 产品填）。
- [ ] **Step 3:** 改 serviceImpl：`insertByBo` 调 `productService` 校验 + uk 前置查（`exists machine_id+product_id+del_flag=0`）；`buildEntity` 不再 set name/image/refValue；`buildVo`/分页后用 `productService.mapByIds(prizeProductIds)` 批量回填展示字段（避免 N+1）。
- [ ] **Step 4:** `mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am` 绿。

---

## Task 4: 后端 — 抽奖快照 + mp/admin 展示 join 产品 + 去 mp 概率

**Files:** Modify `GzGachaDrawServiceImpl.java`（`buildPrizeSnapshot`）· `GzGachaMachineServiceImpl.java`（mp detail 装配）· `GzGachaCollectionServiceImpl.java`（图鉴 cell）· `GzGachaPrizeDetailVo.java`（删 `normalizedProbability`）· `IGzGachaPrizeService.listByMachineId` 调用方。

**Interfaces:**
- Consumes: `IGzGachaProductService.mapByIds`（Task 2）。
- Produces: 快照 Prize 仍含 name/image/rarity/refValue（name/image/refValue 取产品，rarity 取线）；mp `GzGachaMachineDetailVo.prizes` 每条 = 产品图/名/参考价 + 线 rarity，**无 normalizedProbability**；图鉴 cell 名/图取产品，rarity 取线。

- [ ] **Step 1:** `buildPrizeSnapshot(GzGachaPrize p)`：入参补产品 → 改签名 `buildPrizeSnapshot(GzGachaPrize p, GzGachaProduct product)`，`name=product.name / imageId=product.imageId / referenceValueCent=product.referenceValueCent / rarity=p.rarity`。调用处（抽奖事务命中奖品后）先取该 prize 的 `product`（已在内存/单查）。**不改抽奖随机/扣减逻辑**。
- [ ] **Step 2:** `GzGachaMachineServiceImpl` mp detail：组装 prizes 时 `mapByIds` 批量取产品；set 产品名/imageUrl(解析 image_id)/referenceValueCent + 线 rarity；**移除** `normalizedProbability` 赋值与 `ProbabilityNormalizer` 在此处的调用；排序改 `rarity` 档位(SSR>SR>R>N) + create_time。
- [ ] **Step 3:** `GzGachaPrizeDetailVo`：删 `normalizedProbability` 字段（+ 注释）；保留 name/imageUrl/rarity/referenceValueCent/stockRemain/enabled。
- [ ] **Step 4:** `GzGachaCollectionServiceImpl` 图鉴 cell：名/图改取产品（`mapByIds`），rarity 取线。
- [ ] **Step 5:** 全模块编译 + 单测：`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am` 绿；抽奖事务测试（`GzGachaDrawServiceImplTest`）仍绿（快照字段正确）。
- [ ] **Step 6:** `mvn CLEAN install -DskipTests -pl ruoyi-modules/ruoyi-gz-gacha -am` 重打 jar；重启 app。curl 验：mp 详情 `GET /system/gz/gacha/machine-mp/detail?...` 返回无 probability 字段、prize 含产品名/图。

---

## Task 5: Admin — 产品库页（新）

**Files:** Create `plus-ui/src/views/gz-gacha/product/index.vue` · `plus-ui/src/api/gz-gacha/product.ts`；Modify `lang/zh_CN.ts` + `en_US.ts`（加 `gzGachaProduct` 块）。

- [ ] **Step 1:** `api/gz-gacha/product.ts`：`listGzGachaProduct(query)` · `getGzGachaProduct(id)` · `addGzGachaProduct(bo)` · `updateGzGachaProduct(bo)` · `delGzGachaProduct(ids)` · `optionsGzGachaProduct(ipTag?)`（仿 `api/gz-gacha/prize.ts` 风格 + `GzGachaProductVO`/`Form`/`Query` 类型）。
- [ ] **Step 2:** `views/gz-gacha/product/index.vue`：ruoyi CRUD 模板（搜索 name/ipTag/enabled + 表格 + 新增/编辑弹窗）。图片用 ruoyi `ImageUpload`（存 image_id），参考价元↔分（提交 `Math.round(yuan*100)`），enabled 开关，`v-hasPermi` 绑 `gz:gacha:product:*`。
- [ ] **Step 3:** i18n `gzGachaProduct.*`（zh + en）。
- [ ] **Step 4:** `pnpm build:prod`（或 dev typecheck）该页无报错；产品 CRUD 手测（登 gz_owner）。

---

## Task 6: Admin — 奖品池页改「选产品」

**Files:** Modify `plus-ui/src/views/gz-gacha/prize/index.vue` · `api/gz-gacha/prize.ts` · i18n。

- [ ] **Step 1:** `api/gz-gacha/prize.ts`：`GzGachaPrizeForm` 删 `name/imageId/referenceValueCent`，加 `productId`；`GzGachaPrizeVO` 加 `productId/productName/imageId/referenceValueCent`（展示）。
- [ ] **Step 2:** prize `index.vue`：新增/编辑弹窗把「填名/传图/填参考价」换成「**产品选择器**」（`el-select` 远程搜 `optionsGzGachaProduct`，显示 产品名 + 缩略图 + 参考价；选中存 productId）。编辑态 productId 只读。列表列：产品图(join)/产品名/稀有度/权重/库存/启用/操作。保留按机器 machineId 过滤 + 「从机器列表进入」语义（noMachineHint 不变）。
- [ ] **Step 3:** i18n 调整（去 seat 无关；加 `pickProduct/productCol` 等）。
- [ ] **Step 4:** typecheck 无报错；手测：进某机器奖品池 → 选产品加入 → 配权重/库存/稀有度 → 保存 → 列表显示产品图名。

---

## Task 7: mp — 单机详情产品列表（去概率）

**Files:** Modify mp 扭蛋单机详情页（定位：`miniapp/src/pages/gacha/` 下 detail 页）+ 其 api/类型 + 删概率公示组件引用。

- [ ] **Step 1:** 定位详情页与概率公示块（grep `normalizedProbability`/`概率`/`公示` in `miniapp/src/pages/gacha` + `api`）。
- [ ] **Step 2:** 删概率公示模块/折叠区；prizes 渲染为产品卡网格：产品图 + 产品名 + 稀有度标签 + 参考价（空不显示）。移除 `normalizedProbability` 类型字段引用。
- [ ] **Step 3:** vitest unit（若该页有 `.logic.ts`）调整；`pnpm test` 绿。
- [ ] **Step 4:** mp 模拟器 E2E flow（kevin-qa）：reLaunch 扭蛋详情 → 断言产品列表渲染、无概率百分比文本。

---

## Task 8: 权威蓝图 doc 更新

**Files:** Modify `doc/11-字段权威表.md` §7 · `doc/10-业务流权威图.md` §8。

- [ ] **Step 1:** doc/11 §7：新增 `gz_gacha_product` 字段表小节；§7.2 `gz_gacha_prize` 改为投放线（删 name/image/refValue 行，加 product_id + uk 说明，标注 rarity/weight/stock 按机器）。
- [ ] **Step 2:** doc/10 §8：展示读 join 产品库；mp 详情「概率不对外展示」（仅后台驱动）。
- [ ] **Step 3:** 描述写「当前最终状态」（CLAUDE.md §12，不写变更史）。

---

## Task 9: Tier 1B 整批 QA（kevin-qa，主线程统一派）

- [ ] admin Playwright：登 gz_owner → 产品库 CRUD + 奖品池选产品 + 机器列表「管理奖品池」可达（路由已修）。
- [ ] mp 模拟器 E2E：扭蛋详情产品列表渲染 + 无概率。
- [ ] 后端集成 + API 契约回归：抽奖端到端（建产品→投放→抽奖→快照名/图正确→图鉴）。
- [ ] 结果追加 `reports/<T>.md` §AI 测试段；任一 ❌ → 回修闭环。

---

## Self-Review

- **Spec coverage**：ADR §1 产品表→T1/T2；§2 prize 改造→T1/T3；§3 快照→T4；§4 图鉴→T4；§5 迁移→T1；§6 admin→T5/T6；§7 mp 去概率→T4(VO)/T7(页面)；doc→T8。全覆盖。✓
- **Placeholder**：迁移 SQL / join 取值 / VO 字段增删均给具体代码或字段名，无 TODO。✓
- **Type 一致**：`productId` 全链路一致；`GzGachaPrizeVo` 展示字段名 `productName/imageId/referenceValueCent` 与 admin api 类型一致；mp 删 `normalizedProbability` 同步 VO + 页面。✓
