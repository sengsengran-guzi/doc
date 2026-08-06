# GZ-JP-201 完工报告 — 小程序首页（聚合）

**结论：accept #2（vitest）PASS（exit 0，41 条断言）；accept #1（`run.mjs home`）BLOCKED —— 本机微信开发者工具 IDE 登录过期（`cli islogin` → `{"login":false}`），与 GZ-JP-002 同一个人工扫码阻塞，非代码问题。** preflight 7 项 **6 绿 1 红**，红的只有 `devtools-login`。flow 代码用零环境依赖的 self-test 证明可用（**14/14，含 7 个 negative**），并用「真后端响应 → 真 logic 模块」的 live 验证补上了数据链路证据。

> 后端可见性契约背景（closed 场可浏览 / draft 永不下发 / `eventBookable`）见 `doc/jp/tickets/_visibility-extension-pre-201.md`，本报告不重复。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| miniapp-jp 工作区起手 clean | ✅ `main` @ `fccd504`（GZ-JP-002） |
| 上游 GZ-JP-002（E2E harness）已 merge | ✅ `test/e2e/{run,preflight,mp-e2e,build-dist,self-test}.mjs` 齐 |
| 上游 GZ-JP-103（mp 查询 API）可调 | ✅ raw output 见下（`total:1`，fixture id=1 open） |
| 后端起手状态 | ⚠️→✅ 8080 **没在跑**，本会话自行拉起（见「残留进程」） |
| `sys_config` banner key 命名 | ✅ `gz.home.banners`，当前值 `"[]"` → 走默认图降级（**共用 key 隐患见风险 1**） |
| ruoyi-gz-jp jar 是当前码 | ✅ jar mtime `Aug 7 03:58` ≈ commit `66b6b58bc` `03:59`（本卡未改后端） |
| 蓝图引用可读 | ✅ UI:mp.home / .banner / .event_card / .order_entry |
| 兄弟仓未污染 | ✅ miniapp `59635d4` / RuoYi-Vue-Plus `66b6b58bc` / plus-ui `f313c41`，均 0 改动 |

```
$ git -C code/main/miniapp-jp status --short && git log --oneline -2
（无输出 = clean）
fccd504 feat: mp E2E harness + 登录链路验证 (GZ-JP-002)
637d7d6 feat: init miniapp-jp scaffold (GZ-JP-001)

$ curl -s --noproxy '*' 'http://localhost:8080/app/gz/jp/event/list' -H 'clientid: mp-applet-gz-jp'
{"total":1,"rows":[{"id":"1","eventNo":"EVT-20260807-000001","name":"8月上旬快闪场",
 "coverImageUrl":"/static/images/mock-product.png","description":null,"status":"open",
 "startTime":"2026-08-07 10:00:00","endTime":"2026-09-30 22:00:00"}],"code":200,"msg":"查询成功"}

$ curl -s --noproxy '*' 'http://localhost:8080/app/gz/common/config/get?key=gz.home.banners' -H 'clientid: mp-applet-gz-jp'
{"code":200,"msg":"操作成功","data":"[]"}          # ← 一期无运营内容，正好走「默认图降级」常态路径

mysql> SELECT id,event_no,status,start_time FROM gz_jp_event ORDER BY id;
1  EVT-20260807-000001  open   2026-08-07 10:00:00
2  EVT-20260807-000002  draft  2026-09-10 10:00:00     # draft 不下发，list 里确实只有 id=1
```

**蓝图 / 契约关键约束摘录**
- `status ∈ {open, closed}`，**draft 永不下发** → 前端类型只写两值，不做 draft 分支。
- 三组是**纯展示派生**：进行中 = `status==='open' && startTime<=now`；即将开始 = `status==='open' && startTime>now`；已结束 = `status==='closed'`。
- **能不能下单永远看 `status`/`eventBookable`，不看分组、也不拿 `endTime` 跟本地时钟比**（手动关场判不出来 + 客户端时钟不可信）。已写进 `index.logic.ts` javadoc 与 `api/gz-jp/event.ts` 类型注释。

## 实现摘要

```
 M src/locale/home.zh-CN.ts  |  47 +++--          区块/分组/时间行/入口 文案
 M src/pages/index/index.vue | 341 +++++++----    首页从「登录态卡+占位」重写为三区块聚合
 M test/e2e/README.md        |   4 +             加 home flow 用法
 M test/e2e/run.mjs          |   1 +             FLOWS 注册 home
 M test/e2e/flows/smoke.mjs  |   6 +-            首页标志元素换锚点（见下）
 M test/e2e/flows/login.mjs  |  12 +-            首页登录触发点换成订单入口（见下）
 M test/e2e/self-test.mjs    | 144 ++++++-        假件支持 $$/text + 7 条 home 用例
 A src/api/gz-jp/event.ts                        ★ 新建 api 目录：场列表/详情 + 类型镜像
 A src/pages/index/index.logic.ts                ★ 纯逻辑层（分组/降级/时间/路由/角标）
 A src/pages/index/index.logic.test.ts           ★ 41 条单测（accept #2）
 A src/components/biz/BizEventCard.vue           ★ 场卡片原子件
 A src/components/biz/BizEntryCard.vue           ★ 快捷入口原子件（带角标）
 A test/e2e/flows/home.mjs                       ★ accept #1 的 flow
```

**未 commit**（主线程统一收尾）。miniapp-jp 虽是新本地仓、001/002 都自提交过，本卡按派单口径**留在工作区未提交**；doc / RuoYi-Vue-Plus / plus-ui / miniapp 四仓一行未碰。

### 1. 三区块（自上而下）

| 区块 | 实现 | 关键点 |
|---|---|---|
| ① 轮播 banner | `BizHomeBanner` + `buildBannerSlides()` | **永不返回空数组**：无配置 / 全被过滤 / 拉取失败 三条路径统一降级为单张默认 slide（`imageUrl:''` → 组件渲染内置品牌占位块）。默认 slide `link:''` 故不可点 |
| ② 拼团场次 | `groupEvents()` + `BizEventCard` | 固定 3 组、顺序恒为 **进行中 → 即将开始 → 已结束**；组内**保持后端相对顺序**（后端已按 `sort_no, end_time DESC, id DESC` 排好，前端不二次排序）；四态（loading / error+重试 / empty / 有数据）都渲染在同一个 `.jp-home__events` 容器内 |
| ③ 我的订单入口 | `BizEntryCard` + `formatBadgeCount()` | 角标 **0 → 空串 → 不渲染**（不显示误导性的「0」）。游客点它 → `ensureLoggedIn()` 弹协议 sheet |

### 2. `src/api/gz-jp/` 新目录（miniapp-jp 此前没有）

`event.ts`：`fetchEventList()` / `fetchEventDetail()` + `GzJpEventMpVO` 镜像。三条契约纪律写进注释：**ID 全 string**；**分页端点收 `{rows,total}` 不是 `.data`**（`http.ts` 对 `TableDataInfo` 直返整对象，「写成 `res.data`」是本项目 D16 逮到过的一类系统性契约 bug，注释里点名了）；**时间是 `'yyyy-MM-dd HH:mm:ss'` 不是 ISO**，禁止 `Date.parse`。

### 3. 三个「不写下来下次一定再踩」的实现决策

1. **时间解析不能用 `new Date(str)`**。后端 `@JsonFormat(pattern="yyyy-MM-dd HH:mm:ss")` 发空格分隔格式，iOS 真机 `new Date('2026-08-07 10:00:00')` 返 Invalid Date、模拟器却正常 —— 典型「模拟器全绿真机全崩」。工程里现成的 `useCountdown.parseIsoMs()` 正是直接 `new Date(iso)`（其注释假定后端发 'T' 分隔 ISO，对 jp 场接口**不成立**），所以自写 `parseBackendTime()`：按字段手工构造 `new Date(y,m-1,d,...)`，与 `formatClock()` 读取方式对称 → 「解析后再格式化」恒等于原始墙钟、与时区无关（有往返单测背书）。
2. **封面要按「无封面」处理**。后端无图回落 `/static/images/mock-product.png`，但**该静态文件在 miniapp-jp 里根本不存在**（`src/static/images/` 只有 avatar.jpg / default-avatar.png；源工程 miniapp 也没有），直接渲染会 404 出空白框。`hasRealCover()` 把该路径判为无封面 → 渲染内置渐变占位；另加 `<image @error>` 兜住「1h 预签名 URL 过期」的运行时失败。
3. **`status` 异常值一律归「已结束」，但不丢弃**。兜底方向是「宁可把能下单的场展示成已结束，也不能把不能下单的场展示成进行中」（与后端 `GzJpEventStatus.of()` 回落 DRAFT 同一保守思路）。反过来，**`startTime` 解析失败时归「进行中」**——`status` 才是可下单与否的唯一权威，时间只用来把 open 这一桶再切两半。两条都有单测锁死。

### 4. 改了两个既有 flow 的锚点（必须知会）

首页重写后 `.jp-hero__cta`（脚手架的登录/资料 CTA）**已不存在**，GZ-JP-002 报告预告过「要么保留、要么同步改 flow」。选了同步改：

| flow | 原锚点 | 新锚点 | 理由 |
|---|---|---|---|
| smoke | `.jp-hero__cta` | `.jp-home__events` | 场次区块容器，loading/error/empty/有数据**四态都渲染**，比任何一态内的元素都稳 |
| login | `.jp-hero__cta` | `.jp-entry-card`（订单入口） | 首页按「游客优先 / 按需登录」不再放独立「微信登录」按钮；订单入口是首页上唯一需要登录态的动作。login flow 验的三件事（协议默认不勾选 / 未勾选按钮 disabled / clientid 没串号）**一条没少** |

self-test 同步更新并**跑绿**，所以这两处改动不是「改完等 devtools 才知道对不对」。

## AI 自测（raw output）

### 1. accept #2（逐字）—— ★ 真绿

```
$ cd code/main/miniapp-jp && pnpm vitest run src/pages/index/index.logic.test.ts
 ✓ src/pages/index/index.logic.test.ts (41 tests) 6ms
 Test Files  1 passed (1)
      Tests  41 passed (41)
ACCEPT#2 EXIT=0
```

| 组 | 条数 | 关键边界 |
|---|---|---|
| `parseBackendTime` | 7 | 空格分隔 / ISO 'T' 兼容 / 省略秒 / 乱串→NaN / **13 月与 2 月 31 日必须 NaN**（不能让 Date 静默滚月）/ 解析→格式化往返恒等 |
| `classifyEvent` | 9 | ★ `startTime === now` → **进行中**；±1 秒两侧；★ status 异常值（`draft`/`OPEN`/`Open`/`archived`/`''`/null/undefined）**一律已结束**；★ event 本身 null 不抛；★ open 但 startTime 解析失败 → 进行中 |
| `groupEvents` | 5 | 恒 3 组 + 顺序恒为进行中置顶 / 混排各归各组 / **组内保序** / null 入参与数组空洞 / **未知 status 不被丢弃（总数守恒）** |
| `buildBannerSlides` | 7 | ★ 空数组 / null / undefined / **全被过滤掉** 四条路径都降级为单张默认图；默认图 link 为空不可点；有配置时不注入默认图；**任何输入下结果非空（不塌陷不变量）** |
| `hasRealCover` / `buildEventTiming` / `buildEventRoute` / `formatBadgeCount` | 13 | 后端占位路径判无封面 / 时间解析失败→kind=none（不显示 "Invalid Date"）/ 路由带 id+eventNo 且 URL 编码 / 角标 0 与负数→空串、>99→99+ |

### 2. ★ LIVE 验证：真后端响应 → 真 logic 模块（accept #1 跑不了时的数据链路证据）

临时 vitest 用例用 `curl` 打真后端拿**原始响应**，直接喂给页面真正在用的 `index.logic.ts`（跑完已删）：

```
[LIVE] GET /app/gz/jp/event/list 原始响应:
 {"total":1,"rows":[{"id":"1","eventNo":"EVT-20260807-000001","name":"8月上旬快闪场",
  "coverImageUrl":"/static/images/mock-product.png","description":null,"status":"open",
  "startTime":"2026-08-07 10:00:00","endTime":"2026-09-30 22:00:00"}],"code":200,"msg":"查询成功"}
[LIVE] now = Fri Aug 07 2026 04:23:02 GMT+0800 (China Standard Time)
[LIVE] 组 live     → 0 条 []
[LIVE] 组 upcoming → 1 条 [ { name: '8月上旬快闪场', status: 'open',
                             startTime: '2026-08-07 10:00:00',
                             timing: { kind: 'start', at: '08/07 10:00' } } ]
[LIVE] 组 ended    → 0 条 []
```
↑ 真数据落「即将开始」是**对的**：现在 04:23 < 开场 10:00。今天 10:00 后同一条数据自动落「进行中」。

```
[LIVE] GET /app/gz/common/config/get?key=gz.home.banners 原始响应:
 {"code":200,"msg":"操作成功","data":"[]"}
[LIVE] 配置值 = "[]" → 最终 slides = [{"imageUrl":"","link":"","enabled":true}]
```
↑ **拿真配置证明「无 banner 配置 → 降级单张默认图」**，不是只在单测里造数据。

再把 fixture 临时改成 closed 验「已结束」组（**改完已逐列还原**）：

```
=== BEFORE ===  id=1  status=open   version=3  update_time=2026-08-07 03:15:48
=== UPDATE gz_jp_event SET status='closed' WHERE id=1 → ROW_COUNT()=1 ===
[LIVE] 原始响应 ... "status":"closed" ...
[LIVE] 组 live → 0 条 []   组 upcoming → 0 条 []   组 ended → 1 条 [...]
=== 还原 ===
=== AFTER ===   id=1  status=open   version=3  update_time=2026-08-07 03:15:48   ← 逐列与 BEFORE 一致
                id=2  status=draft  version=0
=== 还原后接口回归 ===
{"total":1,"rows":[{"id":"1",..."status":"open",...}],"code":200,"msg":"查询成功"}
```
（`gz_jp_event.update_time` 无 `ON UPDATE CURRENT_TIMESTAMP`、`version` 由 `@Version` 管，裸 SQL 改 `status` 不动这两列，所以还原是逐列精确的。）

### 3. accept #1（逐字）—— BLOCKED：devtools IDE 登录过期

```
$ cd code/main/miniapp-jp && node test/e2e/run.mjs home
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
{"login":false}          # ← 独立复核，与 GZ-JP-002 完全同一个阻塞
```

**处置（严格按「不绕过」）**：没有 kill / 重启 Kevin 的 IDE；没有注释 preflight；没有伪造通过；没有降级。开工前先跑了一次 `build-dist.mjs development` 确保产物是当前代码，排除「产物旧」干扰后阻塞点仍只有登录态一项。**解除条件**：Kevin 扫码 → 重跑 `node test/e2e/run.mjs home`（或 `all`），约 30 秒，无需改任何代码。

### 4. flow 逻辑体检（零环境依赖，证明「flow 代码是好的」）

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

[self-test] 14/14 通过
SELFTEST_EXIT=0
```
14 条里 **7 条是 negative**。为此把 home flow 拆成 `run(mp)`（拉后端）+ `runWith(mp, backendEvents)`（纯断言），**不是**在 flow 里埋测试用环境变量后门。

### 5. E2E 断言用的选择器在**编译产物**里确实存在（替代证据）

```
$ for sel in jp-home__banner jp-home__events jp-home__group-title jp-entry-card \
             jp-event-card__name hb__ph hb__img; do grep -rl "$sel" dist/build/mp-weixin/; done
jp-home__banner        dist/build/mp-weixin/pages/index/index.wxml
jp-home__events        dist/build/mp-weixin/pages/index/index.wxml
jp-home__group-title   dist/build/mp-weixin/pages/index/index.wxml  (+.wxss)
jp-entry-card          dist/build/mp-weixin/components/biz/BizEntryCard.wxml  (+.wxss)
jp-event-card__name    dist/build/mp-weixin/components/biz/BizEventCard.wxml  (+.wxss)
hb__ph / hb__img       dist/build/mp-weixin/components/biz/BizHomeBanner.wxml (+.wxss)

$ grep -q "app/gz/jp/event/list" -r dist/build/mp-weixin/ && echo OK
OK: /app/gz/jp/event/list 已进产物
```
且 `.jp-home__events` 在编译后 wxml 里确实是**外层 view**、四个状态分支（`wx:if` loading / `wx:elif` error / `wx:elif` empty / `wx:else` 列表）全在它里面 —— smoke 锚点在任何数据状态下都在。

### 6. 工程健康（001/002 的绿线全部保持）

```
$ pnpm type-check   → exit=0     # vue-tsc --noEmit，无输出
$ pnpm lint         → exit=0     # 仍是 0 problems
$ pnpm test         → exit=0     # Test Files 7 passed, Tests 84 passed (43 存量 + 41 本卡)
$ node test/e2e/self-test.mjs → exit=0
$ node test/e2e/build-dist.mjs development → exit=0   # dist 是当前代码
$ app.json: pages 仍 6 页 / tabBar 仍 ['首页','我的']  # 本卡不新增页、不动 tabbar

# 兄弟仓 0 污染
miniapp        0 处改动  59635d4
RuoYi-Vue-Plus 0 处改动  66b6b58bc
plus-ui        0 处改动  f313c41
```

## 风险提示 / 已知 issue

1. **★ `gz.home.banners` 是与现有 guzi 小程序共用的 sys_config key（GZ-JP-001 风险 3 的处置说明）**。本卡**沿用共用 key、没另开 `gz.jp.home.banners`**，理由：一期无运营内容、该 key 当前值就是 `"[]"`（已 curl 实证），走的是「无配置 → 默认图降级」路径，**共用问题在「没配置」状态下不会实际暴露**；现在加一个后端不认识的 key 反而要动后端。**但这是一颗定时炸弹**：只要运营给**拼豆小程序**配了首页 banner，**拼团小程序首页会立刻跟着显示拼豆的图**（同 key、同租户、同 `/app/gz/common/config/get` 端点，无 clientid 维度隔离）。处置明确：谁先要配 banner，谁就先做「后端加 `gz.jp.home.banners` + admin 配置项 + 前端 `GZ_CONFIG_KEYS` 换 key」小卡（前端改动 = `src/api/gz-common.ts` 一行常量）。建议在**运营开始配 banner 之前**排掉。
2. **订单入口角标是写死的 0**（`pendingOrderCount = ref(0)`）。订单域后端（GZ-JP-105）与订单页（GZ-JP-205）都没上线，没有可查的真实数据。0 被 `formatBadgeCount` 收敛成空串 → **角标不渲染**。205 实施时换成订单统计接口返回值即可，组件与格式化都不用动。
3. **场卡片 / 订单入口的跳转目标页还不存在**（`/pages/event/index` 归 202、`/pages/order/index` 归 205）。`navigateTo` 的 `fail` 兜了 toast 而不是静默无反应；202/205 合并后路由自然可达，**这两个函数不用改**。
4. **首页分组用客户端时钟**（列表接口不返 serverNow）。只影响**展示分组**；能不能下单永远看 `status`/`eventBookable`。时基是**拉取时快照一次**，跨过开场时刻的重新分组等下次 `onShow` 拉取带上（切走再切回即刷新，一直停在首页不会自己跳组）。
5. **`useCountdown.parseIsoMs()` 对 jp 场接口不适用**：其注释写「后端已统一发 'T' 分隔 ISO」，但 `GzJpEventMpVO` 发的是 `'yyyy-MM-dd HH:mm:ss'`。本卡没用它。后续谁在 jp 侧做倒计时，先把时间串过 `parseBackendTime` 或给 `useCountdown` 补格式兼容。
6. **`BizHomeBanner` 是全项目第一处「带 payload 的 `$emit('tap', link)`」**。mp 里子节点原生 tap 也会冒泡到组件标签的 `bindtap`，那一路进来的实参是**原生事件对象**而非字符串 —— 直接 `link.startsWith()` 会在真机抛 TypeError。已把 `onBannerTap` 入参收成 `unknown` + 类型守卫挡住。（其余卡片组件都是无 payload 的 `emit('tap')`，与 guzi 生产工程 `BizNewsCard`/`BizGachaMachineCard`/`BizPreorderCard` 完全同款、已过 D16 真跑验收，不受影响。）
7. **场封面在 dev 期全是占位块**：fixture 的 `coverImageUrl` 是 mp 侧不存在的文件。真实运营图上线前，首页所有场卡显示渐变 + 🎏 占位。**不是 bug**，但 Kevin 首次看首页会注意到。
8. **accept #1 依赖 dev 库里至少有 1 个「开过的场」**。home flow 核心断言是「页面卡片名 == 后端返回的场名」，后端返 0 条时 flow 会**显式 fail 并提示去造 fixture**（不假绿）。清库 / 换环境后跑这条要先确认 `gz_jp_event` 有 open 或 closed 场。
9. **本卡未跑过真模拟器**（同 GZ-JP-002）。首页三区块的**实际渲染**（样式塌不塌、swiper 高度、两行截断、角标位置）尚未被人或机器看过一眼。self-test 只证明 flow 逻辑自洽，选择器与真实渲染树对不对得等 devtools 登录恢复后首跑。

## 残留进程（需要处置）

本会话**自行拉起了后端**（起手时 8080 没在跑），**刻意保留运行**——下游 kevin-qa 跑 `run.mjs home` 时 flow 会直连它拉真数据，preflight 也要它：

```bash
# 后端 mvn spring-boot:run -pl ruoyi-admin（PID 72376，日志 /tmp/gzjp-201-backend.log）
lsof -ti:8080 | xargs kill        # 不需要时收掉
```

docker 的 MySQL/Redis/MinIO 原本就在跑，未动。临时验证脚本 `src/pages/index/tmp-live-check.test.ts` **已删除**（`ls src/pages/index/` 只剩 `index.logic.test.ts` / `index.logic.ts` / `index.vue`）。dev 库 fixture **已逐列还原并回归验证**。

## 对下游 ticket 的提示

### GZ-JP-202（场详情 / 商品列表）—— 下一个卡，重点看这段

1. **路由参数：`id` 和 `eventNo` 都收得到**，形如 `/pages/event/index?id=1&eventNo=EVT-20260807-000001`（`buildEventRoute()` 生成，有单测）。**`id` 用来调接口**（`GET /app/gz/jp/event/{id}`，后端只提供按主键查）；**`eventNo` 用来展示 / 分享 / 客服对单**。两个都别丢。**页面路径就叫 `/pages/event/index`**，改名的话同步 `index.logic.ts` 的 `EVENT_DETAIL_ROUTE`（一个常量）。
2. 建好页后首页的降级 toast 自然不再触发（不用改代码），但**要往 `test/e2e/flows/smoke.mjs` 的 `PAGES` 加一行**（`{ path:'/pages/event/index?id=1', accept:['pages/event/index'], must:'.xxx' }`），这是 AC X(a) 的落点。
3. **直接复用本卡的两个东西，别重写**：`src/api/gz-jp/event.ts` 的 `fetchEventDetail(id)`（含 closed 场返 200 的说明）；`index.logic.ts` 的 `parseBackendTime` / `formatClock` / `hasRealCover`（商品封面**同样**回落那个不存在的 `/static/images/mock-product.png`）。若详情页也要用，建议把这三个提到 `src/utils/` 或 `src/api/gz-jp/` 下的共享模块（本卡没提前抽，避免为一个使用方过度设计）。
4. **加购置灰判 `eventBookable === false`**，**不要**判 `status`、更不要拿 `endTime` 跟本地时钟比。首页三组分组是纯展示派生，**不能当下单闸门**。
5. **`BizEventCard` 可直接复用**做详情页头（props 是展平展示字段，不绑 API 类型）。

### GZ-JP-205（订单页）

- 首页订单入口落点已就位：`ORDER_LIST_ROUTE = '/pages/order/index'`（`index.logic.ts` 常量），建页后自然打通。
- **角标接真数据**：把 `src/pages/index/index.vue` 的 `pendingOrderCount = ref(0)` 换成订单统计接口返回值（`formatBadgeCount` 已处理 0 隐藏 / >99 收敛）。
- `BizEntryCard` 可复用到「我的」页；「我的」页入口落点见 GZ-JP-001 报告。

### 所有后续 mp 卡

- **新 Biz 组件的事件名**：无 payload 用 `emit('tap')`（项目惯例，生产验证过）；**带 payload 时调用方务必做类型守卫**（原生 tap 冒泡会送进来事件对象），见风险 6。
- **后端时间字段一律先过 `parseBackendTime`**，别 `new Date(str)`（iOS 会炸）。
- **分页端点收 `{rows,total}` 不是 `.data`**。
- 新页记得给 `test/e2e/flows/` 补 flow 或往 smoke 的 `PAGES` 加一行，并**在 `self-test.mjs` 补 1 个 happy + ≥1 个 negative**。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1B 提示**：
- **不依赖 devtools 的部分现在就能跑**：`pnpm test`（84）/ `node test/e2e/self-test.mjs`（14）/ 后端 curl 契约回归。
- **模拟器 E2E 需先由 Kevin 扫码恢复 devtools 登录**（硬 gate 无降级，不要为了变绿改 preflight）。恢复后跑 `cd code/main/miniapp-jp && node test/e2e/run.mjs all`（smoke + login + home）。`run.mjs` 会自动体检并按需重建 dev profile 产物；本会话已手工重建过一次。
- **跑之前确认 8080 后端活着**（home flow 会直连它比对场名），且 `gz_jp_event` 里至少有 1 个 open/closed 场。

---

**一句话结论**：accept #2（`pnpm vitest run src/pages/index/index.logic.test.ts`）**PASS**（exit 0 / 41 tests）；accept #1（`node test/e2e/run.mjs home`）**BLOCKED** 于本机 devtools IDE 登录过期（exit 2，preflight 7 项仅 `devtools-login` 一项红，需 Kevin 扫码 30 秒），flow 代码侧已用 self-test 14/14（含 7 negative）+ 真后端→真 logic 的 live 验证 + 编译产物选择器核对三重背书；**三区块（轮播 banner / 场次三组进行中置顶 / 我的订单入口带角标）全部实现**，type-check / lint / vitest(84) / build 全绿，**未 commit**（工作区 7 改 6 新，见上）。
