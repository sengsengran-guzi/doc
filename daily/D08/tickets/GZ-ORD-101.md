# GZ-ORD-101 — 预购商品 + SKU 数据模型

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §关键字段 § PreorderProduct / 预购 SKU
**关联拆解**: doc/02-需求拆解.md §3.2 第 673-684 行
**关联 mockup**: design/mockup/admin-products.html + preorder-detail.html
**关联 ADR**: —
**依赖**: GZ-SYS-001 ✅（V1.0 已建 ruoyi-gz-ord 模块壳）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §6 V1.1 演进流 §6.3 预购商品上下架流（如无 → 本 ticket 实施前补写）
- **字段表**：doc/11-字段权威表.md
  - **§6.1 gz_ord_product 预购商品主表**（完整 DDL 来源）
  - **§6.2 gz_ord_sku 预购 SKU 表**（含 version 乐观锁字段定义）
  - §6.5 商品状态字段口径（draft / on / off / archived 4 态）
- **UI 参考**：admin `admin-products.html`（商品 CRUD 列表 + 表单）；mp `preorder-detail.html`（详情字段映射）

## What

建立预购业务核心数据模型 — 商品（gz_ord_product）+ 多规格 SKU（gz_ord_sku）两张表，admin 端 CRUD 完整接入 ruoyi 标准范式（复用 V1.0 ADMIN-005 商品管理骨架）：

1. 商品表字段：名称 / 主图 / 轮播图 JSON / 富文本描述 / IP 标签 / 作品系列标签 / 截止日 / 到货日精确（datetime）或模糊（VARCHAR 如"2026 年 9 月"）/ 上下架状态 / 创建运营 / 时间字段
2. SKU 表字段：所属商品 / 规格名（如"S 码红色"）/ 价格分 / 初始库存（NULL 表示无限）/ 当前剩余库存 / version 乐观锁 / 排序
3. admin CRUD 完整：列表 + 详情 + 新增 + 编辑 + 上下架 + 删除（软删）
4. **不写 mp UI**（mp 列表 / 详情由 ORD-102 / ORD-103 接入）

## AC（验收标准）

- [ ] **AC 1**：DDL `V<ts>__GZ-ORD-101-create-gz_ord_product-and-sku.sql` 落两张表（按 doc/11 §6.1 / §6.2）：
  - `gz_ord_product`：id / name VARCHAR(200) NOT NULL / cover_img_url / banner_imgs JSON（数组）/ description LONGTEXT（富文本）/ ip_tag VARCHAR(64) / series_tag VARCHAR(64) / deadline_at DATETIME NOT NULL / arrival_at DATETIME（精确）/ arrival_text VARCHAR(64)（模糊文案，如"2026 年 9 月"）/ status enum(`draft`/`on`/`off`/`archived`) DEFAULT 'draft' / creator_id / 公共字段 + tenant_id
  - 索引 `idx_status_deadline` `idx_ip_tag` `idx_series_tag`（mp 列表筛选用）
  - `gz_ord_sku`：id / product_id / spec_name VARCHAR(100) NOT NULL / price_fen INT NOT NULL / stock_init INT NULL（NULL 表无限） / stock_left INT NULL / version INT NOT NULL DEFAULT 0 / sort_order INT DEFAULT 0 / 公共字段 + tenant_id
  - 外键约束：sku.product_id 不加 FK（mybatis-plus 风格，应用层保证）
  - 索引 `idx_product`
- [ ] **AC 2**：admin 端商品 CRUD 接口（路径前缀 `/system/gz/ord/product`）：
  - `GET /list`（分页 + 按 status / ip_tag / series_tag / 名称模糊筛选 / 排序按 deadline_at / created_at）
  - `GET /{id}`（详情含 SKU 列表）
  - `POST /save`（新增 product + 子 SKU 列表，事务）
  - `PUT /update`（更新 product + SKU；SKU 增删走 diff 算法，已扣库存的 SKU 不允许删 — 软标记 stock_init=NULL 移出）
  - `PUT /status/{id}`（上下架，draft → on / on → off / off → archived）
  - `DELETE /{id}`（软删，UPDATE 为 archived；已有订单的商品不允许 archive）
- [ ] **AC 3**：admin 端 UI（`code/main/plus-ui/src/views/gz-ord/product/`）：
  - `index.vue`（列表页，复用 ADMIN-005 骨架的 BizTable + 搜索栏 + 操作列）
  - `edit.vue` 或 `<el-dialog>` 表单（含 SKU 子表 `<el-table>` 可编辑行）
  - **走 ruoyi/Element Plus 默认审美**（V1.1 视觉规范以 6/14 后为准，今日默认）
- [ ] **AC 4**：SKU 库存乐观锁服务方法 `IGzOrdSkuService.tryDeductStock(skuId, quantity)`：
  - 读 SKU → 如 stock_init IS NULL（无限）→ 直接返回 true，不更新 version
  - stock_left < quantity → 返回 false
  - `UPDATE gz_ord_sku SET stock_left = stock_left - ?, version = version + 1 WHERE id = ? AND version = ?` → affected = 1 返回 true，affected = 0（并发撞车）返回 false（业务层重试 ≤ 3 次或抛 SKU_OUT_OF_STOCK）
  - 本 ticket 仅定义方法 + 单测，调用方在 ORD-104 接入
- [ ] **AC 5**：cron `OrdProductDeadlineJob` 每小时跑：
  - `UPDATE gz_ord_product SET status='off' WHERE status='on' AND deadline_at < NOW()`（截止日已过自动下架）
- [ ] **AC 6**：菜单注册（CLAUDE.md §6 ORD 段 9000-9099）：
  - 9001 预购商品管理（一级 ORD 业务菜单 9000 下）
  - 9002 商品列表（页面权限）+ 9003 新增 / 9004 编辑 / 9005 上下架 / 9006 删除（按钮权限）
- [ ] **AC 7**：单测覆盖：
  - 乐观锁正常扣减
  - 并发撞车（version 不匹配）
  - 无限库存跳过 version
  - 库存不足返回 false
  - 共 ≥ 4 个测试方法
- [ ] **AC 8**：商品 + SKU snapshot 字段清单 ⭐（与 ORD-104 同步 review）：商品名 / 主图 url / SKU 规格名 / 单价分 / 数量 — 至少这 5 个；本 ticket 在 doc/11 §6.3 gz_ord_order snapshot 字段段落确认 / 补写

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`（V1.0 已建模块壳）
  - `controller/admin/GzOrdProductController.java`（路径 `/system/gz/ord/product`）
  - `service/IGzOrdProductService.java` + `impl/GzOrdProductServiceImpl.java`
  - `service/IGzOrdSkuService.java` + `impl/GzOrdSkuServiceImpl.java`（含 tryDeductStock 方法）
  - `domain/GzOrdProduct.java` + `GzOrdSku.java` + req/vo（含嵌套 SkuVO）
  - `mapper/GzOrdProductMapper.java` + `GzOrdSkuMapper.java`
  - `job/OrdProductDeadlineJob.java`（Quartz cron `0 0 * * * ?` 每小时）
  - `enums/OrdProductStatusEnum.java`
  - DDL × 1（两表一文件）
  - menu_id 段：9001-9006（CLAUDE.md §6 强约束）
- **Admin 前端**：`code/main/plus-ui/src/views/gz-ord/product/`
  - `index.vue` + `edit.vue`
  - `src/api/gz-ord/product.ts`
- **小程序**：N/A
- **测试**：mvn 单测 + admin 端浏览器 CRUD 流程 + cron 手动触发测试

## 备注

### 强约束

1. **stock_init = NULL 表示无限库存**（doc/11 §6.2 锚定）— 不允许用 -1 或 999999 表示
2. **version 字段乐观锁** — 不允许用 `SELECT FOR UPDATE` 行锁（预购并发不高，乐观锁性能更好）
3. **menu_id 严格 9001-9006**（CLAUDE.md §6 ORD 段 9000-9099）
4. **截止日自动下架 cron** — 不允许业务上线后期发现没下架靠运营手工干
5. **snapshot 字段清单写入 doc/11 §6.3** — ORD-104 实施时按此清单 INSERT
6. **i18n**：admin 文案走 `t('ord.product.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 商品 + SKU 两表（不合一） | 多规格刚需；单 SKU 商品也用 SKU 表存（规格名"默认"） |
| D2 | 乐观锁 version 字段 | V1.1 并发预计 < 100 req/min，乐观锁充分；扭蛋 GACHA 高并发场景才需要悲观锁 |
| D3 | arrival 字段分精确 datetime + 模糊 VARCHAR 两列 | 谷子预购到货日多数模糊（"2026 年 9 月"），但有精确日期需求时也能放（一列存一种） |
| D4 | 软删 archived 状态 | 已有订单的商品不能硬删（订单 snapshot 仍需展示原图） |
| D5 | cron 而非 trigger 触发自动下架 | ruoyi 已用 Quartz，统一栈；trigger 调试困难 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | SKU 删除时如有订单引用 → snapshot 已落 gz_ord_order 故订单不丢字段 | snapshot 字段保证（ORD-101 + ORD-104 协作） |
| R2 | 商品 archived 后 mp 列表仍可能误显示 | ORD-102 mp 列表强校验 status='on' |
| R3 | 截止日 cron 每小时粒度 → 边界 1 小时内仍可下单 | ORD-103 提交时再校验 deadline_at；双重防线 |
| R4 | banner_imgs JSON 字段查询性能 | 仅做展示用，不做 JSON 函数查询；性能无虞 |
| R5 | rich text description XSS | admin 端富文本编辑器（wangEditor）默认 XSS 过滤；mp 端渲染时再 sanitize |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
