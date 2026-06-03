# GZ-ORD-101 — 预购商品 + SKU 数据模型（gz_ord_product / gz_ord_sku + admin CRUD 从零建 + 截止下架 SnailJob）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §预定货品（商品 / SKU / 截止日 / 到货日 / 库存）
**关联拆解**: doc/02-需求拆解.md §3.2（GZ-ORD-101 预购商品 + SKU 数据模型）
**关联 mockup**: design/mockup/admin-products.html（admin 商品 CRUD 布局参考；admin 走 ruoyi/Element Plus 默认审美，不套 C 系统）
**关联 ADR**: —
**依赖**: GZ-SYS-001 ✅（ruoyi-gz-ord 模块壳已建，当前仅 HelloController；本 ticket 从零落表 + CRUD + executor）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

> 业务流 + 字段表是 ticket 实施的"蓝图"，缺引用 = AI 凭字面猜实现 = 翻车前兆（dongjiaoshan D6 教训）。
> UI 索引在 V1.0 设计冻结期降级为"视觉参考"（不卡硬约束）。

- **业务流**：doc/10-业务流权威图.md
  - **§7 预定货品全流程**（M3，V1.1）— 业务规则（全款 / 截止日 / 到货日精确或模糊 / SKU 级库存可不限）+ 状态机；本表是其上游配置数据
  - **§7.E1**（截止日过 → 不可下单 / 下架）/ **§7.E2**（库存不足扣减口径）/ **§7.N6**（SKU 乐观锁扣减）
  - 物流字段口径见 §9（跨境物流 C1 2 态 + 终态）— 本 ticket **不落物流字段**（物流在 gz_ord_order，ORD-104 建），仅需理解商品/SKU 不含物流列
- **字段表**：doc/11-字段权威表.md
  - **§6.1 `gz_ord_product` 预购商品主表**（完整 DDL 来源，逐字段照搬）
  - **§6.2 `gz_ord_sku` 商品 SKU 表**（含 `version` 乐观锁字段定义 + `stock_remain` 扣减口径 SQL）
  - §6.5 待澄清裁定（F6.1 到货日二选一走业务层校验；F6.4 `delivered` 即终态）
- **UI 参考**（admin）：`design/mockup/admin-products.html`（商品 CRUD 列表 + 表单布局，**仅参考**，走 ruoyi 默认审美）

## What

从零建立预购业务上游配置数据模型 — 预购商品（`gz_ord_product`）+ 多规格 SKU（`gz_ord_sku`）两张表，admin 端商品 + SKU 一体 CRUD（从零建，走 ruoyi/Element Plus 默认范式），SKU 库存乐观锁扣减服务方法（供 ORD-104 调用），截止日自动下架 SnailJob executor。

## AC（验收标准）

- [ ] **AC 1**：DDL `V<时间戳>__GZ-ORD-101-create-gz_ord_product-and-sku.sql`（时间戳 > `V202606051200`）落两张表，**字段逐字段锚 doc/11 §6.1 / §6.2**：
  - `gz_ord_product`：`product_no VARCHAR(32) NOT NULL`（`PRD-yyyyMMdd-6位序号`）/ `name VARCHAR(128) NOT NULL` / `main_image_id BIGINT UNSIGNED NULL`（FK 语义 → gz_file_object.id，不加 DB FK）/ `gallery_image_ids VARCHAR(512) NULL`（逗号分隔 file_object.id）/ `description_html MEDIUMTEXT NULL`（富文本）/ `ip_tag VARCHAR(64) NULL` / `deadline_time DATETIME(3) NOT NULL` / `delivery_date_text VARCHAR(64) NULL` / `delivery_date_exact DATE NULL`（与 text 二选一，DB 不约束）/ `status VARCHAR(16) NOT NULL DEFAULT 'off_shelf'` / `sales_count BIGINT UNSIGNED NOT NULL DEFAULT 0` / `sort_no INT NOT NULL DEFAULT 0` / `version INT NOT NULL DEFAULT 0` / ruoyi 公共字段 + `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'` + `del_flag CHAR(1) DEFAULT '0'`（仅 2 值 0/2，对齐 `@TableLogic`）
    - UNIQUE：`(tenant_id, product_no)`；IDX：`(tenant_id, status, deadline_time)` / `(tenant_id, ip_tag, status)`
  - `gz_ord_sku`：`product_id BIGINT UNSIGNED NOT NULL` / `sku_no VARCHAR(32) NOT NULL`（`SKU-yyyyMMdd-6位序号`）/ `spec_name VARCHAR(64) NOT NULL` / `price_cent BIGINT NOT NULL` / `stock_total INT NULL`（NULL = 无限）/ `stock_remain INT NULL`（NULL = 无限）/ `enabled TINYINT NOT NULL DEFAULT 1` / `sort_no INT NOT NULL DEFAULT 0` / `version INT NOT NULL DEFAULT 0` / ruoyi 公共字段 + `tenant_id` + `del_flag`
    - UNIQUE：`(tenant_id, sku_no)`；IDX：`(tenant_id, product_id)`
  - product_id 不加 DB 外键（mybatis-plus 风格，应用层保证）
- [ ] **AC 2**：admin 端商品 + SKU CRUD 接口（包名 `org.dromara.gz.ord.controller`，路径前缀 `/system/gz/ord/product`）：
  - `GET /list`（分页 + 按 `status` / `ip_tag` / `name` 模糊筛选，排序 `deadline_time` / `create_time`）
  - `GET /{id}`（详情含 SKU 列表）
  - `POST`（新增 product + 子 SKU 列表，同事务；`product_no` / `sku_no` 后端生成）
  - `PUT`（更新 product + SKU；SKU 增删走 diff —— 已被订单引用的 SKU 不允许物理删，改 `enabled=0` 软停用）
  - `PUT /changeStatus`（手动上下架 `on_shelf` ↔ `off_shelf`；**`auto_off` 仅 cron 写入**，admin 不可手动设 `auto_off`）
  - `DELETE /{ids}`（软删 `del_flag=2`，对齐 `@TableLogic`；已被订单引用的商品拒删，返回明确 msg）
- [ ] **AC 3**：admin 端 UI（`code/main/plus-ui/src/views/gz-ord/product/index.vue` + `src/api/gz-ord/product.ts`，**从零建** —— 无 V1.0 商品骨架可复用，ADMIN-005 是 mp 5tab 不是商品骨架）：
  - 列表页（BizTable + 搜索栏 status/ip_tag/name + 操作列：编辑 / 上下架 switch / 删除）
  - 编辑表单（`<el-dialog>` 或 `edit.vue`，含 SKU 子表 `<el-table>` 可编辑行：规格名 / price_cent（元↔分转换）/ stock_total / enabled / sort_no）
  - 富文本 `description_html` 复用 GZ-NEWS-003 已接入的编辑器（白名单同 §5），**不引新依赖**
  - 到货日：`delivery_date_text` 与 `delivery_date_exact` 二选一切换（业务层校验，doc/11 F6.1）
  - **走 ruoyi/Element Plus 默认审美**，i18n 走 `t('ord.product.xxx')` + zh_CN/en_US
- [ ] **AC 4**：SKU 库存乐观锁扣减服务方法 `IGzOrdSkuService.tryDeductStock(skuId, qty)`（**本 ticket 仅定义 + 单测，调用方 ORD-104 接入**），SQL **逐字照 doc/11 §6.2 扣减口径**：
  ```sql
  UPDATE gz_ord_sku SET stock_remain = stock_remain - ?, version = version + 1
  WHERE id = ? AND (stock_remain IS NULL OR stock_remain >= ?) AND version = ?
  ```
  - `stock_remain IS NULL`（无限库存）→ 条件成立但实际不应减成负，无限库存分支直接返回成功不动行（或扣后仍 NULL —— 实现保证无限库存永不耗尽）
  - 影响行数 = 1 → 成功；= 0 → 库存不足或并发冲突 → 业务层重试 ≤ 3 次后抛 `SKU_OUT_OF_STOCK`（doc/10 §7.E2）
- [ ] **AC 5**：截止下架 SnailJob executor `OrdProductDeadlineJob`（**SnailJob `@JobExecutor`，禁 Quartz / 禁 Flyway INSERT sys_job**）：
  - 薄壳 `@Component` + `@JobExecutor(name="ordProductDeadlineJob")`，业务逻辑下沉到可单测 service：`UPDATE gz_ord_product SET status='auto_off' WHERE status='on_shelf' AND deadline_time < NOW()`
  - 任务名 + CRON（建议 `0 0 * * * ?` 每小时）写进 reports + testing-human，**由人在 SnailJob 控制台注册**（不写迁移）
  - `ruoyi-gz-ord` 模块 pom 显式加 `ruoyi-common-job` 依赖（当前空脚手架无此依赖）
- [ ] **AC 6**：菜单注册（迁移文件，menu_id **9100 段**，CLAUDE.md §6 GZ-ORD admin 9100 段）：
  - 9100 预购商品管理（页面权限，perm `gz:ord:product:list`）
  - 9101 新增 `gz:ord:product:add` / 9102 编辑 `gz:ord:product:edit` / 9103 上下架 `gz:ord:product:changeStatus` / 9104 删除 `gz:ord:product:remove`（按钮权限）
  - 仅租户 1001 owner 角色授权（role-menu 映射）
- [ ] **AC 7**：单测覆盖 `tryDeductStock` ≥ 4 个测试方法（`mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-ord -am`）：
  - ① 有限库存正常扣减成功（影响行数 1，stock_remain 减、version +1）
  - ② 并发冲突（version 不匹配）→ 影响行数 0 → 返回 false / 重试
  - ③ 无限库存（stock_remain IS NULL）→ 成功且不耗尽
  - ④ 库存不足（stock_remain < qty）→ 影响行数 0 → 重试耗尽抛 `SKU_OUT_OF_STOCK`
  - ⑤（建议）截止下架 service 单测：`status='on_shelf' AND deadline_time<NOW()` → 转 `auto_off`，未到期不动
- [ ] **AC 8**：snapshot 字段清单 review（与 ORD-104 同步）—— 在 **doc/11 §6.3 `gz_ord_order`** 的 `product_snapshot_json` / `sku_snapshot_json` 字段段落确认/补全本表派生字段：商品名 `name` / 主图 `main_image_id`（**image_id 不存裸 url**）/ IP `ip_tag` / 到货日文案 / SKU `spec_name` / `price_cent`，至少 6 项；ORD-104 落单按此清单 `*_snapshot_json`（JSON 列，不散列）

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-ord/`（V1.0 空脚手架，本 ticket 从零落实体/CRUD/executor）
  - 包名 `org.dromara.gz.ord.{controller,service,mapper,domain,dto}`
  - `controller/GzOrdProductController.java`（路径 `/system/gz/ord/product`）
  - `service/IGzOrdProductService.java` + `impl/GzOrdProductServiceImpl.java`
  - `service/IGzOrdSkuService.java` + `impl/GzOrdSkuServiceImpl.java`（含 `tryDeductStock`）
  - `domain/GzOrdProduct.java` + `GzOrdSku.java`（`@TableLogic del_flag`，乐观锁 `@Version version`）+ `dto`（bo/vo，含嵌套 SkuVo）
  - `mapper/GzOrdProductMapper.java` + `GzOrdSkuMapper.java`
  - `job/OrdProductDeadlineJob.java`（SnailJob `@JobExecutor` 薄壳 → 下沉可单测 service）
  - `enums/OrdProductStatusEnum.java`（`on_shelf` / `off_shelf` / `auto_off`）
  - DDL × 1（两表一文件）+ menu seed × 1（9100 段）
  - pom 新增 `ruoyi-common-job` 依赖
- **Admin**：`code/main/plus-ui/src/views/gz-ord/product/index.vue`（+ 可选 edit.vue）+ `src/api/gz-ord/product.ts`，i18n zh_CN/en_US
- **小程序**：N/A（mp 列表/详情由 ORD-102/103 接入）
- **测试**：mvn 单测（tryDeductStock + 截止下架 service）+ admin 浏览器 CRUD 流程 + executor service 直调单测（不依赖 SnailJob 控制台）

> **纯后端 + admin ticket，无 mp 端 → 跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2 判定：Tech 段无 `miniapp/` 路径 + AC 无微信原生能力）。

## 备注

### 强约束（字段/命名铁律 — 违反直接打回）

1. **金额一律 `_cent`（分）** —— 用 `price_cent`，**禁 `price_fen` / `_fen`**
2. **图片用 `main_image_id` / `gallery_image_ids`（FK gz_file_object）** —— **禁存裸 url**（旧卡 `cover_img_url` / `banner_imgs` 写法已废）
3. **库存 `stock_total` / `stock_remain`** —— **禁 `stock_init` / `stock_left`**；NULL = 无限（不用 -1 / 999999）
4. **状态枚举 `on_shelf` / `off_shelf` / `auto_off`** —— **禁 `draft` / `on` / `off` / `archived` / `off_shelf`(旧) 4 态**；自动下架态名 `auto_off`，仅 cron 写入
5. **乐观锁 `version`** —— 扣减走 `UPDATE ... WHERE id=? AND version=?`，**禁 `SELECT FOR UPDATE` 行锁**
6. **`del_flag` 仅 2 值（0 正常 / 2 删除）** —— 对齐 ruoyi `@TableLogic`，**禁 3 值**；软删走 del_flag，不用 archived 状态表达删除
7. **截止下架走 SnailJob `@JobExecutor`** —— **禁 Quartz / 禁 Flyway INSERT sys_job（启动 hard-fail）**；任务名/CRON 由人在控制台注册
8. **menu_id 严格 9100 段** —— GZ-ORD admin 9100 段（CLAUDE.md §6）
9. **`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`** —— INSERT 不显式赋（走 `InjectionMetaObjectHandler` 自动填充）；UNIQUE 必含 tenant_id
10. **DDL 已应用不可改** —— 改 schema 一律新建更大时间戳文件
11. **admin CRUD 从零建** —— ADMIN-005 是 mp 5tab 改造，不是商品骨架；无骨架可复用，自己搭 ruoyi 标准 CRUD
12. **snapshot 字段清单写入 doc/11 §6.3** —— ORD-104 按此清单 INSERT `*_snapshot_json`（JSON 列不散列）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 商品 + SKU 两表（不合一） | 多规格刚需；单规格商品也用 SKU 表存（spec_name="标准款"），下单统一走 SKU 维度 |
| D2 | 乐观锁 `version`（不用行锁） | 预购并发 < 100 req/min，乐观锁足够；扭蛋高并发才需更强控制（D09 评估） |
| D3 | 到货日分 `delivery_date_text` + `delivery_date_exact` 两列 | 谷子预购到货日多模糊（"8 月下旬"），有精确日时也能放；二选一走业务层校验（doc/11 F6.1，DB 不约束） |
| D4 | 软删 `del_flag=2`（不用 archived 状态） | 已被订单引用的商品 snapshot 仍在订单上，商品记录软删不丢字段；删除语义统一走 ruoyi `@TableLogic` |
| D5 | `auto_off` 仅 cron 写、admin 不可手动设 | 自动下架与手动下架语义区分；admin 手动只在 `on_shelf` ↔ `off_shelf` 切换 |
| D6 | SnailJob 而非 Quartz | 仓库调度框架 = SnailJob（com.aizuda），无 sys_job 表；统一栈，executor 薄壳 + 可单测 service |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **gz-ord 是空脚手架（仅 HelloController），gz_ord_* 表全不存在** | **§0 自检 grep migration 目录确认上游表实际存在**（`ls db/migration/` + grep `gz_ord_` / `gz_file_object` / `gz_pay_`），不假设上游已建；本表从零落 |
| R2 | gz-ord pom 缺 `ruoyi-common-job` → executor 编译失败 | §0 自检确认 pom；新增依赖后先 `mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-ord -am` 再写 executor |
| R3 | SKU 删除时被订单引用 → 历史订单丢字段 | snapshot 已落 `gz_ord_order.*_snapshot_json`（ORD-104 协作）；本表 SKU 不物理删，改 `enabled=0` |
| R4 | 截止 cron 每小时粒度 → 边界 1 小时内仍可下单 | ORD-103/104 下单时再校验 `deadline_time`（双重防线）；本 ticket 仅负责自动转 `auto_off` |
| R5 | `description_html` 富文本 XSS | 复用 GZ-NEWS-003 编辑器白名单（同 §5），不引新依赖；mp 端渲染再 sanitize（ORD-103 负责） |
| R6 | mp 筛选标签字段（`ip_tag`）未建索引 → ORD-102 回退改 schema | DDL 含 `(tenant_id, ip_tag, status)` 索引；ORD-102 实施前 grep migration 确认字段存在 |

### 外部前置 / 协作

- 无外部前置（不涉真实支付 / 微信原生能力）。
- 与 ORD-104 协作点：snapshot 字段清单（AC 8），实施时同步 review，统一落 doc/11 §6.3。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D08/GZ-ORD-101 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
