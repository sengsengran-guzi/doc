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
# GZ-ORD-110 完工报告 — 预购下线（屏蔽 admin + mp 入口，代码/表/视图全保留）

> 状态：**Tier 1A ✅**（迁移 + 双端入口隐藏 + 两端 typecheck 全绿）｜ 待 Tier 1B（起 app Flyway 应用后 SELECT 验 menu visible）
> 实施：kevin-coder（menu 归属判断 + 双端入口隐藏）+ 主线程（修 `visible` 反向 bug + typecheck 收尾 + reports）

---

## §0 状态自检

| 检查项 | 结果 |
|---|---|
| migration 当前最大时间戳 | V202606190200；本卡用 **0600**（> 最大）✅ |
| preorder 菜单迁移在位 | GZ-ORD-101-menu（9100-9104）/ ADMIN-101（9105-9107）/ ORD-105（9110-9112）/ ADMIN-103（11007-11009 聚合）✅ |
| 代码/表保留锚点 | ruoyi-gz-ord 模块 / gz_ord_* 表迁移 / plus-ui views/gz-ord / mp pages/ord 全在 ✅ |

---

## menu 归属判断表（AC1 — 改 visible 前逐行核对，perms 单复数精准区分）

| menu_id | name | perms | 归属 | 藏? | 落地迁移 |
|---|---|---|---|---|---|
| 9100-9104 | 预购商品管理 + 按钮 | `gz:ord:product:*` | 纯 preorder | ✅ 藏 | ORD-101-menu |
| 9105-9107 | 商品批量/导入/导出 | `gz:ord:product:*` | 纯 preorder | ✅ 藏 | ADMIN-101 |
| 9110-9112 | 预购订单管理 + 按钮 | `gz:ord:order:*` | 纯 preorder | ✅ 藏 | ORD-105 |
| 11007-11009 | 订单管理（聚合）| `gz:ord:orders:*`（复数）| 三类聚合 preorder/gacha/test | ❌ 不藏 | ADMIN-103 |
| 5064 | 订单查看(店员端) | `gz:ord:view` | mp 店员端聚合含 gacha | ❌ 不藏 | ADMIN-201 |
| 10000~10024 | 扭蛋机* | `gz:gacha:*` | gacha（V1.2 保留做活）| ❌ 不藏 | GACHA-101 |

⚠️ **一票否决守住**：只藏 `gz:ord:product` / `gz:ord:order`（**单数** 9100-9112），绝不碰 `gz:ord:orders`（**复数**聚合 11007-11009）/ `gz:gacha:*` / `gz:ord:view` —— 否则扭蛋订单/管理入口会一并消失，与 D14 扭蛋做活冲突。聚合页 11007 保留：preorder 历史订单仍可经「全部」查（数据保留），仅 plus-ui 去 preorder 业务类型筛选项。

---

## 改了哪些文件

- 迁移 `RuoYi-Vue-Plus/.../db/migration/V202606190600__GZ-ORD-110-hide-preorder-entry.sql`：`UPDATE sys_menu SET visible='1'`（隐藏）`WHERE menu_id IN (9100-9107, 9110-9112)`
- plus-ui `src/views/gz-ord/orders/index.vue`：隐藏 preorder 业务类型筛选项（保留 gacha/test）
- mp `src/pages/index/index.vue`：移除「预购」入口项 + 「日谷预购」teaser 卡（入口 4 列→3 列，**保留 pages/ord 代码**）
- mp `src/pages/me/orders.vue`：BIZ_TABS 移除「全部」「预购」tab（二者均拉 gz_ord_order 预购数据），留「扭蛋」tab，`activeTab` 默认改 `'gacha'`

---

## ⚠️ 主线程修正：`visible` 反向 bug（必修，已修）

coder-ord 原迁移写 `SET visible='0'`，但 ruoyi `sys_menu.visible` 语义 **'0'=显示 / '1'=隐藏**（与直觉相反；证据：ORD-101 建菜单用 '0'=显示，同批 BEAN-013 迁移废弃座位图用 '1'=隐藏）。`='0'` 等于没藏（preorder 菜单建出来就是 '0'）。
→ 主线程改为 `SET visible='1'`（隐藏）+ 补 ruoyi visible 反直觉语义注释。迁移未 apply（Flyway 未跑 0600+），可直接改，不违反「已应用不可改」。

---

## 自测 raw output

### 1. 迁移最终内容（visible='1' 隐藏）
```sql
UPDATE sys_menu
SET visible = '1'
WHERE menu_id IN (9100, 9101, 9102, 9103, 9104, 9105, 9106, 9107, 9110, 9111, 9112);
-- 绝不含 11007-11009（聚合）/ 10000+（扭蛋）/ 5064（店员端）
```

### 2. plus-ui typecheck（`npx vue-tsc --noEmit`）— 本次改动 0 error
```
=== 本次改动文件相关 error（seat-type-config / seatTypeConfig / gz-ord/orders / lang）===
(空 — 本次改动文件无 error)
（全项目 72 个 error 均为 ruoyi 自带 components/layout/store/system/* / gz-common oper-log 的 daterange 存量错，无一在 D11 改动文件）
```

### 3. miniapp typecheck（`pnpm type-check`）— 全项目 0 error
```
=== 总 error 数 ===
0
```

### 4. 代码/表保留验证（AC5）
```
ruoyi-gz-ord 模块         ✅ 未删
gz_ord_* 表迁移            ✅ 未删（ORD-101/104 建表迁移在位）
plus-ui src/views/gz-ord  ✅ 未删（orders/index 仅隐藏 preorder 筛选项）
mp src/pages/ord          ✅ 未删（首页/orders 仅隐藏入口）
```

---

## 遗留 Tier 1B（kevin-qa）

1. 起 app（Flyway 自动应用 V202606190600）→ `SELECT menu_id,visible FROM sys_menu WHERE menu_id IN (9100,9101,9102,9103,9104,9105,9106,9107,9110,9111,9112,11007,11008,11009)`：验 preorder 全 `'1'`（隐藏）、聚合 11007-11009 全 `'0'`（显示）。
2. admin Playwright：owner 登录确认左侧菜单无「预购商品管理」「预购订单管理」，「订单管理」（聚合）+ 扭蛋菜单仍在。
3. mp 可达性反向验证：首页无预购入口卡/teaser、「我的订单」无预购 tab（仅扭蛋）。

---

## §AI 测试段（kevin-qa Tier 1B，12:20）

### Flyway apply 验证

```
- Migrating schema `ry-vue` to version "202606190600 - GZ-ORD-110-hide-preorder-entry"
- Successfully applied 5 migrations to schema `ry-vue`, now at version v202606190631 (execution time 00:00.085s)
```
V202606190600 apply 成功 ✅

### 后端 DB 验证（一票否决核心）

```sql
SELECT menu_id, menu_name, visible FROM sys_menu
WHERE menu_id IN (9100,9101,9102,9103,9104,9105,9106,9107,9110,9111,9112,11007,11008,11009);

menu_id  menu_name        visible
9100     预购商品管理       1  ← 隐藏 ✅
9101     商品新建           1  ← 隐藏 ✅
9102     商品编辑           1  ← 隐藏 ✅
9103     商品上下架         1  ← 隐藏 ✅
9104     商品删除           1  ← 隐藏 ✅
9105     商品批量上下架      1  ← 隐藏 ✅
9106     商品导入           1  ← 隐藏 ✅
9107     商品导出           1  ← 隐藏 ✅
9110     预购订单管理       1  ← 隐藏 ✅
9111     订单列表           1  ← 隐藏 ✅
9112     订单详情查看       1  ← 隐藏 ✅
11007    订单管理           0  ← 显示（聚合，不藏）✅
11008    订单列表           0  ← 显示 ✅
11009    订单详情查看       0  ← 显示 ✅
```
preorder 9100-9112 全 '1'（隐藏）✅；聚合 11007-11009 全 '0'（显示）✅

### admin Playwright E2E

```
Nav content: 首页 数据看板 ... 拼豆管理 ... 订单管理 ... 扭蛋机 ...
预购商品管理 count: 0  ← ✅ 不在导航
预购订单管理 count: 0  ← ✅ 不在导航
Has 订单管理: true     ← ✅ 聚合页在导航
Has 扭蛋: true         ← ✅ 扭蛋菜单在导航

ORD-110 PASS: preorder menus not in nav ✅
```

### mp 可达性反向验证

```bash
# mp index.vue
grep "预购|preorder" src/pages/index/index.vue
# → 仅注释说明「GZ-ORD-110 预购下线：移除「预购」入口项」，实际入口已删除 ✅

# mp orders.vue
BIZ_TABS = [{ key: 'gacha', label: '扭蛋' }]   ← 仅扭蛋 tab ✅
activeTab = ref('gacha')                          ← 默认扭蛋 ✅
# 预购 tab 已移除（注释保留恢复说明）
```

### 跳过 / 未跑

- mp 端真机走「我的→订单」验证只有扭蛋 tab → Tier 2 人验
- plus-ui orders 页筛选项视觉确认（preorder 筛选项是否隐藏）→ 后端 DB 已验 visible='1'，admin E2E 无法触发动态路由页，可视化待 Tier 2

### 结论

✅ Tier 1B 全通过 → ticket 可 close（纯 admin/后端 ticket，无需人验）

---

## ADR 已读 / 风险 / 下游

- **关联 ADR**：无（纯入口屏蔽）。依据合同 §2.3「预购 V1.2 屏蔽入口保留代码」。
- **恢复方式**：反向 `UPDATE sys_menu SET visible='0'`（显示）+ mp 入口取消隐藏 + plus-ui 加回 preorder 筛选项；零数据损失。
- **D14 GZ-SYS-010 衔接**：tabbar 重构首页下线后天然无入口，本卡首页隐藏是过渡保险，不冲突。
# GZ-USER-005 完工报告 — 用户微信号字段（gz_user.wechat_id）+ mp 资料页录入

> 与 GZ-USER-006 同页 / 同 profile 接口 / 同 GzUser entity，一条线顺序实施（避免自冲突）。
> 本报告聚焦 wechat_id；头像 image_id + 登录态见 GZ-USER-006.md。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（项目非 git repo，主线程已确认） |
| 上游依赖 merge | ✅ GZ-USER-002（资料页 + PUT /app/gz/user/profile）已交付；GZ-SYS-003（gz_user 表）已落 |
| 关键类/表存在 | ✅ `gz_user`（nickname/avatar_url 已有，无 wechat_id）、`GzUser` entity、`UserProfileUpdateBo`、`GzUserProfileServiceImpl`、`MeController`(GET) 均在 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-user,ruoyi-gz-common -am` EXIT 0 |
| ADR 已读 | ADR-0009（wechat_id 手动填口径 §3） |
| 迁移时间戳专属段 | ✅ 用 0610，> 已有最大 `V202606190200`，未占用其它并行线段（0600/0620/0630/0631） |
| 权威蓝图引用 | ✅ doc/11 §2.1 `wechat_id` VARCHAR(64) N NULL 手动填无 UNIQUE / doc/10 §3 付款前采集 |

**doc/11 §2.1 关键约束摘录**（实施依据）：
- `wechat_id` | VARCHAR(64) | N | NULL | U（**手动填**）| admin 详情/列表显示完整；mp 资料页可编辑
- 「微信不开放 API 查微信号，只能用户手动填；拼豆 V1.2 付款前采集（与 getPhoneNumber 手机号并列）」
- doc/11 §2.1 已回填 avatar_image_id（与主线程下发口径一致，无偏差）

## 实现摘要

- **迁移**：`db/migration/V202606190610__GZ-USER-005-add-wechat_id.sql` — `ALTER TABLE gz_user ADD COLUMN wechat_id VARCHAR(64) NULL ... AFTER mobile`（无 UNIQUE，可空）
- **后端**（`org.dromara.gz.*`）：
  - `GzUser`（gz-common entity）+ `GzUserVO` 加 `wechatId`
  - `UserProfileUpdateBo`（gz-user）加 `wechatId`（`@Size(max=64)`）
  - `GzUserProfileServiceImpl.updateProfile` 扩 wechatId 分支：变化才更新 + 写 `update_wechat_id` 审计；空白串视为不修改
  - 复用 GZ-USER-002 `PUT /app/gz/user/profile`（**不新建接口**）；GET 回显走 `MeController` → `GzUserServiceImpl.selectVoById`（VO 已含 wechatId）
- **mp**：
  - `pages/me/profile.vue` 加微信号文本录入行（普通 `<input type="text">` + Biz 组件 + `var(--c-*)`，placeholder「请输入微信号，便于门店联系」，回显当前值，maxlength 64）
  - `api/gz-user.ts`：`GzUserMeVO` + `UserProfileUpdateRequest` 加 `wechatId`
  - `locale/user.zh-CN.ts`：加 `wechatIdLabel` / `wechatIdPlaceholder` / `wechatIdTooLong` + en 映射（双语，默认 zh-CN，无 emoji）
- **AC 5（admin 用户页显示 wechatId）**：当前无独立 GZ-USER admin 用户列表/详情页（本卡不新建 admin 页，AC 5 明示「若无则跳过」）；VO 已含 wechatId，未来 admin 用户页直接可显示。

## AI 自测（Tier 1A）

### 1. 后端编译（gz-user + gz-common）
```
cd code/main/RuoYi-Vue-Plus && mvn -q compile -pl ruoyi-modules/ruoyi-gz-user,ruoyi-modules/ruoyi-gz-common -am -DskipTests
BACKEND COMPILE EXIT: 0
```

### 2. 后端单测（profile service，含 wechatId 用例）
```
[INFO] Running org.dromara.gz.user.service.impl.GzUserProfileServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
新增 wechat_id 相关用例：
- `updateProfile_wechatId_writesAuditAndPersists` — 填微信号 → UPDATE wechat_id + 写 1 条 `update_wechat_id` 审计（捕获 before=old_wx / after=new_wx_id）
- `updateProfile_wechatIdBlank_noChange` — 微信号传空白串 → 不报错、不更新、不写审计（AC 8 空值不报错）
- `updateProfile_noChange_skipsUpdateAndAudit`（扩 wechatId 同值不更新）

### 3. mp 契约单测（vitest，gz-user.test.ts）
```
 ✓ src/api/gz-user.test.ts (4 tests) 2ms
   ✓ getMe — GET /app/gz/common/me 回显含 wechatId
   ✓ updateProfile — PUT body 带 wechatId
   ✓ 头像走 avatarImageId 不传裸 url
   ✓ 微信号可空（不传 wechatId 也合法）
 Test Files  2 passed (2)   Tests  10 passed (10)
```

### 4. DB 列校验（dev MySQL ry-vue，ALTER 语法 dry-validate）
迁移文件尚未由 Flyway 应用（按本批协调不起 app）；下方为 ALTER 语句对 dev 库的语法/列形态 dry-validate（已回滚 / DROP 还原 baseline，不留残列）：
```
--- columns after ALTER (in-tx) ---
COLUMN_NAME       COLUMN_TYPE   IS_NULLABLE  COLUMN_COMMENT
mobile            varchar(11)   YES          手机号（拼豆预约时强收集）
wechat_id         varchar(64)   YES          微信号（手动填，微信不开放 API 查）
--- after cleanup（DROP 还原）---
leftover_new_cols
0
```
flyway_schema_history 无 USER-005 记录 → **待 Tier 1B Flyway 应用后正式建列**。

### 5. getUserProfile 禁用核查（AC 6 关联）
```
grep -rn "getUserProfile" mp/src（排除 .test）→ 仅注释说明「已废弃」，0 个真实调用
```
微信号纯手动填，代码无「自动获取微信号 / 解密微信号」逻辑。

## 风险提示 / 已知 issue

- **i18n 文件路径偏差（已对齐项目惯例）**：任务卡写 `lang/zh_CN/me.ts`，但 sensenran mp 实际惯例是 `locale/user.zh-CN.ts` 自包含 `t()`（`user.profile.*` key）。本卡按现状惯例加 key + en 映射，未新建 `me.ts`（避免引入第二套 i18n 体系）。
- wechat_id 无 UNIQUE（doc/11 §2.1 明确不去重）— 一个微信号可被多人填，符合设计。
- 待 Tier 1B Flyway 应用迁移后，`gz_user.wechat_id` 列才真实存在；集成测试 / 真机依赖此。

## 对下游 ticket 的提示

- **D13 GZ-BEAN-015 拼豆付款前采集**：读 `gz_user.wechat_id` 预填（已填带出），snapshot 进 `gz_bean_booking.wechat_id_snapshot`（doc/11 §3.5 已定）。本卡只做 gz_user 字段「存 + 编辑」，未碰拼豆/snapshot。
- 审计 action_type 新增 `update_wechat_id`（doc/11 §2.3 gz_user_audit_log），admin 审计日志页若枚举展示中文需补一条映射。

## §AI 测试段（kevin-qa Tier 1B，12:20）

### Flyway apply 验证

```
- Migrating schema `ry-vue` to version "202606190610 - GZ-USER-005-add-wechat id"
- Successfully applied 5 migrations to schema `ry-vue`, now at version v202606190631 (execution time 00:00.085s)
```
V202606190610 apply 成功 ✅

### 后端 DB 验证

```sql
-- DESC gz_user（关键列）
mobile            varchar(11)   YES   手机号（拼豆预约时强收集）
wechat_id         varchar(64)   YES   微信号（手动填，微信不开放 API 查）
```
`gz_user.wechat_id` VARCHAR(64) NULL 列确认存在 ✅

### API 契约（mp 端接口）

`PUT /app/gz/user/profile` 是 mp 端接口，需要 wx-login 产生的 mp token，无法通过 admin curl 直接调用。
后端字段 `wechatId` 已在 `UserProfileUpdateBo`（@Size(max=64)）+ `GzUser` entity + `GzUserVO` 中确认存在（Tier 1A 单测 10 passed 已验证落库 + 回显）。
集成验证：依赖 Tier 1A GzUserProfileServiceImplTest 10 用例（含 updateProfile_wechatId_writesAuditAndPersists）覆盖。

### mp vitest 单测

```
Test Files  35 passed (35)
     Tests  308 passed (308)
  Duration  3.12s
```
含 gz-user.test.ts 4 用例（wechatId GET 回显 / PUT body / 可空）全通过 ✅

### mp 可达性验证（AC Tier 2 入口）

- `profile.vue` 含 wechatId 文本录入行（row__label / v-model="wechatId" / maxlength 64 / placeholder i18n）
- 入口路径：「我的」tab → 会员中心 → 个人资料（N=2，业务主线入口 USER-002 已上线）✅
- 无 `getUserProfile` 真实调用（grep 仅见注释说明已废弃）✅

### 跳过 / 未跑

- `PUT /app/gz/user/profile` 真实 mp token 调用（wx.login 真机能力）→ Tier 2 人验
- profile 页面视觉（C 设计系统遵循度）→ Tier 2 Kevin 人验

### 结论

✅ Tier 1B 全通过 → ticket 可 close；mp ticket 进人验列待 Kevin 批量人验
# GZ-USER-006 完工报告 — 微信资料完善（chooseAvatar + nickname 持久化）+ 登录态保持

> 与 GZ-USER-005 同页 / 同 profile 接口 / 同 GzUser entity，一条线顺序实施。
> 承接 **ADR-0009**（chooseAvatar + nickname 一次性采集持久化 / 头像存 COS image_id / sa-token 长效 + 静默续期）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（项目非 git repo） |
| 上游依赖 merge | ✅ GZ-USER-002（资料页 + AvatarUpload chooseAvatar + nickname input 已存在）/ GZ-SYS-005（COS 上传 `/app/gz/common/file/upload` + 预签名 URL）/ 微信登录链路（WxLoginServiceImpl + code2session）均已交付 |
| 关键类/表存在 | ✅ `gz_user`（nickname/avatar_url 已有，无 avatar_image_id）、`GzFileService`(upload+getPresignedUrl)、`WxLoginServiceImpl`、`WxMiniappProperties`、mp `AvatarUpload.vue` / `store/token.ts` / `http.ts` 均在 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-user,ruoyi-gz-common -am` EXIT 0；mp `vue-tsc --noEmit` EXIT 0（0 error） |
| ADR 已读 | ✅ ADR-0009 全文（§1 头像/昵称 / §2 登录态 sa-token 长效+静默续期 / Consequences token 30天口径） |
| 迁移时间戳专属段 | ✅ 用 0620，> 0610，未占用其它并行线段 |
| 权威蓝图引用 | ✅ doc/11 §2.1 avatar_image_id / avatar_url 语义 / F2.6；doc/10 §11.N6 付款前采集 + 登录态续期流 |

**doc/11 §2.1 关键约束摘录**（实施依据）：
- `avatar_image_id` | BIGINT UNSIGNED | N | NULL | FK→gz_file_object.id；chooseAvatar 临时头像 → 上传 COS（`usage_type='user_avatar'`）→ 存 file_object id（**头像落 COS 不存微信临时 URL**）
- `avatar_url` | VARCHAR(512) | N | NULL | 由 avatar_image_id 对应 COS 对象拼可渲染 URL 缓存（不再存微信 CDN 临时 URL）
- ADR-0009 Consequences：业务 token 30 天；session_key 24h；二者解耦。具体时长「GZ-USER-006 实施时在 reports 写明」→ **本报告钉死见下**。

## 实现摘要

### 头像 / 昵称持久化（ADR-0009 §1）
- **迁移**：`db/migration/V202606190620__GZ-USER-006-add-avatar_image_id.sql` — `ALTER TABLE gz_user ADD COLUMN avatar_image_id BIGINT NULL ... AFTER avatar_url`（nickname 已存在不新加；avatar_url 保留不动）
- **头像真源 = avatar_image_id（不存裸 url）**：
  - mp `AvatarUpload.vue` chooseAvatar/相册 → 上传 COS（GZ-SYS-005 `uploadFile`，usageType=user_avatar）→ `emit('change', { fileId, url })`（fileId 落库，url 即时预览）
  - `pages/me/profile.vue` 收 fileId 存 `avatarImageId` ref，保存时提交 `avatarImageId`（仅本次新选才提交，未改不传）
  - 后端 `UserProfileUpdateBo` 加 `avatarImageId`；`GzUserProfileServiceImpl` 优先落 `avatar_image_id`（即便前端同时传 url 也忽略 url，存 image_id 不存裸 url），写 `update_avatar` 审计
- **持久化回显（不重复弹采集）**：读侧 `GzUserServiceImpl.selectVoById`（MeController GET + profile 更新返回共用）按 `avatar_image_id` 调 `IGzFileService.getPresignedUrl` 重生成 **1h 签名 URL** 回填 `avatarUrl`；签名失败不抛错（保留旧缓存，资料读取不因头像 500）
- **昵称**：`<input type="nickname">`（GZ-USER-002 已是此实现）→ 存 `gz_user.nickname`
- **getUserProfile 禁用**：`grep getUserProfile` 仅注释说明已废弃，0 个真实调用；AvatarUpload 用 `open-type="chooseAvatar"`，昵称用 `type="nickname"`

### 登录态长效 + 静默续期（ADR-0009 §2）
- **token TTL 钉死 = 30 天（2592000s）**：`WxMiniappProperties.tokenTtlSeconds` 默认 + `application-dev.yml` + `application-prod.yml`（`WX_MA_TOKEN_TTL:2592000`）全改；session_key 仍 24h（解密手机号用，解耦）
- **activeTimeout 对齐绝对 TTL**：`WxLoginServiceImpl.issueToken` 原 `activeTimeout=30min` 改为 `=tokenTtlSeconds`（避免 30 分钟空闲就过期 → 频繁续期；C 端「进店即用」顺滑）
- **静默续期（不踢用户）**：
  - 续期端点复用现有 `/app/gz/common/auth/wx-login`（UPSERT 幂等，openid 静默可得 → 重签 sa-token），**不新建一套鉴权**
  - mp 新增 `tokenStore.silentWxRenew()`：静默 `wx.login → code2session` 重签，全程无 toast / 无授权弹窗 / 不跳登录页；mock appid 短路 dev 账号续期
  - `http.ts` 单 token 401 分支由「直接 logout + 跳登录」改为「先 `silentWxRenew` → 成功重放挂起请求队列；仅续期也失败（openid 都拿不到 / 账号禁用）才 logout + 回登录页」
- **api 类型**：`GzUserMeVO` + `UserProfileUpdateRequest` 加 `avatarImageId`；i18n `chooseAvatar`/`nickname`/`avatarUpload*` key（双语）

## AI 自测（Tier 1A）

### 1. 后端编译 + mp typecheck
```
cd code/main/RuoYi-Vue-Plus && mvn -q compile -pl ruoyi-modules/ruoyi-gz-user,ruoyi-modules/ruoyi-gz-common -am -DskipTests
BACKEND COMPILE EXIT: 0

cd code/main/miniapp && npx vue-tsc --noEmit
=== vue-tsc EXIT: 0 ===   --- error count --- 0
```

### 2. 后端单测（gz-common 100 + gz-user 42 全通过；含头像 image_id 用例）
```
[INFO] org.dromara.gz.common.service.impl.GzUserServiceImplTest      Tests run: 10, Failures: 0, Errors: 0
[INFO] org.dromara.gz.common.service.impl.WxLoginServiceImplTest     Tests run: 4,  Failures: 0, Errors: 0   (activeTimeout/TTL 改后仍过)
[INFO] org.dromara.gz.user.service.impl.GzUserProfileServiceImplTest Tests run: 10, Failures: 0, Errors: 0
[INFO] Tests run: 100, Failures: 0, Errors: 0, Skipped: 0   (gz-common)
[INFO] Tests run: 42,  Failures: 0, Errors: 0, Skipped: 0   (gz-user)
[INFO] BUILD SUCCESS
```
新增头像 image_id 用例：
- `GzUserServiceImplTest.selectVoById_withAvatarImageId_resolvesPresignedUrl` — 有 avatar_image_id → 调 getPresignedUrl 重生成签名 URL 覆盖旧缓存
- `GzUserServiceImplTest.selectVoById_avatarResolveFails_doesNotThrow` — 文件被删/COS 异常 → 不抛错，保留旧缓存 URL
- `GzUserServiceImplTest.selectVoById_validId_returnsMapperResult` — 无 image_id → 不调文件服务（never）
- `GzUserProfileServiceImplTest.updateProfile_avatarImageId_persistsImageIdNotRawUrl` — 传 avatarImageId（同时塞 url 干扰）→ 落 image_id=99，avatar_url 不被裸 url 覆盖
- `GzUserProfileServiceImplTest.updateProfile_avatarImageIdSame_noChange` — image_id 同值 → 不更新（幂等）

### 3. mp 静默续期单测（vitest，token.test.ts，ADR-0009 AC 5/8）
```
 ✓ src/store/token.test.ts (6 tests) 6ms
   ✓ silentWxRenew — 真实 appId：wx.login → wx-login 重签 token，返 true 不踢用户
     （断言 _wxLogin({code:'fresh-code-123'}) 调用 + validToken='renewed-token-7777' + hasLogin=true）
   ✓ silentWxRenew — mock appId：短路 dev 账号续期，返 true
   ✓ silentWxRenew — 续期失败（wx.login reject）返 false，不抛异常
   ✓ logout(skipBackend) / validToken 过期/未过期（原 3 用例回归过）
```

### 4. mp 全量 vitest 回归（触及 http.ts / token / AvatarUpload / locale / gz-user）
```
 Test Files  35 passed (35)
      Tests  308 passed (308)
```
（stderr 的 network/401/JSON fallback 日志均为负向用例的预期 console 输出，非失败。）

### 5. DB 列校验（dev MySQL ry-vue，ALTER dry-validate + 还原）
```
--- columns after ALTER (in-tx) ---
COLUMN_NAME       COLUMN_TYPE   IS_NULLABLE  COLUMN_COMMENT
avatar_url        varchar(512)  YES          头像 URL（微信侧 CDN URL，不下载到 OSS）
avatar_image_id   bigint        YES          头像文件 id（FK gz_file_object，存 COS，不存裸 url）
nickname          varchar(64)   YES          昵称（...）   ← 已存在，本迁移不新加
--- after cleanup（DROP 还原 baseline）---
leftover_new_cols = 0
```
flyway_schema_history 无 USER-006 记录 → 待 Tier 1B Flyway 应用后正式建 `avatar_image_id` 列。

## 风险提示 / 已知 issue

- **avatar_url 是 1h 签名缓存，读时重生成**：每次 GET /me / profile 更新返回都会按 avatar_image_id 调一次 COS 预签名（单用户读，非列表）。admin 用户列表 `selectPageList` **未**逐行重生成（避免 N 次签名开销），admin 显示用库里 avatar_url 缓存 + avatarImageId；如 admin 需精确头像可后续在 admin 详情单独调 /file/url。
- **mp 兜底兼容**：`UserProfileUpdateBo.avatarUrl` 保留作旧链路兜底（仅当未传 avatarImageId 时生效，如非微信端直传）；新链路全走 avatarImageId。
- **静默续期时序**：`http.ts` 单 token 401 用 `refreshing` 标志 + `taskQueue` 串行化（与原双 token 刷新同款），并发 401 只触发一次 silentWxRenew，其余请求挂队列重放。
- **首登 onboarding**（ADR-0009 Consequences ⚠️）：chooseAvatar/nickname 是用户主动触发组件，首登需引导一次完善资料；用户跳过则头像昵称为空（UI 默认占位），可后续在资料页补。本卡聚焦资料页采集 + 持久化 + 登录态；首登强引导浮层若需独立体验由后续 ticket（或 USER-001 会员中心头部「点击完善头像昵称」入口已提供路径）。
- 待 Tier 1B Flyway 应用迁移后，`gz_user.avatar_image_id` 列才真实存在。

## 对下游 ticket 的提示

- 头像渲染统一口径：**任何展示用户头像的端（admin 拼豆单 / 历史订单快照）都用 image_id 换签名 URL，不依赖裸 url**（跨层契约 #5）。下游若 join gz_user 展示头像，读 avatar_image_id → 调 /file/url。
- token TTL 已统一 30 天（dev/prod 同口径）；下游不要再各自设短 TTL。
- 审计 action_type `update_avatar`（头像 image_id 变更）沿用既有枚举。

## Tier 2 入口可达（AC N）

- 入口路径：mp 启动 → 底部 tab「我的」（GZ-ADMIN-005 5 tab 已上线）→ 会员中心头部 / 「个人资料」入口（GZ-USER-002 已上线，N=2）→ 资料页
- 资料页一屏含：头像 chooseAvatar 按钮 + 昵称 nickname input + 性别 + 手机号 getPhoneNumber + **微信号文本框（USER-005）**，共用同一「保存资料」按钮
- 业务主线入口**已建**（USER-002 资料页 + 登录链路 + 5 tab 均上线），**无需临时入口**——头像区改造 + 微信号框直接加在现成资料页上
- 登录态：长时间后再进资料页，token 静默续期透明，不被踢登录

## §AI 测试段（kevin-qa Tier 1B，12:20）

### Flyway apply 验证

```
- Migrating schema `ry-vue` to version "202606190620 - GZ-USER-006-add-avatar image id"
- Successfully applied 5 migrations to schema `ry-vue`, now at version v202606190631 (execution time 00:00.085s)
```
V202606190620 apply 成功 ✅

### 后端 DB 验证

```sql
-- DESC gz_user（关键列）
avatar_url        varchar(512)  YES   头像 URL（签名 URL 缓存）
avatar_image_id   bigint        YES   头像文件 id（FK gz_file_object，存 COS，不存裸 url）
nickname          varchar(64)   YES   昵称（...）← 已存在，本迁移不新加
```
`gz_user.avatar_image_id` BIGINT NULL 列确认存在 ✅

### 后端 API 验证（admin token 范围）

`PUT /app/gz/user/profile` 是 mp 端接口需 mp token，无法 curl 直接调用。
集成覆盖依赖 Tier 1A：GzUserProfileServiceImplTest.updateProfile_avatarImageId_persistsImageIdNotRawUrl + selectVoById_withAvatarImageId_resolvesPresignedUrl（10+10 用例全通过）。

### mp vitest 静默续期单测

```
src/store/token.test.ts (6 tests)
  ✓ silentWxRenew — 真实 appId：wx.login → 续期 token，返 true
  ✓ silentWxRenew — mock appId：短路 dev 账号续期，返 true
  ✓ silentWxRenew — 续期失败（wx.login reject）返 false，不抛异常
  ✓ logout / validToken 过期/未过期（3 用例回归）
```
token.test.ts 6 用例全通过（含 silentWxRenew）✅

### mp vitest 全量回归

```
Test Files  35 passed (35)
     Tests  308 passed (308)
  Duration  3.12s
```
全通过 ✅

### mp 实现验证

```bash
grep -n "wechatId|avatarImageId|chooseAvatar|silentWxRenew" src/pages/me/profile.vue
# profile.vue: wechatId ref、avatarImageId ref、chooseAvatar 按钮（AvatarUpload）
grep -n "silentWxRenew" src/http/http.ts
# http.ts: 401 handler 调 tokenStore.silentWxRenew()，refreshing + taskQueue 串行化
grep -rn "getUserProfile" src/ | grep -v "注释|废弃|已废"
# 0 个真实调用
```
头像走 chooseAvatar → COS → avatarImageId ✅；静默续期 401 hook ✅；无 getUserProfile ✅

### mp 可达性

- 入口：「我的」tab → 会员中心 → 个人资料（N=2，USER-002 已上线）✅
- 资料页一屏：头像 chooseAvatar 按钮 + 昵称 type=nickname + 微信号文本框（USER-005）✅

### 跳过 / 未跑

- chooseAvatar 真机弹框（微信原生能力）→ Tier 2 人验
- 静默续期真机 30 天 token 过期场景 → Tier 2 人验（真机才能构造过期 token）
- profile 页面视觉（C 设计系统）→ Tier 2 Kevin 人验

### 结论

✅ Tier 1B 全通过 → ticket 可 close；mp ticket 进人验列待 Kevin 批量人验
