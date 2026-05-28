# GZ-ADMIN-101 — 预购商品管理 CRUD

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M7.1 商品管理
**关联拆解**: doc/02-需求拆解.md §3.5 第 907-917 行
**关联 mockup**: design/mockup/admin-products.html ⚠️ V1.0/V1.1 设计冻结期：admin 走 ruoyi 默认 + plus-ui BizTable / Element Plus 默认组件，**不参考 mockup 视觉**；mockup 仅作页面结构 / 功能项参考
**关联 ADR**: —
**依赖**: GZ-ORD-101 ✅(D08/D09 — 商品 + SKU schema 已落)

---

## 必读权威文档（缺一不可）

- **业务流**：doc/10-业务流权威图.md **§7 预定货品全流程** §业务规则 + §关键节点 N1（admin 新建商品）
- **字段表**：doc/11-字段权威表.md **§6.1 `gz_ord_product` 预购商品**（完整字段 + DDL 已在 D08/D09 落地）+ **§6.2 `gz_ord_sku` 商品 SKU**（多 SKU 表结构）+ §10.2 sys_dict_data §IP 字典 / 状态字典
- **UI 参考**（设计冻结期）：doc/12 §AD-ORD-PRODUCTS §页面结构（列表 toolbar / 表格列 / 新建编辑抽屉）+ §组件映射（el-table / el-drawer）

## What

admin 端预购商品 CRUD：列表（按 IP / 状态筛 + 搜索） / 新建 / 编辑 / 上下架开关 / 批量上下架 / 多 SKU 管理 / 富文本商品描述（复用 GZ-NEWS-003 编辑器）。后端复用 D08/D09 已建的 `IGzOrdProductService`（如 D09 已建则本 ticket 不需后端，只补 admin perm + UI；如未建则补 admin 视角的 CRUD）。

## AC（验收标准）

- [ ] **AC 1**：admin 端 plus-ui 页 `views/gz-ord/product/index.vue`（菜单路径 `/ord/product`）使用 plus-ui BizTable + Element Plus 默认风格
- [ ] **AC 2**：列表 toolbar：搜索框（按商品名 / SKU 名） + IP 筛 select（按字典 `gz_product_ip`） + 状态筛 select（上架 / 下架） + 时间范围 picker + "新建商品" 绿按钮 + 批量操作 dropdown（批量上架 / 批量下架）
- [ ] **AC 3**：列表表格列：勾选 / thumb（封面缩略） / 商品名 / IP 标签 / SKU 数 / 截止日（带 countdown 倒计时显示）/ 到货日 / 销量 / 状态 switch（点击切换上下架）/ 操作（编辑 / 详情 / 删除软删）
- [ ] **AC 4**：新建 / 编辑 抽屉（el-drawer）：
  - 商品基本信息：商品名 / IP（select 字典）/ 封面图（GZ-SYS-005 OSS 上传）/ 截止日（datetime-picker） / 到货日（datetime-picker） / 排序 number
  - 多 SKU 嵌套表格（el-table 内嵌）：规格名 input / 价格 input number / 库存 input number / 删除按钮 / "+ 添加 SKU"
  - 富文本商品描述编辑器（**复用 GZ-NEWS-003 富文本编辑器组件**，已在 D07/D08 落 wangeditor 或 tinymce + sanitize-html）
  - 上下架开关 switch
  - 表单校验：商品名必填 / 至少 1 个 SKU / SKU 价格 > 0 / 库存 ≥ 0 / 截止日 < 到货日
- [ ] **AC 5**：admin perm 接入 sa-token-staff：list `gz:ord:product:list` / add `gz:ord:product:add` / edit `gz:ord:product:edit` / remove `gz:ord:product:remove`；菜单插入 `sys_menu` menu_id 段 **9100-9199**（CLAUDE.md §6 #6 GZ-ORD admin 段）
- [ ] **AC 6**：批量上下架：勾选多行 → toolbar "批量上架" → 后端 `POST /system/gz/ord/product/batch-online` body=`{ids: [...]}` → UPDATE status；下架同理
- [ ] **AC 7**：i18n 全覆盖（zh_CN/en_US `gz-ord.product.*`）；默认 zh-CN
- [ ] **AC 8**：单测 `GzOrdProductServiceImplTest` happy（add / edit / batchOnline 各 1）
- [ ] **AC 9**：DDL 已在 D08/D09 落，本 ticket 不再写 DDL；如需要 menu / dict 落地 → 新 SQL `V<时间戳>__GZ-ADMIN-101-menu.sql`

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-ord/`
  - `controller/GzOrdProductController.java`（admin 路径 `/system/gz/ord/product`，新建或在 D08/D09 基础上补 admin CRUD）
  - `service/IGzOrdProductService.java` + impl：list / getInfo / insertByBo / updateByBo / removeByIds / batchOnline / batchOffline
  - `service/IGzOrdSkuService.java` + impl：嵌套 SKU 增删改（与 product 同事务）
  - `domain/bo/GzOrdProductBo.java` + `domain/vo/GzOrdProductVO.java`（含 skuList）
  - menu SQL：`ruoyi-admin/src/main/resources/db/migration/V<时间戳>__GZ-ADMIN-101-menu.sql`（menu_id 9100-9120 段）
- **Admin**：`code/main/plus-ui/src/`
  - `views/gz-ord/product/index.vue`（列表）
  - `views/gz-ord/product/components/ProductDrawer.vue`（新建 / 编辑抽屉）
  - `views/gz-ord/product/components/SkuTable.vue`（多 SKU 嵌套表）
  - `api/gz-ord/product.ts`（封装 list / getInfo / add / edit / remove / batchOnline / batchOffline）
  - `lang/zh_CN/gz-ord.ts` + `en_US/gz-ord.ts`（i18n keys）
- **小程序**：不动（本 ticket admin-only）
- **测试**：单测 + admin 端走一遍新建 → 编辑 → 批量上架 → 删除

## 备注

### 强约束

1. **设计冻结期：admin 走 ruoyi/Element Plus 默认审美 + plus-ui BizTable**，不调样式不引用 mockup 像素；可用 el-table / el-drawer / el-form 默认组件
2. **富文本编辑器复用 GZ-NEWS-003**（D07/D08 已建）：不重新引入新依赖（CLAUDE.md §6 #8）；编辑器渲染 + sanitize-html 走 NEWS-003 同一套
3. **多 SKU 嵌套保存事务一致**：service 层 `@Transactional` 包裹 product UPDATE + sku 批量 INSERT/UPDATE/DELETE；防部分成功
4. **menu_id 9100-9199 段**（CLAUDE.md §6 #6 GZ-ORD admin）：插入前 `SELECT MAX(menu_id) FROM sys_menu WHERE menu_id BETWEEN 9100 AND 9199` 确认
5. **UNIQUE 必含 tenant_id**（CLAUDE.md §6 #3）：商品名 UNIQUE 应是 `(tenant_id, name)`；D08/D09 应已落
6. **包名 `org.dromara.gz.ord.*`**（CLAUDE.md §6 #4）

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | SKU 嵌套保存 vs 独立接口 | 用户视角 product + sku 是一体；嵌套保存简化前端逻辑 + 事务保护 |
| D2 | 批量上下架走单独接口 | 减少 N 次 API 往返；后端单 UPDATE WHERE id IN(...) 一次完成 |
| D3 | countdown 倒计时前端 reactive 计算 | 不在后端 SQL 算时间差；前端按 deadline - now() 显示 |
| D4 | 富文本字段类型 LONGTEXT | 商品描述可能含图片 base64 / 长 HTML；TEXT(64K)不够 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | D08/D09 product / sku schema 字段名不一致 doc/11 §6.1/6.2 | §0 自检：`DESC gz_ord_product` + `DESC gz_ord_sku` 字段对齐 doc/11；缺则回 D08/D09 修 |
| R2 | 富文本嵌入外站链接 / XSS | 复用 NEWS-003 sanitize-html 配置；不重新引入 |
| R3 | SKU 删除时已有订单 → 数据完整性 | 软删（del_flag）；不允许硬删；订单 snapshot 已冻结字段保留历史 |
| R4 | 批量上架时部分商品 SKU 不全 / 库存 0 / 已过截止日 → 业务规则限制 | 后端校验：批量上架前过滤掉不满足条件的，返回 `{success: [...], skipped: [{id, reason}]}` |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
