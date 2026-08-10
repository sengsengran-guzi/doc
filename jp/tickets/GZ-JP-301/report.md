# GZ-JP-301 完工报告 — 联调回归与上线

> **accept #2（新小程序全量 E2E）★ 7/7 全绿 —— 本项目第一次全量真跑通过**；**accept #3（Flyway）PASS**。
> **accept #1（老小程序全量回归）BLOCKED** 于本机 devtools 的**每工程独立** GUI 开关（Kevin 只给 miniapp-jp 勾过），
> 已用不依赖模拟器的手段把「D1 多 appid 改造有没有伤到老小程序」这个问题**单独回答清楚了：没有**（见下）。
>
> 过程中**逮到 1 个真产品缺陷**（购物车改数量会把人带走）和 **3 个 harness 缺陷**，全部已修。

## accept 逐条

### #2 新小程序全流程 E2E ✅ 7/7

```
$ cd code/main/miniapp-jp && node test/e2e/run.mjs all
=== flow: smoke ===     [PASS] smoke
=== flow: login ===     [PASS] login
=== flow: home ===      [PASS] home
=== flow: product ===   [PASS] product
=== flow: cart ===      [PASS] cart
=== flow: checkout ===  [PASS] checkout
=== flow: orders ===    [PASS] orders

[run] 结束：7/7 flow 通过     EXIT=0
```

打的是**真模拟器 + 真本地后端 + 真库**，不是 mock。链路覆盖：
首页 → 场 → 商品 → 加购 → 购物车 → 去结算 → 地址 → 提交下单（真落库 `JPO-20260809-000005`）
→ mock 支付驱动结算（订单 `paid`、商品行进 `purchasing`）→ 支付结果页 → 订单列表 / 详情。

### #3 两库迁移全部应用且无 pending ✅

```
$ docker exec sensenran-dev-mysql mysql ... -e "SELECT COUNT(*) FROM flyway_schema_history WHERE success=0" | grep -qx 0
ACCEPT3 PASS (success=0 的迁移 0 条)
```
本项目 10 个 jp 迁移全部 `success=1`（101 建表+seed / 102 建表+seed / 104 车 / 105 单+seed / 107 退款 / 108 菜单 / 109 菜单）。

### #1 老小程序全量回归 ⛔ BLOCKED（环境，非代码）

```
$ cd code/main/miniapp && node test/e2e/run.mjs all
[FAIL] ×6   Cannot destructure property 'rawPath' ...      ← 老 harness 没有 launch 重试
（改成逐 flow 独立进程重跑后）
  tour ✅   kevin-check ✅   smoke ❌   login ❌   focus ❌   daypass ❌
```

**但 `tour` / `kevin-check` 的 PASS 不能当数据面通过用** —— 看截图才发现问题：

![](file:///tmp/gz-e2e-shots/tour_pages_bean_my-list.png) `我的预约` 页显示「**加载失败，下拉重试**」，
`资讯中心` 页同样「加载失败」。**老 harness 只断言"页面落对了 + 渲染出 N 个 view"，不断言数据加载**，
所以数据全挂它照样报 PASS。这本身是老 harness 的一个真缺陷（见「发现的 harness 缺陷」#4）。

根因用 jp 那套 app 侧探针测死了：

```
[probe] ❌ 老小程序打不到本地后端：小程序侧 wx.request 被域名校验拦下（request:fail url not in domain list）
```

**「不校验合法域名」这个开关在微信开发者工具里是【每个工程独立】的**，Kevin 之前只给
`miniapp-jp` 勾过，`miniapp` 那个工程还没勾。两个 dist 的 `project.config.json` 都是
`setting.urlCheck=false`，**压不住它**（harness 注释里已实测记录：改配置 / 换 appid / 换路径 / cli 重开都没用，只能 GUI 勾一次）。

**没有为了变绿去改 preflight 或降级断言**（那是把硬 gate 变成假绿）。
解除办法（Kevin，一次性 30 秒）：微信开发者工具 → 打开 `code/main/miniapp/dist/build/mp-weixin`
→ 右上「详情」→「本地设置」→ 勾「不校验合法域名…」→ 我再重跑一次即可。

#### 「D1 多 appid 改造有没有伤到老小程序」—— 用不依赖模拟器的手段单独回答：**没有**

这才是 accept #1 真正要回答的问题。四条独立证据：

1. **本项目从未改过老小程序的源码**。老仓工作区 `git status --porcelain` **0 变更**，
   最后一次提交 `59635d4 2026-07-27`，而本拼团项目 **2026-08-06** 才开工；
   `git log --since=2026-08-05 -- src` **为空**。⇒ 只可能经由**共享后端**影响它。
2. **老小程序的 clientid 走多 appid 后端登录正常**（这正是 D1 唯一改到的面）：
   ```
   $ curl -X POST /app/gz/common/auth/wx-login -H 'clientid: mp-applet-sensenran-guzi' -d '{"code":"mock-code"}'
   {"code":200,"msg":"操作成功","data":{"token":"eyJ..."}}     ← 解出 clientid=mp-applet-sensenran-guzi, tenantId=1001
   ```
   （顺带印证配置注册齐全：故意传错 clientid 时后端报 `已配置：[mp-applet-sensenran-guzi, mp-applet-gz-jp]`。）
3. **老小程序在用的业务接口仍正常返数据**：`/app/gz/news/article/list` 匿名 200 / `total=5`。
   即页面上的「加载失败」是**模拟器网络被拦**，不是后端坏了。
4. **D1 的改动面**（`WxMiniappProperties` / `WxAdapterDispatcher` / `WxAppResolver`）只经过
   wx 登录 / 手机号 / 头像昵称 / 支付 / 发货上报；而 4 个红 flow 断言的是资讯列表渲染、
   登录页按钮、回收详情 view 数、拼豆日期步骤 —— **没有一条经过这些代码**。

**结论**：无 D1 回归证据；D1 唯一真实改动面（老 clientid 的多 appid 登录）实测为绿。
**诚实边界**：我**没有**跑到"老小程序全量 E2E 绿"这一步，也**没有** pre-D1 基线可比对。
上线前建议 Kevin 勾一次开关让我把老小程序全量回归真跑完（见「残留」）。

## ★ 逮到的真产品缺陷：购物车点「＋」会把人带离购物车

**现象**：cart flow 报「改数量后合计没刷新：页面=null」。

**根因**（不是合计不刷新，症状离病因很远）：mp 里**原生 tap 会穿过自定义组件边界往上冒泡**。
`BizStepper` 的加减按钮用的是 `@tap`（编译成 `bindtap`），而购物车行
`<BizCartItem @tap="onItemTap">` 编译出来是组件标签上的 `bindtap` ——
点「＋」在改数量的**同时**触发了行点击 `uni.navigateTo(商品详情)`。
数量确实改对了、库也落了，但人已经跳走，页面所有断言自然全查空。

编译产物实证：
```
dist ... <biz-cart-item ... bindtap="{{item.d}}"/>          ← 行点击（跳商品详情）
dist ... class="...biz-stepper__plus..." bindtap="{{e}}"    ← 修前：冒泡上去
dist ... class="...biz-stepper__plus..." catchtap="{{e}}"   ← 修后：就地消费
```

**修**：`BizStepper` 加减按钮改 `@tap.stop`（`catchtap`），并在组件头写明**别改回去**的理由。
同组件的勾选框 / 删除本来就写了 `@tap.stop` —— 作者知道这个坑，只是漏了 stepper。

修后：`✓ ★ 改数量实时刷新合计：¥80 → ¥160（后端 qty=2）`。

**波及面**：`BizStepper` 只用在购物车行与商品详情两处；商品详情没有行级点击，无影响。

**顺带加了一条精确回归断言**（原来的失败信息指向症状不指向病因）：
```js
// 点完「＋」先确认人还在购物车
if (!pathAfterQty.includes('pages/cart/index')) fails.push(`★ 点「＋」改数量把人带离了购物车：当前页=${pathAfterQty}...`)
```

## 发现并修掉的 harness 缺陷（4 个，都会造成"假红"）

| # | 缺陷 | 后果 | 处置 |
|---|---|---|---|
| 1 | `run.mjs` 硬超时 **240s 是整轮预算**，却是照单 flow 定的 | 跑 `all`（7 flow）最后一个必被砍，报成 flow 挂了 | 改成 `flow 数 × 240s`，可用 `MP_E2E_TIMEOUT_MS` 覆盖 |
| 2 | 7 个 flow **共用一个 automator 会话** | 逐个往下烂：先是深层页查不到元素，最后连首页场卡都查不出（同时刻后端 curl 一切正常）。实测 3/7 → 换成独占会话后 **7/7** | 每个 flow 独占一个全新会话，跑完即断（+10-20s/flow，很值） |
| 3 | 跳页后用固定 `sleep(2500)` 等接口驱动的元素 | 商品卡挂在 `v-else`（loading/failed/空 三分支之后），接口慢一点就报「没有商品卡」 | 新增 `deepWait()` 轮询等待（命中即返回，等不到照样失败，**不放宽断言**） |
| 4 | **老 miniapp harness 没有 app 侧后端可达性 gate** | 数据全部加载失败，flow 仍报 PASS（`tour`/`kevin-check` 就是这么"绿"的） | ⚠️ **未修**（属老仓，见「未做的事」） |

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| 上游 108/109/205 已完成 | ✅ D5 QA 门已过 |
| 老 miniapp 仓工作区干净、未被本项目污染 | ✅ `git status --porcelain` = 0；最后提交 2026-07-27 |
| Kevin 在飞的 GZ-BEAN-053 改动未被碰 | ✅ 全程未动 `ruoyi-gz-bean/**`、`plus-ui` 的 gz-bean 文件 |
| Flyway 无失败迁移 | ✅ accept #3 |
| 甲方四件行政事项 | ⛔ 未完成（备案/类目/商户号绑定）→ **按本卡 §0 只能到 staging，不能上 prod** |

## 未做的事（诚实列明，不是漏了）

1. **staging / prod 部署**：需要 Kevin 的服务器凭据 + 甲方行政事项（ICP 备案 2-3 周是最长杆）。本卡只做到"代码与迁移就绪"。
2. **真机 1 分钱支付（新旧各一遍）**：wxMOCK 下物理拉不起真收银台，必须真机 + 真 appid + 商户号绑定后由 Kevin 跑。
3. **微信发货信息上报验证**：同上，依赖真实支付单。
4. **老 miniapp 的 3 个既有单测失败**（`token.test.ts` 的 `silentWxRenew` ×2、`MeHeader.test.ts` ×1）：
   工作区与 HEAD 逐字节一致 ⇒ **在 2026-07-27 那个 commit 上就是红的**，与本项目无关。
   ⚠️ **但值得 Kevin 单独看一眼**：`silentWxRenew()` 返回 false 意味着**静默续期失败 → 用户被踢去重登**。
   本卡**没有替它改**（属拼豆域、且 Kevin 正在该仓域内有在飞改动，越界改反而危险）。
5. **老 miniapp harness 的可达性 gate**（上表 #4）：同属老仓，未改。补它的收益很大（否则老仓 E2E 的"绿"信不过）。

## 风险提示

1. ★ **老小程序 E2E 的"绿"目前信不过**（harness 缺陷 #4）。在补上 app 侧可达性 gate 之前，
   不要拿 `tour`/`kevin-check` 的 PASS 当"老小程序没问题"的证据。
2. **`gz.home.banners` 是与谷子宇宙共用的 sys_config key**（201 报告风险 1）——运营一配 banner，拼团首页会跟着显示拼豆的图。**建议在运营开始配 banner 之前排掉**。
3. **8 个 mp 新页 + 1 个 admin 看板页从未被人眼看过**（视觉首版拍板未做）。功能有 E2E 背书，视觉没有。
4. 图片是预签名 **1h 过期**，长时间停留后会 404（各页已 `@error` 兜占位块）。

## 对下游 / 上线的提示

上线前残留已汇总在 [doc/jp/GO-LIVE-CHECKLIST.md](../../GO-LIVE-CHECKLIST.md)（4 桶：appid 回补 / 甲方行政 / Kevin 真机人验 / prod 部署缺口）。
本卡新增两条进该清单：
- **老 miniapp 工程的「不校验合法域名」需勾一次**，否则老小程序回归永远真跑不了；
- **老 miniapp 3 个既有单测红**（含 `silentWxRenew`），建议上线前单独查一次。

## §AI 测试段（kevin-qa 追加）

### D6 QA 门 · 第 1 轮 —— **FAIL**

干净 QA（全新上下文、未读本报告）跑完整 L0-L3，结论：

| 级 | 结果 |
|---|---|
| **L0 静态** | ✅ miniapp-jp 294 单测 / type-check / lint 全过；后端 `ruoyi-gz-jp` **194 单测 0 失败**；JP 19 个迁移全部 tracked；Flyway 磁盘 156 = 已应用 156，pending 0 |
| **L1 集成** | ✅ **34/34**。走真 API 建数据、断言查 DB（不手写 INSERT 自证）。下单链路 22/22（订单额 = Σ 行额 = 车合计、行额 = 单价 × 数量、支付流水额 = 订单额、重复回调幂等）；退款链路 12/12（行级退款 rollup、**全额退完转 refunded**、★金额守恒 Σ已退 = 订单总额、跨域退款单打错回调被拒）。**全库 sweep：不平订单 0 / 超退 0 / 行超退 0 / 流水不符 0** |
| **L2 端侧** | ✅ miniapp-jp **7/7**（QA 自己强制重建 dev dist 后跑，反 stale）；plus-ui 4 个 JP admin 页真浏览器渲染真数据、**0 console error**。⛔ 老 miniapp 跑不出结果（环境） |
| **L3 邪路** | ✅ 32/34（2 条是 QA 自己断言写错，已更正）。**并发**：并发加购只 1 行不丢更新 / ★同一批 cartItemIds 并发下单 ×5 只落 1 单（codes=[200,4107×4]）/ 并发支付回调只 paid 一次 / ★并发标记失败只出 1 张退款单。**多 appid 串味 6 条全过**：跨 clientid token → 401、拼豆用户读 JP 订单 → 4105 不泄漏、未登记 clientid → 明确报错。**权限**：mp token 打 5 个 `/system/**` 5/5 被拒。**跨日期**：真等到跨过 `end_time`，场读时翻 closed、车内项自动失效、结算被拒 4102 |

**QA 判定 FAIL 的两条**（不是 JP 代码质量问题）：
1. **accept #1 拿不到端侧证据** —— 老 miniapp 工程的「不校验合法域名」没勾（每工程独立）。
2. **需求与实现冲突：拼团没接 `upload_shipping_info`** —— 任务卡 What 明确要求，代码刻意不接（理由正当：支付当下无发货事实），但**置 delivered 那一刻也没人接**，等于 JP 单永不上报，涉及资金结算。

### 第 1 轮返工（本轮已做）

| 问题 | 处置 |
|---|---|
| 老 harness 无 app 侧可达性 gate / 超时写死 240s / launch 不重试 | ✅ 已修并提交（`miniapp` 仓 `c513435`，**仅测试 harness，未动业务代码**）。现在没勾开关会**立刻报错并给出确切 GUI 路径**，不再伪装成业务 bug |
| 老 miniapp 工程的域名开关 | ⬜ **只能 Kevin 手勾**（30 秒，见 GO-LIVE-CHECKLIST §3.1 #3）。勾完重跑即可补上 accept #1 |
| 拼团实物发货上报 | 🔄 已派实现（在**置 delivered 那一刻**接，不动支付回调的正确判断） |
| accept #3 文案「两库」 | ✅ 已改（实际只有 `ry-vue` 一个库） |
| 脏数据 / 登出 404 / dist appid 改写等 4 条次要项 | 📋 已登记进 GO-LIVE-CHECKLIST 桶 5 |

**顺带读码核实**（QA 列为"没验到"的一条）：JP 退款回调在 real 模式下**是真验签的** ——
`WechatPayV3ClientImpl.parseAndVerifyRefundNotify` 用官方 SDK `NotificationParser` 做
AES-GCM 验签 + 解密，失败抛 `WechatPayVerifyException`。mock 通道不验签只是 mock 的事。
（这是**读码结论**，不是活跑验证。）

### D6 QA 门 · 第 2-5 轮（全部围绕「微信发货信息上报」）

第 1 轮逮到「任务卡 What 要求但一处调用都没有」之后，实现 → QA → 返工循环跑了 4 轮。
**每一轮 QA 都用真接口真库真并发逮到了单测照不出的东西**，逐条如实记：

| 轮 | QA 判定 | 逮到什么 | 处置 |
|---|---|---|---|
| 2 | FAIL | ① `is_all_delivered` 只在发货那刻算快照 → 最后一款走「标购买失败」落定时永不收口；② 追加包裹是无锁读-改-写 → 同支付单并发发两个运单丢一个；③ `shipping_list_json VARCHAR(4000)` 装不下微信允许的 15 个包裹、静默截断且无 `last_error` | 全修 + 真库复验 |
| 3 | FAIL | ① 收口在**并发**下仍卡死（事务内快照 + 盲覆盖）；② ★**上一轮的 `FOR UPDATE` 没命中索引**（唯一键是 `(tenant_id, transaction_id)`，查询不带 tenant）→ 全表 X 锁 → 实测锁 1 条无关拼豆行就让 JP 发货等 7.1s | 补 `idx_transaction_id` + 收口改单调收敛 + 提交后重算 |
| 4 | FAIL | ★★ **上一轮的索引把「慢但正确」换成了「快但静默丢钱」**：`FOR UPDATE` 探不存在的行拿 gap lock，两笔并发 INSERT 互相要 insert-intention → 死锁；且**与是否同一笔单无关**（同 gap 即撞），这张表拼豆/拼团/预购/扭蛋共用。InnoDB 死锁回滚**整个事务**而代码把异常吞了 → 9 张互不相干订单并发发货只有 1 张真落库；**两笔拼豆支付回调并发掉 1 笔且回微信 SUCCESS** | 改 insert-first + 死锁类异常一律上抛 |
| 5 | FAIL | ① 死锁确认修好（对照实验：旧写法必炸/新写法 0 死锁），但**上抛被 `GzJpFulfillServiceImpl` 两层 `catch(Exception)` 原地吃掉** → 人为造死锁仍能骗回 200；② 收口改库了但**从没报给微信**：`markAllDelivered` 跑在 `afterCommit` 里，用的还是刚提交那条事务的连接，写入对异步上报那条连接不可见 → 早退。判决性对照：同方法从退款侧（事务外）调 100% 成功、从 `afterCommit` 调 100% 失败 | 两层 catch 放行 `ConcurrencyFailureException` + 收口改走 `@Async`（换线程=换连接） |

**第 5 轮修完后的真库复验**（都是修前必挂的场景）：

| 场景 | 修前 | 修后 |
|---|---|---|
| 9 张互不相干订单并发发货 | 真落库 **1/9** | **9/9**，上报 9/9 success，死锁 0 |
| 两笔互不相干拼豆支付回调并发 | 真 paid **1/2** | **2/2** |
| 4 路并发把整单发完 | 6/6 卡 `pending`，微信只收到 `allDelivered=false` | `is_all_delivered=1` / `upload_status=success` / 包裹 4，**微信侧真收到 `allDelivered=true packages=4`** |

**这一段最该记住的教训**：695 个单测全绿、每一轮都全绿，**却一次都没照出上面任何一条**。
死锁、Spring 事务同步语义、连接可见性——纯 Mockito 单测在结构上就测不到。
这类链路的正确性只能靠**真库并发**背书。

### 48h 发货时限 —— 查清了，**预售场景不适用，方案不用推翻**

QA 第 5 轮提的「微信要求支付后 48h 内上传、而拼团几周后才发货」这条，查完微信规则后**不成立**：
普通商品才是 48h，**预售商品按商家承诺周期、上限 330 天**；「约定发货时效」以**商品详情页展示的最短时效**为准；
超时是**运营规范层面**处置（警告 → 3 天 → 风险提示 → 暂停交易），**不是接口硬拒**。
⇒ 拼团/代购天然是预售，**发货那一刻才上报是对的**。

真待办变小但更具体：商品页的「预计到货」(`deliveryDateText`) **商家不填时兜底是「待定（以店内通知为准）」**，
那不构成承诺时效 → 可能被按 48h 判。需做成 admin 必填、或换成明确周期（**数得甲方给**）。
详见 [GO-LIVE-CHECKLIST.md](../../GO-LIVE-CHECKLIST.md)。

### 第 6 轮：前两条修好，同族第三条

第 5 轮那两条（死锁穿透 7/7 双向注入、收口真报到微信）复验通过。但同一条链路第三条：
`doUpload` 先打微信（真 HTTP 往返）、回来才**盲写 success**，这段窗口里另一个店员的「追加包裹」
已把行改成 `pending/新清单`，盲写把它覆盖掉 → 第 2..N 个包裹一次都没报过。
**40 笔并发命中 7 笔（17.5%）**，且 dev 用的是微秒级 mock，prod 真网络窗口大几个数量级。
行是 `success` ⇒ cron 与手动补报都只扫 `pending|failed`，永远扫不到 = **静默永久丢包裹**。

修：回写改成 `updateStatusGuarded`，用 `(upload_status, attempt_count)` 作代际守卫；
守卫未命中 = 我这次结果已过时 ⇒ 什么都不写，交给那次追加派出的新上报报最新整份清单（上报幂等）。
**真库复验**：4 单 × 4 款共 16 路并发 → 4/4 单微信侧真收到 `allDelivered=true packages=4`，
与 DB 完全一致，日志里守卫跳过 1 次证明确实生效。

### accept #1 已解锁（整场卡在这）

真因不是「没勾开关」，而是**devtools 按「工程路径」存这个开关**：
`dist/dev/mp-weixin` 与 `dist/build/mp-weixin` 是**两个不同工程**。人自然打开 `dist/dev` 去勾
（那是 `pnpm dev:mp` 的产物），而 harness 默认打开 `dist/build` —— 勾了没用，且现象与没勾一模一样。
改用已授信的 `MP_DIST=dist/dev/mp-weixin` 后，`✓ 小程序侧 wx.request 能打到本地后端`。

首次真跑 `run.mjs all` = **3/6**（smoke / tour / kevin-check 绿）。三条红的经核查
**都不是 D1 多 appid 改造伤的**，而是**本项目开工前就坏、只是从没跑起来所以没人发现**：

| flow | 真实根因 | 为什么与 D1 无关 |
|---|---|---|
| login | `page.$` 跨不了自定义组件边界，登录按钮嵌在 `BizPanel` 的 slot 里 | 报错发生在**任何网络调用之前** |
| focus | `page.$$('view')` 数不到组件内部的 view（`views 过少`） | 纯渲染计数口径 |
| daypass | 缺夹具（门店未选 + 某桌型 `day_pass_quota>0`） | 报错信息自己写明了 |

已派单独修复（把 jp harness 那套 `deep()` xpath 跨组件查询搬过来 + 补夹具）。


---

## 最终收口（三条 accept 全绿）

| accept | 结果 |
|---|---|
| ① 现有小程序全量回归 `miniapp && run.mjs all` | ✅ **6/6**（`MP_DIST=dist/dev/mp-weixin`，见下） |
| ② 新小程序全流程 `miniapp-jp && run.mjs all` | ✅ **7/7** |
| ③ 迁移全部应用且无 pending | ✅ `success=0` 计数 = 0 |

**accept #1 卡了整场的真因**：devtools「不校验合法域名」按**工程路径**存，
`dist/dev/mp-weixin` 与 `dist/build/mp-weixin` 是两个不同工程 —— 人自然打开 `dist/dev` 去勾
（那是 `pnpm dev:mp` 的产物），而 harness 默认开 `dist/build`，勾了没用且现象与没勾一模一样。
程序化改 devtools 的 localstorage 无效（一开工程就被覆盖回去，实测）。

**开关解除后首跑 3/6** —— 三条红的**都不是 D1 多 appid 改造伤的**，而是**本项目开工前就坏、
只是被域名校验挡着从没跑起来所以没人发现**：`login` 的选择器跨不了自定义组件边界（报错发生在
任何网络调用之前）、`focus` 的 `page.$$('view')` 数不到组件内部、`daypass` 缺夹具。已全部修好（6/6）。

★ 顺带逮到更隐蔽的一条：`tour` / `kevin-check` 的 `doLogin` 抄的是同一串坏选择器，
**它们从来没真登录过却一直报 PASS** —— 典型假绿。

**QA 第 7 轮那条未定性的 jp `login` FAIL**：devtools 重启后复跑 **PASS**
（协议默认未勾 ✓ / 未勾时按钮 disabled ✓ / clientid 路由 ✓ / 「同意一次」持久化 ✓），
确认是 devtools 坏状态下的**假红**，不是合规真 bug。

### 发货上报最终修完的缺陷（黑盒 6 轮 + 白盒 1 轮，共 10 条）

| # | 缺陷 | 怎么发现的 |
|---|---|---|
| 1 | 功能压根没接（任务卡 What 要求，代码零调用） | 黑盒 QA 第 1 轮 |
| 2-4 | 收口只算快照 / 追加包裹无锁读改写丢包 / 列装不下 15 包裹静默截断 | 第 2 轮真库并发 |
| 5 | `FOR UPDATE` 没命中索引 → 全表 X 锁，拖住无关的拼豆回调 7.1s | 第 3 轮 |
| 6 | 补索引后变 gap-lock 死锁 + 异常被吞 → **拼豆支付回调掉单还回微信 SUCCESS** | 第 4 轮 |
| 7 | 死锁异常被调用方两层 catch 吃掉 / 收口从没真报给微信 | 第 5 轮 |
| 8 | 回写盲踩并发追加的重排队 → 第 2..N 个包裹永不上报 | 第 6 轮 |
| 9 | 守卫用 `(status, attempt)` 当代际 = **ABA，等于没守** | **白盒复查** |
| 10 | `markAllDelivered` 在 autocommit 下 `FOR UPDATE` 等于没锁，能复活 `blocked` | **白盒复查** |
| 11 | `blocked` 不是终态：12 秒第二枪自动重报，烧掉唯一一次「重新发货」机会 | 第 7 轮 |
| 12 | 「需人工并单」的告警被下一次成功上报清空 → 零痕迹 | 第 7 轮 |

**元观察**：这 12 条里，**纯 Mockito 单测一条都没照出来**（每轮 700+ 条全绿）。
它们的类型是锁、事务可见性、连接语义、并发回写 —— mock 在结构上就测不到。
全部靠**真库并发 + 白盒读码**逮出来。这条已写进 zhixing skill 的 L1「并发形态四条」。
