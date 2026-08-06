# GZ-JP-102 完工报告 — 商品（gz_jp_product）建表 + admin 商品管理

> 在 GZ-JP-101 建好的 `ruoyi-gz-jp` 模块内继续加表与端点，**未动任何 pom**。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（RuoYi / plus-ui 均在 staging） | ✅ | 开工前两仓 `git status --short` 空输出 |
| **上游 GZ-JP-101 已 merge** | ✅ | `b1f1ecedb D3/GZ-JP-101: 场（gz_jp_event）建表 + admin 场管理`；活库 `gz_jp_event` 表存在、`sys_menu` 14000 目录存在 |
| `gz_file_object` + OSS 上传链路可用 | ✅ | 表存在，5 行历史文件（gacha/recycle/avatar 各场景），`GzImageUpload` 走 `/system/gz/file/upload` 既有链路 |
| **menu 14010 段空闲** | ✅ | `SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14010 AND 14019` → **0**；`MAX(menu_id)` → **14005** |
| dict_id / dict_code 空闲 | ✅ | `MAX(dict_id)=9280` / `MAX(dict_code)=92803` → 本卡用 **9281 / 92804-92805** |
| 迁移时间戳 = 当下真实时间 | ✅ | `date +V%Y%m%d%H%M` → `V202608070232`；已应用最大 `V202608070203` |
| Flyway append-only 自检 | ✅ | migration 目录 `git status --short` 只有 `??`（新增 2 个），**无 M/D/R** |
| 编译健康（基线） | ✅ | `mvn -o compile -pl ruoyi-gz-jp,ruoyi-gz-common -am` → EXIT=0 |
| 权威蓝图已读 | ✅ | field-ssot gz_jp_product 段 / flows F-JP-01.step2 / ui-index admin.product / requirements REQ-PROD-001~007 |
| ADR | 无相关（doc/jp 无 ADR 目录；沿用 101 骨架与跨层契约，无新架构决策） |

### 权威蓝图关键约束摘录

- `FLOW:F-JP-01.step2` —「在场内逐个上架商品 / **produces: 商品 status=on_shelf；未开场时仍不可见**」→ 建商品**不要求场已 open**；可见性在读侧用派生字段表达。
- `FIELD:gz_jp_product.notice_text` —「甲方明确要求的独立字段，下单前须显著展示，**不混进图集**」。
- `FIELD:gz_jp_product.price_cent` —「★ **全包邮**，此价即客人最终支付价，不叠加运费」。
- `FIELD:gz_jp_product.status` —「★ 一期**无库存字段**」→ accept #2 断言 `stock%` 列数为 0。
- `main_image_id` nullable=false，FK `gz_file_object.id`（**禁裸 url**）；`gallery_image_ids` 逗号分隔，**一期用图集承载详情不做富文本**。
- `REQ-PROD-007`（deferred）— Kevin 拍板一期不做多规格，**甲方未表态**，反悔属结构性返工（波及 102+105）。
- `UI:admin.product` — 顶部按场筛选；列：编号/主图/名称/所属场/价格/预计到货/状态/操作；多选批量上下架；表单含注意事项；不做 Excel 导入导出。
- `common_field_blocks` — 七件套，`create_dept` 标注「最易漏」。

---

## 实现摘要

### 改动文件

```
=== RuoYi-Vue-Plus ===
 M ruoyi-modules/ruoyi-gz-common/.../enums/GzFileUsageType.java         |  4 ++-  (加 JP_PRODUCT_IMAGE)
 M ruoyi-modules/ruoyi-gz-jp/.../service/IGzJpEventService.java         | 27 +++++ (加 selectOptions/selectOptionMap)
 M ruoyi-modules/ruoyi-gz-jp/.../service/impl/GzJpEventServiceImpl.java | 42 +++++ (同上实现 + toOptionVO)
?? ruoyi-admin/src/main/resources/db/migration/V202608070232__GZ-JP-102-create-gz_jp_product.sql
?? ruoyi-admin/src/main/resources/db/migration/V202608070233__GZ-JP-102-seed-dict-menu.sql
?? ruoyi-modules/ruoyi-gz-jp/.../controller/GzJpProductController.java
?? ruoyi-modules/ruoyi-gz-jp/.../domain/entity/GzJpProduct.java
?? ruoyi-modules/ruoyi-gz-jp/.../domain/enums/GzJpProductStatus.java
?? ruoyi-modules/ruoyi-gz-jp/.../domain/bo/{GzJpProductBo,GzJpProductQueryBo,GzJpProductStatusBo}.java
?? ruoyi-modules/ruoyi-gz-jp/.../domain/vo/{GzJpProductAdminVO,GzJpEventOptionVO}.java
?? ruoyi-modules/ruoyi-gz-jp/.../mapper/GzJpProductMapper.java
?? ruoyi-modules/ruoyi-gz-jp/.../service/IGzJpProductService.java
?? ruoyi-modules/ruoyi-gz-jp/.../service/impl/GzJpProductServiceImpl.java
?? ruoyi-modules/ruoyi-gz-jp/src/test/.../GzJpProductServiceTest.java   (20 用例)

=== plus-ui ===
 M src/api/gz-common/file.ts |  3 ++-  (加 JP_PRODUCT_IMAGE，与后端枚举同步)
 M src/lang/zh_CN.ts         | 66 ++++ (gzJpProduct 命名空间)
 M src/lang/en_US.ts         | 66 ++++ (同上)
?? src/api/gz-jp/product.ts
?? src/views/gz-jp/product/index.vue
```

### 关键实现决策

1. **新建即 `off_shelf`，上架是显式动作** —— 上/下架只走 `POST /product/status`，普通 PUT 改不了 status（同 101 场 open/close 口径）。
2. **★ 建商品不要求场已开场，可见性在读侧派生** —— FLOW 正常顺序是 建场(draft)→上架→开场，所以**没有**用 `isBookable` 卡门，只校验「场存在」。admin VO 增派生字段 `visibleToCustomer = 商品 on_shelf && 场生效状态 open`，列表给「已上架但场没开」的行打黄色警示 icon，直接消解店员最易困惑的一格。
3. **场信息批量回填，不做 N+1** —— 给 `IGzJpEventService` 加 `selectOptionMap(Collection<Long>)`。**场的读时惰性判定仍只有一处实现**（`GzJpEventStatus.effective`），商品侧一行 end_time 比较都没写。
4. **`product_no` 生成含软删行** —— `selectMaxProductNoIncludeDeleted` 裸 `@Select`（不带 del_flag），否则「当日上架→软删→当日再上架」撞 `uk_product_no` 409。已实测回归（§5）。
5. **`@Version` insert 前显式置 0**（GZ-BEAN-039 教训）。
6. **图集 = 逗号分隔 file id 串**（同 `gz_recycle_appointment.verify_image_ids`），入/出参 `List<Long>`，service 层 join/split，脏数据片段跳过并 WARN；上限 9 张。
7. **价格单位统一「分」** —— admin 填「元」→ `Math.round(yuan*100)`；下限 1 分（0 元单微信支付走不通），上限 ¥999,999.99（防手滑多打 0）。
8. **`/event-options` 挂商品权限而非场权限** —— 商品页只依赖 `gz:jp:product:*`；下拉标签带「（进行中/未开始/已结束）」后缀，避免挂到已结束的场。
9. **删除守卫**：已上架不可删，需先下架（同场「进行中不可删」）。
10. **`GzFileUsageType.JP_PRODUCT_IMAGE`** 后端枚举 + plus-ui `GZ_FILE_USAGE_TYPE` 同步加。

### 菜单 / 字典 / 权限

| menu_id | 类型 | 名称 | path / component | perms |
|---|---|---|---|---|
| 14010 | C | 商品管理（parent=14000，**目录复用不重建**） | `product` / `gz-jp/product/index` | `gz:jp:product:list` |
| 14011 | F | 商品查询 | — | `gz:jp:product:list` |
| 14012 | F | 商品新增 | — | `gz:jp:product:add` |
| 14013 | F | 商品编辑（含批量上下架） | — | `gz:jp:product:edit` |
| 14014 | F | 商品删除 | — | `gz:jp:product:remove` |

- 授权：owner(100) 全给；staff(101) 查/增/改（删除只留 owner）
- 字典 `gz_jp_product_status`：dict_id 9281 / dict_code 92804(on_shelf) + 92805(off_shelf)

### admin 端点

| Method | Path | perms |
|---|---|---|
| GET | `/system/gz/jp/product/list` | `gz:jp:product:list` |
| GET | `/system/gz/jp/product/event-options` | `gz:jp:product:list` |
| GET | `/system/gz/jp/product/{id}` | `gz:jp:product:list` |
| POST | `/system/gz/jp/product` | `gz:jp:product:add` |
| PUT | `/system/gz/jp/product` | `gz:jp:product:edit` |
| POST | `/system/gz/jp/product/status` | `gz:jp:product:edit` |
| DELETE | `/system/gz/jp/product/{ids}` | `gz:jp:product:remove` |

---

## AI 自测（Tier 1A）

### 1. 编译 + 单测（34 用例全绿：20 新增 + 14 上游 101 回归）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dsurefire.failIfNoSpecifiedTests=false
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductServiceTest
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.733 s
[INFO] Running org.dromara.gz.jp.service.impl.GzJpEventStatusTest
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.070 s
[INFO] Tests run: 34, Failures: 0, Errors: 0, Skipped: 0
[INFO] ruoyi-gz-common .................................... SUCCESS [  3.443 s]
[INFO] ruoyi-gz-jp ........................................ SUCCESS [  1.252 s]
[INFO] BUILD SUCCESS

$ mvn -o clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-jp -am
[INFO] Installing .../ruoyi-gz-common-5.6.1.jar to ~/.m2/...
[INFO] Installing .../ruoyi-gz-jp-5.6.1.jar to ~/.m2/...
[INFO] BUILD SUCCESS
```

`GzJpProductServiceTest`（`@Tag("dev")`，20 例）覆盖：新建默认 off_shelf + version=0 + productNo 生成 + 图集 join + 名称 trim / **productNo 跳过软删占号** / 场不存在拒绝 / **场 draft 时仍允许上架商品** / 价格 ≤0 与超上限拒绝 / 图集超 9 张拒绝 / 编辑不改 productNo·status·version / 乐观锁冲突显式报错 / 批量上架跳过同态项 / 非法状态拒绝 / 批量超 200 条拒绝 / 已上架不可删 / 下架可删 / **visibleToCustomer 四象限**（open+on_shelf、open+off_shelf、draft+on_shelf、closed+on_shelf）/ 列表回填场信息 + 图集展开 + 筛选下沉 SQL / 未知 status 筛选忽略 / 场被删容错 / 详情不存在返 null / 图集脏数据容错 / **实体无 stock·sku·inventory 字段**。

### 2. Flyway 迁移（启动自动跑）

```
DbMigrate - Migrating schema `ry-vue` to version "202608070232 - GZ-JP-102-create-gz jp product" [out of order]
DbMigrate - Migrating schema `ry-vue` to version "202608070233 - GZ-JP-102-seed-dict-menu" [out of order]
DbMigrate - Successfully applied 2 migrations to schema `ry-vue`, now at version v202608070233 (execution time 00:00.100s)
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功   ლ(´ڡ`ლ)ﾞ

mysql> SELECT version, script, success FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 4;
202608070233	V202608070233__GZ-JP-102-seed-dict-menu.sql	1
202608070232	V202608070232__GZ-JP-102-create-gz_jp_product.sql	1
202608070203	V202608070203__GZ-JP-101-seed-dict-menu.sql	1
202608070202	V202608070202__GZ-JP-101-create-gz_jp_event.sql	1
```

### 3. DB 结构验证（七件套齐 + 无 stock 列 + 索引）

```
mysql> SELECT column_name, column_type, is_nullable, column_default FROM information_schema.columns
       WHERE table_schema='ry-vue' AND table_name='gz_jp_product' ORDER BY ordinal_position;
id                  bigint          NO   NULL
product_no          varchar(32)     NO   NULL
event_id            bigint          NO   NULL
name                varchar(128)    NO   NULL
main_image_id       bigint          NO   NULL
gallery_image_ids   varchar(512)    YES  NULL
price_cent          bigint          NO   NULL
delivery_date_text  varchar(64)     YES  NULL
notice_text         varchar(1024)   YES  NULL          ← REQ-PROD-005 独立字段
status              varchar(16)     NO   off_shelf
sort_no             int             NO   0
version             int             NO   0
tenant_id           varchar(20)     NO   1001          ┐
create_dept         bigint          YES  NULL          │
create_by           bigint          YES  NULL          │ 七件套（create_dept 没漏）
create_time         datetime        YES  NULL          │
update_by           bigint          YES  NULL          │
update_time         datetime        YES  NULL          │
del_flag            char(1)         NO   0             ┘
remark              varchar(500)    YES  NULL
（★ 全表 20 列，无任何 stock* / sku* 列）

mysql> SHOW INDEX FROM gz_jp_product;
PRIMARY           id           unique
uk_product_no     tenant_id    unique     ← 唯一约束含 tenant_id
uk_product_no     product_no   unique
idx_event_status  tenant_id / event_id / status / sort_no    non-unique
```

菜单 / 字典 / 授权：

```
mysql> SELECT menu_id, menu_name, menu_type, parent_id, path, component, perms, visible, status, icon
       FROM sys_menu WHERE menu_id BETWEEN 14000 AND 14019 ORDER BY menu_id;
14000  日本拼团   M  0      gz-jp    NULL                                     0 0 shopping
14001  场管理     C  14000  event    gz-jp/event/index    gz:jp:event:list    0 0 date
14002~14005  场按钮 F 14001 ...                                （GZ-JP-101，未动）
14010  商品管理   C  14000  product  gz-jp/product/index  gz:jp:product:list  0 0 category
14011  商品查询   F  14010           gz:jp:product:list                       0 0 #
14012  商品新增   F  14010           gz:jp:product:add                        0 0 #
14013  商品编辑   F  14010           gz:jp:product:edit                       0 0 #
14014  商品删除   F  14010           gz:jp:product:remove                     0 0 #

mysql> SELECT dict_code, dict_label, dict_value, dict_type, list_class, is_default FROM sys_dict_data WHERE dict_type='gz_jp_product_status';
92804  已上架  on_shelf   gz_jp_product_status  success  N
92805  已下架  off_shelf  gz_jp_product_status  info     Y

mysql> SELECT role_id, GROUP_CONCAT(menu_id ORDER BY menu_id) FROM sys_role_menu WHERE menu_id BETWEEN 14010 AND 14019 GROUP BY role_id;
100  14010,14011,14012,14013,14014     ← owner 全给
101  14010,14011,14012,14013           ← staff 无删除
```

admin 动态路由（前端零注册）：

```
$ GET /system/menu/getRouters
{ "name": "Gz-jp14000", "path": "/gz-jp", "component": "Layout", "meta": {"title":"日本拼团","icon":"shopping"},
  "children": [
    { "name":"Event14001",   "path":"event",   "component":"gz-jp/event/index",   "meta":{"title":"场管理","icon":"date"} },
    { "name":"Product14010", "path":"product", "component":"gz-jp/product/index", "meta":{"title":"商品管理","icon":"category"} } ] }

$ ls -la plus-ui/src/views/gz-jp/product/index.vue
-rw-r--r--  1 wkui  staff  19559 Aug  7 02:47   ✅ component 串与文件一一对应
```

### 4. API 端到端烟雾测试（真起应用打真库）

```bash
# ── 场下拉（挂商品权限，状态是读时惰性判定后的生效状态）
$ GET /system/gz/jp/product/event-options
{ "code":200, "data":[{"id":"1","eventNo":"EVT-20260807-000001","name":"8月上旬快闪场","status":"draft"}] }

# ── 上架商品（FLOW:F-JP-01.step2）
$ POST /system/gz/jp/product {"eventId":"1","name":"柯南 吧唧 一番赏 A赏","mainImageId":"1",
    "galleryImageIds":["2","3"],"priceCent":12800,"deliveryDateText":"8月下旬",
    "noticeText":"日本线下采购，包装可能有轻微磨损，介意慎拍","sortNo":1}
{ "code": 200, "msg": "新建成功", "data": 1 }
$ POST /system/gz/jp/product {"eventId":"1","name":"排球少年 亚克力立牌","mainImageId":"2","priceCent":6800,...}
{ "code": 200, "msg": "新建成功", "data": 2 }

# ── 列表：业务码自动生成 + 场信息回填 + 图集展开 + 默认下架
$ GET /system/gz/jp/product/list
{ "total": 2, "rows": [
  { "id":"1","productNo":"JPP-20260807-000001","eventId":"1","eventNo":"EVT-20260807-000001",
    "eventName":"8月上旬快闪场","eventStatus":"draft","name":"柯南 吧唧 一番赏 A赏",
    "mainImageId":"1","galleryImageIds":["2","3"],"priceCent":12800,"deliveryDateText":"8月下旬",
    "noticeText":"日本线下采购，包装可能有轻微磨损，介意慎拍",
    "status":"off_shelf","visibleToCustomer":false,"sortNo":1,"version":0, ... },
  { "id":"2","productNo":"JPP-20260807-000002",...,"galleryImageIds":[],"noticeText":null,
    "status":"off_shelf","visibleToCustomer":false,"sortNo":2 } ], "code":200 }

# ── ★ 批量上架 → 场还是 draft，visibleToCustomer 必须仍 false（FLOW step2「未开场时仍不可见」）
$ POST /system/gz/jp/product/status {"ids":["1","2"],"status":"on_shelf"}
{ "code":200, "msg":"操作成功", "data":2 }        ← data = 实际改动条数
  JPP-20260807-000001  status=on_shelf  eventStatus=draft  visibleToCustomer=False
  JPP-20260807-000002  status=on_shelf  eventStatus=draft  visibleToCustomer=False

# ── 重复上架同一批 → changed=0（同态项跳过，不报错）
$ POST /system/gz/jp/product/status {"ids":["1","2"],"status":"on_shelf"}
{ "code":200, "msg":"操作成功", "data":0 }

# ── ★ 开场（FLOW step3）→ visibleToCustomer 立刻翻转 true（读时判定，无 cron）
$ POST /system/gz/jp/event/open/1   →  { "code":200 }
  JPP-20260807-000001  status=on_shelf  eventStatus=open  visibleToCustomer=True
  JPP-20260807-000002  status=on_shelf  eventStatus=open  visibleToCustomer=True

# ── 筛选下沉 SQL（分页 total 准确）
$ GET /list?eventId=1 → total=2      $ GET /list?eventId=999 → total=0
$ GET /list?status=on_shelf → total=2   $ GET /list?status=off_shelf → total=0
$ GET /list?name=排球 → total=1

# ── 编辑：篡改 productNo / status 必须被后端忽略
$ PUT /system/gz/jp/product {"id":"1","productNo":"HACK-0001","status":"off_shelf","eventId":"1",
    "name":"柯南 吧唧 一番赏 A赏（改名）","mainImageId":"1","galleryImageIds":["2"],
    "priceCent":13800,"deliveryDateText":"8月底","noticeText":"改过的注意事项","sortNo":5}
{ "code": 200, "msg": "操作成功" }
mysql> SELECT id,product_no,name,status,price_cent,gallery_image_ids,notice_text,sort_no,version FROM gz_jp_product WHERE id=1;
id=1  product_no=JPP-20260807-000001   ← 未被篡改
      status=on_shelf                  ← 未被篡改（PUT 改不了状态）
      price_cent=13800  gallery_image_ids=2  notice_text=改过的注意事项  sort_no=5  version=2 ← 乐观锁自增

# ── 删除守卫：已上架不可删
$ DELETE /system/gz/jp/product/1
{ "code":500, "msg":"商品「柯南 吧唧 一番赏 A赏（改名）」仍在上架中，请先下架再删除" }

# ── 参数校验
priceCent=0         → { "code":500, "msg":"售价必须大于 0" }
priceCent=100000000 → { "code":500, "msg":"售价超出上限（¥999999），请确认是否多输了 0" }
eventId=999         → { "code":500, "msg":"所属场不存在或已删除：999" }
无 mainImageId      → { "code":500, "msg":"请上传商品主图" }
gallery 10 张       → { "code":500, "msg":"图集最多 9 张" }
/status status=sold_out → { "code":500, "msg":"非法的商品状态：sold_out" }
```

### 5. ★ 软删后当日再上架，product_no 不得重用（uk_product_no 撞库回归）

```bash
$ POST /system/gz/jp/product/status {"ids":["2"],"status":"off_shelf"}   → { "code":200, "data":1 }
$ DELETE /system/gz/jp/product/2                                          → { "code":200 }

mysql> SELECT id, product_no, del_flag FROM gz_jp_product ORDER BY id;
1  JPP-20260807-000001  0
2  JPP-20260807-000002  1      ← 已软删（本项目 logicDeleteValue=1）

$ POST /system/gz/jp/product {"eventId":"1","name":"软删后再建的商品","mainImageId":"3","priceCent":9900}
{ "code": 200, "msg": "新建成功", "data": 3 }

mysql> SELECT id, product_no, name, del_flag FROM gz_jp_product ORDER BY id;
1  JPP-20260807-000001  柯南 吧唧 一番赏 A赏     0
2  JPP-20260807-000002  排球少年 亚克力立牌      1
3  JPP-20260807-000003  软删后再建的商品         0   ← 跳过被软删占用的 000002，未撞 409 DuplicateKey
```
> 软删残留行随后已 **HARD DELETE** 清掉（项目铁律：测试数据不留软删残留）。

### 6. plus-ui 构建 + 类型 + lint

```
$ npx vue-tsc --noEmit -p tsconfig.json | grep -icE "gz-jp|gzJpProduct"
0            （新增文件 0 类型错误；仓库既有基线 error 与本 ticket 无关）

$ npx eslint src/views/gz-jp/product/index.vue src/api/gz-jp/product.ts src/lang/zh_CN.ts src/api/gz-common/file.ts
（无输出 —— 0 error）

$ npx vite build --mode production
dist/index.html.gz 111.32kb -> 48.39kb    ✓ built     VITE_BUILD_EXIT=0
```

---

## accept 三条结果

| # | name | form | 结果 |
|---|---|---|---|
| 1 | 建表且公共字段全集齐 | DDL | ✅ **PASS**（逐字执行，EXIT=0） |
| 2 | 注意事项与包邮价字段就位，且无库存列（一期不做） | DDL | ✅ **PASS**（逐字执行，EXIT=0） |
| 3 | 菜单 path/component 非空且父级有效（防 404 与错父级） | MENU | ✅ **PASS**（逐字执行，EXIT=0；ticket 已修正 del_flag，无需再改） |

```
════════ accept #1 ════════
docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema='ry-vue' AND table_name='gz_jp_product'
  AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" | grep -qx 7
EXIT=0

════════ accept #2 ════════
docker exec ... "... column_name IN ('notice_text','price_cent','delivery_date_text','event_id')" | grep -qx 4 &&
docker exec ... "... column_name LIKE 'stock%'" | grep -qx 0
EXIT=0

════════ accept #3 ════════
docker exec ... "SELECT COUNT(*) FROM sys_menu m WHERE m.menu_id BETWEEN 14010 AND 14019
  AND ( (m.menu_type IN ('M','C') AND (m.path IS NULL OR m.path=''))
     OR (m.menu_type='C' AND (m.component IS NULL OR m.component=''))
     OR (m.parent_id<>0 AND NOT EXISTS (SELECT 1 FROM sys_menu p WHERE p.menu_id=m.parent_id)) )" | grep -qx 0 &&
docker exec ... "SELECT COUNT(*) FROM sys_menu WHERE menu_id BETWEEN 14010 AND 14019" | grep -qE '^[1-9]'
EXIT=0
```

---

## 风险提示 / 已知 issue

1. **REQ-PROD-007（多规格 SKU）是 Kevin 暂定、甲方未表态**。若甲方后续要多规格，需加 sku 子表 + `gz_jp_order_item.sku_id` + 改 `product_snapshot_json` 结构 —— 结构性返工，波及 102 + 105，需重新排期。口径已固化进 DDL 注释与枚举 javadoc，反悔成本可见。
2. **无库存 = 无超卖保护**。「卖完」只能靠店员手动下架，存在人工滞后窗口。这是需求侧刻意选择（field-ssot 明示），不是实现缺陷。
3. **`UI:admin.event` 的「商品数」列仍未做**（101 遗留，当时无表可查）。现在表有了，但 `plus-ui/src/views/gz-jp/event/index.vue` **不在本 ticket touches 范围**故未动，补法见下。
4. **`POST /product` 返回 `R<Long>`**（`data:1` 是 number），与 101 及全部既有 gz 模块一致；VO 里 id 已是 string；`id` 是 AUTO_INCREMENT 非 snowflake，不逼近 JS 安全整数；admin 页也不消费该返回值。
5. **`/status` 带 `@RepeatSubmit`**：5 秒内提交完全相同 body 会被幂等拦截（自测中实际撞到一次）。admin 正常操作不触发；写自动化测试要注意间隔。
6. **迁移是 `[out of order]` 应用的**（既有配置 `out-of-order=true`），两条 `success=1`，不影响。
7. **staging / prod 未部署**，只在本地 dev 库验证；上线时 Flyway 自动补跑这 2 条。
8. **权限变更后 admin 需重登**（`sys_role_menu` 走登录时快照）。
9. 本次起过的 `spring-boot:run` 已 kill，**8080 已释放**；**未 commit 任何 git**。

### dev 库遗留状态（有意留给 GZ-JP-103 当 fixture）

```
gz_jp_event    id=1  EVT-20260807-000001  status=open
gz_jp_product  id=1  JPP-20260807-000001  柯南 吧唧 一番赏 A赏   on_shelf   12800 分
               id=3  JPP-20260807-000003  软删后再建的商品        off_shelf   9900 分
```
正好满足 GZ-JP-103 accept #2 的 `?eventId=1` 前提，且同时具备 on_shelf / off_shelf 两态可断言「off_shelf 不下发」。无软删残留行。

---

## 对下游 ticket 的提示

### 给 GZ-JP-103（mp 端场 / 商品查询 API）—— 你只需加 `controller/applet/` 下的类

**现成可用**
- 实体 / 枚举 / mapper 全就位：`GzJpProduct` / `GzJpProductStatus`（`ON_SHELF`/`OFF_SHELF`，`of()` 未知值回落 OFF_SHELF）/ `GzJpProductMapper`。
- **「场仍可下单」直接调 `IGzJpEventService.isBookable(eventId)`**；批量场景用我新加的 `selectOptionMap(Collection<Long>)` → `Map<Long, GzJpEventOptionVO>{id, eventNo, name, status(生效)}`，别自己写 end_time 比较。
- 场的 mp 端点 101 已做好：`GET /app/gz/jp/event/list`（`TableDataInfo`，读 `res.rows`）+ `GET /app/gz/jp/event/{id}`（`R<GzJpEventMpVO>`，读 `res.data`）。你只需补 product 两个。

**你要新建的（本 ticket 刻意没做）**
- `controller/applet/GzJpProductMpController`（`/app/gz/jp/product`，`@SaIgnore` 匿名可读）
- `domain/vo/GzJpProductMpVO` —— **别复用 `GzJpProductAdminVO`**（它带 `remark`/`version`/`visibleToCustomer`/`eventStatus` 等运营字段，不该下发客人）
- `IGzJpProductService` 加 mp 方法（`selectMpPage(eventId, pageQuery)` / `selectMpDetail(id)`）

**accept #2 要求的 mp VO 字段名（我这边命名已对齐 camelCase，照抄即可）**
```
必须有： noticeText / priceCent / deliveryDateText
必须无： stockRemain（一期无库存，别顺手加）
建议有： id(string) / productNo / name / mainImageUrl / galleryImageUrls / eventId(string) / eventNo
```
- **主图 / 图集 mp 侧要给可渲染 URL 而非 file id**：照 101 `GzJpEventServiceImpl.resolveImageUrl()` 用 `IGzFileService.getPresignedUrl(id).getUrl()`，失败回落 `/static/images/mock-product.png`。admin VO 给的是 file id（列表不逐条预签名），mp 必须给 URL。
- `galleryImageIds` 落库是逗号串（实体上是 `String`）；service 内有私有 `splitGallery` / `joinGallery`（含脏数据容错）。要复用建议提到小工具类，别写第三份。
- **mp 可见性条件（两层都要，缺一即错）**：`商品 status='on_shelf' AND 场生效状态=open（isBookable）`。只查商品 status 会把「未开场/已结束的场里的 on_shelf 商品」漏出去。建议 mp 列表先 `isBookable(eventId)`，false 直接返空页 / `R.fail("该场不存在或已结束")`。
- **列表返 `TableDataInfo`（rows+total）、详情返 `R<T>`** —— 与 101 同口径，`doc/jp/verify.sh` 与你的 accept 都按这个断言。
- mp 路由参数建议用业务码 `productNo`（JPP-yyyyMMdd-6位），但**你 accept #2 是拿 `rows[0].id` 再打 `/{id}`，所以 `/{id}` 这条必须按 id 收**。
- dev fixture 已备好（见上），`?eventId=1` 直接有数据，无需再 seed。

### 给 GZ-JP-105 / 后续订单与履约
- `product_snapshot_json` 至少含 `{productNo, name, mainImageId, priceCent, deliveryDateText, noticeText}` —— **`noticeText` 必须进快照**，商品后续改注意事项不能影响已下单的举证。
- **`priceCent` 已是包邮终价**（REQ-ORDER-004），订单行金额 = `priceCent × qty`，**不得再加运费行**。
- 商品可能被软删 / 下架，订单行永远读快照不回查 `gz_jp_product`。

### 编号 / 段位现状（下一 ticket 直接接着用）

| 资源 | 已占 | **下一个空号** |
|---|---|---|
| `sys_menu` GZ-JP 段 | 14000-14005（场）、14010-14014（商品） | 场按钮 **14006**；商品按钮 **14015**；订单管理按 field-ssot 用 **14020** 段；履约看板 **14030** 段 |
| `sys_dict_type.dict_id` | 9280、9281 | **9282** |
| `sys_dict_data.dict_code` | 92801-92803、92804-92805 | **92806** |
| Flyway 版本 | …V202608070233 | 用 `date +V%Y%m%d%H%M` 当下真实时间 |
| `GzFileUsageType` | …`JP_EVENT_IMAGE`、`JP_PRODUCT_IMAGE` | 新场景两端（后端枚举 + plus-ui `GZ_FILE_USAGE_TYPE`）**必须同时加** |

### 补「场列表的商品数」列（`UI:admin.event` 遗留缺口）
不在本 ticket touches 内。最小改法：① `GzJpEventAdminVO` 加 `Integer productCount`；② `GzJpEventServiceImpl.selectAdminPage` 拿到本页 event ids 后用 `GzJpProductMapper` 一次 `GROUP BY event_id` 批量回填（**别逐行 count，N+1**）；③ `plus-ui/src/views/gz-jp/event/index.vue` 加一列 + i18n `gzJpEvent.colProductCount`。

### 全 jp 域通用（101 已提，仍成立）
- **改 `ruoyi-gz-jp` 任何代码后必须 `mvn clean install`**（非 clean 的 install 既不重打 jar 也不重编译测试，`exit 0` 会骗人）。
- 单测类必须 `@Tag("dev")`，否则 surefire `<groups>` 直接跳过、静默「通过」。
- 纯 mock 单测断言 `LambdaQueryWrapper.getSqlSegment()` 时，`@BeforeAll` 必须 `TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), ""), Entity.class)`。
- plus-ui 分页接口泛型写 `AxiosPromise<行元素[]>`；表格用原生 `<el-table>` + `<pagination>`；业务图片用 `<GzImageUpload v-model="fileId字符串">` / `<GzImageThumb :file-id>`。

---

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

Tier 1B 建议覆盖：
- **admin Playwright E2E**：登录 → 侧边栏「日本拼团 → 商品管理」→ 场下拉筛选 → 新建商品（主图 + 图集真实上传走 OSS）→ 列表校验（缩略图渲染 / 价格元显示 / 状态 dict-tag）→ 多选批量上架 → 「已上架但场没开」黄色警示 icon → 编辑 → 详情抽屉（注意事项整段展示）→ 批量下架 → 删除 → 权限按钮显隐（staff 无「删除」）
- **后端集成**：`/system/gz/jp/product/*` 全端点 + 权限 403 校验（staff 调 DELETE 应 403）
- **API 契约回归**：VO 字段名 camelCase 与 field-ssot 一致、id 全 string、无 stock 字段
- 本 ticket **无 mp 页面**（mp 端点从 GZ-JP-103 起才有），mp 模拟器 E2E 从 GZ-JP-201 起才有覆盖对象

---

**结论：accept 三条全 PASS（三条 EXIT=0）。**
