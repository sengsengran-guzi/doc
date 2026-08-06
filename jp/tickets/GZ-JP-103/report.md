# GZ-JP-103 完工报告 — mp 端场 / 商品查询 API

> 在 GZ-JP-101（场）+ GZ-JP-102（商品）已建好的 `ruoyi-gz-jp` 模块内**只加 mp 只读层**。**无 DDL / 无迁移 / 无菜单 / 未动 pom / 未动 plus-ui / 未动 miniapp**。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（RuoYi-Vue-Plus，分支 staging） | ✅ | 开工前 `git status --short` 空输出 |
| 上游 GZ-JP-101 已 merge | ✅ | `b1f1ecedb D3/GZ-JP-101: 场（gz_jp_event）建表 + admin 场管理` |
| 上游 GZ-JP-102 已 merge | ✅ | `7dc1d98a1 D3/GZ-JP-102: 商品（gz_jp_product）建表 + admin 商品管理` |
| dev 库有 open 场 + 商品（无需 seed） | ✅ | `gz_jp_event id=1 status=open`；`gz_jp_product id=1 on_shelf` + `id=3 off_shelf` |
| 101 的 mp 场端点现状（本卡不重写，只确认） | ✅ | `controller/applet/GzJpEventMpController` 已存在，运行时实测见 §2 |
| 编译健康（基线） | ✅ | `mvn -o compile -pl ruoyi-gz-jp -am` → `BUILD SUCCESS` / EXIT=0 |
| Flyway append-only 自检 | ✅ N/A | 本卡无 DDL；`git status -- db/migration/` 空输出，最大版本仍 `V202608070233` |
| 8080 空闲 | ✅ | `lsof -iTCP:8080 -sTCP:LISTEN` 无输出 |
| 权威蓝图已读 | ✅ | `FLOW:F-JP-02.step1` / `F-JP-01.step2` / `UI:mp.home` / `UI:mp.event_detail` / `UI:mp.product_detail` / field-ssot `gz_jp_product` / REQ-EVENT-001·PROD-001·003·004·005 |
| ADR | 无相关（doc/jp 无 ADR 目录，沿用 101/102 骨架，无新架构决策） |

### 权威蓝图关键约束摘录

- `FLOW:F-JP-02.step1` —「客人(mp) 浏览场 / 进场看商品 / 看详情（含注意事项）；**produces: 无写入**」→ 本卡纯只读，零写路径。
- `FLOW:F-JP-01.step2` —「商品 status=on_shelf；**未开场时仍不可见**」→ **可见性必须两层**，本卡核心约束。
- `UI:mp.event_detail.product_grid` —「两列网格；**无筛选无排序**；几十到上百，**上拉分页**」→ 不做筛选参数，排序服务端固定，必须真分页。
- `UI:mp.product_detail.notice` —「★ 甲方明确要求的『额外注意事项』，必须在 CTA 之上、**默认展开不折叠**」→ `noticeText` 必下发。
- `FIELD:gz_jp_product.price_cent` —「★ **全包邮**，此价即最终支付价，不叠加运费」。
- `FIELD:gz_jp_product.status` —「★ 一期**无库存字段**」→ VO 不得有 `stockRemain`。
- `FIELD:gz_jp_product.main_image_id` —「FK `gz_file_object.id`（**禁裸 url**）」→ 落库存 file id，mp 出参换预签名 URL。
- `UI:mp.home` —「场分**进行中 / 即将开始 / 已结束**三组」→ ⚠️ **与现状不一致，见 R1**。

---

## 实现摘要

### 改动文件（只碰 `ruoyi-gz-jp` 一个模块）

```
 M .../service/IGzJpProductService.java          |  40 ++++-   (加 selectMpPage / selectMpDetail 声明)
 M .../service/impl/GzJpProductServiceImpl.java  | 120 +++++++  (mp 两方法 + toMpVO + resolveImageUrl + buildMpPage；构造器多注入 IGzFileService)
 M src/test/.../GzJpProductServiceTest.java      |   7 +-     (102 单测跟进构造器新增参数)
?? .../controller/applet/GzJpProductMpController.java   (94 行)
?? .../domain/vo/GzJpProductMpVO.java                   (94 行)
?? src/test/.../GzJpProductMpQueryTest.java             (382 行 / 18 用例)
（无 SQL 迁移 / 无 sys_menu / 无 sys_dict / plus-ui 零改动 / miniapp 零改动）
```

### 103 完工后的完整 C 端只读面

| Method | Path | 归属 | 鉴权 | 返回 | 可见性 |
|---|---|---|---|---|---|
| GET | `/app/gz/jp/event/list` | 101（**本卡未改**） | `@SaIgnore` | `TableDataInfo<GzJpEventMpVO>` | 生效状态 open |
| GET | `/app/gz/jp/event/{id}` | 101（**本卡未改**） | `@SaIgnore` | `R<GzJpEventMpVO>` | 同上，否则 `R.fail("该场不存在或已结束")` |
| GET | `/app/gz/jp/product/list?eventId=` | **103 新建** | `@SaIgnore` | `TableDataInfo<GzJpProductMpVO>` | 商品 on_shelf ∧ 场 open |
| GET | `/app/gz/jp/product/{id}` | **103 新建** | `@SaIgnore` | `R<GzJpProductMpVO>` | 同上，否则 `R.fail("该商品已下架或所属场已结束")` |

### 关键实现决策

1. **★ 可见性两层，第 1 层短路** — `status='on_shelf'` ∧ `IGzJpEventService.isBookable(eventId)`。列表先判场，不可下单**直接返空页、根本不查商品表**；详情先判商品再判场。**商品侧没写任何 `end_time` 比较**，惰性判定只在 `GzJpEventStatus.effective` 一处。
2. **`TableDataInfo.build(List.of())` 而非 `build()`** — ruoyi 无参 `build()` **不 setRows**，会给 mp 吐 `"rows": null` 直接崩。第一版就踩了，被新增单测当场逮住（见 §1 脚注）。
3. **`GzJpProductMpVO` 全新，不复用 admin VO** — admin VO 带 `remark`（写着「供货商 A」这类内部备注）/ `version` / `sortNo` / `eventStatus` / `visibleToCustomer` / `createTime`，全不该下发客人。
4. **图片给可渲染 URL 不给 file id** — 走 `IGzFileService.getPresignedUrl(id).getUrl()`（照 101）；null / 文件已删 / 空串一律回落 `/static/images/mock-product.png`，**绝不返 null**。
5. **一次请求内 URL 缓存去重** — `Map<Long,String>` **方法内局部变量，不跨请求**。真实收益：一番赏 A/B/C 赏共用盒图 → 列表跨行只签一次；详情主图常落在图集里 → 只签一次。
6. **列表不下发图集（`galleryImageUrls` 恒 `[]`），详情才展开** — 商品卡只用主图；一页 20 条 × 9 张 = 180 次 `selectById`+签名纯浪费。已在 VO 字段 javadoc 大写标注。
7. **★ mp 分页收口：默认 20 / 封顶 50** — ruoyi `PageQuery.DEFAULT_PAGE_SIZE = Integer.MAX_VALUE`，漏传就 `LIMIT 2147483647` 拉走整场。本接口**匿名可调且每行一次 DB + 一次 HMAC 签名**，等于给未鉴权调用方一个放大器。
8. **`eventId` 用 `required=false` + `@NotNull`（刻意）** — Spring 的 `required=true` 先抛 `MissingServletRequestParameterException` 落兜底分支，返回「发生未知异常，请联系管理员」+ ERROR 堆栈（第一版实测）；改走 `ConstraintViolationException` 后返回「请选择场」。
9. **排序服务端固定 `sort_no ASC, id ASC`**，不接受调用方传 `orderByColumn`。
10. **零 `@Transactional`、零写路径** — 关场后商品 `status` 仍是 `on_shelf`（DB 实测未改写），可见性纯读时判定。
11. **场信息回填复用 102 的 `selectOptionMap(Collection)`**，整页一次查回，不 N+1；场被删时字段留空不挂页。
12. **复用 102 私有 `splitGallery`** — mp 方法就在同一个 Impl 类里，**不需要第三份实现、不需要新工具类**。

---

## AI 自测（Tier 1A）

### 1. 编译 + 单测（52 用例全绿：18 新增 + 34 上游回归）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -Dsurefire.failIfNoSpecifiedTests=false
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductServiceTest
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.799 s
[INFO] Running org.dromara.gz.jp.service.impl.GzJpEventStatusTest
[INFO] Tests run: 14, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.047 s
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductMpQueryTest
[INFO] Tests run: 18, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.030 s
[INFO] BUILD SUCCESS        TEST_EXIT=0

$ mvn -o clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-jp     # ★ 必须 clean
[INFO] Installing .../ruoyi-gz-jp-5.6.1.jar to ~/.m2/repository/org/dromara/ruoyi-gz-jp/5.6.1/
[INFO] BUILD SUCCESS        INSTALL_EXIT=0
```

`GzJpProductMpQueryTest`（`@Tag("dev")`，18 例）覆盖：两层可见性下沉 SQL / **场不可下单→空页且不查商品表** / **空页必须给 `[]` 不给 null** / eventId 必传 / **pageSize 缺省 20 封顶 50** / 主图给 URL·列表不给图集 / 跨行同图只签一次 / 主图 null→占位图 / 预签名抛异常→占位图 / 场被删容错 / **详情全字段 + 图集展开** / **商品 off_shelf→不下发** / **★★ on_shelf 但场未开→不下发** / 商品不存在·id null / 图集脏数据容错 / 详情主图落图集里只签一次 / **VO 无 stock·sku·inventory** / **VO 必含 accept 依赖字段 + 不含 7 个运营字段** / **id·eventId 序列化为 string**。

> ★ 第一版 `selectMpPage` 用了无参 `TableDataInfo.build()`，单测 `listReturnsEmptyWhenEventNotBookable` 立刻 NPE 报 `getRows()` 返回 null —— 这就是那条会让 GZ-JP-202「场已结束页面白屏」的 bug，进 runtime 前就拦下了。

### 2. ★ accept 两条（逐字执行 frontmatter 命令，改动后重放 3 次均 EXIT=0）

```bash
════════ accept #1：场列表接口返回结构完整且只含应可见的场 ════════
RESP=$(curl -s 'http://localhost:8080/app/gz/jp/event/list' -H 'clientid: mp-applet-gz-jp'); \
echo "$RESP" | jq -e '.rows | length > 0 and (.[0] | has("eventNo") and has("name") and has("startTime") and has("endTime") and has("status"))' >/dev/null && \
echo "$RESP" | jq -e '[.rows[] | select(.status=="draft")] | length == 0' >/dev/null
ACCEPT1_EXIT=0        ✅ PASS

--- 响应 raw ---
{ "total": 1,
  "rows": [ { "id": "1", "eventNo": "EVT-20260807-000001", "name": "8月上旬快闪场",
              "coverImageUrl": "/static/images/mock-product.png", "description": null,
              "status": "open", "startTime": "2026-08-07 10:00:00", "endTime": "2026-09-30 22:00:00" } ],
  "code": 200, "msg": "查询成功" }
（库里此刻 2 个场：id=1 open / id=2 draft。draft 没出现 → 断言 2 成立）

════════ accept #2：商品详情返回注意事项与包邮价 ════════
PID=$(curl -s 'http://localhost:8080/app/gz/jp/product/list?eventId=1' -H 'clientid: mp-applet-gz-jp' | jq -r '.rows[0].id'); \
curl -s "http://localhost:8080/app/gz/jp/product/$PID" -H 'clientid: mp-applet-gz-jp' \
  | jq -e '.data | has("noticeText") and has("priceCent") and has("deliveryDateText") and (has("stockRemain")|not)' >/dev/null
ACCEPT2_EXIT=0        ✅ PASS   (PID=1)

--- /product/list?eventId=1 raw ---
{ "total": 1, "rows": [ {
    "id": "1", "productNo": "JPP-20260807-000001", "eventId": "1",
    "eventNo": "EVT-20260807-000001", "eventName": "8月上旬快闪场",
    "name": "柯南 吧唧 一番赏 A赏",
    "mainImageUrl": "http://localhost:9000/sensenran-dev/gz/2026/06/24/30a889d8...png?X-Amz-Algorithm=AWS4-HMAC-SHA256&...&X-Amz-Expires=3600&X-Amz-Signature=c8c1acd2...",
    "galleryImageUrls": [], "priceCent": 12800, "deliveryDateText": "8月下旬",
    "noticeText": "日本线下采购，包装可能有轻微磨损，介意慎拍", "status": "on_shelf" } ],
  "code": 200, "msg": "查询成功" }
（event=1 下有 2 个商品：id=1 on_shelf / id=3 off_shelf。off_shelf 没出现，total=1）

--- /product/1 raw ---
{ "code": 200, "msg": "操作成功", "data": {
    "id": "1", "productNo": "JPP-20260807-000001", "eventId": "1",
    "eventNo": "EVT-20260807-000001", "eventName": "8月上旬快闪场",
    "name": "柯南 吧唧 一番赏 A赏",
    "mainImageUrl": "http://localhost:9000/.../30a889d8...png?...Signature=c8c1acd2...",
    "galleryImageUrls": [ "http://localhost:9000/.../6d73668f...png?...Signature=9fcc15fd...",
                          "http://localhost:9000/.../b2207e1e...png?...Signature=1544a4bd..." ],
    "priceCent": 12800, "deliveryDateText": "8月下旬",
    "noticeText": "日本线下采购，包装可能有轻微磨损，介意慎拍", "status": "on_shelf" } }
（★ 详情把图集展开成 2 个可渲染 URL；同一商品在列表里是 [] —— 有意的，见决策 6）
```

### 3. ★★ mp 可见性两层矩阵（AC 要求但不在 accept 命令里，专门造对照 fixture 实测）

先用 admin API 造出「**on_shelf 商品挂 draft 场**」这个只判一层就会漏的组合：

```
mysql> SELECT e.id ev_id, e.event_no, e.status ev_status, p.id p_id, p.product_no, p.name, p.status p_status
       FROM gz_jp_event e LEFT JOIN gz_jp_product p ON p.event_id=e.id AND p.del_flag='0'
       WHERE e.del_flag='0' ORDER BY e.id, p.id;
ev_id  event_no             ev_status  p_id  product_no           name                            p_status
1      EVT-20260807-000001  open       1     JPP-20260807-000001  柯南 吧唧 一番赏 A赏             on_shelf   ← 唯一该可见
1      EVT-20260807-000001  open       3     JPP-20260807-000003  软删后再建的商品                 off_shelf  ← 第2层拦
2      EVT-20260807-000002  draft      4     JPP-20260807-000004  未开场里的上架商品（可见性对照）  on_shelf   ← ★第1层拦
```

| # | 组合 | mp 列表 | mp 详情 | 判定 |
|---|---|---|---|---|
| 1 | on_shelf + 场 open | `total=1 rows=[JPP-...0001]` | `code=200` 全字段 | ✅ 唯一可见 |
| 2 | **off_shelf** + 场 open | 不出现（`total=1`） | `{"code":500,"msg":"该商品已下架或所属场已结束"}` | ✅ 第 2 层拦住 |
| 3 | **on_shelf + 场 draft** | `{"total":0,"rows":[],"code":200}` | `{"code":500,"msg":"该商品已下架或所属场已结束"}` | ✅ **第 1 层拦住（只判商品 status 必漏）** |
| 4 | draft 场本身 | 场列表无 `EVT-...0002` | `/event/2` → `{"code":500,"msg":"该场不存在或已结束"}` | ✅ AC「draft 场不下发」 |

```bash
# ③ 的 admin 侧对照：商品确实 on_shelf，只是场没开
$ GET /system/gz/jp/product/list?eventId=2
[{"id":"4","status":"on_shelf","eventStatus":"draft","visibleToCustomer":false}]
# admin 能看到 2 个场（对照 mp 只能看到 1 个）
$ GET /system/gz/jp/event/list
{"total":2,"rows":[{"eventNo":"EVT-20260807-000001","status":"open"},{"eventNo":"EVT-20260807-000002","status":"draft"}]}
```

**关场 → 立刻从 mp 消失 → 重新开场 → 恢复**（读时惰性判定，无 cron 依赖；prod 没部署 SnailJob 也照样对）：

```bash
$ 关场前   GET /app/gz/jp/product/list?eventId=1   → {"total":1}
$ POST /system/gz/jp/event/close/1                 → {"code":200,"msg":"操作成功"}
$ 关场后   GET /app/gz/jp/product/list?eventId=1   → {"total":0,"rows":[]}
$ 关场后   GET /app/gz/jp/product/1                → {"code":500,"msg":"该商品已下架或所属场已结束"}
$ 关场后商品自身状态（DB 未被改写，纯读时判定）：
  mysql> SELECT id,status FROM gz_jp_product WHERE id=1;   →  1  on_shelf
$ POST /system/gz/jp/event/open/1                  → {"code":200}
$ 开场后   GET /app/gz/jp/product/list?eventId=1   → {"total":1,"rows":["JPP-20260807-000001"]}
```

### 4. 匿名可调 + 字段契约

```bash
# ── 完全不带任何 header（无 Authorization、无 clientid）
$ curl -s -o /dev/null -w "HTTP=%{http_code}\n" http://localhost:8080/app/gz/jp/event/list
HTTP=200   {"code":200,"total":1,"rows":["EVT-20260807-000001"]}
$ curl ... /app/gz/jp/product/list?eventId=1     HTTP=200   {"code":200,"total":1,"rows":["JPP-20260807-000001"]}
$ curl ... /app/gz/jp/product/1                  HTTP=200   {"code":200,"name":"柯南 吧唧 一番赏 A赏"}
→ ✅ @SaIgnore 生效，「先逛后登录」无登录墙

# ── 字段契约（对 /product/1 的 .data 做 jq 断言）
detail keys : ["id","productNo","eventId","eventNo","eventName","name",
               "mainImageUrl","galleryImageUrls","priceCent","deliveryDateText","noticeText","status"]
全 camelCase（无下划线 / 无大写开头）                                    → ✅ PASS
无 stock / sku / inventory 任何键                                        → ✅ PASS
id、eventId 是 string（跨层 ID 契约）                                    → ✅ PASS
priceCent 是 number（单位「分」）                                        → ✅ PASS
不下发 remark/version/sortNo/visibleToCustomer/eventStatus/create*/update* → ✅ PASS
```

### 5. 边界 / 参数校验 + accept 对 null 字段的鲁棒性

```bash
eventId 不传          → {"code":500,"msg":"请选择场"}        ← 第一版是「发生未知异常」，已修（决策 8）
eventId=999（不存在） → {"code":200,"total":0,"rows":[]}     ← 空页非报错，rows 是 [] 不是 null
商品 id=999 不存在    → {"code":500,"msg":"该商品已下架或所属场已结束"}  ← 不区分「不存在/已下架」，不泄漏内部状态
分页 pageSize=1       → {"total":1,"n":1}

# ★ accept #2 拿 rows[0]，万一 rows[0] 的 noticeText/deliveryDateText 是 NULL 会不会 has() 失败？
#   临时把 product3（sort_no=0，notice/delivery 均 NULL）上架让它排到 rows[0] 实测：
$ GET /app/gz/jp/product/list?eventId=1
[{"id":"3","productNo":"JPP-20260807-000003","noticeText":null,"deliveryDateText":null},
 {"id":"1","productNo":"JPP-20260807-000001","noticeText":"日本线下采购...","deliveryDateText":"8月下旬"}]
   ↑ 顺带验证排序：sort_no 升序（p3 sort=0 在前，p1 sort=1 在后）✅
$ accept #2 在 rows[0] 全 null 字段下 → ✅ PASS
   （ruoyi 未开 NON_NULL，null 仍保留 key；已确认 JacksonConfig 与 application.yml 都没设 default-property-inclusion）
$ 已还原 product3 为 off_shelf，保留「off_shelf 不下发」fixture
```

### 6. ★ 分页收口的运行时证据（SQL 日志）

```
# 修前（PageQuery 默认 Integer.MAX_VALUE）：
Execute SQL：SELECT ... FROM gz_jp_product WHERE del_flag = '0'
             AND (event_id = 1 AND status = 'on_shelf') ORDER BY sort_no ASC, id ASC LIMIT 2147483647
# 修后：
$ GET /product/list?eventId=1                          → LIMIT 20   （缺省收口）
$ GET /product/list?eventId=1&pageSize=99999&pageNum=1  → LIMIT 50   （封顶）
# 同时可见：可见性两层确实下沉进 SQL（不是内存过滤，所以分页 total 准）
Execute SQL：SELECT COUNT(*) AS total FROM gz_jp_product WHERE del_flag = '0' AND (event_id = 1 AND status = 'on_shelf')
```

### 7. L1 回归包 `doc/jp/verify.sh`

```
── 断言 0：产物新鲜度 ──      ✓ [fresh] jar 版本新鲜
── L1：建表与公共字段 ──      ✓ gz_jp_event(7)   ✓ gz_jp_product(7)
                              ✗ gz_jp_cart_item / gz_jp_order / gz_jp_order_item — 期望[7] 实得[0]
── L1：跨表对账 ──            ✗ 订单相关 5 条 — 期望[0] 实得[]      ✓ gz_user 无空 app_id
── L1：C 端接口契约 ──        ✓ 场列表结构完整且不下发 draft        ← 本卡相关那条，绿
```

> **8 条 ✗ 全是「表还没建」**，与本卡无关：`SELECT table_name ... LIKE 'gz_jp%'` → 只有 `gz_jp_event` / `gz_jp_product`。`cart_item`/`order`/`order_item` 由 GZ-JP-201 及之后建（field-ssot 的 migration 字段已预留）。**本卡范围内 3 条断言全绿。**

### 8. 对抗式 code review（spawn `feature-dev:code-reviewer`）

按 6 类风险逐项核查（可见性漏洞 / 信息泄漏 / N+1 与缓存 / NPE / 跨层契约 / 事务与租户），**结论：未发现置信度 ≥80 的真问题，无需打回**。其提出的两条理论项已确认非本卡引入：① `isBookable()` 与商品查询之间毫秒级 TOCTOU 窗口（101 同款既有模式）；② `p.getEventId()` 理论 NPE（field-ssot `event_id nullable:false` + 写路径 `requireEventExist` 强制，正常业务不可达，且是 `selectAdminById` 既有写法）。

---

## 风险提示 / 已知 issue

### R1 ★★ 蓝图 vs 实现冲突：mp 只看得到「进行中」的场 —— **已由主线程处置，见下**

| 权威蓝图 | 101 + 103 实际行为（本卡完工时） |
|---|---|
| `UI:mp.home`：场分「**进行中 / 即将开始 / 已结束**」三组，进行中置顶 | `/event/list` 只返 `status=open AND end_time>now` → **只有「进行中」一组有数据源** |
| `UI:mp.event_detail`：「**场已结束时商品仍可浏览**，加购与下单入口置灰并提示『本场已结束』」 | `/event/{id}` 对已结束场返 `R.fail`；`/product/list` 返空页 → **已结束场根本进不去** |
| ticket AC：「draft 场不下发」 | ✅ 一致 |

**主线程处置**：GZ-JP-201 ticket 原文已写明「Kevin 已拍板首页做聚合...分「进行中/即将开始/已结束」三组」，GZ-JP-202 也写明「场已结束时商品仍可浏览，加购入口置灰」——这不是待澄清的新问题，是**已经决定但 101/103 未完整覆盖**的行为。主线程在派 GZ-JP-201/202 前先派一轮后端扩展（不新开正式 ticket，直接扩展 101/103 已建的服务）：`/event/list` 与 `/event/{id}` 改为 open+closed（仍排除 draft）都返回，`/product/list` 与 `/product/{id}` 对 closed 场放行，全部加 `bookable` 派生字段供前端置灰。详见 GZ-JP-201 完工报告的「视野扩展」段。

### R2 匿名请求 SQL **不带 `tenant_id`**（项目级既有特性，非本卡引入，单租户下零影响）

```
# mp 匿名（本卡）：      ... FROM gz_jp_product WHERE del_flag='0' AND (event_id=1 AND status='on_shelf')      ← 无 tenant_id
# 101 场 mp（匿名）：    ... FROM gz_jp_event   WHERE del_flag='0' AND (status='open' AND end_time>'...')      ← 同样无 → 证明既有
# admin 登录态同一张表： ... FROM gz_jp_product WHERE id IN (3) AND del_flag='0' AND tenant_id='1001'          ← 有
```
根因：无登录用户时 `TenantHelper` 拿不到租户，`TenantLineInnerInterceptor` 跳过 append。项目 2026-07-27 已合并单租户 1001，**实际零影响**；将来真多租户需在 gz-common 层统一给 `/app/**` 补租户上下文（跨模块基建，不在本卡 touches 内，此处登记）。

### R3 `PageQuery` 构造器是 **`(pageSize, pageNum)`** 反直觉顺序
102 单测里 `new PageQuery(1, 10)` 其实是 pageSize=1 / pageNum=10（`selectPage` 被 mock 所以没暴露）。本卡新单测已全改成 `new PageQuery(10, 1)`。**下游写分页单测别写反。**

### R4 列表 `galleryImageUrls` 恒 `[]`（有意，非 bug）
GZ-JP-202 详情页必须打 `/product/{id}` 拿图集。已写进 VO 字段 javadoc。

### R5 预签名 URL 有效期 1h
mp 页面长时间挂着不刷新后图片会 403。全项目既有口径（gz-gacha / gz-ord / gz-jp-event 一致），非本卡引入。202 若做长驻页面需下拉刷新重取。

### R6 `verify.sh` 尚未沉淀本卡 C 端契约断言
建议收尾时按同风格追加商品列表/详情两条断言（详见 kevin-coder 原始报告内容，未擅自改该共享文件）。

### R7 其它
- **未 commit**（工作区留 3 M + 3 ??）。无 DDL / 无迁移 / 无 menu / 无 dict，Flyway 最大版本仍 `V202608070233`。
- staging / prod 未部署，只本地 dev 验证。
- 本次起的 `mvn spring-boot:run` **已 kill，8080 已释放**（实测无监听）。
- 改 `ruoyi-gz-jp` 每次都跑 `mvn clean install`（非 clean 的 install 不重打 jar，exit 0 骗人）。

### dev 库遗留状态（**有意留作 Tier 1B / GZ-JP-202 的可见性 fixture**）

```
gz_jp_event    id=1  EVT-20260807-000001  8月上旬快闪场                  status=open   （end_time 2026-09-30 22:00，短期不会自然过期）
               id=2  EVT-20260807-000002  9月中旬未开场（可见性对照）    status=draft  ← 新增
gz_jp_product  id=1  JPP-20260807-000001  柯南 吧唧 一番赏 A赏           on_shelf  event=1  12800分  主图+2张图集+noticeText
               id=3  JPP-20260807-000003  软删后再建的商品               off_shelf event=1   9900分  notice/delivery 均 NULL
               id=4  JPP-20260807-000004  未开场里的上架商品（可见性对照）on_shelf event=2   8800分  ← 新增
```
正好覆盖「唯一可见 / 第 2 层拦 / **第 1 层拦**」，kevin-qa 与 202 的 mp E2E 可直接用，无需再造。无软删残留行。

---

## 对下游 ticket 的提示

### 给 GZ-JP-201 / 202（mp 前端页面）—— 返回结构

```ts
// ① GET /app/gz/jp/event/list?pageNum=1&pageSize=10  → 读 res.rows
export interface JpEventMpVO {
  id: string;                // ★ string 别写 number
  eventNo: string;           // EVT-yyyyMMdd-6位，路由/客服沟通用它
  name: string;
  coverImageUrl: string;     // 已是可渲染 URL；无图时是 /static/images/mock-product.png
  description: string | null;
  status: 'open';            // mp 侧恒为 open（见 R1，扩展后会有 open/closed）
  startTime: string;         // 'yyyy-MM-dd HH:mm:ss'
  endTime: string;           // 倒计时用
}
// ② GET /app/gz/jp/event/{id} → 读 res.data；code!==200 按「该场已结束」处理

// ③ GET /app/gz/jp/product/list?eventId={id}&pageNum=1&pageSize=20  → 读 res.rows
export interface JpProductMpVO {
  id: string;                      // ★ string
  productNo: string;               // JPP-yyyyMMdd-6位
  eventId: string;                 // ★ string
  eventNo: string | null;          // 场被删时 null
  eventName: string | null;        // 面包屑可用，省一次场详情请求
  name: string;
  mainImageUrl: string;            // 已是 URL；失败/无图回落占位图，永不为 null
  galleryImageUrls: string[];      // ★ 列表恒为 []，只有详情接口才有值
  priceCent: number;               // 「分」；★ 已包邮，结算页不得再加运费行
  deliveryDateText: string | null; // 「8月下旬」，可能 null → UI 兜「待定」
  noticeText: string | null;       // ★ 详情页须在 CTA 之上、展开不折叠；null 时整块隐藏
  status: 'on_shelf';              // mp 侧恒为 on_shelf
}
// ④ GET /app/gz/jp/product/{id} → 读 res.data（galleryImageUrls 在这里才有值）；
//    code!==200 → 「该商品已下架或所属场已结束」
```

**前端必注意 6 点**：
1. **列表读 `res.rows` 不是 `res.data`**，详情才是 `res.data` —— D16 一次逮到 6 处这类错。
2. **所有 id 是 string**，路由参数 / `:key` / 加购回传都按 string，别 `parseInt`。
3. **`pageSize` 必传**（不传服务端按 20 兜底；上限 50，传更大被静默收到 50，**不是丢数据**）。
4. **详情页图集要单独打详情接口**。
5. **`deliveryDateText` / `noticeText` 可能 `null`**，UI 要兜底（notice 为空时整块隐藏，别渲染空框）。
6. **两个接口都匿名可调**，浏览不用登录；加购/下单才 `ensureLoggedIn()`（项目「游客优先 / 无登录墙」口径）。

**mp 可达性（CLAUDE.md §8.3）**：本卡纯后端，无 mp 页面 → 无 flow、无临时入口。201/202 建页时记得给 `code/main/miniapp/test/e2e/flows/` 补 flow（AC X(a) 强制），本卡留的 3 条 fixture 可直接断言「draft 场里的上架商品不出现」。

### 给 GZ-JP-104 / 后续订单与履约
- **下单前必须服务端二次校验可见性两层**（`FLOW:F-JP-02.step3`）。直接复用 `IGzJpProductService.selectMpDetail(id)` —— 返回 null 就等价于「此刻不可下单」，**别另写一套判定**。
- `product_snapshot_json` 至少含 `{productNo, name, mainImageId, priceCent, deliveryDateText, noticeText}` —— **`noticeText` 必须进快照**；快照存 **`mainImageId`（file id）不是 URL**（URL 是 1h 预签名会失效）。
- **`priceCent` 已是包邮终价**，行金额 = `priceCent × qty`，不得加运费行。

### 编号 / 段位现状
| 资源 | 已占 | 下一个空号 |
|---|---|---|
| `sys_menu` GZ-JP 段 | 14000-14005（场）、14010-14014（商品） | 场按钮 **14006**；商品按钮 **14015**；订单 **14020** 段；履约看板 **14030** 段 |
| `sys_dict_type.dict_id` | 9280、9281 | **9282** |
| `sys_dict_data.dict_code` | 92801-92805 | **92806** |
| Flyway 版本 | …`V202608070233`（本卡无新增） | `date +V%Y%m%d%H%M` |

（本卡纯只读 API，**不占任何 menu / dict / 迁移号**。）

---

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

Tier 1B 建议覆盖：
- **后端集成 / API 契约回归**：`/app/gz/jp/product/list` + `/{id}` 全路径；重点重放 §3 的**可见性两层矩阵**（fixture 已在 dev 库：event1-open/product1-on_shelf、product3-off_shelf、event2-draft/product4-on_shelf）；断言字段 camelCase、id 全 string、无 stock 字段、`rows` 非 null。
- **匿名鉴权**：不带任何 header 调两端点应 200。
- **分页**：缺省 = 20、超大值封顶 50、`rows` 恒为数组。
- 本卡 **无 admin 页面**（plus-ui 零改动）→ 无 Playwright E2E 对象；**无 mp 页面**（miniapp 零改动）→ mp 模拟器 E2E 从 201/202 起才有对象。
- **Kevin 残留人验：N/A**（纯后端只读接口，不碰真机微信原生能力、无新页首版视觉）。

---

**结论：accept 两条全 PASS（ACCEPT1_EXIT=0 / ACCEPT2_EXIT=0，改动后重放 3 次均绿）。**

**⚠️ 本卡完工后，主线程发现并处置了 R1（mp 只看得到「进行中」场，与 GZ-JP-201/202 的三态分组+已结束仍可浏览需求不符）——见 GZ-JP-201 完工报告「视野扩展」段的后端扩展记录。**
