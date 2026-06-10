# GZ-COUPON-001 — 券模板 + 用户券 + 发放策略 SPI（manual 实现 + 预留 register_window/event）+ admin 批量发放

**优先级**: P1
**复杂度**: M
**关联 PRD**: doc/02-prd.md M9 §优惠券（V1.2 代金券，仅拼豆抵扣）
**关联拆解**: doc/02-需求拆解.md §优惠券域 GZ-COUPON-001（券地基 + 发放策略 SPI）
**关联 mockup**: N/A（admin 走 ruoyi/Element Plus 默认审美，不取像素；mp 我的券/选券 = D13 GZ-COUPON-003）
**关联 ADR**: 无（发放策略 SPI 设计权威 = doc/11 §11.1.a，不另立 ADR）
**依赖**: GZ-SYS-003（`gz_user` 用户表，发券对象）+ GZ-ADMIN-001（admin RBAC + owner 角色）

---

## 必读权威文档（缺一不可 — §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§12 优惠券流（M9，代金券 V1.2，仅拼豆抵扣）**
- **字段表**：doc/11-字段权威表.md **§11.1 `gz_coupon_template`（券模板逐字段）** + **§11.1.a 发放策略 SPI（ICouponIssuanceStrategy + manual/register_window/event）** + **§11.2 `gz_user_coupon`（用户券 + 券态机）** + **§11.3 抵扣 + GMV 口径** + **§11.4 待澄清（F11.4 manual 选用户 / F11.5 策略 V1.2 落地边界）** + 附录 **A.17（券态）** / **A.18（模板态）** / **A.19（折扣类型）** / **A.22（发放策略）**
- **UI 参考**（设计冻结期 admin 走 ruoyi 默认）：`N/A（admin 走 ruoyi/Element Plus 默认审美，不取像素）`

## What

新建独立优惠券域模块 `ruoyi-gz-coupon`（包名 `org.dromara.gz.coupon.*`），落地代金券地基：`gz_coupon_template`（券模板）+ `gz_user_coupon`（用户券）两表 + 发放策略 SPI（`ICouponIssuanceStrategy`）+ admin 模板 CRUD + admin 批量发放页。**V1.2 仅实现 `ManualIssuanceStrategy`**（admin 选用户 / 上传名单 → 每用户生成一张 unused 券，发放事务内乐观锁校验 `issued_count + N <= total_quota`）；**预留** `RegisterWindowStrategy` + `EventIssuanceStrategy`（留接口可编译 + `CouponIssuanceEvent` 事件发布/监听骨架，含 D14 回收完成发券钩子位）。本卡**只建表 + 发放**，券抵扣/锁定/核销/过期/回滚逻辑 = D13 GZ-COUPON-002（依赖 BEAN-014 下单事务）。

## AC（验收标准）

- [ ] **AC 1 — 建表迁移**：新迁移 `V<时间戳 > 202606190631>__GZ-COUPON-001-create-coupon-tables.sql` 建 `gz_coupon_template` + `gz_user_coupon`，字段/索引严格对齐 doc/11 §11.1 / §11.2：
  - `gz_coupon_template`：`template_no`(`CPN-`, UNIQUE(tenant_id,template_no)) / `name` / `discount_type`(`cash` V1.2 唯一) / `amount_cent` / `applicable_business`(`pindou`) / `valid_days`(默认 30) / `total_quota`(NULL=不限) / `issued_count`(默认 0) / `issue_strategy`(`manual` 默认) / `issue_config_json`(JSON NULL) / `status`(`active`) / `version`(乐观锁) + 公共字段 + IDX `(tenant_id,status,applicable_business)`/`(tenant_id,discount_type)`/`(tenant_id,issue_strategy)`
  - `gz_user_coupon`：`coupon_no`(`UC-`, UNIQUE) / `template_id` / `user_id` / `amount_snapshot_cent` / `status`(`unused`) / `gained_time` / `expire_time` / `used_time`(NULL) / `related_pay_out_trade_no`(NULL) + 公共字段 + IDX `(tenant_id,user_id,status)`/`(tenant_id,template_id)`/`(tenant_id,status,expire_time)`/`(tenant_id,related_pay_out_trade_no)`
  - `tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`（INSERT 不显式赋）；UNIQUE 必含 tenant_id；`del_flag` 2 值。
- [ ] **AC 2 — 字典 seed**：`V<时间戳+1>__GZ-COUPON-001-seed-dict-menu.sql` seed 字典（附录 A.17/A.18/A.19/A.22）：`gz_coupon_discount_type`(cash) / `gz_coupon_issue_strategy`(manual/register_window/event) / 券态 `gz_coupon_status`(unused/locked/used/expired) / 模板态 `gz_coupon_template_status`(active/paused/archived)。字典走 sys_dict，**不写死枚举常量**。
- [ ] **AC 3 — 后端 CRUD + 业务码**：`org.dromara.gz.coupon.*` 模板 CRUD（`GzCouponTemplateController` `/gz/coupon/template`：list/getInfo/add/edit + 暂停 paused / 归档 archived 切状态）+ 用户券查询（`/gz/coupon/userCoupon` list，admin 查发放记录）；`template_no`/`coupon_no` 生成 `域大写-yyyyMMdd-6位序号` 全局唯一；entity `@TableLogic` + `tenant_id` 自动填充；Bo 校验（amount_cent ≥ 0 / valid_days ≥ 1 / discount_type 属字典 / issue_strategy 属字典，V1.2 仅 manual 可选）。
- [ ] **AC 4 — 发放策略 SPI（钉死 doc/11 §11.1.a）**：
  - 接口 `ICouponIssuanceStrategy`（按 `issue_strategy` 路由；输入模板 + `issue_config_json` + 名单 → 批量 INSERT `gz_user_coupon`，事务内乐观锁校验 `issued_count + N <= total_quota`）。
  - **实现 `ManualIssuanceStrategy`**（V1.2 全链路）：admin 多选 `gz_user` / 按条件筛名单 → 每用户生成一张 `unused` 券（`amount_snapshot_cent` = template.amount_cent snapshot，`expire_time = gained_time + valid_days`）；发放事务内乐观锁 `issued_count + N <= total_quota`（NULL=不限），耗尽拦截（doc/11 §11.4 F11.4）+ 写操作日志。
  - **预留 `RegisterWindowStrategy`**（按 `gz_user.register_time` 区间）：接口实现存在 + 留位可编译（不实现逻辑，抛 UnsupportedOperationException 或 TODO 注释带说明）。
  - **预留 `EventIssuanceStrategy` + `CouponIssuanceEvent`**：事件发布/监听骨架留位（含 D14 RECYCLE-003 `paid` 发 `CouponIssuanceEvent(event_type='recycle_paid')` 钩子位 + 监听器按 `issue_strategy='event'` 且 `issue_config_json.event_type` 匹配的模板发券骨架）。V1.2 仅留事件 + 监听骨架不强制配可用模板。
  - reports 验：manual 发放生效 + register_window/event 接口存在可编译 + event 监听钩子留位。
- [ ] **AC 5 — admin 模板 CRUD 页 + 批量发放页**（plus-ui BizTable + Element Plus 默认）：① 模板列表/新增/编辑（含 `issue_strategy` 选择 V1.2 仅 manual 可选 + amount 元↔分换算 + 暂停/归档）；② 批量发放页（选 active manual 模板 + 多选用户/筛名单 → 发放 → 配额耗尽提示）；i18n 全覆盖（`zh_CN/gz-coupon.ts` + `en_US/gz-coupon.ts`，key `gz-coupon.*`）默认 zh-CN 不混 emoji；perm `@SaCheckPermission`（`gz:coupon:template:list/add/edit` + `gz:coupon:issue`）仅 owner 授权；菜单 seed 落 **menu_id 12000 段**（12000 目录 / 12001 模板 / 12002 发放记录，doc/11 §10.3；seed 前 `SELECT MAX(menu_id) ... BETWEEN 12000 AND 12999` 确认空闲）。
- [ ] **AC 6 — 发放配额防超发**：`issued_count` 乐观锁（version）；批量发放事务内校验 `issued_count + N <= total_quota`（NULL=不限），耗尽拦截不超发。reports 必含乐观锁 raw output（`issued_count + N > total_quota` 时拦截，不超发）。
- [ ] **AC 7 — 券态只产 unused**：发放生成 `unused` 券，`expire_time = gained_time + template.valid_days`；`unused→locked→used`/`locked→unused`/`unused→expired` 流转 = D13 COUPON-002（本卡只建表 + 字段 + 发放）；**不建独立 use 流水表**（核销以 `gz_user_coupon.status` + `related_pay_out_trade_no` 追溯）。
- [ ] **AC 8 — 单测**：发放乐观锁（并发发券击穿 total_quota → 拦截）+ manual 策略 happy path（选 N 用户 → 生成 N 张 unused 券 + issued_count += N + expire_time 计算正确）。

> admin + 后端 ticket，**跳过 Tier 2 入口可达 AC**（CLAUDE.md §8.2，无 mp 页 + 无微信原生能力，AI Tier 1A+1B 全 ✅ 即终态）。mp 我的券/选券 = D13 GZ-COUPON-003。

## Tech（端 + 范围）

- **后端**：**新建模块** `ruoyi-modules/ruoyi-gz-coupon/`（包名 `org.dromara.gz.coupon.*`）
  - 参考现有 gz 模块结构（如 `ruoyi-gz-ord` / `ruoyi-gz-news`）建 pom + 注册进父 `ruoyi-modules/pom.xml` + `ruoyi-admin/pom.xml` 依赖；改 ruoyi-gz-* 后 `mvn install -am`（CLAUDE.md §5，新模块 404/Bean 不存在排查）
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V<时间戳 > 202606190631>__GZ-COUPON-001-create-coupon-tables.sql` + `V<+1>__GZ-COUPON-001-seed-dict-menu.sql`
  - `domain/GzCouponTemplate.java` + `GzUserCoupon.java`（entity，`@TableLogic` + `@Version`）+ bo/vo
  - `controller`（模板 CRUD + 发放 + 用户券查询，每端点 `@SaCheckPermission`）
  - `service` + `strategy`（`ICouponIssuanceStrategy` + `ManualIssuanceStrategy` impl + `RegisterWindowStrategy`/`EventIssuanceStrategy` 留位）
  - `event/CouponIssuanceEvent`（发布/监听骨架）
  - `mapper`
- **Admin**：`code/main/plus-ui/src/views/gz-coupon/`（template/index.vue + issue/index.vue）+ `api/gz-coupon/*.ts` + `lang/{zh_CN,en_US}/gz-coupon.ts`
- **小程序**：不动（mp 我的券/选券 = D13 GZ-COUPON-003）
- **测试**：单测（AC 8）+ kevin-qa Tier 1B（后端集成 + COUPON admin Playwright E2E：登录 owner → 建模板 → 批量发券 → 配额耗尽拦截 → 暂停/归档）

## 备注

### 强约束（每条复核）

1. **独立域模块 `ruoyi-gz-coupon`**（包名 `org.dromara.gz.coupon.*`，CLAUDE.md §6 #4）；新建模块必须注册进父 pom + ruoyi-admin pom + `mvn install -am` 否则路由 404。
2. **发放策略 SPI 钉死**（doc/11 §11.1.a）：V1.2 仅 `ManualIssuanceStrategy` 落地全链路；`register_window`/`event` 留接口 + 事件钩子不实现逻辑；`issue_strategy`/`issue_config_json` 列 V1.2 即落库落代码，后续加策略只补一个 impl 不动 DDL。
3. **字段严格对齐 doc/11 §11.1/§11.2**；偏离回改 doc/11 源头不在卡内 patch（§9.5）。
4. **金额 `amount_cent`/`amount_snapshot_cent`（分）**，不用 `_fen`；snapshot 用 `*_snapshot`；前端元↔分换算在 UI 层。
5. **券面额不计 GMV**（doc/11 §11.3）；本卡只建表 + 发放，抵扣/锁定/核销/回滚 = D13 COUPON-002。
6. **乐观锁防超发**：`issued_count` version + 事务内 `issued_count + N <= total_quota`（NULL=不限）。
7. **字典走 sys_dict**（4 个：折扣类型/发放策略/券态/模板态），不写死枚举；UI 用字典 label。
8. **menu_id 12000 段**（doc/11 §10.3）：seed 前 `SELECT MAX(menu_id) ... BETWEEN 12000 AND 12999` 确认空闲（§0 已验 12000 段无命中）；仅 owner 授权。
9. **DDL 命名 `V<yyyyMMddHHmm>__GZ-COUPON-001-<desc>.sql`**，时间戳 > 202606190631；已应用不可改。
10. **业务码 `CPN-`/`UC-` = `域大写-yyyyMMdd-6位序号`**，全局唯一 DB 约束。
11. **`tenant_id VARCHAR(20) NOT NULL DEFAULT '1001'`**（INSERT 不显式赋，自动填充）；UNIQUE 必含 tenant_id；`del_flag` 2 值。
12. **i18n 全覆盖**（zh_CN + en_US，key `gz-coupon.*`），默认 zh-CN 不混 emoji。
13. **不动 ruoyi 自带模块源码**。

### 关键技术决策（承接 doc/11 §11.1.a）

| # | 决策 | 理由 |
|---|---|---|
| D1 | 发放方式做成 SPI（`ICouponIssuanceStrategy` + issue_strategy 列 + issue_config_json） | 券「怎么发」与「券本身」解耦；新增策略不返工模板结构/DDL（§11.1.a） |
| D2 | V1.2 仅实现 manual，register_window/event 留接口 + event 事件钩子 | F11.5 默认裁定：甲方定策略后补 impl 即生效不动 DDL |
| D3 | 不建独立 use 流水表 | 核销以 `gz_user_coupon.status` + `related_pay_out_trade_no` 追溯（§11 引言） |
| D4 | issue_config_json 通用 JSON 列承载各策略参数 | schema 不为每策略加专列，策略各自读本字段（§11.1） |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R5 | 批量发放超发（并发发券击穿 total_quota） | `issued_count` 乐观锁 version + 事务内 `issued_count + N <= total_quota` 校验；单测覆盖并发发券 |
| R6 | menu 12000 段冲突 | §0 已验 12000 段无命中（max 现有 11009）；seed 前再 `SELECT MAX(menu_id) ... BETWEEN 12000 AND 12999` |
| R9 | 新建模块未注册 → 路由 404 / Bean 不存在 | 注册父 pom + ruoyi-admin pom + `mvn install -am`（CLAUDE.md §5；memory dev-infra） |
| R10 | event 事件钩子与 D14 RECYCLE-003 耦合提前 | V1.2 仅留事件发布/监听骨架（不强制配可用模板），D14 RECYCLE-003 发 `CouponIssuanceEvent` 时接 |

---

## §revision（Kevin 批量人验后填，初始空 —— 本卡 admin+后端 AI 终态，通常无人验）

<!--
- 问题 1：<现象> / 期望：<期望>
AI 修完追加"已修 / 改了 <文件>"。
-->
