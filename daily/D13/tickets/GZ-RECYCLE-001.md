# GZ-RECYCLE-001 — 回收价目表 + 时长规则（admin）

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md 回收域
**关联拆解**: doc/02-需求拆解.md GZ-RECYCLE-001
**关联 mockup**: N/A（admin 走 ruoyi 默认，不引 mockup）
**关联 ADR**: 无（价目表 + 区间校验权威 = doc/11 §12.1）
**依赖**: GZ-ADMIN-001 / GZ-SYS-005（字典基础设施，已就绪）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §13（回收估价口径）
- **字段表**：doc/11-字段权威表.md §12.1（`gz_recycle_price_rule`）+ 附录 A.21（回收品类字典）
- **UI 参考**：N/A（admin 走 ruoyi 默认）

## What

新建 `ruoyi-gz-recycle` 模块 + `gz_recycle_price_rule` 价目表（品类 × 数量区间 → 单价 + 时长）+ admin 价目表配置页 + 区间不重叠校验 + 字典 `gz_recycle_category`。本卡仅地基（估价计算 + mp 填单在 D14 RECYCLE-002）。

## AC（验收标准）

- [ ] **AC1 价目表（doc/11 §12.1）**：`gz_recycle_price_rule`（`category`(字典 gz_recycle_category)/`qty_min`/`qty_max`(NULL=无上界)/`unit_price_cent`/`duration_minutes`(按数量匹配时长)/`enabled`/`sort_no` + 审计列）；**UNIQUE(tenant_id, category, qty_min)**；金额 `_cent`；`tenant_id` DEFAULT '1001' 自动填充；`del_flag` 2 值。
- [ ] **AC2 区间不重叠校验（doc/11 §12.1 末段）**：同一 `category` 下各 `[qty_min, qty_max]` 区间**不得重叠**（**业务层校验**，admin 保存时 assert 拦截；**DB 不加复杂 CHECK**，跨 MySQL 版本兼容差）。reports 必含「重叠区间 admin 保存被拦截」raw output。
- [ ] **AC3 估价命中唯一区间**：`qty_min <= qty AND (qty_max IS NULL OR qty <= qty_max)` 命中唯一；命中 0 → 提示「无报价规则」；命中多（配置错） → 提示「配置有误」。本卡提供命中 service（D14 RECYCLE-002 mp 填单消费）。
- [ ] **AC4 字典 `gz_recycle_category`**：二次元周边品类（甲方维护可扩展）；seed 若干 demo 品类。
- [ ] **AC5 admin 价目表 CRUD 页**：plus-ui `views/gz-recycle/price-rule/index.vue`（ruoyi/Element Plus 默认，BizTable，**不引 mockup/不调样式**）；列表 + 查询 + 新增/编辑弹窗（元↔分换算）+ 启用/停用；menu 挂 **13000 目录 / 13001 价目表**。
- [ ] **AC6 单测**：区间不重叠校验（重叠拒绝 / 相邻不重叠通过 / qty_max NULL 无上界）+ 估价命中（命中唯一 / 命中 0 / 命中多）。

## Tech（端 + 范围）

- **后端领地**（新建模块，独占）：`ruoyi-modules/ruoyi-gz-recycle/`（包名 `org.dromara.gz.recycle.*`，**仿 gz-coupon 31 文件分层**：entity/bo/vo/mapper/service(+impl)/internal/controller）。
  - **父 pom 注册**：`ruoyi-modules/pom.xml` 加 `<module>ruoyi-gz-recycle</module>`（现注册到 coupon）+ `ruoyi-admin/pom.xml` 加 ruoyi-gz-recycle 依赖块。
  - 依赖：仅 `ruoyi-gz-common`（传递 mybatis/web/tenant/security）+ spring-boot-starter-test。无新第三方依赖。
- **Admin**：`code/main/plus-ui/src/views/gz-recycle/price-rule/index.vue` + `api/gz-recycle/priceRule.ts`（id 全 string）+ i18n block `gzRecyclePriceRule`。
- **DDL**：时间戳 `V202606210200`+（price_rule 表）/ `V202606210201`+（dict + 13000 menu seed）。**dict_id 用 9240-9245 / dict_code 9241-9246**（避开 COUPON 9220-9236 + PAY-105 并行用 9250+）。migration 用 raw SQL 验证不污染 flyway_schema_history。

## 备注（并行批次纪律 ⭐）

- **本卡与 COUPON-002 / PAY-105 第一波并行**。你独占新建 gz-recycle + 父pom/admin pom（仅你改）+ admin gz-recycle；不碰 gz-common/gz-bean/gz-coupon 源码。
- **编译/单测**：新模块首次解析 reactor 依赖若报缺 gz-common，先确认 .m2 已有 gz-common 稳定 jar（D12 已装）→ `mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-recycle`（gz-common 走 .m2）。**不要 `mvn install`**（留主线程统一）。
- **plus-ui i18n 单文件 append**（`src/lang/zh_CN.ts`+`en_US.ts`）：PAY-105 并行也 append。**append `gzRecyclePriceRule` block 前重读文件实际尾部**，Edit 锚定你新增 block 紧邻的稳定上文；若 Edit 失配 = 并行已改，重读再 append，**不覆盖他人 block**。
- 跨层契约：金额 `_cent` / id 全 string / UNIQUE 含 tenant_id + del_flag / 不写 `any`。
- **不要 spawn kevin-qa**（子不能 spawn 孙；Tier 1B 主线程统一派）。写完 reports（含 §AI 测试段占位）即返回。

---

## §revision（Kevin 批量人验后填，初始空）
