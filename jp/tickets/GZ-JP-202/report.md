# GZ-JP-202 完工报告 — 小程序场详情 + 商品详情

**结论：accept #2（grep 注意事项区块）PASS（exit 0）；accept #1（`run.mjs product`）BLOCKED —— 本机微信开发者工具 IDE 登录过期（`cli islogin` → `{"login":false}`），与 GZ-JP-002 / 201 同一个人工扫码阻塞，非代码问题。** preflight 7 项 **6 绿 1 红**，红的只有 `devtools-login`。

**两个页面都已做完**：场详情（页头 + 倒计时 + 商品两列网格 + 上拉加载 + 已结束提示条）、商品详情（主图轮播 → 名称 → 价格大字+包邮 → 预计到货 → ★ 购买须知 → 底部固定 CTA）。

accept #1 的替代证据是三层：新增 **80 条单测**（总 164 全绿）+ **self-test 30/30（其中 16 条 negative）** + ★ **「真后端 → 真 logic → 真 flow 断言」LIVE 全链路**（含把 dev 库 fixture 临时改成 `closed` 直验 AC「场已结束时加购置灰」，改完已逐列还原）。

> 后端可见性契约（closed 场可浏览 / draft 永不下发 / `eventBookable`）见 `doc/jp/tickets/_visibility-extension-pre-201.md`，本报告不重复。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| miniapp-jp 工作区起手 clean | ✅ `main` @ `a869cb1`（GZ-JP-201） |
| 上游 GZ-JP-201（首页）已 merge | ✅ commit `a869cb1`「小程序首页聚合」在 log 里 |
| 首页可进场（第 1 跳入口存在） | ✅ `index.logic.ts` 的 `buildEventRoute()` 生成 `/pages/event/index?id=..&eventNo=..`，`EVENT_DETAIL_ROUTE` 常量与本卡新建的页面路径一致 |
| 上游 GZ-JP-103（mp 商品 API）可调 | ✅ raw output 见下（列表 / 详情 / 图集 / `eventBookable` 全对得上） |
| 后端起手状态 | ✅ 8080 **已在跑**（GZ-JP-201 特意留的 PID 72376），健康检查 `event/list` HTTP 200，**本会话未重启、未新起** |
| dev 库 fixture 在 | ✅ 场 id=1 open / id=2 draft；商品 id=1 on_shelf(有 notice+2 张图集) / id=3 off_shelf / id=4 draft 场对照 |
| 蓝图引用可读 | ✅ `UI:mp.event_detail` / `UI:mp.product_detail` / `UI:mp.product_detail.notice`（`authority/ui-index.yaml`）+ `design-options/mp-product-detail.md`（方案 A 已选定） |
| 兄弟仓未污染 | ✅ miniapp `59635d4` / RuoYi-Vue-Plus `66b6b58bc` / plus-ui `f313c41`，均 0 改动 |

```
$ git status --short && git log --oneline -3
（无输出 = clean）
a869cb1 feat: 小程序首页聚合（GZ-JP-201）
fccd504 feat: mp E2E harness + 登录链路验证 (GZ-JP-002)
637d7d6 feat: init miniapp-jp scaffold (GZ-JP-001)

$ curl -s --noproxy '*' -o /dev/null -w '%{http_code}' localhost:8080/app/gz/jp/event/list -H 'clientid: mp-applet-gz-jp'
200                       # 8080 活着，复用不重启

$ curl -s --noproxy '*' 'localhost:8080/app/gz/jp/product/list?eventId=1' -H 'clientid: mp-applet-gz-jp'
{"total":1,"rows":[{"id":"1","productNo":"JPP-20260807-000001","eventId":"1","eventNo":"EVT-20260807-000001",
 "eventName":"8月上旬快闪场","name":"柯南 吧唧 一番赏 A赏","mainImageUrl":"http://localhost:9000/...",
 "galleryImageUrls":[],          # ← 列表接口图集恒空（契约如此），详情才下发
 "priceCent":12800,"deliveryDateText":"8月下旬",
 "noticeText":"日本线下采购，包装可能有轻微磨损，介意慎拍","status":"on_shelf","eventBookable":true}],"code":200}

$ curl -s --noproxy '*' 'localhost:8080/app/gz/jp/product/1' -H 'clientid: mp-applet-gz-jp'
... "galleryImageUrls":[ 2 个预签名 URL ] ...   # ← 详情接口才有图集，与 VO javadoc 一致

mysql> SELECT id,event_no,status FROM gz_jp_event ORDER BY id;
1  EVT-20260807-000001  open      # 唯一可浏览场
2  EVT-20260807-000002  draft     # 不下发
mysql> SELECT id,event_id,status,price_cent FROM gz_jp_product ORDER BY id;
1  1  on_shelf   12800
3  1  off_shelf   9900            # 不下发
4  2  on_shelf    8800            # draft 场里的，不下发
```

**蓝图 / 契约关键约束摘录**（`authority/ui-index.yaml` + `_visibility-extension-pre-201.md`）
- `UI:mp.event_detail`：顶部场信息（封面/名称/倒计时或已结束提示）→ 商品两列网格 → 上拉分页；**一期无筛选无排序**；**场已结束时商品仍可浏览，加购与下单入口置灰**。
- `UI:mp.product_detail`：主图轮播（主图+图集）→ 名称 → 价格（大字，标「包邮」）→ 预计到货 → ★ 注意事项 → 底部固定 CTA。**一期不做富文本，商品说明用图集承载**。
- `UI:mp.product_detail.notice`（★ 甲方硬要求，`design-options/mp-product-detail.md` 方案 A 已拍板）：**在 CTA 之上 + 默认整段展开不做收起交互 + 底色区分于正文**。
- `REQ-ORDER-004`：拼团**全包邮**，商品价即最终支付价，**任何页面不得再出运费行**。
- 加购放行**只看 `eventBookable`**：不看 `status`、不拿 `endTime` 跟本地时钟比（店员手动关场判不出来 + 客户端时钟不可信）。

## 实现摘要

```
 M src/pages/index/index.logic.ts |  82 +--    三个共用函数上提，原样 re-export（201 的 41 条测试零改动）
 M test/e2e/run.mjs               |   1 +     FLOWS 注册 product
 M test/e2e/flows/smoke.mjs       |   7 +     PAGES 加两页（AC X(a) 可达性落点）
 M test/e2e/mp-e2e.mjs            |  20 +-    sleep 支持 MP_E2E_SLEEP_SCALE（只缩放等待，不动断言）
 M test/e2e/self-test.mjs         | 202 ++-   currentPage 返完整 page + product 假件 + 16 条用例
 M test/e2e/README.md             |  15 +-    product flow 用法 + negative 清单

 A src/api/gz-jp/format.ts             183   ★ 后端契约适配层（时间/倒计时/图片兜底/分→元）
 A src/api/gz-jp/format.test.ts        107   16 条（倒计时 + 金额）
 A src/api/gz-jp/product.ts            120   ★ 商品 API + GzJpProductMpVO 镜像
 A src/locale/event.zh-CN.ts            74
 A src/locale/product.zh-CN.ts          75
 A src/components/biz/BizProductCard.vue 198  ★ 商品卡（两列网格用）
 A src/components/biz/BizStepper.vue    125   ★ 数量步进器
 A src/pages/event/index.vue            509   ★ 场详情页
 A src/pages/event/index.logic.ts       223   ★ 纯逻辑（展示态/倒计时/★加购放行/分页合并/路由）
 A src/pages/event/index.logic.test.ts  290   37 条
 A src/pages/product/detail.vue         515   ★ 商品详情页（accept #2 断言的就是这个文件）
 A src/pages/product/detail.logic.ts    152   ★ 纯逻辑（轮播/数量/★须知正文/★区块顺序）
 A src/pages/product/detail.logic.test.ts 225 27 条
 A test/e2e/flows/product.mjs           337   ★ accept #1 的 flow（真点两跳）
```

**未 commit**（按派单口径留在工作区，主线程统一收尾）。doc / RuoYi-Vue-Plus / plus-ui / miniapp 四仓一行未碰。
`src/pages.json` 由 uni-pages 自动生成且已 `.gitignore`，两个新页已自动注册（见产物核对）。

### 1. 场详情（`/pages/event/index`）

| 区块 | 实现 | 关键点 |
|---|---|---|
| ① 场信息头 | 封面 / 名称 / 状态标签 / 时间行 / 场编号 | 时间行三态：进行中→**倒计时**（每秒 tick，`onUnload` 清 interval）/ 即将开始→开场时刻 / 已结束→结束时刻 |
| ② 已结束提示条 | `v-if="event.status === 'closed'"` | 文案「本场已结束，商品仅可浏览，不能加入购物车」，琥珀底 |
| ③ 商品两列网格 | `BizProductCard` × N + `onReachBottom` 上拉分页 | 卡片 = 主图 + 名（2 行截断）+ 价格 + **包邮标签** + 预计到货；`eventBookable=false` 的卡整卡降饱和 + 「已结束」角标 |

四态（loading / error+重试 / empty / 有数据）全渲染在同一个 `.jp-event-detail__grid` 容器内 —— smoke 锚点在任何数据状态下都在（同 201 首页 `.jp-home__events` 的取法）。

### 2. 商品详情（`/pages/product/detail`）

模板顺序**严格照 `SECTION_ORDER` 常量**：`gallery → name → price → delivery → notice → cta`。
把顺序写成常量而不是只存在于模板里，是为了让「★ 注意事项在 CTA 之上」这条甲方硬要求**能被单测直接断言** —— 模板里改坏了没人拦得住，常量改坏了单测立刻红（且有一条 negative 用例专门证明该断言不是恒真）。

★ 三条硬要求的落地：
- **在 CTA 之上** → `SECTION_ORDER` 单测 + 编译后 wxml 位置核对 + E2E flow 渲染顺序断言，三重锁。
- **默认整段展开、不做收起交互** → 页面无任何截断/切换逻辑；`buildNoticeText` 返回整段正文；样式 `white-space: pre-wrap` 不限行数；accept #2 的 grep 就是守这条。
- **底色区分正文** → 正文区是白卡/透明，须知区 `background: var(--c-amber-soft)` + 琥珀色标题 + 圆形「!」角标。

另外 **`noticeText` 为空时区块不消失**，兜一段通用风险提示（`noticeFallback`）。理由写在 `buildNoticeText` 的 javadoc：一个时有时无的告知位，客人形成不了阅读习惯，事后纠纷也没有「页面上一直写着」这个立足点。

### 3. ★ 加购是**占位交互**，没有假装成功

购物车域归 GZ-JP-104（后端）/ GZ-JP-203（购物车页），本卡不实现。点「加入购物车」：

- `eventBookable !== true` → toast「本场已结束，无法加入购物车」，按钮已置灰；
- 否则 → toast「购物车即将上线，敬请期待」。

**两条分支都不写任何本地/远端购物车数据，也不给「已加入」的成功反馈** —— 不制造看起来能用其实是假的功能。数量 stepper 是真的（值会变、会 clamp），只是它的值目前没有下游消费者。

### 4. 三个「不写下来下次一定再踩」的实现决策

1. **加购放行判定只写一份，两页共用**。`buildAddToCartState` 定义在 `pages/event/index.logic.ts`，商品详情页 `import` 过去用，**刻意不在商品详情里重写一遍**。两个页面各写一份「怎么算能不能加购」是这类 bug 的经典温床。缺字段（`undefined`/`null`/非布尔）一律判置灰 —— 拦错方向的代价不对等（放进一笔已结束场的单 > 拦下一笔本可成交的单，何况后端下单时还会用 `isBookable` 再拦一道）。
2. **倒计时归零退化成「已于…结束」，绝不显示 `00:00:00` 或负数**。`countdownParts` 在 `left <= 0` 时返回 `null`（从源头收敛，而不是在模板里到处判 `< 0`）；页面据此切文案。⚠️ 但**倒计时归零不是下单闸门** —— 本地时钟已过 `endTime` 而后端还报 `open` 时，CTA 依然按 `eventBookable` 走可点，这是刻意的。
3. **分页合并按 id 去重**。翻页途中店员改 `sort_no` 会让同一条商品出现在两页里，直接 concat 会「同一商品在网格里出现两次」且 `:key` 重复导致节点复用错乱。重复时**保留先到的那条**（不覆盖）：网格自上而下追加，把已经渲染在屏上的卡片换成后到副本会造成可见跳动。「还有没有下一页」用 `已加载 < total` 判而不是 `上页条数 == pageSize`（后者在总数刚好整除时多打一次空请求，且某页因下架不满时会提前误判到底）。

### 5. 共用层上提（201 报告点名建议的事）

201 报告说：`parseBackendTime` / `formatClock` / `hasRealCover` 现在有第二个使用方了，建议上提。已照做 → 新建 `src/api/gz-jp/format.ts`。

- **放 api/ 而不是 utils/**：这三个函数每个都在补一条**后端契约**的坑（后端发的时间串格式 / 后端无图回落的占位路径 / 后端金额单位是分），契约变了要一起改。放 utils 会让人以为是通用工具、改后端时想不到来看。
- **`index.logic.ts` 原样 re-export 这三个**，所以 201 的 41 条单测与首页 import 路径**一行没改**（已实测复跑 41/41 绿）。
- `BACKEND_PLACEHOLDER_COVER` 留在 `event.ts` 没动（201 的测试从那里 import）。

### 6. 改了 harness 一处（必须知会）

`mp-e2e.mjs` 的 `sleep()` 新增 `MP_E2E_SLEEP_SCALE` 缩放系数（默认 1 = 原速）。self-test 用**假句柄**跑 flow 时渲染是瞬时的，那些为真模拟器准备的 `sleep(2500)` 纯属空等 —— 加了 product 的 16 条用例后 self-test 直接超过 2 分钟、于是没人会愿意跑它，等于白写。self-test 设为 0 后整轮秒级。

**★ 只缩放「等多久」，不改任何断言、不跳过任何步骤**，`run.mjs` 真跑时不设置该变量（恒为原速）。这不是让断言变松的后门。

## AI 自测（raw output）

### 1. accept #2（逐字）—— ★ 真绿

```
$ grep -q 'notice' code/main/miniapp-jp/src/pages/product/detail.vue && \
    ! grep -qE 'collapse|折叠' code/main/miniapp-jp/src/pages/product/detail.vue
ACCEPT#2 EXIT=0
```

含义 = 页面文件叫 `src/pages/product/detail.vue`、内容含 `notice`、且**全文（含注释）不出现 `collapse` / `折叠`**。
写这个文件时全程规避了这两个词（想表达「不折叠」的地方一律写成「默认整段展开 / 不做收起交互 / 不限行数不截断」），CSS 也没用 `border-collapse`。

### 2. 单测 —— ★ 真绿（164 = 84 存量 + 80 本卡）

```
$ pnpm test
 ✓ src/api/gz-jp/format.test.ts        (16 tests)
 ✓ src/pages/event/index.logic.test.ts (37 tests)
 ✓ src/pages/product/detail.logic.test.ts (27 tests)
 ✓ src/pages/index/index.logic.test.ts (41 tests)   ← 201 的，一行没改，原样绿（re-export 回归）
 ✓ src/api/gz-common.test.ts / gz-user.test.ts / store/token.test.ts /
   components/biz/MeHeader.test.ts / utils/watermark.test.ts / composables/useCountdown.test.ts
 Test Files  10 passed (10)
      Tests  164 passed (164)
VITEST_EXIT=0
```

| 组 | 条数 | 关键边界（★ = AC 直接相关） |
|---|---|---|
| `buildAddToCartState` | 5 | ★ `false` → 置灰 / ★ 缺字段与非布尔真值（`'true'` / `1`）一律置灰 / ★ `status='on_shelf'` + `eventBookable=false` 仍置灰 |
| `SECTION_ORDER` / `noticeIsAboveCta` | 5 | ★ notice 下标 < cta / **顺序被改坏时必须判 false**（证明断言非恒真）/ notice 或 cta 缺失也判 false |
| `buildNoticeText` | 5 | ★ 商家没填四种形态（null/undefined/空串/纯空白）都出兜底、区块不消失 / ★ 800 字长文不截断 / 多行保留 |
| `buildHeaderTiming` | 8 | ★ 倒计时归零与已过点都退化成 endedAt（不出 00:00:00 / 负数）/ 解析失败 → none 不渲染 "Invalid Date" / 随 now 推进递减 |
| `eventPhase` | 7 | `startTime === now` → live / status 异常值 7 种一律 ended / open 但 startTime 坏 → live |
| `mergeProductPage` | 7 | ★ 按 id 去重 + 重复保留先到 / 空洞与 null 元素 / ★ id 缺失不参与去重 / 不改原数组 |
| `hasMoreProducts` | 5 | ★ 已加载 == 总数即到底 / 某页不满但总数没到仍判还有 / total 脏值 |
| `buildProductRoute` | 4 | id + productNo 都带 / URL 编码 / 路由常量与文件路径一致 |
| `buildGalleryImages` | 9 | ★ 主图恒在最前 / ★ 滤掉后端占位图 / ★ 去重（主图重复进图集）/ ★ 一张真图都没有 → 空数组 |
| `clampQuantity` | 8 | ★ 越界夹取 / ★ 小数向下取整（1.9 → 1，不凭空多算钱）/ ★ 数字字符串（mp input 返字符串的项目老坑）|
| `countdownParts` / `formatHms` / `formatYuan` | 16 | ★ 已到点 / 已过点 → null / ★ 无价 → 空串不渲染 NaN / ★ 后端发字符串金额不当数字算 / 整元省小数 |

### 3. ★ LIVE 全链路：真后端 → 真 logic → 真 flow 断言（accept #1 跑不了时的核心替代证据）

临时 vitest 用 `curl` 打真后端拿**原始响应**，用**页面实际在用的** logic 模块（`formatYuan` / `buildAddToCartState` / `buildNoticeText` / `buildGalleryImages`）算出「页面会渲染成什么」，再喂给 **product flow 的真断言主体 `runWith`**（跑完已删）：

```
[LIVE] event/list 原始响应: {"total":1,"rows":[{"id":"1","eventNo":"EVT-20260807-000001",
       "name":"8月上旬快闪场","status":"open","startTime":"2026-08-07 10:00:00",
       "endTime":"2026-09-30 22:00:00"}],"code":200,"msg":"查询成功"}
[LIVE] product detail 关键字段: {"name":"柯南 吧唧 一番赏 A赏","priceCent":12800,
       "deliveryDateText":"8月下旬","noticeText":"日本线下采购，包装可能有轻微磨损，介意慎拍",
       "eventBookable":true,"gallery":2}
[LIVE] 真 logic 算出：price="128" cta.disabled=false notice=21字 gallery=3张

  ✓ 第 1 跳：首页场卡 → 场详情（pages/event/index）
  ✓ 场详情页头场名来自后端真数据："8月上旬快闪场"
  ✓ 已结束提示条与后端 status=open 一致（未渲染）
  ✓ 商品网格文案来自后端真数据：["柯南 吧唧 一番赏 A赏"]
  ✓ 第 2 跳：场详情商品卡 → 商品详情（pages/product/detail）—— ★ 从首页两跳可达
  ✓ 价格来自后端真数据：¥128（priceCent=12800）
  ✓ ★ 价格旁有「包邮」标识（REQ-ORDER-004）
  ✓ ★ 注意事项区块正文与后端逐字一致（21 字，未截断）
  ✓ ★ 注意事项节点在 CTA 之上（渲染顺序断言）
  ✓ ★ 加购按钮状态与后端 eventBookable=true 一致（可点）
  ✓ 首页两跳可达商品详情 + 场/商品文案来自后端真数据 + 包邮标识 + 注意事项在 CTA 之上 + 加购态与后端一致
 Test Files  1 passed (1)
```

★★ **AC「场已结束时加购置灰」直验** —— 把 fixture 临时改成 `closed`（改完已逐列还原，见下）：

```
mysql> UPDATE gz_jp_event SET status='closed' WHERE id=1;   → ROW_COUNT()=1

$ curl .../app/gz/jp/event/1
{"code":200,"data":{"id":"1","status":"closed",...}}                    ← 场仍可浏览（不是 404）
$ curl .../app/gz/jp/product/1
{"code":200,"name":"柯南 吧唧 一番赏 A赏","status":"on_shelf",
 "eventBookable":false,"noticeText":"日本线下采购，包装可能有轻微磨损，介意慎拍"}
                                                        ↑ 商品仍下发，但 eventBookable=false

[LIVE-CLOSED] event.status = closed
[LIVE-CLOSED] 商品仍可浏览： 1 件                        ← AC「场已结束时商品仍可浏览」
[LIVE-CLOSED] 真 logic 算出 cta = {"disabled":true,"reason":"ended"}
[LIVE] 真 logic 算出：price="128" cta.disabled=true notice=21字 gallery=3张
  ✓ 已结束提示条与后端 status=closed 一致（已渲染）
  ✓ ★ 加购按钮状态与后端 eventBookable=false 一致（置灰）      ← ★ AC 直验通过
  ✓ 首页两跳可达商品详情 + ... + 加购态与后端一致
```

**fixture 已逐列还原 ✅**（`gz_jp_event.update_time` 无 `ON UPDATE CURRENT_TIMESTAMP`、`version` 由 `@Version` 管，裸 SQL 改 `status` 不动这两列，所以还原是精确的）：

```
=== BEFORE ===  1 open   version=3 update_time=2026-08-07 03:15:48 update_by=1 del_flag=0
                2 draft  version=0 update_time=2026-08-07 03:14:58 update_by=1 del_flag=0
=== AFTER  ===  1 open   version=3 update_time=2026-08-07 03:15:48 update_by=1 del_flag=0   ← 逐列一致
                2 draft  version=0 update_time=2026-08-07 03:14:58 update_by=1 del_flag=0

=== 还原后接口回归 ===
event/list             {"total":1,"rows":[{"id":"1",..."status":"open",...}],"code":200}
product/list?eventId=1 {"total":1,"rows":[{"id":"1","status":"on_shelf","eventBookable":true}]}
=== 可见性契约回归（201/103 的口径没被本卡碰坏）===
event/2   (draft)      {"code":500,"msg":"该场不存在"}
product/4 (draft场里)  {"code":500,"msg":"该商品已下架"}
product/3 (off_shelf)  {"code":500,"msg":"该商品已下架"}
```

临时脚本 `src/pages/product/tmp-live-check.test.ts` **已删除**（`ls src/pages/product/` 只剩 `detail.logic.test.ts` / `detail.logic.ts` / `detail.vue`）。

### 4. accept #1（逐字）—— BLOCKED：devtools IDE 登录过期

```
$ cd code/main/miniapp-jp && node test/e2e/run.mjs product
[preflight] 硬 gate 体检（无降级）
  ✓ devtools cli: /Applications/wechatwebdevtools.app/Contents/MacOS/cli
  ✓ devtools 服务端口开着 (http://127.0.0.1:26863)
  ✗ devtools 未登录（cli islogin → {"login":false}）—— 模拟器 runtime 起不来，表象会是
    launch 报「http port is open」或每条命令 10s 超时，都不是代码问题
    → 修复：打开微信开发者工具 → 用手机微信扫码登录（本机一次性人工动作，脚本代不了），然后重跑
  ✓ dist 完整: .../dist/build/mp-weixin/app.json
  ✓ dist = dev profile（本地后端 + wxMOCK + jp clientid）
  ✓ 后端可达: http://localhost:8080 (HTTP 401)
  ✓ 后端认 clientid=mp-applet-gz-jp（openid=mock-jp-tester）
[preflight] ❌ 阻塞（devtools-login）—— 硬 gate 无降级，修好上面再跑
ACCEPT#1 EXIT=2          # 2 = preflight 阻塞，符合退出码语义

$ /Applications/wechatwebdevtools.app/Contents/MacOS/cli islogin
{"login":false}          # 独立复核，与 GZ-JP-002 / 201 完全同一个阻塞
```

**处置（严格按「不绕过」）**：没有 kill / 重启 Kevin 的 IDE；没有注释 preflight；没有伪造通过；没有降级。跑之前先做了一次 `build-dist.mjs development` 确保产物是当前代码，排除「产物旧」干扰后阻塞点仍只有登录态一项。**解除条件**：Kevin 扫码 → 重跑 `node test/e2e/run.mjs product`（或 `all`），约 30 秒，无需改任何代码。

### 5. flow 逻辑体检（零环境依赖，证明「flow 代码是好的」）

```
$ node test/e2e/self-test.mjs
  ✓ smoke / 全部页面正常 → 通过
  ✓ smoke / 首页缺 .jp-home__events 标志元素 → 必须 fail
  ✓ smoke / 某页渲染空壳(view 数不足) → 必须 fail
  ✓ login / 已登录起步（先登出再重登）→ 通过
  ✓ login / 游客起步 → 通过
  ✓ login / 协议框默认已勾选（合规回归）→ 必须 fail
  ✓ login / 登成了另一个小程序的用户（串号）→ 必须 fail
  ✓ home / 三区块齐 + 卡片名与后端一致 → 通过
  ✓ home / 三组混排（进行中置顶）→ 通过
  ✓ home / ★页面显示前端 mock 文案（与后端对不上）→ 必须 fail
  ✓ home / ★banner 塌陷（swiper 里既无图也无默认占位）→ 必须 fail
  ✓ home / ★缺订单入口区块 → 必须 fail
  ✓ home / ★分组顺序错（已结束排到了进行中前面）→ 必须 fail
  ✓ home / ★后端 0 条场（fixture 没了）→ 必须 fail 而不是假绿
  ✓ product / 两跳可达 + 场·商品文案与后端一致 + 包邮 + notice 在 CTA 之上 → 通过
  ✓ product / 已结束场（closed + eventBookable=false，CTA 置灰 + 提示条）→ 通过
  ✓ product / ★第 1 跳跳错页（首页场卡路由与场详情文件名对不上）→ 必须 fail
  ✓ product / ★第 2 跳跳错页（商品卡路由不对）→ 必须 fail
  ✓ product / ★场详情显示前端 mock 场名（与后端对不上）→ 必须 fail
  ✓ product / ★商品网格显示前端 mock 商品名 → 必须 fail
  ✓ product / ★后端 closed 但页面没渲染「已结束」提示条 → 必须 fail
  ✓ product / ★场没结束却显示「已结束」提示条（吓跑客人）→ 必须 fail
  ✓ product / ★价格与后端 priceCent 对不上（分→元换算错）→ 必须 fail
  ✓ product / ★价格旁没有「包邮」标识（AC）→ 必须 fail
  ✓ product / ★注意事项区块整个不见了 → 必须 fail
  ✓ product / ★注意事项正文被截断（"…介意慎拍" 只显示前半段）→ 必须 fail
  ✓ product / ★注意事项被排到 CTA 之后（违反甲方硬要求）→ 必须 fail
  ✓ product / ★★ 场已结束（eventBookable=false）但加购按钮仍可点 → 必须 fail
  ✓ product / ★场进行中却把加购按钮置灰（白白拦掉成交）→ 必须 fail
  ✓ product / ★后端该场 0 件在架商品（fixture 没了）→ 必须 fail 而不是假绿

[self-test] 30/30 通过
SELFTEST_EXIT=0
```

30 条里 **16 条是 negative**（本卡新增 16 条中 14 条 negative）。为此把 product flow 拆成 `run(mp)`（拉后端）+ `runWith(mp, data)`（纯断言），**不是**在 flow 里埋测试用环境变量后门。

**加购置灰这条特意写了两个方向的 negative**：「场已结束却能点」和「场进行中却置灰」都必须 fail —— 只测一个方向的话，把按钮写成「永远置灰」也能骗过测试。

### 6. E2E 断言用的选择器在**编译产物**里确实存在（替代证据）

```
$ node -e "const j=require('./dist/build/mp-weixin/app.json'); console.log(j.pages.join('\n'))"
pages/index/index
pages/agreement/index
pages/event/index        ← ★ 本卡新页，uni-pages 自动注册
pages/login/index
pages/me/about
pages/me/index
pages/me/profile
pages/product/detail     ← ★ 本卡新页
tabBar: 首页/我的          ← 本卡不动 tabbar（详情页不该进 tab）

$ 逐个 grep dist/build/mp-weixin/
jp-event-detail__grid        pages/event/index.wxml       # smoke 锚点
jp-event-detail__name        pages/event/index.wxml
jp-event-detail__ended-text  pages/event/index.wxss
jp-product-card               components/biz/BizProductCard.wxss
jp-product-card__name        components/biz/BizProductCard.wxss
jp-product-detail            pages/product/detail.wxss    # smoke 锚点
jp-product-detail__price     pages/product/detail.wxss
jp-product-detail__price-row pages/product/detail.wxml
jp-product-notice__body      pages/product/detail.wxml
jp-product-cta__btn          pages/product/detail.wxss
biz-stepper                  components/biz/BizStepper.wxml

$ 新接口已进产物
OK: app/gz/jp/product/list     OK: app/gz/jp/product/     OK: app/gz/jp/event/

$ locale 文案已进产物
包邮 / 购买须知 / 本场已结束 / 购物车即将上线 / 国际邮费与国内运费已包含在价格内 / 距结束 / 预计到货
  → locale/product.zh-CN.js + locale/event.zh-CN.js
```

★ **「注意事项在 CTA 之上」在编译后的真 wxml 里核对**（与 flow 的断言口径完全相同）：

```
$ node -e "const s=require('fs').readFileSync('dist/build/mp-weixin/pages/product/detail.wxml','utf8');
           console.log('jp-product-notice @', s.indexOf('jp-product-notice'));
           console.log('jp-product-cta    @', s.indexOf('jp-product-cta'))"
jp-product-notice @ 3580
jp-product-cta    @ 3956
OK: notice 在 CTA 之上
```

### 7. 工程健康（001/002/201 的绿线全部保持）

```
$ pnpm type-check   → exit=0     # vue-tsc --noEmit，无输出
$ pnpm lint         → exit=0     # eslint 0 problems
$ pnpm test         → exit=0     # 164 passed（84 存量 + 80 本卡）
$ node test/e2e/self-test.mjs → exit=0    # 30/30
$ node test/e2e/build-dist.mjs development → exit=0   # dist 是当前代码，dev profile

# 兄弟仓 0 污染
miniapp        0 处改动  59635d4
RuoYi-Vue-Plus 0 处改动  66b6b58bc
plus-ui        0 处改动  f313c41
doc            2 处改动（test/kevin-test.xlsx + 未跟踪 doc/，均为本卡开工前既有，非本卡产生）
```

## 风险提示 / 已知 issue

1. **★ 加购是占位交互，不是真功能**。点「加入购物车」只 toast，**没有任何数据落地**。Kevin 或客户演示时看到这个 toast 是**预期行为**不是 bug；真购物车归 GZ-JP-104/203。
2. **本卡未跑过真模拟器**（同 GZ-JP-002 / 201）。两个新页的**实际渲染**（两列网格塌不塌、swiper 高度 640rpx 合不合适、须知区琥珀底够不够醒目、底部 fixed CTA 与安全区的关系、倒计时每秒重绘卡不卡）**尚未被人或机器看过一眼**。self-test 只证明 flow 逻辑自洽，选择器与真实渲染树对不对得等 devtools 登录恢复后首跑。
3. **上拉分页在当前 fixture 下测不到**：dev 库该场只有 1 件商品，`total=1 < pageSize=20`，`onReachBottom` 分支永远不触发。合并/去重/到底判定有 12 条单测覆盖，但**真机上拉的手感与触发时机没被验证过**。要真验需要往 `gz_jp_product` 造 ≥ 21 件商品（本卡刻意没造，避免污染共享 dev 库 fixture、影响 103/201 的既有断言）。
4. **商品图是 MinIO 预签名 URL，1h 过期**。停留超过 1 小时再滚动，图会 404 —— 卡片与详情都做了 `@error` 兜到占位块（不出破图），但**用户看到的是占位块不是商品图**。真机长时间停留时会遇到。根治要后端换长效 URL 或前端定时重拉，不在本卡范围。
5. **场封面在 dev 期全是占位块**：fixture 的 `coverImageUrl` 是 mp 侧不存在的 `/static/images/mock-product.png`。场详情页头会显示渐变 + 🎏 占位。**不是 bug**（`hasRealCover` 刻意判掉），但 Kevin 首次看这页会注意到。商品主图有真 MinIO 图，所以商品卡/详情是有图的。
6. **倒计时用客户端时钟**（详情接口不返 serverNow）。只影响**展示**；能不能加购永远看 `eventBookable`。用户改系统时间能让倒计时乱跳，但改不动加购闸门。
7. **`onReachBottom` 依赖页面滚动**：商品少时页面不足一屏，触底事件不触发（这是正常的，因为也没有下一页）。但如果将来页头变得很高而商品仍很少，可能出现「有下一页却触不了底」—— 现在 `hasMore` 为 true 时底部不显示「没有更多了」，用户能看出还有内容。
8. **`MP_E2E_SLEEP_SCALE` 是新加的 harness 变量**。虽然只缩放等待时长，但**如果将来有人在 CI 里误设成 0 去跑 `run.mjs`**，真模拟器会因为不等渲染而大面积假红（不是假绿，方向是安全的）。README 已写明「run.mjs 真跑时不设置」。
9. **`galleryImageUrls` 只有详情接口下发**（列表恒空数组）。这条契约写进了 `product.ts` 的 javadoc；下游若想在列表里做图集轮播，需要先改后端，别指望列表接口带回来。

## 残留进程（需要处置）

后端**是 GZ-JP-201 会话起的、本卡未重启也未新起**（起手就在跑，健康检查 200）。**继续保留运行** —— 下游 kevin-qa 跑 `run.mjs product` 时 flow 会直连它拉真数据比对，preflight 也要它：

```bash
# 后端 mvn spring-boot:run -pl ruoyi-admin（PID 72376，日志 /tmp/gzjp-201-backend.log）
lsof -ti:8080 | xargs kill        # 不需要时收掉
```

docker 的 MySQL / Redis / MinIO 原本就在跑，未动。本会话自己起的后台任务只有一次 self-test（已结束、已清理，`pgrep` 无残留）。dev 库 fixture **已逐列还原并回归验证**。

## 对下游 ticket 的提示

### ★ GZ-JP-104 / 203（购物车）—— 接真加购时改哪里

**只需要改 1 个函数 + 1 个 locale key，页面结构与置灰逻辑一行不用动**：

1. `src/pages/product/detail.vue` 的 `onAddToCart()` —— 当前是：
   ```
   if (ctaDisabled) → toast「本场已结束，无法加入购物车」; return
   否则            → toast「购物车即将上线，敬请期待」      ← 把这一行换成真加购
   ```
   换成：`ensureLoggedIn()`（加购要登录，`useAuth` 已有）→ 调购物车 API（带 `productId` / `eventId` / `quantity.value`）→ 成功 toast + 可选跳购物车。
   **`ctaDisabled` 那条分支别动** —— 它是 AC「场已结束时加购置灰」的落地，且有 4 条 self-test negative 守着。
2. `src/locale/product.zh-CN.ts` 的 `addToCartComingSoon` 可删（换成 `addToCartSuccess` 之类）。
3. **数量已经是真的**：`quantity` ref + `BizStepper` + `clampQuantity`（8 条单测），直接取 `quantity.value` 用，值一定在 `[1,99]` 的整数区间内。
4. **加购请求体所需字段商品详情 VO 全有**：`id`（商品主键）、`eventId`（所属场主键，后端刻意下发以免再查一次）、`productNo` / `eventNo`（业务码，做订单快照用）。
5. **写路径纪律**（`_visibility-extension-pre-201.md` 已强调，再说一次）：加购 / 提交订单 / 支付一律以后端 `isBookable` 为准再拦一道，**前端置灰只是体验层**，不要因为「前端已经灰了」就省掉后端校验。
6. **购物车失效项判定**与本卡同一套：失效 = `eventBookable === false`（场已结束）或商品详情 fail（已下架）。可以直接复用 `buildAddToCartState`（在 `pages/event/index.logic.ts`），**别再写第二份**。

### GZ-JP-203（购物车页）/ 204（下单确认页）

- **★ 全包邮（REQ-ORDER-004）**：购物车与确认页**只有商品合计一行，不得出现运费行**。`formatYuan()`（`@/api/gz-jp/format`）直接复用，返回的是不带 `¥` 的纯数字串（便于「小 ¥ + 大数字」排版），货币符号从 `t('product.currency')` 取。
- **★ 确认页要加「已阅读不支持退款」勾选一次**：这是注意事项方案 A 的配套举证手段（`design-options/mp-product-detail.md` Kevin 拍板原话：「选 A。配合下单确认页勾一次「已阅读不支持退款」做举证」）。**本卡只做了 A 的展示形态，举证那一半在 204**，别漏。
- `BizStepper` 可直接复用到购物车行内（`v-model` + `min`/`max`/`disabled`）。
- `BizProductCard` 是两列网格形态，购物车是横向行形态，**不要硬套** —— 新写一个 `BizCartItem` 更省事。

### GZ-JP-205（订单页）

- 首页订单入口落点已就位（201 报告已说明）；本卡未碰。
- `parseBackendTime` / `formatClock` / `countdownParts` / `formatHms` 现在都在 `@/api/gz-jp/format`，订单时间展示直接复用，**别 `new Date(str)`**（iOS 会返 Invalid Date）。

### 所有后续 mp 卡

- **新页记得两件事**：① 往 `test/e2e/flows/smoke.mjs` 的 `PAGES` 加一行（AC X(a) 可达性落点）；② 在 `self-test.mjs` 补 1 个 happy + **≥1 个 negative**。
- **`self-test.mjs` 的假件已支持完整 page**（`currentPage()` 返回带 `$` / `$$` / `wxml` 的对象），所以「点一下 → 跳页 → 在新页上继续断言」这类多跳 flow 现在写得出来了（product flow 就是范例）。
- **共用的后端契约适配函数放 `@/api/gz-jp/format.ts`**，不要在页面 logic 里各写一份。
- **分页端点收 `{rows,total}` 不是 `.data`**（http.ts 对 `TableDataInfo` 直返整对象）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1B 提示**：
- **不依赖 devtools 的部分现在就能跑**：`pnpm test`（164）/ `node test/e2e/self-test.mjs`（30）/ `pnpm type-check` / `pnpm lint` / 后端 curl 契约回归。
- **模拟器 E2E 需先由 Kevin 扫码恢复 devtools 登录**（硬 gate 无降级，**不要为了变绿改 preflight**）。恢复后跑 `cd code/main/miniapp-jp && node test/e2e/run.mjs all`（smoke + login + home + product）。`run.mjs` 会自动体检并按需重建 dev profile 产物；本会话已手工重建过一次。
- **跑之前确认 8080 后端活着**（product flow 会直连它比对场名/商品名/价格/注意事项/eventBookable），且 `gz_jp_event` 至少 1 个 open/closed 场、该场至少 1 件 `on_shelf` 商品 —— 缺任一 flow 会**显式 fail 并提示去造 fixture**（不假绿）。
- **想额外验「场已结束加购置灰」的真机表现**：`UPDATE gz_jp_event SET status='closed' WHERE id=1;` 跑完 `run.mjs product` 再 `UPDATE ... SET status='open'` 还原（`version` / `update_time` 不会被裸 SQL 动，还原是精确的；本卡已这样验过一轮）。

---

**一句话结论**：**accept #1（`node test/e2e/run.mjs product`）= BLOCKED**（devtools IDE 登录过期，exit 2，preflight 7 项仅 `devtools-login` 红，需 Kevin 扫码 30 秒，代码侧无需改动）；**accept #2（grep 注意事项区块）= PASS**（exit 0）；**场详情页 + 商品详情页两个页面都已完整做完**（含倒计时 / 两列网格 / 上拉分页 / ★ 注意事项在 CTA 之上且整段展开 / ★ 包邮标识 / ★ 加购置灰绑定 `eventBookable` / 加购占位交互不假装成功），type-check / lint / vitest(164) / self-test(30，16 negative) / build 全绿，dev 库 fixture 已逐列还原。
