# GZ-ADMIN-101 — 预购商品 + SKU 管理 CRUD（plus-ui，从零建）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M3 §商品管理
**关联拆解**: doc/02-需求拆解.md §3.5 GZ-ORD / GZ-ADMIN-101 预购商品管理
**关联 mockup**: design/mockup/admin-products.html ⚠️ admin 走 ruoyi/Element Plus 默认审美（**不套用 C 系统**）+ plus-ui BizTable / Element Plus 默认组件，**不参考 mockup 视觉**；mockup 仅作页面结构 / 功能项参考
**关联 ADR**: —
**依赖**: GZ-ORD-101（D08 — `gz_ord_product` + `gz_ord_sku` schema 已落地）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§7 预定货品全流程** §业务规则（截止日 / 到货时间 / 库存 SKU 级可选）+ §关键节点 N1（admin 配置商品 + SKU 是预购流入口数据）+ §异常分支 E3（商品下架拦截下单）
- **字段表**：doc/11-字段权威表.md **§6.1 `gz_ord_product` 预购商品**（完整字段 + 索引）+ **§6.2 `gz_ord_sku` 商品 SKU**（多 SKU 表结构 + `stock_total` / `stock_remain` / 乐观锁 `version`）+ §10.2 sys_dict_data §`gz_ord_product_status`（`on_shelf` / `off_shelf` / `auto_off`）
- **UI 参考**（设计冻结期 admin 走 ruoyi 默认）：`N/A（admin 走 ruoyi/Element Plus 默认审美）`；功能项可参考 doc/12 §AD-ORD-PRODUCTS 页面结构（列表 toolbar / 表格列 / 新建编辑抽屉），不取像素

## What

plus-ui admin 端从零建预购商品 + SKU 管理：列表（按 IP / 状态筛 + 搜索 + 分页）/ 新建 / 编辑 / 软删 / 上下架开关 / 批量上下架 / 多 SKU 嵌套增删改（同事务）/ 富文本商品描述（复用 GZ-NEWS-003 编辑器）/ 主图 + 画廊图上传（image_id）/ EasyExcel 导入导出。后端在 `ruoyi-gz-ord` 模块从零写 admin 视角 CRUD（不复用 ADMIN-005）。

## AC（验收标准）

- [ ] **AC 1**：plus-ui 页 `views/gz-ord/product/index.vue`（菜单路径 `/gz-ord/product`），用 plus-ui BizTable + Element Plus 默认风格；列表分页，按 `(tenant_id, status, deadline_time)` 默认排序，tenant_id 固定 1001（走自动填充，前端不传）。
- [ ] **AC 2**：列表 toolbar — 搜索框（按商品名 `name`）+ IP 筛 select（按 `ip_tag`）+ 状态筛 select（`on_shelf` / `off_shelf` / `auto_off` 三态，走字典 `gz_ord_product_status`）+ 截止日范围 picker（按 `deadline_time`）+「新建商品」按钮 + 批量操作 dropdown（批量上架 / 批量下架）+「导入」/「导出」按钮。
- [ ] **AC 3**：列表表格列 — 勾选 / 主图缩略（`main_image_id` 解析签名 URL，FK `gz_file_object`）/ 商品名 / IP 标签 / SKU 数 / 截止日 `deadline_time` / 到货（`delivery_date_exact` 或 `delivery_date_text`）/ 销量 `sales_count` / 状态列（el-switch 切 `on_shelf` ⇄ `off_shelf`，`auto_off` 态展示为禁用 switch + tag）/ 操作（编辑 / 删除软删）。
- [ ] **AC 4**：新建 / 编辑抽屉（el-drawer）商品基本信息表单 —
  - 商品名 `name`（必填）/ IP `ip_tag`（select 字典）/ 主图 `main_image_id`（GZ-SYS-005 OSS 上传，存 image_id 非裸 url）/ 画廊图 `gallery_image_ids`（多图，逗号分隔 file_object.id）/ 截止日 `deadline_time`（datetime-picker，必填）/ 到货日（`delivery_date_exact` 日期 或 `delivery_date_text` 模糊文案，二选一）/ 排序 `sort_no`（number）
  - 富文本商品描述 `description_html`（**复用 GZ-NEWS-003 富文本编辑器组件 + sanitize-html 白名单**，不新引依赖）
- [ ] **AC 5**：抽屉内多 SKU 嵌套表格（el-table 内嵌）— 规格名 `spec_name`（必填）/ 单价 `price_cent`（前端元 → 分换算，input number）/ 总库存 `stock_total`（input number，空 = 无限）/ 启用 `enabled`（switch）/ 排序 `sort_no` / 删除按钮 + 「+ 添加 SKU」。保存时 product + SKU 在**同一后端事务**内增删改（service `@Transactional` 包裹）。
- [ ] **AC 6**：表单校验 — 商品名必填 / 至少 1 个 SKU / SKU 单价 > 0 / `stock_total` ≥ 0（或空）/ 截止日必填且早于到货日（若填精确到货日）；后端 Bo 校验兜底（`@NotBlank` / `@Min`）。
- [ ] **AC 7**：批量上下架 — 勾选多行 →「批量上架」→ `PUT /gz/ord/product/status` body `{ids:[...], status:'on_shelf'}` → 一次 `UPDATE ... WHERE id IN(...) AND tenant_id=1001`；`auto_off` 态不可被批量上架覆盖（后端过滤），返回 `{success:[...], skipped:[{id,reason}]}`。下架同理（target `off_shelf`）。
- [ ] **AC 8**：EasyExcel 导入导出 — 导出当前筛选结果（商品名 / IP / 截止日 / 到货 / SKU 规格价格库存 平铺）；导入按模板批量建商品 + SKU（事务，行级校验失败汇总返回，不部分提交）。
- [ ] **AC 9**：del_flag 软删 — 删除走 `@TableLogic`（`del_flag` 仅 0/2，2=删除）；不硬删（保留订单 snapshot 历史完整性，doc/10 §7.E3 / E4）。
- [ ] **AC 10**：admin perm 走 ruoyi RBAC `@SaCheckPermission` — list `gz:ord:product:list` / add `gz:ord:product:add` / edit `gz:ord:product:edit` / remove `gz:ord:product:remove` / status `gz:ord:product:status` / import `gz:ord:product:import` / export `gz:ord:product:export`；菜单 seed 落 **menu_id 9100 段**（9100-9199，GZ-ORD admin 段），仅 owner(100) 授权。
- [ ] **AC 11**：i18n 全覆盖（`zh_CN/gz-ord.ts` + `en_US/gz-ord.ts`，key `gz-ord.product.*`）；默认 zh-CN，不混 emoji。
- [ ] **AC 12**：单测 `GzOrdProductServiceImplTest` happy path（`insertByBo` 含 SKU 嵌套 / `updateByBo` 改 SKU 增删 / `batchUpdateStatus` 过滤 auto_off 各 1 个，≥ 60% 覆盖核心）。

> 纯 admin ticket，**跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2 — Tech 段无 `miniapp/` 路径 + AC 无微信原生能力 → 不进人验列，AI Tier 1A + 1B 全 ✅ 即终态）。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`（包名 `org.dromara.gz.ord.*`）
  - `controller/GzOrdProductController.java`：admin 路径 `/gz/ord/product`（list / getInfo / add / edit / remove / status 批量 / import / export），每端点挂 `@SaCheckPermission`
  - `service/IGzOrdProductService.java` + `impl`：`queryPageList` / `queryById`（含 skuList）/ `insertByBo`（product + SKU 同事务）/ `updateByBo`（SKU 增删改 diff）/ `removeByIds`（软删）/ `batchUpdateStatus`（过滤 auto_off，返回 success/skipped）/ `importData` / `exportList`
  - `service/IGzOrdSkuService.java` + `impl`：SKU 嵌套增删改（被 product service 在同事务内调用，不单独暴露 CRUD 端点）
  - `domain/GzOrdProduct.java` + `GzOrdSku.java`（entity，`@TableLogic del_flag`，`@Version version`）
  - `domain/bo/GzOrdProductBo.java`（含 `List<GzOrdSkuBo> skuList`）+ `domain/vo/GzOrdProductVo.java`（含 skuList + 主图签名 URL）
  - `domain/excel/GzOrdProductImportVo.java` / `GzOrdProductExportVo.java`（EasyExcel）
  - DDL（仅 menu + dict seed，**商品/SKU 表 DDL 已由 GZ-ORD-101 落地，本卡不重建表**）：`ruoyi-admin/src/main/resources/db/migration/V202606061000__GZ-ADMIN-101-product-menu.sql`（menu_id 9100-9199 段 + 7 个 perm + dict `gz_ord_product_status` 三值 + owner 100 授权）
  - **模块 pom 无新增依赖**（用 ruoyi 已有 EasyExcel / sa-token / mybatis-plus；富文本 sanitize 复用 GZ-NEWS-003 同一套）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-ord/product/index.vue`（列表 + toolbar + 批量 + 导入导出）
  - `views/gz-ord/product/components/ProductDrawer.vue`（新建 / 编辑抽屉 + 富文本 + 图片上传）
  - `views/gz-ord/product/components/SkuTable.vue`（多 SKU 嵌套表）
  - `api/gz-ord/product.ts`（list / getInfo / add / edit / remove / batchStatus / import / export）
  - `lang/zh_CN/gz-ord.ts` + `en_US/gz-ord.ts`
- **小程序**：不动（本 ticket admin-only）
- **测试**：单测（AC 12）+ kevin-qa Playwright E2E（登录 owner → 新建商品 + 2 SKU → 编辑改 SKU → 批量上架 → 导出 → 软删）

## 备注

### 强约束（每条复核）

1. **从零建，不复用 ADMIN-005**（ADMIN-005 不存在 / 非本域）。`ruoyi-gz-ord` 截至本日是空脚手架（1 个 HelloController），admin CRUD 从零写。
2. **admin 走 ruoyi/Element Plus 默认审美** + plus-ui BizTable + EasyExcel，**不引用 mockup 像素**，不调样式（admin 不评判视觉）。可用 el-table / el-drawer / el-form 默认组件。
3. **富文本编辑器复用 GZ-NEWS-003**（D07 已建）：渲染 + sanitize-html 白名单同 §5 资讯一套，**不重新引入新依赖**（CLAUDE.md §6 #8）。
4. **多 SKU 嵌套保存事务一致**：service `@Transactional` 包裹 product UPSERT + SKU 批量 INSERT/UPDATE/软删；防部分成功。
5. **库存字段 `stock_total` / `stock_remain`**（不用 init/left）；乐观锁 `version`（改价 / 改状态 / 库存扣减防并发）。admin 端只配 `stock_total`，`stock_remain` 由下单流（GZ-ORD-104）扣减，本卡新建时 `stock_remain = stock_total`。
6. **状态枚举三值 `on_shelf` / `off_shelf` / `auto_off`**（不用 off_shelf/archived 之外的值）；`auto_off`=截止日到自动下架，admin 不可手动设、不可被批量上架覆盖。
7. **金额 `price_cent`（分）**，不用 `_fen`；前端元 ↔ 分换算在 UI 层，DB 存分。
8. **图片走 `main_image_id` / `gallery_image_ids`（FK gz_file_object）**，不存裸 url；列表 / 详情按 file_object.id 换签名 URL。
9. **`del_flag` 仅 2 值（0/2）** 对齐 ruoyi `@TableLogic`，软删不硬删（doc/10 §7.E3 订单 snapshot 历史保留）。
10. **`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`**；INSERT 不显式赋 tenant_id（走 `InjectionMetaObjectHandler` 自动填充）；UNIQUE 必含 tenant_id（`product_no` / `sku_no` 已在 GZ-ORD-101 落 `(tenant_id, *_no)`）。
11. **包名 `org.dromara.gz.ord.{controller,service,mapper,domain,dto}`**（CLAUDE.md §6 #4）。
12. **menu_id 9100 段**（本卡定制 + CLAUDE.md §6）：seed 前 `SELECT MAX(menu_id) FROM sys_menu WHERE menu_id BETWEEN 9100 AND 9199` 确认不冲突。
13. **编号格式**：商品 `product_no = PRD-yyyyMMdd-6位序号`，SKU `sku_no = SKU-yyyyMMdd-6位序号`（doc/11 §6.1/6.2 — 这是商品主数据编号，**区别于**订单号 `PREORD-`，勿混）。

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | SKU 嵌套保存 vs 独立 CRUD 端点 | 用户视角 product + SKU 是一体；嵌套保存简化前端 + 事务保护，SKU 不单独暴露端点 |
| D2 | 批量上下架走单独端点（`PUT /status`）| 减少 N 次 API 往返；后端单 `UPDATE ... WHERE id IN(...)` 一次完成 |
| D3 | 截止日倒计时 admin 不算 | admin 只显示 `deadline_time` 原值，不做 reactive countdown（那是 mp 端 GZ-ORD-102 的事）|
| D4 | `description_html` 列 MEDIUMTEXT | 商品描述含长 HTML / 图片引用；doc/11 §6.1 已定 MEDIUMTEXT |
| D5 | import 行级校验全失败回滚 | 不部分提交，避免半套数据；失败汇总行号 + 原因返回 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | **上游表未落地**（GZ-ORD-101 是 D08，`gz_ord_product` / `gz_ord_sku` 可能尚未建）| **§0 自检 grep migration 目录确认上游表实际存在**：`ls .../db/migration/ \| grep GZ-ORD-101` + `grep -rl 'gz_ord_product\|gz_ord_sku' .../db/migration/`；缺 → STOP 报 Kevin，本卡不开工（V1.1 从零起，不假设上游已 merge）|
| R2 | product/SKU schema 字段名偏离 doc/11 §6.1/6.2 | §0 自检 `DESC gz_ord_product` + `DESC gz_ord_sku` 逐字段对齐 doc/11；缺则回 GZ-ORD-101 修源头，不在本卡 patch |
| R3 | 富文本嵌外站链接 / XSS | 复用 GZ-NEWS-003 sanitize-html 白名单，不重新配置 |
| R4 | SKU 删除时已有订单引用 | SKU 软删（`del_flag`），不硬删；订单 `sku_snapshot_json` 已冻结历史，删 SKU 不影响旧单 |
| R5 | 批量上架含未配 SKU / 已过截止日商品 | 后端过滤不满足条件项（无 SKU / `deadline_time < NOW`），返回 `skipped` 列表，前端提示哪些被跳过 |
| R6 | menu_id 段误用 doc/11 §10.3 的 9001（GZ-ORD 业务表段）| 本卡 admin 菜单用 **9100 段**（本批次定制）；9000-9099 是业务表预留段，admin 菜单挪到 9100 段避免与 ORD-101~104 业务菜单冲突 |

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D10/GZ-ADMIN-101 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。
-->
