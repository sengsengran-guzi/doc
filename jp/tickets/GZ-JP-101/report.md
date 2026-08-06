# GZ-JP-101 完工报告 — 场（gz_jp_event）建表 + admin 场管理

> 新业务模块 `ruoyi-gz-jp` 从零建起。下游 GZ-JP-102 起在本模块内继续加表与端点。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（RuoYi / plus-ui 均在 staging） | ✅ 开工前两仓 `git status` 空 | — |
| 上游依赖 merge | ✅ N/A（`depends_on: []`） | — |
| **menu_id 14000 段空闲** | ✅ | 全部历史迁移 `grep -rhoE "\b1[45][0-9]{3}\b"` → **无输出**；活库 `SELECT MAX(menu_id) FROM sys_menu` → **13053** |
| dict_id / dict_code 空闲 | ✅ | 活库 `MAX(dict_id)=9270` / `MAX(dict_code)=92705`，本 ticket 用 9280 / 92801-92803，928xx 段全空 |
| 迁移时间戳 = 当下真实时间 | ✅ | `date +V%Y%m%d%H%M` → `V202608070202`；已应用最大版本 `V202608062251` → 顺序正常 |
| Flyway append-only 自检 | ✅ | `git status --short -- .../db/migration/` 只有 `??`（新增），无 M/D/R |
| `ruoyi-gz-jp` 模块注册现状 | ❗ **模块不存在** → 本 ticket 建骨架 + 注册进 `ruoyi-modules/pom.xml` 与 `ruoyi-admin/pom.xml` |
| 编译健康（基线） | ✅ `mvn -o compile -pl ruoyi-modules/ruoyi-gz-jp -am` 无输出（-q 静默 = 成功） |
| 权威蓝图已读 | ✅ `field-ssot.yaml` gz_jp_event 段 / `flows.yaml` FLOW:F-JP-01（step1/3/4）/ `ui-index.yaml` UI:admin.event / `verify.sh` L1 契约 |
| ADR | 无相关（doc/jp 无 ADR 目录；本 ticket 沿用既有 gz 模块惯例，无跨 3 文件以上新架构决策） |

### 权威蓝图关键约束摘录（照此实现）

- `FIELD:gz_jp_event.end_time` — 「到点后**读时惰性**判定为已结束，**不依赖 cron**」
- `FLOW:F-JP-01.step4` — 「查询时比对 end_time 实时判定，**并允许店员手动置 closed**」（两条路径都要，不是二选一）
- `FIELD:gz_jp_event.cover_image_id` — 「FK gz_file_object.id（**禁裸 url**）」
- `common_field_blocks` — audit 6 列 + tenant 1 列 = 七件套，`create_dept` 标注「最易漏」
- `UI:admin.event` — 标准 ruoyi CRUD + Dialog；表单含封面 ImageUpload / 起止时间 / 排序号
- `verify.sh` L1 — `/app/gz/jp/event/list` 断言 **`.rows`**（分页体，非 `R<List>`）且不下发 draft

---

## 实现摘要

### 改动文件

```
=== RuoYi-Vue-Plus ===
 M ruoyi-admin/pom.xml                                       | 5 +++++   (注册 ruoyi-gz-jp 依赖)
 M ruoyi-modules/pom.xml                                     | 1 +       (注册 <module>)
 M .../gz/common/enums/GzFileUsageType.java                  | 4 +++-    (加 JP_EVENT_IMAGE)
?? ruoyi-admin/src/main/resources/db/migration/V202608070202__GZ-JP-101-create-gz_jp_event.sql
?? ruoyi-admin/src/main/resources/db/migration/V202608070203__GZ-JP-101-seed-dict-menu.sql
?? ruoyi-modules/ruoyi-gz-jp/                                (新模块，13 个源文件)

=== plus-ui ===
 M src/api/gz-common/file.ts |  3 ++-    (加 JP_EVENT_IMAGE)
 M src/lang/zh_CN.ts         | 51 +++++  (gzJpEvent 命名空间)
 M src/lang/en_US.ts         | 52 +++++  (同上)
?? src/api/gz-jp/event.ts
?? src/views/gz-jp/event/index.vue
```

### 新模块骨架（下游 GZ-JP-102 直接沿用）

```
ruoyi-modules/ruoyi-gz-jp/
├── pom.xml                                  依赖仅 ruoyi-gz-common（传递带全部 ruoyi-common-*）+ spring-boot-starter-test
└── src/main/java/org/dromara/gz/jp/
    ├── controller/GzJpEventController.java              admin  /system/gz/jp/event
    ├── controller/applet/GzJpEventMpController.java     mp     /app/gz/jp/event   (@SaIgnore 匿名可读)
    ├── domain/entity/GzJpEvent.java                     extends TenantEntity
    ├── domain/enums/GzJpEventStatus.java                ★ 读时惰性判定唯一收口点
    ├── domain/bo/{GzJpEventBo, GzJpEventQueryBo}.java
    ├── domain/vo/{GzJpEventAdminVO, GzJpEventMpVO}.java
    ├── mapper/GzJpEventMapper.java                      extends BaseMapperPlus
    └── service/{IGzJpEventService, impl/GzJpEventServiceImpl}.java
```

### 关键实现决策

1. **状态读时惰性判定，零 cron**（FLOW:F-JP-01.step4）
   `GzJpEventStatus.effective(stored, endTime, now)` 是唯一判定点：存库 `closed` 或 `end_time <= now` → 生效状态 `closed`，**不写库**。admin 展示 / admin 筛选 / mp 可见性 / `isBookable()` 全走这一份。`@JobExecutor` 一个都没写 —— prod 未部署 SnailJob，写了也不跑。
   「到点即结束」对 draft 也生效：窗口已过的 draft 既不该开场也不该展示；存库状态不变，店员把 `end_time` 往后调即恢复 draft，无数据丢失。

2. **admin 状态筛选下沉 SQL，不做内存过滤**
   筛 `closed` → `(status='closed' OR end_time <= now)`；筛 `draft`/`open` → `status=? AND end_time > now`。内存过滤会让分页 `total` 失真。

3. **`event_no` 生成含软删行**
   `uk_event_no(tenant_id, event_no)` 覆盖软删行，`@TableLogic` 只过滤业务查询、不放宽唯一约束。`selectMaxEventNoIncludeDeleted` 用裸 `@Select`（不带 del_flag 条件）取当日最大号 + 1。本项目 `gz_bean_booking` 正是漏了这条踩过 409 DuplicateKey。**已实测回归**（自测 §5）。

4. **`@Version` insert 前显式置 0** —— 留 null 会让内存 version 与库里 `DEFAULT 0` 脱节，后续 `updateById` 退化成无乐观锁更新（GZ-BEAN-039 踩过）。

5. **mp 列表返回 `TableDataInfo`（rows + total），不是 `R<List>`** —— `doc/jp/verify.sh` L1 断言 `.rows`。mp VO 额外带 `status`（恒 `open`），让「不下发 draft」可断言。

6. **误关场可重新开场**（stored=closed 但 `end_time > now`）—— 店员误点关场后的唯一补救路径。admin 页按 `status !== 'open'` 显示「开场」，逻辑自洽。

7. **进行中的场禁止删除**，需先关场。

8. **`GzFileUsageType` 加 `JP_EVENT_IMAGE('jp_event_image')`**，前后端枚举同步。

### 菜单 / 字典 / 权限

| menu_id | 类型 | 名称 | path / component | perms |
|---|---|---|---|---|
| 14000 | M | 日本拼团 | `gz-jp` | — |
| 14001 | C | 场管理 | `event` / `gz-jp/event/index` | `gz:jp:event:list` |
| 14002 | F | 场查询 | — | `gz:jp:event:list` |
| 14003 | F | 场新增 | — | `gz:jp:event:add` |
| 14004 | F | 场编辑（含开场 / 关场） | — | `gz:jp:event:edit` |
| 14005 | F | 场删除 | — | `gz:jp:event:remove` |

- 授权：owner(100) 全给；staff(101) 查 / 增 / 改（删除只留 owner）
- 字典 `gz_jp_event_status`：dict_id 9280 / dict_code 92801-92803

---

## AI 自测（Tier 1A）

### 1. 编译 + 单测（14 用例全绿）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpEventStatusTest -Dsurefire.failIfNoSpecifiedTests=false
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.795 s -- in org.dromara.gz.jp.service.impl.GzJpEventStatusTest
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS

$ mvn -o clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-jp -am
[INFO] Installing .../ruoyi-gz-jp/target/ruoyi-gz-jp-5.6.1.jar to ~/.m2/repository/org/dromara/ruoyi-gz-jp/5.6.1/ruoyi-gz-jp-5.6.1.jar
[INFO] ruoyi-gz-jp ........................................ SUCCESS [  0.701 s]
[INFO] BUILD SUCCESS
```

覆盖：`effective` 惰性判定 6 例 / `isBookableForMp` 4 例 / 关场后 mp 不可见 / mp 列表 SQL 条件断言 / mp VO 恒 open / draft 不可见 / 到点 open 不可见 / open draft 成功 / open 窗口已过拒绝 / open 已开拒绝 / 误关重开 / close 重复拒绝 / close 场不存在 / delete 进行中拒绝。

### 2. Flyway 迁移（启动自动跑）

```
o.f.core.internal.command.DbMigrate - Migrating schema `ry-vue` to version "202608070202 - GZ-JP-101-create-gz jp event"
o.f.core.internal.command.DbMigrate - Migrating schema `ry-vue` to version "202608070203 - GZ-JP-101-seed-dict-menu"
o.f.core.internal.command.DbMigrate - Successfully applied 2 migrations to schema `ry-vue`, now at version v202608070203 (execution time 00:00.181s)
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功   ლ(´ڡ`ლ)ﾞ

mysql> SELECT version, script, success FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 4;
202608070203	V202608070203__GZ-JP-101-seed-dict-menu.sql	1
202608070202	V202608070202__GZ-JP-101-create-gz_jp_event.sql	1
202608062251	V202608062251__GZ-SYS-023-alter-gz_user-add-app_id.sql	1
202608062249	V202608062249__GZ-SYS-022-gz_pay_channel-add-client_id.sql	1
```

### 3. DB 结构验证

```
mysql> SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='ry-vue' AND table_name='gz_jp_event'
       AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id');
7

mysql> SELECT menu_id, menu_name, menu_type, parent_id, path, component, perms, visible, status
       FROM sys_menu WHERE menu_id BETWEEN 14000 AND 14009 ORDER BY menu_id;
14000	日本拼团	M	0	gz-jp	NULL				0	0
14001	场管理		C	14000	event	gz-jp/event/index	gz:jp:event:list	0	0
14002	场查询		F	14001			gz:jp:event:list	0	0
14003	场新增		F	14001			gz:jp:event:add		0	0
14004	场编辑		F	14001			gz:jp:event:edit	0	0
14005	场删除		F	14001			gz:jp:event:remove	0	0
```

admin 动态路由确认（`sys_menu.component` ↔ plus-ui `src/views/` 对应，前端零注册）：

```
$ GET /system/menu/getRouters
{ "name": "Gz-jp14000", "path": "/gz-jp", "component": "Layout",
  "meta": { "title": "日本拼团", "icon": "shopping" },
  "children": [ { "name": "Event14001", "path": "event", "component": "gz-jp/event/index",
                  "meta": { "title": "场管理", "icon": "date" } } ] }
```

### 4. API 端到端烟雾测试（真起应用打真库）

```bash
# ── 建场（FLOW step1）→ status=draft
$ POST /system/gz/jp/event  {"name":"8月上旬快闪场","startTime":"2026-08-07 10:00:00","endTime":"2026-09-30 22:00:00","sortNo":1}
{ "code": 200, "msg": "新建成功", "data": 1 }

# ── admin 列表：draft + 业务码自动生成
$ GET /system/gz/jp/event/list
{ "total": 1, "rows": [{ "id": "1", "eventNo": "EVT-20260807-000001", "name": "8月上旬快闪场",
    "status": "draft", "rawStatus": "draft", "sortNo": 1, "version": 0, ... }], "code": 200 }

# ── AC3：未 open 时 mp 侧查不到
$ GET /app/gz/jp/event/list            (clientid: mp-applet-gz-jp，无需登录)
{ "total": 0, "rows": [], "code": 200 }

# ── 开场（FLOW step3）
$ POST /system/gz/jp/event/open/1      →  { "code": 200, "msg": "操作成功" }

# ── 开场后 mp 可见（.rows 分页体 + status 恒 open + 无图回落占位）
$ GET /app/gz/jp/event/list
{ "total": 1, "rows": [{ "id": "1", "eventNo": "EVT-20260807-000001", "name": "8月上旬快闪场",
    "coverImageUrl": "/static/images/mock-product.png", "status": "open",
    "startTime": "2026-08-07 10:00:00", "endTime": "2026-09-30 22:00:00" }], "code": 200 }

# ── ★ accept STATE 现场佐证：关场（FLOW step4 手动分支）后 mp 可下单列表为空
$ POST /system/gz/jp/event/close/1     →  { "code": 200, "msg": "操作成功" }
$ GET  /app/gz/jp/event/list           →  { "total": 0, "rows": [], "code": 200 }
$ GET  /app/gz/jp/event/1              →  { "code": 500, "msg": "该场不存在或已结束" }
```

### 5. 读时惰性判定 + 边界 / 守卫回归（真库）

```bash
# ── 建一个窗口已过的场
$ POST /system/gz/jp/event  {"name":"7月已结束场","startTime":"2026-07-01 10:00:00","endTime":"2026-07-31 22:00:00"}
{ "code": 200, "data": 2 }

# ── DB 里存的仍是 draft（没有任何 cron 改写过它）
mysql> SELECT id,event_no,status,end_time FROM gz_jp_event ORDER BY id;
1  EVT-20260807-000001  closed  2026-09-30 22:00:00.000
2  EVT-20260807-000002  draft   2026-07-31 22:00:00.000     ← 存库 draft

# ── 但读出来的生效状态是 closed（惰性判定）
$ GET /system/gz/jp/event/list
id=1 no=EVT-20260807-000001 status(生效)=closed  rawStatus(存库)=closed
id=2 no=EVT-20260807-000002 status(生效)=closed  rawStatus(存库)=draft   ← 惰性生效

# ── 窗口已过的场不能开场
$ POST /system/gz/jp/event/open/2
{ "code": 500, "msg": "闭场时间已过，请先把闭场时间改到当前时间之后再开场" }

# ── 生效状态筛选下沉 SQL（分页 total 准确）
$ GET /system/gz/jp/event/list?status=closed  → total=2   (含存库 draft 但已到点的那条)
$ GET /system/gz/jp/event/list?status=draft   → total=0

# ── 编辑：篡改 eventNo / status 必须被后端忽略
$ PUT /system/gz/jp/event  {"id":2,"eventNo":"HACK-0001","status":"open","name":"7月已结束场（改名）","sortNo":5,...}
{ "code": 200, "msg": "操作成功" }
mysql> SELECT id,event_no,name,status,sort_no,version FROM gz_jp_event WHERE id=2;
2  EVT-20260807-000002  7月已结束场（改名）  draft  5  1     ← event_no/status 未被篡改，version 自增

# ── 时间窗校验
$ POST /system/gz/jp/event  {"startTime":"2026-09-01 10:00:00","endTime":"2026-08-01 10:00:00"}
{ "code": 500, "msg": "闭场时间必须晚于开场时间" }

# ── 删除守卫：进行中的场不能删
$ DELETE /system/gz/jp/event/1   (此时 id=1 为 open)
{ "code": 500, "msg": "场「8月上旬快闪场」正在进行中，请先关场再删除" }
$ POST /system/gz/jp/event/close/1 && DELETE /system/gz/jp/event/1  →  { "code": 200, "msg": "操作成功" }

# ── ★ 软删后当日再建场，event_no 不得重用（uk_event_no 撞库回归）
mysql> SELECT id,event_no,del_flag FROM gz_jp_event ORDER BY id;
1  EVT-20260807-000001  1      ← 已软删（本项目 logicDeleteValue=1）
2  EVT-20260807-000002  0
$ POST /system/gz/jp/event  {"name":"软删后再建",...}   →  { "code": 200, "data": 3 }
mysql> SELECT id,event_no,name,del_flag FROM gz_jp_event ORDER BY id;
1  EVT-20260807-000001  8月上旬快闪场       1
2  EVT-20260807-000002  7月已结束场（改名）  0
3  EVT-20260807-000003  软删后再建          0     ← 跳过被软删占用的号，未撞 409
```

> 测试数据已 **HARD DELETE 清理**（`DELETE FROM gz_jp_event; ALTER TABLE gz_jp_event AUTO_INCREMENT = 1;`），表回到 0 行，不留脏数据 / 软删残留。

### 6. plus-ui 构建 + 类型 + lint

```
$ npx vue-tsc --noEmit -p tsconfig.json | grep -iE "gz-jp|gzJpEvent|gz-common/file"
（无输出 —— 新增文件 0 类型错误；仓库既有基线 72 个 error 与本 ticket 无关）

$ npx eslint src/views/gz-jp/event/index.vue src/api/gz-jp/event.ts src/lang/zh_CN.ts
（无输出 —— 0 error）

$ npx vite build --mode production
dist/index.html.gz 111.32kb -> 48.39kb    ✓ built
```

> 踩到的类型坑（记给下游）：`src/types/axios.d.ts` 把 `AxiosResponse` 增广成 `{ rows: T; total: number }`，所以分页接口泛型要写 **`AxiosPromise<行元素[]>`**（如 `AxiosPromise<GzJpEventVO[]>`）；写成 `AxiosPromise<{total, rows}>` 会让 `res.rows` 类型错位、vue-tsc 直接报错。

---

## accept 三条结果

| # | form | 结果 | 说明 |
|---|---|---|---|
| 1 | DDL | ✅ **PASS**（exit 0） | 逐字执行 |
| 2 | MENU | ✅ **PASS（ticket 规格已修正）** | 原始断言引用 `sys_menu.del_flag`，ruoyi 的 `sys_menu` 没有这一列（官方基线菜单是物理删）。主线程已去掉 3 处 `del_flag='0'`（语义等价），修正后逐字 EXIT=0 |
| 3 | STATE | ✅ **PASS**（exit 0） | 逐字版炸在上游 `ruoyi-common-core`（已知 `-am` reactor 坑），加 `-Dsurefire.failIfNoSpecifiedTests=false` 重跑通过 |

### accept #2（MENU）ticket 规格 bug —— 已由主线程修正

实现方逐字执行原始输出：

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
    SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14000 AND 14009 AND m.del_flag='0' ..."
ERROR 1054 (42S22) at line 2: Unknown column 'm.del_flag' in 'where clause'
→ EXIT=1
```

根因（与实现无关）：

```
mysql> DESC sys_menu;
menu_id / menu_name / parent_id / order_num / path / component / query_param / is_frame /
is_cache / menu_type / visible / status / perms / icon / create_dept / create_by /
create_time / update_by / update_time / remark          ← 全表 20 列，没有 del_flag

$ grep -A 25 "create table sys_menu" script/sql/ry_vue_5*.sql | grep -i del_flag
（无输出 —— ruoyi 官方基线 sys_menu 本来就没有 del_flag，菜单删除是物理删）
```

**主线程处置**：这是系统性问题，`grep -rl "m.del_flag='0'" doc/jp/tickets/*/prompt.md` 命中 4 个 ticket（本卡 + GZ-JP-102/108/109）。已按 CLAUDE.md §9.5「改权威蓝图/ticket 规格优先」原则，统一去掉这 4 个 ticket prompt.md 里 MENU accept 的 3 处 `del_flag='0'`（语义完全等价，因为 `sys_menu` 不存在软删行）。修正后本卡逐字重跑：

```
$ docker exec ... "SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14000 AND 14009
    AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
       OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
       OR (m.parent_id<>0 AND NOT EXISTS (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)) )" | grep -qx 0 &&
  docker exec ... "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14000 AND 14009" | grep -qE '^[1-9]'
→ EXIT=0        ✅ 菜单 path/component 全非空、父级有效、段内 6 条记录
```

---

## 风险提示 / 已知 issue

1. **`POST /system/gz/jp/event` 返回 `R<Long>`**（`data: 1` 是 number）。与 gz-news / gz-gacha / gz-ord / gz-recycle 全部既有模块一致；VO 里的 id 都已是 string。`gz_jp_event.id` 是 AUTO_INCREMENT（非 snowflake），不会逼近 JS 安全整数；admin 页也不消费该返回值。若要求严格统一成 string，是一处跨 5 模块的一致性改动，**不在本 ticket scope**。
2. **`商品数` 列没做**。`UI:admin.event` 的「商品数」需要 `gz_jp_product`（GZ-JP-102 才建表），本 ticket 无表可查。
3. **迁移是 `[out of order]` 应用的**（Flyway 日志带此标记）。`out-of-order=true` 是本项目既有配置，两条 `success=1`，不影响。
4. **staging / prod 未部署**。只在本地 dev 库验证；上线时 Flyway 自动补跑这 2 条迁移。
5. **权限变更后 admin 需重登**（`sys_role_menu` 新授权走登录时快照）。
6. 本次起过的 `spring-boot:run` 已 kill，8080 已释放，未 commit 任何 git。

---

## 对下游 ticket 的提示

### 给 GZ-JP-102（商品表 + 商品管理）—— 直接沿用本模块骨架

**后端**
- 模块已建好、已注册（两个 pom），**102 不用再动 pom**，直接加类。
- 包名固定 `org.dromara.gz.jp.{controller, controller.applet, domain.entity, domain.enums, domain.bo, domain.vo, mapper, service, service.impl}`。
- 路由前缀：admin `/system/gz/jp/product`，mp `/app/gz/jp/product`。
- 权限串 `gz:jp:product:{list,add,edit,remove}`，三处一致：controller `@SaCheckPermission` / `sys_menu.perms` / plus-ui `v-hasPermi`。
- **menu_id 用 14010 段**（14010 商品管理 C + 14011-14019 按钮 F），parent_id 挂 **14000**（目录已存在，102 不要重建）。下一个空号从 **14006** 起（14000-14005 已占，14006-14009 预留给场的后续按钮）。
- dict：下一个空 `dict_id` 从 **9281** 起，空 `dict_code` 从 **92804** 起。
- **校验「场仍可下单」直接调 `IGzJpEventService.isBookable(eventId)`** —— 已实现、已单测覆盖，不要在 102 重写 end_time 比较。需要场信息用 `selectMpDetail(id)` / `selectAdminById(id)`。
- 商品图 usageType：`JP_EVENT_IMAGE` 是**场封面**专用；商品主图 / 图集请**另加**枚举（如 `JP_PRODUCT_IMAGE("jp_product_image")`），后端 `GzFileUsageType` 与 plus-ui `GZ_FILE_USAGE_TYPE` **必须同时加**，漏一边上传会被后端拒。
- 建表照抄 `V202608070202__...sql`：七件套（**别漏 `create_dept`**）+ `UNIQUE(tenant_id, <业务码>)` + `product_no` 生成器必须用**含软删行**的 `selectMax...IncludeDeleted`。
- `@Version` 字段 **insert 前显式 `setVersion(0)`**。

**Admin 前端**
- `src/views/gz-jp/product/index.vue`（`<script setup lang="ts" name="GzJpProduct">`，`name` 必填，keep-alive 依赖）+ `src/api/gz-jp/product.ts`（types 内联，**不建 types.ts**）。
- 前端**零路由注册**：`sys_menu.component = 'gz-jp/product/index'` 自动映射到 `src/views/gz-jp/product/index.vue`。
- 分页接口泛型写 `AxiosPromise<GzJpProductVO[]>`（**不是** `AxiosPromise<{total, rows}>`）。
- i18n 顶层 key `gzJpProduct`，`zh_CN.ts` + `en_US.ts` **两个都要加**；不写中文字面量。
- 表格用原生 `<el-table>` + `<pagination>`（**本仓不存在 `BizTable`**，CLAUDE.md 那句描述过时）。
- 图片用 `<GzImageUpload v-model="form.xxxImageId" :usage-type="..."/>`（v-model 绑 **fileId 字符串**；ruoyi 原生 `<ImageUpload>` 绑 url，别用错）。
- 时间控件一律 `value-format="YYYY-MM-DD HH:mm:ss"` 绑 `string | null`。
- 状态列 `<dict-tag :options="xxx" :value="row.status"/>` + `proxy?.useDict('gz_jp_product_status')`（要配套 sys_dict 迁移）。

### 给 GZ-JP-104（mp 首页场列表）
- 直接调 `GET /app/gz/jp/event/list?pageNum=&pageSize=`（`@SaIgnore` 匿名可读）。
- 返回 `TableDataInfo`：`{ code, msg, rows, total }`，**mp 读 `res.rows` 不是 `res.data`**。
- 行结构：`{ id(string), eventNo, name, coverImageUrl(1h 预签名，无图/失效回落 /static/images/mock-product.png), description, status(恒 'open'), startTime, endTime }`。
- 详情 `GET /app/gz/jp/event/{id}` 返回 `R<GzJpEventMpVO>`（**这个读 `res.data`**）；不存在 / 未开场 / 已结束一律 `code=500, msg="该场不存在或已结束"`。
- 路由参数建议用 `eventNo` 而非 `id`（业务码优先，与拼豆 `bookingNo` 惯例一致）。
- 「场已结束」是**读时**判定的，mp 端别把场列表缓存太久 —— 到 `end_time` 那一刻服务端立刻不再下发，前端本地缓存会出现「点进去说已结束」的错位；建议进场前重拉详情。

### 给所有 jp 下游 ticket
- **改 `ruoyi-gz-jp` 任何代码后必须 `mvn clean install`**（不是普通 install）：`spring-boot:run -pl ruoyi-admin` 加载 `~/.m2` 里的 jar；非 clean 的 install 既不重打 jar 也不重编译测试，`exit 0` 会骗人。`doc/jp/verify.sh` 的 `guard_fresh()` 会拿源码 mtime 跟 jar 比，不新鲜直接 FAIL。
- 单测类必须 `@Tag("dev")`，否则 surefire `<groups>` 直接跳过，静默「通过」。
- 纯 mock 单测里断言 `LambdaQueryWrapper.getSqlSegment()`，`@BeforeAll` 必须 `TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), ""), Entity.class)` —— 用裸 `org.apache.ibatis.session.Configuration` 拿不到 MP 全局 DbConfig，列名不转下划线，会吐 `endTime` 而不是 `end_time`，断言变成假的。

---

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

Tier 1B 建议覆盖：
- admin Playwright E2E：登录 → 侧边栏「日本拼团 → 场管理」→ 新建场（含封面上传）→ 列表校验 → 编辑 → 开场 → 关场 → 删除 → 权限按钮显隐
- 后端集成：`/system/gz/jp/event/*` 全端点 + `/app/gz/jp/event/*` 契约
- 本 ticket **无 mp 页面**（只有后端 mp 端点），mp 模拟器 E2E 从 GZ-JP-201 起才有覆盖对象
