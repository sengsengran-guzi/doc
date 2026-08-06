# 修正：mp 可见性模型放宽（GZ-JP-101/103 完工后，GZ-JP-201 开工前）

> 不是正式 ticket（doc/jp/tickets 没有独立编号），是主线程发现的蓝图-实现不一致，按 CLAUDE.md §9.5「改源头」原则在 GZ-JP-201/202 开工前直接处置。改动范围：`ruoyi-modules/ruoyi-gz-jp`（GZ-JP-101/103 已建的场/商品 mp 查询层）。

## 为什么要做这件事

GZ-JP-101（场表+admin）和 GZ-JP-103（mp 查询 API）完工时，把 mp 端可见范围实现成「只有 open 状态的场才能看到」（closed/draft 都完全隐藏，商品同理）——严格符合 101/103 各自的 AC 字面（「场未 open 时 mp 侧查不到」「draft 场不下发」）。

但下游 GZ-JP-201/202 的 ticket 原文明确写着 Kevin 已拍板的需求：

- GZ-JP-201：「Kevin 已拍板首页做**聚合**...2. **进行中的场** —— 纵向卡片流，分「**进行中 / 即将开始 / 已结束**」三组，进行中置顶」
- GZ-JP-202：「场**已结束时商品仍可浏览**，加购入口置灰并提示「本场已结束」」

101/103 的实现只有「进行中」一组数据源，已结束的场完全查不到（404/500），201/202 根本没法实现这两条已拍板需求。这不是新的产品决策，是**已经决定但 101/103 未完整覆盖**，所以在 201 开工前直接补齐。

## 派单时的一处指令偏离（值得记录）

派单时给出的实现建议是 `isVisibleForMp(stored, endTime, now) = effective(...) != DRAFT`。**kevin-coder 没有照抄，理由充分**：`effective()` 会把「窗口已过的 draft」惰性算成 `CLOSED`（101 既有且正确的行为）。照抄的话，一个店员建完就忘、从未开过的 draft 场，会在 end_time 过后突然出现在客人的「已结束」列表里——直接违反 FLOW:F-JP-01.step1「draft 客人不可见」。

修正为**纯状态判定、不接时间**：

```java
// GzJpEventStatus.java
public static boolean isVisibleForMp(String stored) {
    return of(stored) != DRAFT;
}
```

到点与否只影响 VO 里显示成 `open` 还是 `closed`（仍走 `effective()`），不影响「能不能被看到」。已加 2 个单测专门锁死这个陷阱场景（`visibleForMpNeverLeaksExpiredDraft` / `expiredDraftEventStillInvisibleToMp`），真库也专门验证过（见下）。

## 两处超出字面指令、已确认合理的决策

1. **mp 场列表排序改了**：`sort_no ASC, start_time ASC` → `sort_no ASC, end_time DESC, id DESC`。closed 场进列表后，若仍按 `start_time ASC`，分页第 1 页会被陈年已结束场占满，「进行中置顶」在分页下失效。`end_time DESC` 让未结束的场（`end_time` 在未来）天然排在已结束之前，组内又是「最近的在前」。
2. **两条失败文案改了**（因为 closed 不再是失败态）：场详情 `该场不存在或已结束` → `该场不存在`；商品详情 `该商品已下架或所属场已结束` → `该商品已下架`。draft 场里的商品也回同一句，**刻意不区分**「不存在」和「未发布」，不向客人泄漏 draft 场的存在。

## 新旧行为对照表

`GET /app/gz/jp/*`，5 种场状态 × 4 个维度（**粗体 = 本次变化**）：

| 场（存库 status + 窗口） | event/list | event/{id} | product/list?eventId | product/{id}（该场 on_shelf 商品） |
|---|---|---|---|---|
| **draft**，窗口未到 | 不出现 | fail（`该场不存在`） | 空页 | fail |
| **draft**，窗口已过（陷阱点） | 不出现（照抄 spec 会漏） | fail | 空页 | fail |
| **open**，进行中 | 出现 `status:"open"` | 200 `status:"open"` | 出商品 + `eventBookable:true` | 200 + `eventBookable:true` |
| **open**，end_time 已过 | 旧不出现 → **新出现 `status:"closed"`** | 旧 fail → **新 200 `status:"closed"`** | 旧空页 → **新出商品 + `eventBookable:false`** | 旧 fail → **新 200 + `eventBookable:false`** |
| **closed**（手动关场） | 旧不出现 → **新出现 `status:"closed"`** | 旧 fail → **新 200 `status:"closed"`** | 旧空页 → **新出商品 + `eventBookable:false`** | 旧 fail → **新 200 + `eventBookable:false`** |

商品维度另有一条不受本次影响：`off_shelf` 商品在任何场状态下都不下发（list 不含、detail fail）。

### 前端契约要点（GZ-JP-201/202 直接用）

- `GzJpEventMpVO.status ∈ {"open","closed"}`，**`open` ⟺ 可下单**；`draft` 永不下发。
- 首页三组：进行中 = `status==='open' && startTime<=now`；即将开始 = `status==='open' && startTime>now`；已结束 = `status==='closed'`。「即将开始」不是第四种后端状态，是前端拿 `status`+`startTime` 派生的展示分组。
- `GzJpProductMpVO.eventBookable`（新字段）与 `status`（商品自身状态，mp 侧恒 `on_shelf`）是两码事：加购按钮置灰判 `eventBookable`，**别在前端拿 `endTime` 跟本地时钟比**（手动关场判不出来 + 客户端时钟不可信）。

## 改了哪些文件

```
 controller/applet/GzJpEventMpController.java   |  17 +--
 controller/applet/GzJpProductMpController.java |  21 ++--
 domain/enums/GzJpEventStatus.java              |  30 +++++-
 domain/vo/GzJpEventMpVO.java                   |  12 ++-
 domain/vo/GzJpProductMpVO.java                 |  15 +++     (新增 eventBookable 字段)
 service/IGzJpEventService.java                 |  42 ++++++--   (新增 isVisible，isBookable 不动)
 service/IGzJpProductService.java               |  17 +--
 service/impl/GzJpEventServiceImpl.java         |  47 ++++++---
 service/impl/GzJpProductServiceImpl.java       |  42 +++++---
 service/impl/GzJpEventStatusTest.java          | 115 ++++++++++++++++-----
 service/impl/GzJpProductMpQueryTest.java       |  69 ++++++++++---
 11 files changed, 329 insertions(+), 98 deletions(-)
```

全部在 `ruoyi-modules/ruoyi-gz-jp/` 内。**0 个迁移文件**、**admin 逻辑 0 改动**（`selectAdminPage`/`toAdminVO`/`open`/`close`/`delete`/`visibleToCustomer` 全未动），plus-ui、miniapp、miniapp-jp 未碰。

`isBookable`（严格，仅 effective==open）保留原样——未来订单/加购/支付继续用它；`isVisible`（宽松，open 或 closed）只服务只读浏览路径。两条闸在 `IGzJpEventService` 类 javadoc 里并列写明，防后人混用。SQL 用 `IN (open, closed)` 白名单而非 `!= draft` 黑名单，脏/未知 status 值一并挡外面，与 `GzJpEventStatus.of()` 回落 DRAFT 的「最保守」口径一致。

## 单测（101+102+103 全量 + 新增）

```
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductServiceTest
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.jp.service.impl.GzJpEventStatusTest
[INFO] Tests run: 17, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.jp.service.impl.GzJpProductMpQueryTest
[INFO] Tests run: 20, Failures: 0, Errors: 0, Skipped: 0
[INFO] Tests run: 57, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

52 → 57（场 14→17，商品 admin 20→20 一字未改，mp 18→20）。哪些断言改了方向：只有 4 条，全部是「closed/到点场在 mp 不可见」这条**本次要推翻的模型本身**（`closedEventDisappearsFromMp`→`closedEventStaysBrowsableButNotBookable` 等）。**「draft 不下发」和「off_shelf 不下发」的断言一条都没翻方向**，且都加了强化（draft 多了 `isVisible=false` 断言，off_shelf 多了 `never isVisible`）。

## 真库验证（dev 库，起后端跑真接口）

基线（fixture：id=1 open / id=2 draft）：

```
GET /app/gz/jp/event/list                    {"total":1,"rows":[{"id":"1","status":"open"}]}
GET /app/gz/jp/event/2 （draft）              {"code":500,"msg":"该场不存在"}
GET /app/gz/jp/product/list?eventId=1        {"total":1,"rows":[{"id":"1","status":"on_shelf","eventBookable":true}]}
GET /app/gz/jp/product/list?eventId=2        {"code":200,"total":0,"rows":[]}
GET /app/gz/jp/product/4 （draft场的on_shelf）{"code":500,"msg":"该商品已下架"}
GET /app/gz/jp/product/3 （off_shelf）        {"code":500,"msg":"该商品已下架"}
```

造 closed 场（`UPDATE gz_jp_event SET status='closed' WHERE id=1`）：

```
GET event/list      ★ closed 现在出现   {"total":1,"rows":[{"id":"1","status":"closed"}]}
GET event/1          ★ 改动前是 500     {"code":200,"data":{"id":"1","status":"closed"}}
GET product/list?eventId=1  ★ 商品可浏览 {"total":1,"rows":[{"id":"1","status":"on_shelf","eventBookable":false}]}
GET product/1        ★ 详情200+eventBookable=false+noticeText在
    {"code":200,"data":{"id":"1","eventBookable":false,"noticeText":"日本线下采购，包装可能有轻微磨损，介意慎拍"}}
closed 期间 draft 仍完全不可见：{"code":500,"msg":"该场不存在"} / {"code":500,"msg":"该商品已下架"} / {"total":0}
closed 期间 off_shelf 仍不可见：{"code":500,"msg":"该商品已下架"}
```

★★ 陷阱验证：窗口已过的 draft（`id=2 end_time` 改到过去，`status` 仍 `draft`）：

```
event/list  → {"total":1,"ids":["1"],"statuses":["closed"]}    ← 列表里只有 1，2 没漏出来
event/2     → {"code":500,"msg":"该场不存在"}                   ← 详情仍 fail
product/list?eventId=2 → {"total":0,"rows":[]}                 ← 商品列表仍空
product/4   → {"code":500,"msg":"该商品已下架"}                 ← 商品详情仍 fail
```

★ 到点的 open 场（`id=1 status=open` + `end_time` 已过）→ 惰性判定报 `closed`：

```
event/list  → {"total":1,"rows":[{"id":"1","status":"closed"}]}
event/1     → {"code":200,"status":"closed"}
product/list?eventId=1 → {"total":1,"rows":[{"id":"1","status":"on_shelf","eventBookable":false}]}
```

## fixture 已还原 ✅

```
gz_jp_event    id=1  status=open   version=3（原封未动）  update_time 原封未动
               id=2  status=draft  version=0（原封未动）
gz_jp_product  id=1  on_shelf  event=1
               id=3  off_shelf event=1
               id=4  on_shelf  event=2（draft 场对照）
```

还原后回归：`event/list` 只有 id=1(open)，`product/list?eventId=1` 有 id=1，`eventBookable=true`。`doc/jp/verify.sh` L1「场列表结构完整且不下发 draft」原样重放通过。`~/.m2` jar 已 `mvn clean install` 刷新到最新。起的后端已关，8080 无监听。

## 给 GZ-JP-201/202 的提示

- `miniapp-jp/src/api/` 目前没有 `gz-jp.ts`（103 是纯后端），201 建 API 类型镜像时写 `status: 'open' | 'closed'`、`eventBookable: boolean`（string ID 契约照旧）。三组分组按上面口径派生。
- 加购置灰判 `eventBookable === false`，提示文案「本场已结束」；场详情页头的已结束提示判 `event.status === 'closed'`。商品详情在 closed 场下照常 200，别再按 `code !== 200` 走失效页。
- 购物车失效项同一套字段够用：失效 = `eventBookable === false`（场已结束）或商品详情 fail（已下架）。
- 写路径纪律：加购 / 提交订单 / 支付一律继续用 `isBookable`（未变），**不要**因为「列表能查到」就放行下单。

---

**结论**：draft 仍然完全不可见（含窗口已过的 draft，真库四维度逐一验过）；closed（含到点的 open）现在可浏览、场 VO 报 `status=closed`、商品带 `eventBookable=false`；全部回归单测 57/57 全绿，其中「draft 不下发」「off_shelf 不下发」两组断言一条都没翻方向，`verify.sh` L1 契约原样重放通过。**未 commit**（主线程收尾）。
