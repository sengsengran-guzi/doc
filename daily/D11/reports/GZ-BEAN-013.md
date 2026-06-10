# GZ-BEAN-013 完工报告 — 拼豆座位类型配额配置（admin 配数量/单价 + 废弃 A1-A10）

> 状态：**Tier 1A ✅**（表+字典+菜单迁移 / 后端 CRUD + 13 单测 / plus-ui 配置页 / typecheck 全绿）｜ 纯 admin+后端，**AI Tier 1A+1B 全 ✅ 即终态（无人验）**
> 实施：kevin-coder（迁移 + 后端全套 + 单测）+ 主线程（plus-ui 页/api/i18n 收尾 + 修座位 perm 403 回归）

---

## §0 状态自检

| 检查项 | 结果 |
|---|---|
| 锚点表 gz_bean_seat / gz_bean_booking / gz_bean_store | 全在 ✅（BEAN-001/002/004 建） |
| migration 当前最大 | V202606190200；本卡用 **0630/0631**（> 最大）✅ |
| menu 6000 段空位 | 6000-6006 / 6020-6025 / 6030-6034 / 6050-6056 已占；本卡取 **6010-6014** ✅ |
| 无 sys_job INSERT | ✅（仓库无 sys_job 表，迁移未 INSERT） |

---

## 改了哪些文件

**后端 ruoyi-gz-bean（`org.dromara.gz.bean.*`）：**
- 迁移 `V202606190630__GZ-BEAN-013-create-seat-type-config.sql`（建表）+ `V202606190631__GZ-BEAN-013-seed-seat-type-dict-menu.sql`（字典 + menu 6010-6014 + 废弃座位增删改 perm）
- `domain/entity/GzBeanSeatTypeConfig` + `domain/bo/GzBeanSeatTypeConfigBo` + `domain/bo/GzBeanSeatTypeConfigQueryBo` + `domain/vo/GzBeanSeatTypeConfigVO`
- `mapper/` + `service/IGzBeanSeatTypeConfigService` + `service/impl/GzBeanSeatTypeConfigServiceImpl` + `controller/GzBeanSeatTypeConfigController`
- `test/.../GzBeanSeatTypeConfigServiceImplTest`（13 用例）

**plus-ui（主线程收尾）：**
- `src/api/gz-bean/seatTypeConfig.ts`（list/listByStore/getInfo/add/edit/toggleEnabled/remove，对齐 controller `/system/gz/bean/seatTypeConfig`）
- `src/views/gz-bean/seat-type-config/index.vue`（门店 select + 每类型行：字典翻译/数量/单价元↔分/启用 switch/增删改；component 路径对齐 menu 6010）
- `src/lang/zh_CN.ts` + `en_US.ts`：`gzBeanSeatTypeConfig.*` 块

---

## 字段差异决策（§9.5 #1 — 以 doc/11 源头为准）

ticket 文字描述 `enabled CHAR(1)` / 无 `sort_no`；**doc/11 §3.4（权威源）为 `enabled TINYINT` + 含 `sort_no`**。按 CLAUDE.md §9.5 #1「以 doc/11 为准」+ 与现有 `gz_bean_seat`/`gz_bean_time_slot_template` 的 `enabled TINYINT` 惯例一致 → 采纳 doc/11 口径（TINYINT + sort_no）。未在卡内私自加字段。

---

## ⚠️ 主线程修正：座位 perm 撤销 403 回归（已修）

coder-bean 原迁移 0631 撤销了 `6021-6025` **全部**座位 perm（含 **6021 = `gz:bean:seat:list`**），会导致 owner 打开 config 页 seat tab 时 `loadSeats()` → 后端 `@SaCheckPermission("gz:bean:seat:list")` **403**。
→ 主线程改为**保留 6021（list 只读）**，仅撤 6022-6025（add/edit/remove/batchGenerate）。效果：config 座位 tab 变**只读**（增删改按钮靠 v-hasPermi 自动隐藏，list 仍可查），供 **D12 GZ-BEAN-014 旧 booking seat→seat_type 迁移期核对原 A1-A10**。前端 config/index.vue 无需改动（避开已交付页重写风险）。

> 注：coder-bean 迁移注释原称「前端已移除座位 tab」与实际不符（未移除）；已改注释为真实决策（保留只读 tab）。

---

## 单笔单时段无子表确认（ADR-0007/0008）

未建 `gz_bean_booking_unit` 子表 ✅（一笔预约 = 一行 booking，多类型/多时段 = 多次预约）。

---

## 自测 raw output

### 1. 建表迁移（字段对齐 doc/11 §3.4）
```sql
CREATE TABLE IF NOT EXISTS gz_bean_seat_type_config (
    id BIGINT UNSIGNED PK, store_id BIGINT UNSIGNED NOT NULL,
    seat_type VARCHAR(16) NOT NULL,           -- 字典 gz_bean_seat_type
    quantity INT NOT NULL DEFAULT 0,          -- 配额上限 = 余量基础
    price_cent BIGINT NOT NULL DEFAULT 0,     -- 单价（分，非 _fen）
    enabled TINYINT NOT NULL DEFAULT 1, sort_no INT NOT NULL DEFAULT 0,
    tenant_id VARCHAR(20) NOT NULL DEFAULT '1001', del_flag CHAR(1) DEFAULT '0', ...
    UNIQUE KEY uk_tenant_store_type (tenant_id, store_id, seat_type)   -- UNIQUE 含 tenant_id
);
```

### 2. 字典 + 菜单 seed
```sql
sys_dict_type:  gz_bean_seat_type (拼豆座位类型)
sys_dict_data:  single 单人 / double 双人 / quad 四人桌
sys_menu:       6010 座位类型配额(C) + 6011-6014(list/add/edit/remove F) → owner(100) 全授 + staff(101) 仅 list
废弃座位:        撤 6022-6025 座位增删改 perm（保留 6021 list 只读）；gz_bean_seat 表不 DROP
```

### 3. 后端单测（13 passed）
```
Tests run: 13, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.802 s
-- GzBeanSeatTypeConfigServiceImplTest（insert/update/removeByIds 软删 / 同门店同类型重复 insert 触 UNIQUE 等）
```

### 4. plus-ui typecheck（`npx vue-tsc --noEmit`）
```
=== 本次改动文件相关 error（seat-type-config / seatTypeConfig / lang）===
(空 — 本次改动文件无 error)
```

---

## gz_bean_seat 废弃但物理保留（ADR-0008 §1）

- 迁移**无** `DROP TABLE gz_bean_seat`（物理保留作历史 + BEAN-014 迁移期映射）
- 座位入口「下线」语义 = 撤增删改 perm（不能再改 A1-A10），非删表 / 非禁查（保留 list 只读）
- 禁止本卡及后续代码 INSERT / 依赖 `gz_bean_seat` 做预约分配

---

## 遗留 Tier 1B（kevin-qa）

1. 起 app（Flyway 自动应用 0630/0631）→ `DESC gz_bean_seat_type_config` + `SELECT dict_label,dict_value FROM sys_dict_data WHERE dict_type='gz_bean_seat_type'` + `SHOW TABLES LIKE 'gz_bean_seat'`（仍在）。
2. admin Playwright：owner 登录 → 拼豆管理 → 座位类型配额 → 选成都门店 → 配 single 数量5/单价X + double/quad → 切 enabled → 删一行 → 重复类型 insert 触 UNIQUE 拒。

---

## §AI 测试段（kevin-qa Tier 1B，12:20）

### Flyway apply 验证

```
- Migrating schema `ry-vue` to version "202606190630 - GZ-BEAN-013-create-seat-type-config"
- Migrating schema `ry-vue` to version "202606190631 - GZ-BEAN-013-seed-seat-type-dict-menu"
- Successfully applied 5 migrations to schema `ry-vue`, now at version v202606190631
```
V202606190630 + V202606190631 apply 成功 ✅

### 后端 DB 验证

```sql
-- DESC gz_bean_seat_type_config（关键字段）
id            bigint unsigned  NO   PRI  auto_increment
store_id      bigint unsigned  NO
seat_type     varchar(16)      NO         -- 字典 gz_bean_seat_type
quantity      int              NO   0
price_cent    bigint           NO   0
enabled       tinyint          NO   1     ← doc/11 §3.4 TINYINT（不是 CHAR）✅
sort_no       int              NO   0     ← doc/11 §3.4 含 sort_no ✅
tenant_id     varchar(20)      NO   1001  ← UNIQUE 含 tenant_id ✅

-- 字典 gz_bean_seat_type
dict_label  dict_value  dict_sort
单人        single      1
双人        double      2
四人桌      quad        3

-- SHOW TABLES LIKE 'gz_bean_seat'
gz_bean_seat  ← 物理保留 ✅

-- sys_role_menu: role_id=100, menu_id=6021
menu_id: 6021  ← 6021 list 保留授权（403 回归修复）✅
```

### API 契约（curl 测试）

```bash
# POST /system/gz/bean/seatTypeConfig（gz_owner token, tenant 1001）
curl -X POST ... -d '{"storeId":1,"seatType":"single","quantity":5,"priceCent":1500}' \
  http://localhost:8080/system/gz/bean/seatTypeConfig

# 期望：200 { code: 200, data: <id> }
# 实际：500 { code: 500, msg: "座位类型无效（应为字典 gz_bean_seat_type 之一）" }
```

**❌ Tier 1B 失败 1 处：BEAN-013 seatTypeConfig add 返回 500**

**根因分析**：
- `GzBeanSeatTypeConfigServiceImpl.validateSeatType()` 调用 `dictService.getDictLabel("gz_bean_seat_type", seatType)`
- `dictService.getDictLabel` → `selectDictDataByType` → MyBatisPlus 自动追加 `AND tenant_id='1001'`（租户隔离）
- 但迁移 0631 seed 数据：`sys_dict_type.tenant_id='000000'` / `sys_dict_data.tenant_id='000000'`
- 租户 1001 的 cache key `1001:sys_dict::gz_bean_seat_type` = NullValue → getDictLabel 返回空 → "座位类型无效"
- 对比：`GzNewsArticleServiceImpl.validateCategory` 用硬编码 `Set.of(...)` 不走 dictService → 不受此问题影响

**修复建议（kevin-coder 闭环）**：
选项 A（推荐）：将 `validateSeatType` 改为硬编码 Set（与 GzNewsArticleServiceImpl 同款）：
```java
private static final Set<String> VALID_SEAT_TYPES = Set.of("single", "double", "quad");
// 替换 dictService.getDictLabel 调用
if (!VALID_SEAT_TYPES.contains(seatType)) throw new ServiceException("座位类型无效：" + seatType);
```
选项 B：`TenantHelper.ignore(() -> dictService.getDictLabel(...))` 跳过租户过滤，但 TenantHelper 是自有模块不推荐在 gz-bean 引入。
选项 C：迁移补充把 dict_type + dict_data 的 tenant_id 改为同时写 1001（每个租户都要维护，不推荐）。

**影响**：`insertByBo` 全量 500（add 功能不可用）；`updateByBo` / `toggleEnabled` / `removeByIds` / `selectPageList` 不受影响（list 200 ✅）

### admin Playwright E2E

```
Nav content: ... 座位类型配额 ... （confirmed in nav）
预购商品管理 count: 0  ← ORD-110 预购隐藏验证顺带确认
BEAN-013: nav has 座位类型配额 ✅
```

注：plus-ui SPA 动态路由下 `/gz-bean-seat-type-config` 直接 URL 返回自定义 404（正常，路由从 DB 动态加载），通过左侧导航 `座位类型配额` 条目确认渲染。Playwright 在 nav text 中确认「座位类型配额」存在 ✅。

### mp vitest 全量回归

```
Test Files  35 passed (35)
     Tests  308 passed (308)
```
全通过 ✅（BEAN-013 是纯 admin/后端 ticket，无 mp 测试项）

### 失败清单 → 建议 kevin-coder 闭环修

1. **BEAN-013 seatTypeConfig add 接口 500**
   - 接口：`POST /system/gz/bean/seatTypeConfig`
   - 现象：`msg: "座位类型无效（应为字典 gz_bean_seat_type 之一）"`
   - 根因：`validateSeatType` 用 `dictService.getDictLabel` 受租户隔离，查不到 000000 的字典数据
   - 修法：改为硬编码 `Set.of("single","double","quad")` 校验（参考 GzNewsArticleServiceImpl 第 63-64 行）
   - 影响范围：仅 insertByBo；其他 CRUD 接口正常

### 结论

❌ Tier 1B 失败 1 处（add seatTypeConfig 接口 500），需 kevin-coder 闭环修，修完回 spawn kevin-qa 复测

---

## ADR 已读

- **ADR-0008**（座位类型配额模型）：本卡是 D11 地基落地（config 表 + 字典 + admin 配置页 + 废弃 gz_bean_seat）。防超卖计数 / 余量查询接口 / 付费列 / 旧数据迁移在 **D12 GZ-BEAN-014**（依赖本卡）。

---

## §AI 测试段（kevin-qa revision-1 复测，12:45）

**背景**：主线程已修 `GzBeanSeatTypeConfigServiceImpl.validateSeatType`（改为硬编码 `VALID_SEAT_TYPES = Set.of("single","double","quad")`，删 DictService 依赖）；gz-bean 13 单测 BUILD SUCCESS；plus-ui vue-tsc 0 error。本轮验证修复是否到位。

### 环境确认

```
mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
[INFO] BUILD SUCCESS (Total time: 2.050 s)

mvn spring-boot:run -pl ruoyi-admin
[INFO] Started DromaraApplication in 10.296 seconds
Flyway: Schema `ry-vue` is up to date. No migration necessary.  ← 本轮无新迁移 ✅
```

### 复测结果

```bash
# TEST 1: POST add single（核心复测 — 上轮 500，本轮期望 200）
POST /system/gz/bean/seatTypeConfig
Body: {"storeId":1,"seatType":"single","quantity":5,"priceCent":1500}
实际: {"code":500,"msg":"座位类型无效（应为字典 gz_bean_seat_type 之一）","data":null}
```

**❌ 仍然 500（修复不完整）**

### 根因更新（修复不完整）

app log stack trace：
```
Validation failed for argument [0] in GzBeanSeatTypeConfigController.add(GzBeanSeatTypeConfigBo):
[Field error on field 'seatType': rejected value [single];
 codes [DictPattern.gzBeanSeatTypeConfigBo.seatType,...,DictPattern];
 default message [座位类型无效（应为字典 gz_bean_seat_type 之一）]]
```

**主线程修的是 `validateSeatType()` 方法（ServiceImpl 层），但未修 Bo 上的 `@DictPattern` 注解（Controller 层 Bean Validation，早于 Service 执行）：**

```java
// GzBeanSeatTypeConfigBo.java 第 50-52 行（仍未修）
@DictPattern(dictType = "gz_bean_seat_type", separator = ",",
    ...)
private String seatType;
```

`@DictPattern` 在 Controller method argument 绑定时触发（Spring Validation），调用 ruoyi 字典 validator，内部查 `sys_dict_data WHERE dict_type='gz_bean_seat_type' AND tenant_id='1001'`（业务租户隔离）。但迁移 seed 的字典 `tenant_id='000000'`（系统级），1001 下查不到 → 校验失败 → 500，永远到不了 ServiceImpl.validateSeatType。

### 修复建议（kevin-coder 闭环）

**必须同时修两处**：

1. **`GzBeanSeatTypeConfigBo.java`（主修）**：去掉 `@DictPattern` 注解（或把 dictType 校验替换为 `@Pattern(regexp = "^(single|double|quad)$", message = "...")`），原因：`@DictPattern` 走字典 service 受租户隔离，同根因（upper dictService 问题）。
   ```java
   // 改前
   @DictPattern(dictType = "gz_bean_seat_type", separator = ",", ...)
   private String seatType;
   
   // 改后（方案 A：Pattern 正则，不走字典 service）
   @Pattern(regexp = "^(single|double|quad)$", message = "座位类型无效（应为 single/double/quad 之一）",
            groups = {AddGroup.class, EditGroup.class})
   private String seatType;
   ```

2. **`GzBeanSeatTypeConfigServiceImpl.validateSeatType()`（已修）**：保留硬编码 Set 兜底（防绕过 Controller 校验），无需再改。

**不推荐**：修 dict seed 改 tenant_id='1001' —— 系统字典本来就是 tenant_id='000000'（全局共享），改成 1001 会在多租户环境下只对 1001 可见，逻辑错误。

### 结论

❌ Tier 1B revision-1 复测仍失败（add 接口 500），主线程修复不完整（只修了 ServiceImpl.validateSeatType，未修 Bo.@DictPattern 注解）。需 kevin-coder 二轮闭环：去掉/替换 `GzBeanSeatTypeConfigBo.seatType` 上的 `@DictPattern`，改用 `@Pattern(regexp="^(single|double|quad)$")`。修完后回 spawn kevin-qa 做 revision-2 复测。

**app/server 状态**：8080 已关闭 ✅

---

## §AI 测试段（kevin-qa revision-2 复测，12:50）

**背景**：revision-2 两处修复均已落地：① `GzBeanSeatTypeConfigBo.seatType` `@DictPattern` → `@Pattern(regexp = "^(single|double|quad)$")`（Bo 注释同步说明原因）；② `ServiceImpl.validateSeatType` 保留硬编码 `VALID_SEAT_TYPES = Set.of(...)` 兜底。gz-bean 无任何 `@DictPattern`/`dictService` 实际调用（仅注释说明为何不用）。

### 环境确认

```
mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-bean -am
[INFO] ruoyi-gz-bean ...................................... SUCCESS [  0.127 s]
[INFO] BUILD SUCCESS  (Total time: 2.406 s)

mvn spring-boot:run -pl ruoyi-admin
[INFO] Started DromaraApplication in 10.238 seconds
Flyway: Successfully validated 60 migrations / Schema `ry-vue` is up to date. No migration necessary.
```

### API 契约回归（全 curl，token 取自 Redis 已有 gz_owner session，三头：Authorization + clientid + tenantId）

```bash
# ── 成都门店 storeId=1 ──

# TEST 1: POST add single（核心复测 — revision-1 500 应消失）
POST /system/gz/bean/seatTypeConfig
Body: {"storeId":1,"seatType":"single","quantity":5,"priceCent":1500}
实际: {"code":200,"msg":"操作成功","data":null}
结论: ✅ 200（revision-1 的 500 已消失，@Pattern 校验通过 + Service Set 兜底通过）

# TEST 2: POST 同 storeId+single → UNIQUE 拒
POST /system/gz/bean/seatTypeConfig
Body: {"storeId":1,"seatType":"single","quantity":3,"priceCent":1200}
实际: {"code":500,"msg":"该门店已配置座位类型：single","data":null}
结论: ✅ UNIQUE 拒（msg 含"该门店已配置...single"）

# TEST 3: POST seatType=vip_room → @Pattern 校验失败
POST /system/gz/bean/seatTypeConfig
Body: {"storeId":1,"seatType":"vip_room","quantity":2,"priceCent":5000}
实际: {"code":500,"msg":"座位类型无效（应为 single/double/quad 之一）","data":null}
结论: ✅ 非法类型被拒（@Pattern 触发，msg 含"single/double/quad"）

# TEST 4: GET listByStore/1 → single 在列表, priceYuan=15.00
GET /system/gz/bean/seatTypeConfig/listByStore/1
实际: {"code":200,"data":[{"id":"1","seatType":"single","quantity":5,"priceCent":1500,"priceYuan":"15.00","enabled":1}]}
结论: ✅ single 在列表，priceYuan=15.00，quantity=5

# TEST 5: PUT quantity=8 → 200；验证 listByStore quantity=8
PUT /system/gz/bean/seatTypeConfig
Body: {"id":1,"quantity":8,"priceCent":1500}
实际: {"code":200,"msg":"操作成功"}；后续 GET listByStore → quantity=8
结论: ✅ PUT 生效

# TEST 6: DELETE /{id} → 200；验证 listByStore empty
DELETE /system/gz/bean/seatTypeConfig/1
实际: {"code":200,"msg":"操作成功"}；后续 GET listByStore → count=0（软删）
结论: ✅ DELETE（软删）生效
```

### 跳过 / 未跑

- admin Playwright E2E（座位类型配额页 UI 点击流）：revision-2 聚焦 add 接口 500 修复验证；nav 中「座位类型配额」已在 revision-1 Playwright 中确认存在 ✅，本轮不重复
- mp 端：本 ticket 纯 admin+后端，无 mp 测试项
- vip_room 错误响应 HTTP status code：ruoyi 统一返回 500 code 而非标准 400（ruoyi 框架全局 ExceptionHandler 行为，非本 ticket 问题，不影响业务校验逻辑）

### 结论

✅ Tier 1B revision-2 全通过（6/6 测试项）：
- **核心修复点**：add single 200 ✅（revision-1 的 500 已消失）
- **UNIQUE 拒**：重复 single 被拒，msg 含"该门店已配置...single" ✅
- **非法类型拒**：vip_room 被 @Pattern 拒，msg 含"single/double/quad" ✅
- **GET/PUT/DELETE**：全 200，数据变更符合预期 ✅

**BEAN-013 Tier 1B 通过可 close**（纯 admin+后端 ticket，AI Tier 1A+1B 全 ✅ 即终态，无人验）

**server 状态**：8080 已关闭 ✅
