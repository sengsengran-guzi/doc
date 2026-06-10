# GZ-COUPON-001 完工报告 — 优惠券地基（券模板 + 用户券 + 发放策略 SPI + admin 批量发放）

> 端：后端（新建 `ruoyi-gz-coupon` 域）+ admin（plus-ui）。复杂度 M。AI 终态（无 mp / 无人验）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本项目此路径非 git 仓库，§0 跳过 git） |
| 上游依赖 merge | ✅ `gz_user` 表已建 + sys_role owner(100)/staff(101) 已建（docker mysql 实测） |
| 关键表/段空闲 | ✅ `gz_coupon_template` / `gz_user_coupon` 不存在（从零建）；`ruoyi-gz-coupon` 模块不存在（新建）；menu 12000 段空闲（`MAX(menu_id) BETWEEN 12000 AND 12999 = EMPTY`） |
| 迁移时间戳 | ✅ flyway 已应用最大 = `202606190631`；本卡用 `V202606200100` / `V202606200101`（> 已有，BEAN-014 用 V20260620000x 不冲突） |
| 字典段避冲突 | ✅ 现有 max dict_id=9210 / dict_code=91309；本卡取 dict_id 9220-9233 / dict_code 9221-9236（避开 BEAN-013 9210-9213） |
| 编译通过 | ✅ `mvn -o compile -pl ruoyi-modules/ruoyi-gz-coupon` BUILD SUCCESS |
| ADR 已读 | 无相关 ADR（发放策略 SPI 设计权威 = doc/11 §11.1.a，ticket 卡明示「不另立 ADR」） |
| 权威蓝图引用 | ✅ doc/11 §11.1/§11.1.a/§11.2/§11.3/§11.4 + 附录 A.17/A.18/A.19/A.22 + §10.2 dict 映射表 + §10.3 menu 段；doc/10 §12 全读（摘录见文末） |

**§0 期间发现的 doc 偏差（按 CLAUDE.md §9.5 #1「以 doc/11 为准」处理）**：
- ticket 卡 AC 2 文字写「`gz_user_coupon_status`」，但 doc/11 §10.2 dict 映射表（line 1314）+ 附录 A.17（line 1748）权威定义 dict_type = **`gz_coupon_status`**。已按 doc/11 落地 `gz_coupon_status`（迁移注释 + 本报告记录）。**建议主线程在 doc 复盘时确认 ticket 卡此处改齐 doc/11**（源头已对，仅 ticket 文字笔误）。

## 实现摘要

### 新建模块 `ruoyi-modules/ruoyi-gz-coupon`（包名 `org.dromara.gz.coupon.*`，照 ruoyi-gz-news 结构）
- **根 pom 注册（2 处）**：`ruoyi-modules/pom.xml` 加 `<module>ruoyi-gz-coupon</module>`；`ruoyi-admin/pom.xml` 在 gacha 依赖块后加 ruoyi-gz-coupon 依赖块。
- **依赖**：仅 `ruoyi-gz-common`（传递引入 mybatis/web/tenant/security/log/json）+ spring-boot-starter-test；复用 common 的 `IGzUserService`（发券名单解析）。无新第三方依赖。
- 31 个 Java 文件（含 3 个测试），分层 entity / bo / vo / mapper / service(+impl) / strategy / event / internal / controller。

### 迁移（2 个）
- `V202606200100__GZ-COUPON-001-create-coupon-tables.sql`：`gz_coupon_template` + `gz_user_coupon`，字段/索引严格对齐 doc/11 §11.1/§11.2。业务码 UNIQUE 含 `del_flag`（跨层契约 #3 软删可复用）；`tenant_id` DEFAULT '1001'；金额 `*_cent`；`issue_config_json` JSON；`version` 乐观锁。
- `V202606200101__GZ-COUPON-001-seed-dict-menu.sql`：4 字典（discount_type/issue_strategy/coupon_status/template_status，逐字对齐附录）+ 11 个 12000 段菜单（目录/券模板/发放记录 + 按钮 perm）+ owner(100) 全授权。

### 发放策略 SPI（doc/11 §11.1.a）
- `ICouponIssuanceStrategy`（`supports()` 路由 + `issue(ctx)`）+ `CouponIssuanceContext`（模板 + 名单）。
- `ManualIssuanceStrategy`（V1.2 全链路）：乐观锁 `increaseIssuedCount`（DB 行锁内「校验配额 + 扣减 + version+1」单条 UPDATE）→ 批量 INSERT unused 券（amount_snapshot snapshot + expire = now + valid_days）。
- `RegisterWindowIssuanceStrategy` / `EventIssuanceStrategy`（预留，留位可编译，`issue()` 抛带说明的 `UnsupportedOperationException`）。
- `CouponIssuanceEvent` + `CouponIssuanceEventListener`（@EventListener 骨架，含 D14 RECYCLE-003 `recycle_paid` 钩子注释占位）。

### admin（plus-ui，ruoyi/Element Plus 默认审美，不引 mockup）
- `views/gz-coupon/template/index.vue`：模板列表 + 查询 + 新增/编辑弹窗（元↔分换算，V1.2 仅 cash/manual 可选）+ 暂停/启用/归档 + **批量发放弹窗**（选 active 模板 → 多选用户/筛关键词 → 发放 → 配额回显）。
- `views/gz-coupon/user-coupon/index.vue`：发放记录列表（回填 templateName/userNickname/userMobile）。
- `api/gz-coupon/{template,userCoupon}.ts`（id 全 string）+ `lang/{zh_CN,en_US}.ts` 加 `gzCouponTemplate` / `gzCouponUserCoupon` 块（全覆盖，默认 zh-CN 不混 emoji）。
- 菜单/路由走 DB seed（component path `gz-coupon/template/index` → 视图），无手写 route 文件。

## AI 自测（Tier 1A）

### 1. 编译 + 单测（mvn -o，未占 8080）
```
[INFO] Tests run: 8, Failures: 0, Errors: 0, Skipped: 0 -- GzCouponTemplateServiceImplTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0 -- GzCouponIssuanceServiceImplTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0 -- ManualIssuanceStrategyTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
覆盖：manual 策略 happy path（N 用户 → N 张 unused 券 + amount_snapshot + expire = now+valid_days）、乐观锁防超发（increaseIssuedCount 返 0 → 抛异常且不 INSERT 券）、名单空拒绝、策略路由、非 active/非 manual 模板拒绝、keyword 名单解析、并发抢最后配额（仅一单成功其余拒单）、枚举校验（仅 cash/pindou/manual）、template_no 生成、状态流转边界。
`mvn -o install -DskipTests -pl ruoyi-modules/ruoyi-gz-coupon` → BUILD SUCCESS（jar 装入 ~/.m2，避免 Bean 404）。

### 2. DDL 验证（docker mysql ry-vue，迁移可应用 + 结构/索引比对）
```
create OK / seed OK  （两迁移幂等应用，未污染 flyway_schema_history → 启动时 flyway 幂等重跑）

gz_coupon_template 索引：
  PRIMARY id / uk_tenant_template_no(tenant_id,template_no,del_flag)
  idx_status_business(tenant_id,status,applicable_business) / idx_discount_type / idx_issue_strategy   ✅ 对齐 doc/11 §11.1
gz_user_coupon 索引：
  PRIMARY id / uk_tenant_coupon_no(tenant_id,coupon_no,del_flag)
  idx_user_status / idx_template / idx_status_expire / idx_related_pay   ✅ 对齐 doc/11 §11.2

字典（值逐字对齐附录）：
  gz_coupon_discount_type   3  cash,full_reduce,percent
  gz_coupon_issue_strategy  3  manual,register_window,event
  gz_coupon_status          4  unused,locked,used,expired
  gz_coupon_template_status 3  active,paused,archived

menu 12000 段 11 行（目录 12000 + 券模板 12001 + 发放记录 12002 + 8 按钮 perm）；owner(100) 授权 = 11 ✅
```

### 3. 乐观锁防超发功能验证（AC 6，DB 直跑 increaseIssuedCount 同款 SQL，total_quota=3）
```
线程 A：N=2 version=0  → affected=1  issued_count 0→2, version 0→1
线程 B：N=2 version=0  → affected=0  （version 失配，拦截，不超发）
线程 B 重试：N=2 version=1 → affected=0  （配额 2+2>3，拦截，不超发）
线程 C：N=1 version=1  → affected=1  （恰好填满 2+1<=3）
最终：issued_count=3 = total_quota，version=2  → 无超发 ✅
（测试模板已 DELETE 清理）
```

### 4. plus-ui 构建（pnpm build:prod = vue-tsc + vite，未起 dev server）
```
> vite build --mode production
vite v7.3.2 building client environment for production...
dist/assets/userCoupon-DXlYCRl_.js   0.25 kB  （发放记录视图 chunk 已出）
（template 视图打进 index-* 主 chunk）
EXIT=0   无 TS error / 无 vue-tsc error
```

## 风险提示 / 已知 issue

- R5（批量发放超发）：已用 `issued_count` 乐观锁 version + 事务内 `issued_count + N <= total_quota` 单条 UPDATE 兜死（DB 实测拦截，单测覆盖并发抢最后名额）。
- R9（新模块未注册 → 404）：已注册父 pom + ruoyi-admin pom + `mvn install`。kevin-qa Tier 1B 起 app 后请确认 `/system/gz/coupon/template/list` 不 404。
- **迁移未走 flyway 应用**（我用 docker mysql 直跑验证 SQL 可应用，未写 flyway_schema_history）：app 下次启动 flyway 会幂等重跑这两个迁移（`CREATE TABLE IF NOT EXISTS` + `DELETE...INSERT` seed 均幂等），无 checksum 问题。kevin-qa 起 app 时观察 flyway 正常应用即可。
- **doc 偏差**（dict_type `gz_coupon_status` vs ticket 卡 `gz_user_coupon_status`）：已按 doc/11 权威落地，建议 doc 复盘订正 ticket 卡文字（源头 doc 已对）。
- 待 Kevin 批量人验关注：N/A（纯 admin + 后端，无 mp 页、无微信原生能力 → AI Tier 1A+1B 全 ✅ 即终态，无人验，ticket AC 已明示跳过 Tier 2 入口可达）。

## 对下游 ticket 的提示

- **D13 GZ-COUPON-002（拼豆抵扣 + 锁定/核销/过期 SnailJob）**：
  - 券态流转 `unused→locked→used` / `locked→unused` / `unused→expired` 由你落地；本卡只产 unused，`gz_user_coupon` 已建全字段（含 `used_time` / `related_pay_out_trade_no` 占位）。
  - 抵扣依赖 BEAN-014 下单事务：拼豆下单选券 → `unused→locked` + 写 `gz_bean_booking.coupon_id`；onPaid → `locked→used` + 写 `used_time` + `related_pay_out_trade_no`。抵扣口径 doc/11 §11.3（实付下限 0，券面额不计 GMV）。
  - 过期 SnailJob（`gz.coupon.expire.cron`）扫 `unused` 且 `expire_time < NOW()` → `expired`；本模块 pom 未加 `ruoyi-common-job`（本卡无 cron），你加 SnailJob 时补该依赖。
  - 复用现成乐观锁基础设施：`GzCouponTemplateMapper.increaseIssuedCount` 已是「版本 CAS + 配额校验」单条 UPDATE 模板，过期/回滚可仿此写条件 UPDATE。
- **D13 GZ-COUPON-003（mp 我的券 / 选券）**：mp 端，新建 applet controller（`/app/gz/coupon/*`）；选券接口 `GET usable?business=pindou&total_amount`（doc/10 §12.N3）返用户 unused 未过期券。
- **D14 GZ-RECYCLE-003（回收完成发券钩子）**：回收单 paid 时 `applicationEventPublisher.publishEvent(new CouponIssuanceEvent(this, "recycle_paid", userIds))` 即可接入；`CouponIssuanceEventListener` 骨架已留位（按 issue_strategy='event' + issue_config_json.event_type 匹配模板发券的逻辑由你/甲方定策略后补，不动本模块 DDL）。
- 业务码序号空间：`CPN-` 查 template_no、`UC-` 查 coupon_no，各自独立空间；批量发券一次取基序号后内存自增（DB UNIQUE 兜底）。

## doc/11 §11 / doc/10 §12 引用摘录（实施钉死口径）

- §11.1 模板：template_no `CPN-`(UNIQUE tenant_id,template_no) / discount_type 默认 cash / amount_cent / applicable_business 默认 pindou / valid_days 默认 30 / total_quota NULL=不限 / issued_count 默认 0 / issue_strategy 默认 manual / issue_config_json JSON NULL / status 默认 active / version 乐观锁。IDX (tenant_id,status,applicable_business)/(tenant_id,discount_type)/(tenant_id,issue_strategy)。
- §11.1.a SPI：ICouponIssuanceStrategy 按 issue_strategy 路由；事务内乐观锁 `issued_count + N <= total_quota`。V1.2 仅 manual 落地；register_window 仅接口；event 留接口 + 事件钩子（RECYCLE-003 发 CouponIssuanceEvent）。后续加策略只补一个实现不动 DDL。
- §11.2 用户券：coupon_no `UC-`(UNIQUE) / template_id / user_id / amount_snapshot_cent（领券时从 template snapshot）/ status 默认 unused / gained_time / expire_time = gained_time + valid_days / used_time NULL / related_pay_out_trade_no NULL。IDX (tenant_id,user_id,status)/(tenant_id,template_id)/(tenant_id,status,expire_time)/(tenant_id,related_pay_out_trade_no)。
- §11.3 抵扣/GMV：实付 = 单笔金额 − amount_snapshot_cent（下限 0）；券面额不计 GMV；不建独立 use 流水表（status + related_pay_out_trade_no 追溯）。本卡只建表 + 发放，抵扣 = D13。
- §11.4 F11.4：manual 选用户/筛名单批量 INSERT + 乐观锁配额校验。F11.5：register_window/event 不实现逻辑，仅 SPI + 事件钩子，甲方定策略补一个实现即生效不动 DDL。
- 附录 A.17 `gz_coupon_status`(unused/locked/used/expired) / A.18 `gz_coupon_template_status`(active/paused/archived) / A.19 `gz_coupon_discount_type`(cash/full_reduce/percent) / A.22 `gz_coupon_issue_strategy`(manual/register_window/event)。
- doc/10 §12.N1 建模板 / N2 发放（策略路由 + 乐观锁配额）/ N3-N8 抵扣锁定核销过期（= D13）；E1 发放超配额乐观锁失败提示。

## §AI 测试段（kevin-qa Tier 1B，15:04-15:20）

### Flyway 迁移验证

```
[INFO] Migrating schema `ry-vue` to version "202606200100 - GZ-COUPON-001-create-coupon-tables"
[WARN] DB: Table 'gz_coupon_template' already exists (SQL State: 42S01 - Error Code: 1050)
[WARN] DB: Table 'gz_user_coupon' already exists (SQL State: 42S01 - Error Code: 1050)
[INFO] Migrating schema `ry-vue` to version "202606200101 - GZ-COUPON-001-seed-dict-menu"
[INFO] Successfully applied 4 migrations to schema `ry-vue`, now at version v202606200101
```

`CREATE TABLE IF NOT EXISTS` 幂等通过（表已存在 WARN 为预期，非 ERROR），flyway_schema_history 记录 success=1。

DB 验证：
- gz_coupon_template: PRIMARY + uk_tenant_template_no + idx_status_business + idx_discount_type + idx_issue_strategy ✅
- gz_user_coupon: PRIMARY + uk_tenant_coupon_no + idx_user_status + idx_template + idx_status_expire + idx_related_pay ✅
- 字典：gz_coupon_discount_type(3) / gz_coupon_issue_strategy(3) / gz_coupon_status(4) / gz_coupon_template_status(3) ✅
- 菜单：12000 段 11 行（目录+模板+发放记录+8按钮），owner(100) 全授权 ✅

### 后端集成 + API 契约

```bash
# AC3: 模板 CRUD
POST /system/gz/coupon/template
Body: {name:"QA测试代金券5元", discountType:"cash", amountCent:500, validDays:30, totalQuota:10, issueStrategy:"manual"}
# 实际：code=200, msg="新建成功" ✅

GET /system/gz/coupon/template/{id}
# 实际：templateNo=CPN-20260609-000001, discountType=cash, amountCent=500, issuedCount=0
#        id 返回 string 类型 ✅（API 契约）

POST /system/gz/coupon/template/pause/2   → code=200 ✅
POST /system/gz/coupon/template/archive/2 → code=200, DB status=archived ✅
```

```bash
# AC4/AC6: 批量发放（manual策略，userIds=[7,8]，共2张）
POST /system/gz/coupon/template/issue
Body: {templateId:2, userIds:[7,8]}
# 实际：code=200, msg="发放成功", issuedCount=2 ✅
# DB验证：
#   gz_user_coupon 2行: status=unused, amount_snapshot_cent=500
#   expire_time = gained_time + 30天（2026-07-09）✅
#   issuedCount: 0→2 ✅
```

```bash
# AC6: 配额耗尽拦截（totalQuota=3，尝试发5张）
# 新建模板 totalQuota=3，POST /system/gz/coupon/template/issue userIds=[1,2,3,4,5]
# 实际：code=500，msg="发放失败：配额不足或模板已被并发修改（已发 0 / 配额 3），请重试" ✅
```

```bash
# AC3/AC5: 非active模板拒绝发放（archived状态）
POST /system/gz/coupon/template/issue  Body: {templateId:2, userIds:[7]}
# 实际：code=500，msg="模板非启用状态，不可发放：archived" ✅
```

```bash
# AC3: 发放记录列表
GET /system/gz/coupon/userCoupon/list?pageNum=1&pageSize=10
# 实际：code=200, total=9, couponNo=UC-20260609-格式 ✅
```

### 单测 raw output

```
[INFO] Tests run: 8,  Failures: 0, Errors: 0, Skipped: 0 -- GzCouponTemplateServiceImplTest
[INFO] Tests run: 7,  Failures: 0, Errors: 0, Skipped: 0 -- GzCouponIssuanceServiceImplTest
[INFO] Tests run: 3,  Failures: 0, Errors: 0, Skipped: 0 -- ManualIssuanceStrategyTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

### admin Playwright E2E

Playwright MCP 工具在当前环境不可用（`No such tool available: mcp__plugin_playwright_playwright__browser_navigate`）。改用 curl API 契约回归替代 admin 端 E2E 覆盖（CRUD + 发放 + 配额 + 状态切换全通过，见上）。

plus-ui 前端 AC5 视觉/表单验证（元↔分换算、dict-tag 翻译、issue_strategy 仅 manual 可选）：未通过 Playwright 验证，建议 Kevin 在 admin 页面上 spot check 以下两点：
1. dict-tag 中文渲染（`gz_coupon_status` = 未使用/已锁定/已使用/已过期）
2. issue_strategy 下拉 V1.2 是否只显示 manual（不显示 register_window/event）

### 跳过 / 未跑

- Playwright E2E（MCP 工具不可用）：改 curl API 替代，功能路径全覆盖
- dict-tag 中文渲染视觉验证：需人工 admin spot check

### 结论

- ✅ Flyway 迁移应用（V20260620010x 两文件，幂等通过）
- ✅ AC1 建表：字段/索引对齐 doc/11 §11.1/§11.2
- ✅ AC2 字典 seed：4 个字典全 seed，menu 12000 段 11 行
- ✅ AC3 模板 CRUD：list/getInfo/add/pause/archive，id 返 string
- ✅ AC4 发放策略 SPI：manual 全链路，issued_count+N，unused 券生成，expire_time 正确
- ✅ AC5 admin 功能（API层验证）：CRUD + 状态切换 + 发放页
- ✅ AC6 配额防超发：5张超过 totalQuota=3 被拒，msg 明确
- ✅ AC7 券态只产 unused：发放后 status=unused，used/expired 流转 = D13
- ✅ AC8 单测：18 tests passed (GzCouponTemplate + GzCouponIssuance + ManualIssuance)
- ⚠️ admin Playwright E2E 未执行（MCP 不可用）：dict-tag 渲染 + issue_strategy 下拉建议 Kevin spot check
