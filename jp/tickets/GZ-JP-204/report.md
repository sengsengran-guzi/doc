# GZ-JP-204 完工报告 — 小程序下单确认 + 支付

> **accept #2 = PASS**（exit 0，逐字执行）
> **accept #1 = BLOCKED**（exit **2** = 环境硬 gate，**不是 flow 断言失败**）
> devtools 登录这轮**已恢复**（preflight 7 项本项目首次全绿 ✅），但撞到**下一道**本机 GUI 开关：「不校验合法域名」没勾 → 小程序里所有 `wx.request` 一律 `url not in domain list`。已排除代码原因（七种绕法全试过），并做成带修复指引的硬 gate。
> **下单确认 + 支付全流程已实现并在真后端端到端跑通**：LIVE 9/9 + LIVE-FLOW（真后端数据驱动 checkout flow 的**全部断言**）全绿；单测 268、self-test 69/69（含 23 条 checkout / 21 条 negative）。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| miniapp-jp 起手 clean | ✅ | `main` @ `20d4aa8`（203 已 commit） |
| 上游 GZ-JP-105 下单接口可调 | ⚠️→✅ | 起手 8080 跑的是 **06:13 的旧 jar**，`POST /app/gz/jp/order` → **404**。已 `mvn -o clean install -pl gz-common,gz-user,gz-jp -am` + 重启，现返 401（存在，需登录） |
| GZ-SYS-022 多 appid 已 merge | ✅ | RuoYi `staging` @ `6618054d6`；preflight「后端认 clientid=mp-applet-gz-jp（openid=mock-jp-tester）」通过 |
| `VITE_MOCK_PAY` 与后端 mock 通道对齐 | ✅ | `.env.development` `VITE_MOCK_PAY=true`；后端 `gz.test.enabled=${GZ_TEST_ENABLED:true}` + `gz.pay.client-mode=mock`；`POST /app/gz/test/pay/simulate-callback` 实测 `{"code":200}` |
| 用户自助版 vs admin 版 mock 端点 | ✅ | `/app/gz/test`（`GzTestController`，`@SaCheckLogin`，只能结算自己的单）≠ `/system/gz/pay/test`（`@SaCheckPermission("gz:pay:test")`，C 端必 403）。用的是前者 |
| 蓝图已读 | ✅ | `UI:mp.order_confirm` + `.summary` / `FLOW:F-JP-02.step3·4·5·6` / `REQ-ORDER-003/004/006` / `design-options/mp-product-detail.md` |
| 兄弟仓 0 污染 | ✅ | RuoYi / plus-ui / miniapp 三仓 `git status` 全空 |

**蓝图关键约束摘录**：`UI:mp.order_confirm`「收货地址（选择/新增）→ 商品清单（只读）→ 备注 → 合计 → 提交订单 → 拉起微信支付；提交前后端重算金额并复校：场仍 open、商品仍 on_shelf、价格未变；不一致则退回购物车提示」；`.summary`「★ 只有「商品合计」与「实付」两行」；`REQ-ORDER-003`「全款，无定金无分期」；`FLOW:F-JP-02.step6`「订单 paid；每个 order_item fulfill_status=purchasing」。

## 改动文件

新增（10 个，3602 行）：
```
src/api/gz-jp/order.ts                269  订单 API + VO 镜像 + 错误码表 + 4 个路由常量
src/api/gz-user-address.ts             93  地址簿 API（gz-user 域，不放 gz-jp/）
src/locale/order.zh-CN.ts             166  文案（刻意不提供任何第二笔费用的 key）
src/pages/order/confirm.logic.ts      310  ★ 纯逻辑（ids/清单/金额/地址/提交闸门/错误码→动作）
src/pages/order/confirm.logic.test.ts 365  41 条单测
src/pages/order/confirm.vue          1237  ★ 下单确认页（含内嵌地址选择/新增 sheet）
src/pages/order/result.logic.ts       146  轮询状态机
src/pages/order/result.logic.test.ts  122  15 条单测
src/pages/order/result.vue            332  ★ 支付结果轮询页
test/e2e/flows/checkout.mjs           562  ★ accept #1 的 flow
```
修改（18 个）：
```
src/http/{http,types}.ts           +20  加 rawBizError 可选项（默认关，既有页面 catch 一行不改）
src/api/gz-pay.ts                  +26  加 simulatePayCallbackSelf（/app/ 用户自助版）
src/components/biz/BizCartItem.vue +35  加 readonly + qtyText（默认 false，购物车行为不变）
src/pages/*.vue（11 个）            +11  ★ <BizScreen> → <BizScreen class="jp-screen">（E2E 锚点，无样式）
test/e2e/mp-e2e.mjs               +150  ★ deep/deepAll/deepTexts + assertBackendReachableFromMp + appid 改真值
test/e2e/run.mjs                   +32  注册 checkout + launchWithRetry + 小程序侧网络硬 gate
test/e2e/self-test.mjs            +421  checkout 场景机（真读写四表）+ 23 条用例 + 深选择器归一
test/e2e/flows/smoke.mjs            +8  两个新页进可达性表（AC X(a)）
test/e2e/README.md                 +66  三条新坑写死
```
**未 commit**。doc / RuoYi-Vue-Plus / plus-ui / miniapp 四仓一行没碰。

## 实现要点（值得复核的 8 条）

1. **金额区两行同源于一个 `checkoutAmountCent`** —— 「商品合计」与「实付」渲染同一个 computed，物理上没有能插进第三笔的地方。E2E 额外断言**结构上恰好 2 个 `.jp-confirm-sum__row`**（光 grep 文案挡不住「其它费用 ¥0」这种换名的第三行）。locale 里不提供任何相关 key。⚠️ **该文件连注释都不能出现那两个字**（accept #2 是整文件 grep，本卡实测踩到一次）。
2. **★「已阅读不支持退款」勾一次**（Kevin 2026-08-06 原话的另一半）：默认**不勾**，不勾时提交置灰；点灰按钮 toast 具体缺什么（不是不说话的死按钮）。带「?」入口弹《拼团购买须知》全文。
3. **提交闸门抽成 `buildSubmitGate` 返回 `reason`**：5 个 disabled 来源，优先级刻意是「先报客人自己解决不了的」——购物车已空的客人不该被引导去「先勾一下已阅读」。
4. **前端不重复实现下单校验**：场/商品/价格复校**全由后端一个事务里做**（105 已实现）。前端只做两件事：进页面重拉整车标出 `invalid` 并拦住提交（省一次白跑）、**正确处理错误码**。两套判定必然漂移，漂移那刻客人会看到「页面说能买、点了说不能买」。
5. **错误码 → 动作**：4101/4102 退回购物车（**不原地重试**）/ 4103 重选地址 / 4104 刷新本页 / **4107 去我的订单（绝不重试）**。msg 一律用后端原文。
6. **`http.ts` 加 `rawBizError`**：默认行为下业务错误 reject 的是 `responseData.data`（恒 null），拿不到 code 就没法区分 4102 与 4104 —— 两者动作完全相反。**默认关，既有页面零改动**。
7. **结果页回读后端订单状态，不信 `requestPayment` 的 success**（跨层契约 #6）。`resolvePhase` 的入参里**根本没有**「微信说成功了没」。**到顶不说「支付失败」**（那会让已付过钱的客人再付一次）。`paid/partial_refunded/refunded` 都算钱已到。
8. **地址最小可用**：确认页内嵌 sheet（选择列表 + 新增表单），没做独立管理页。手机号 `type="number"` 只为唤数字键盘，后端 `mobile` 本就是 String（`@Pattern`），不存在「数字字段收到字符串」那类 400。

## AI 自测（Tier 1A）

### 1. accept #2（逐字）
```
$ ! grep -qE '运费|freight|shipping.?fee' code/main/miniapp-jp/src/pages/order/confirm.vue
ACCEPT2_REAL_EXIT=0        ← PASS
```

### 2. accept #1（逐字）—— BLOCKED，exit 2 = 环境闸门
```
$ cd code/main/miniapp-jp && node test/e2e/run.mjs checkout
[preflight] ✓ devtools cli / ✓ 服务端口 / ✓ devtools 已登录      ← ★ 本项目首次全绿
           ✓ dist 完整 / ✓ dev profile / ✓ 后端可达(401) / ✓ 认 clientid
[run] ✓ automation launched
[run] launch/run 异常: 小程序侧 wx.request 被域名校验拦下（request:fail url not in domain list）。
  ↑ 这是**本机 GUI 开关**没打开，不是代码问题：
    微信开发者工具 →「详情」→「本地设置」→ 勾「不校验合法域名…」，然后重跑。
ACCEPT1_REAL_EXIT=2
```

### 3. ★★ LIVE 全链路（真后端 → 真 logic → 页面会渲染的值）9/9
```
[LIVE] wx-login → userId=14 openid=mock-jp-tester；起点 车里 1 款/25600 分/地址簿 1 条
 ✓ 去结算 ids = 58（购物车项 id，非商品 id 1）
 ✓ 金额区：商品合计 ¥256 / 实付 ¥256 / 已包邮 / 共 2 件   ← 两行同值，==后端 validAmountCent
 ✓ 地址卡：张三 13800000000 / 四川省 成都市 锦江区 春熙路 1 号
 ✓ 新增地址真落库 id=2 → 四川省 成都市 锦江区 LIVE 测试路 515310 号
 ✓ 闸门文案：未选地址→「请先选择收货地址」/ 未勾→「请先阅读并勾选购买须知」
 ✓ 4104 → 商品价格有变动，当前应付 256.00 元… → 动作=reload
 ✓ 4103 → 收货地址无效，请重新选择        → 动作=pick_address
 ✓ 4101 → 请选择要结算的商品              → 动作=back_to_cart
 ★★ happy path：
    提交成功 orderNo=JPO-20260807-000038 实付=25600分 outTradeNo=JPO-20260807-000039
    结果页路由 = /pages/order/result?orderId=24&orderNo=…038&outTradeNo=…039&paid=1
    支付前 businessStatus=created → resolvePhase=polling
    mock 支付走完：已支付 paidTime=2026-08-07 08:11:56 商品行=["购买中"]
      → 结果页显示「支付成功」+「查看订单详情」
    下单后购物车 itemCount = 0
Test Files 1 passed   Tests 9 passed
```
顺带被真数据验到：`payParams.outTradeNo`（…039）**不等于** `orderNo`（…038）——mock 回调 / 查支付必须传前者。

### 4. ★★ LIVE-FLOW（用真后端数据驱动 checkout flow 的**全部断言**）
flow 的 `runWith` 一字未改，后端读写全走 curl 打真 8080（加购/存地址/下单/mock 回调都是真的）：
```
起点：场=8月上旬快闪场 商品=柯南 吧唧 一番赏 A赏 车=1款/25600分
  ✓ ★ 第 1 跳：购物车 →「去结算」→ 下单确认页，带的是购物车项 id ["59"]
  ✓ 自动选中默认收货地址：张三
  ✓ ★ 新增收货地址真落库并立刻选中：E2E收569381 / 13961569381 / E2E 测试路 569381 号
  ✓ 商品清单文案来自后端真数据：["柯南 吧唧 一番赏 A赏"]
  ✓ 商品清单是只读的（无操作区/无 stepper/无删除，数量静态展示 ["×2"]）
  ✓ ★★ 金额区只有商品合计与实付两行、无第三行，实付 ¥256（25600 分）
  ✓ ★★ 「已阅读不支持退款」闸门双向正确：未勾→置灰，勾上→可点
  ✓ ★ 提交订单真落库：JPO-20260807-000040 实付 25600 分 款数=1
  ✓ ★ 提交后落到支付结果页 pages/order/result
  ✓ ★★ mock 支付走完结算：订单=已支付(paid) 付款时间=2026-08-07 08:12:51 商品行=["purchasing"]
  ✓ 支付结果页显示：["支付成功"]        ✓ ★ 下单后购物车已清空
[LIVE-FLOW] ✅ checkout flow 的全部断言在【真后端真数据】上通过
```
**剩下没被覆盖的只有「真模拟器里的点击与像素渲染」**——正是被 GUI 开关卡住的那一段。

### 5. 单测 268 全绿（212 存量 + 56 本卡）
```
✓ src/pages/order/confirm.logic.test.ts (41)  ← 本卡
✓ src/pages/order/result.logic.test.ts  (15)  ← 本卡
✓ cart(48)/index(41)/event(37)/product(27) …  ← 201/202/203 原样绿
Test Files 13 passed (13)    Tests 268 passed (268)
```
关键边界：重复 id 去重、脏 `amountCent` 按 0 计不出「¥NaN」、以后端 `amountCent` 为准不在前端乘、直辖市「北京市 北京市」不重复、**闸门优先级**（车空+没地址+没勾 → 报「没商品」）、到顶→unpaid 而非「支付失败」、`orderNo ≠ outTradeNo` 都要带。

### 6. self-test 69/69（46 存量 + 23 本卡，21 条 negative）
```
✓ checkout / 下单确认到支付全流程 → 通过        ✓ 地址簿为空走「新增」路径 → 通过
✓ ★★ 去结算传成了商品 id（不是购物车项 id）→ 必须 fail
✓ ★★ 点了「保存并使用」但地址没真落库 → 必须 fail
✓ ★清单里混进数量步进器 / 删除按钮 → 必须 fail
✓ ★★ 金额区出现第三行（哪怕不叫那个名字）→ 必须 fail
✓ ★★ 金额区出现配送费用字样 → 必须 fail
✓ ★★ 压根没做「已阅读不支持退款」勾选 → 必须 fail
✓ ★勾选文案里没提「退款」→ 必须 fail
✓ ★★ 没勾也能提交 / ★★ 勾了仍置灰 → 必须 fail（两个方向各一条）
✓ ★★ 点了提交但订单没落库 → 必须 fail
✓ ★★ mock 支付没驱动结算（订单停在 created）→ 必须 fail
✓ ★后端已 paid 但结果页还在转圈 → 必须 fail    ✓ ★下单后购物车没被清空 → 必须 fail
[self-test] 69/69 通过
```
checkout 假件带**内存版后端四张表**（车/地址/订单/订单行），假 app 的 tap+input 写它、假页面从它渲染、flow 的四个 reader 也读它 —— negative 只要让两者脱钩就必然 fail。

### 7. 产物核对
```
app.json pages: ['pages/order/confirm', 'pages/order/result']    ← 已自动注册
选择器命中：jp-confirm / jp-confirm-sum__row / jp-confirm-agree__box-wrap /
          jp-confirm-bar__submit / jp-addr-form__region / jp-addr-form__save /
          jp-payres / jp-payres__btn / biz-cart-item__qty-text
API 进 bundle：app/gz/jp/order / app/gz/user/address / app/gz/test/pay/simulate-callback
文案进 bundle：已阅读并同意 / 不支持退款 / 商品合计 / 实付 / 已包邮 / 确认订单 / 支付成功
产物 pages/order/ 下 grep 配送费用字样 → 0 命中
```

### 8. 工程健康
```
pnpm type-check exit=0 · pnpm lint exit=0 · pnpm test exit=0(268)
self-test exit=0(69/69) · build-dist development exit=0
```

## accept #1 的阻塞点（已排除代码原因）

**现象**：小程序里**所有** `wx.request` → `request:fail url not in domain list`。页面全停在 loading，flow 报「登录失败」——**看着像代码 bug，不是**。

| 试过的 | 结果 |
|---|---|
| `project.config.json` 的 `setting.urlCheck:false` | 本来就是 false（uni 按 manifest 生成），无效 |
| 写 `project.private.config.json`（含 urlCheck:false） | **反而更糟**：一旦存在，devtools 以它为准解释设置，域名校验重新打开 |
| `cli close --project` 后重开 | 无效 |
| `touristappid` → 真 appid | 必需但不充分（游客模式**强制**域名校验，urlCheck 完全无效） |
| 复制 dist 到全新工程路径重新导入 | 无效 |
| `localhost` → `127.0.0.1` | 两个都被拦（同一个错） |
| `cli` 有无对应子命令 | 没有（`cli --help` 全看过） |

**修法只有一个（本机一次性人工动作，同 devtools 扫码登录那一类）**：
> 微信开发者工具 → 打开 `code/main/miniapp-jp/dist/build/mp-weixin` → 右上角「详情」→「本地设置」→ 勾上 **「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**

勾完 `node test/e2e/run.mjs checkout` 直接重跑（代码侧无需改动）。

**工程化收尾**：`run.mjs` 在 launch 之后加了硬 gate `assertBackendReachableFromMp`（用小程序自己的 `wx.request` 探一发，命中即以上面那段人话 exit 2）——preflight 原有的「后端可达」是 node 用 curl 探的，探不出这一层。README 把七种无效尝试写死了。

## 顺带修掉的两个 harness 级真缺陷（不修则 flow 永远跑不了）

### A. ★★ 选择器不跨自定义组件 → 「不该存在」类断言恒真
微信 `SelectorQuery`（automator `page.$`/`$$` 底层）**不跨自定义组件边界**。`.biz-cart-item__name` / `.jp-event-card` / `.login-agree__box` / `.me-header__top` 这类写在组件内部的类，直接查一律 `null`/`[]`。

**最阴的地方**：`$$` 查不到返回 `[]`，于是「页面上不该有 X」这类断言**恒真**——本卡的「清单必须只读」原本就中了这一枪，**写了等于没写**。

修法：每页 `<BizScreen class="jp-screen">` 作页面级锚点（无样式；必需——本工程每页模板根就是 `BizScreen` 组件、登录弹层还挂它内部，没锚点时登录 sheet 在页面作用域里连一个可选的祖先都没有）+ `mp-e2e.mjs` 新增 `deep/deepAll/deepTexts`（拼官方 `'.jp-screen >>> X'`）+ `loginIfNeeded` 改用 deep（**它此前从来没可能成功过**，只是没人跑到那一步）+ 只读断言先验正向锚点 `.biz-cart-item__qty-text`（这样查询失效会变红不会变绿）。

**判断规则**：选择器定义在 `src/pages/**` → 直接 `page.$`；在 `src/components/biz/**` → 必须 `deep`。

### B. `rawPath` 瞬态：dist 重建后第一跑必红
`Cannot destructure property 'rawPath' of 't.getPageMetaByWebviewId(...)' as it is null` = devtools 正在重导入/重编译工程，automator 拿到空 page meta，**与被测代码无关**。`run.mjs` 加 `launchWithRetry` 自动重试一次。

## 风险提示 / 已知 issue

1. **★ 本卡未跑过真模拟器渲染**，两个新页的**实际像素**没被人或机器看过一眼。功能与数据流已由 LIVE + LIVE-FLOW 覆盖，**视觉未验**。底部条现在两层（协议勾选行 + 金额/提交行），`.jp-confirm__spacer` 按 220rpx 让位——**算出来的不是看出来的**。
2. **★「已阅读不支持退款」的勾选只是前端闸门，没落库**——后端 `GzJpOrderSubmitBo` 没有该字段（105 已 commit，本卡 touches 只含 `miniapp-jp/**`）。**真要用于纠纷举证需后端加一列（`agreed_no_refund` + 时间戳），建议另开 ticket**。当前：不勾下不了单（闸门有效），但事后拿不出「他勾过」的证据。
3. 地址簿只做了确认页内嵌的选择/新增，无编辑/删除/设默认管理页（超出本卡范围）。新增的第一条自动设默认。
4. 省市区用原生 `<picker mode="region">`，E2E 走 `element.trigger('change', ...)`（派发的仍是页面自己的 `onRegionChange`，不是绕过页面逻辑塞值）。
5. **`http.ts` 动了一处共享代码**（`rawBizError` + 业务错误分支尊重 `hideErrorToast`）。前者默认关，后者全仓此前零使用 → 既有页面行为零变化。
6. **11 个页面加了 `class="jp-screen"`**——无样式纯锚点，但确实动了 201/202/203 的页面文件（各 1 行）。
7. **201/202/203 的 flow（home/product/cart）仍用组件内选择器**，**域名校验放开后它们仍会红**，需照本卡方式改 `deep()`（锚点与 helper 已就位，改动机械）。同理 smoke 的 `.me-header__top` 要改 deep；`MIN_VIEWS=3` 对「游客/空态只有 2 个页面级 view」的页偏严（内容都在组件里），建议加 per-page `minViews`。**本卡刻意没动它们**（非本卡 scope，且会掩盖谁在改什么）。
8. **8080 后端由本卡重启**（起手那个是旧 jar，没有 105 的订单接口）。当前是 clean install 后的 jar（PID 43136），**保留运行**给 Tier 1B，`/app/gz/jp/event/list` → 200。
9. dev 库现状：`gz_jp_order` **5 张全 paid**（105 的 2 张 + 本卡 3 张）/ 6 条订单行 / 购物车已清空 / 地址簿只剩 `id=1 张三`（本卡造的 2 条测试地址已软删）。205 的 fixture 更足。临时工程 `/tmp/gzjp-e2e-proj` 已删，临时 `__live.test.ts` 已删。
10. **待 Kevin 残留人验**：真机真实微信支付（本卡走 dev mock 通道，属上线前节点）+ **新页首版视觉拍板**（确认页 / 支付结果页）。

## 对下游 GZ-JP-205（订单列表 / 详情）的提示

**1. 你要建的两个页面，路由常量已定好并被本卡引用**（`src/api/gz-jp/order.ts`）：
```ts
ORDER_DETAIL_ROUTE = '/pages/order/detail'   // buildOrderDetailRoute(orderId) → ?id=<订单主键>
ORDER_LIST_ROUTE   = '/pages/order/list'     // buildOrderListRoute(tab)       → ?tab=created
ORDER_LIST_TAB_UNPAID = 'created'            // ★ 取后端状态原值，别自造 'unpaid'
```
**改路径要同步改这两个常量**（结果页两个出口按钮都用它们；205 合并前 `navigateTo` 会 fail，已兜 toast「即将上线」，**不是静默无反应**）。

**2. 支付结果页长这样**（`/pages/order/result?orderId=&orderNo=&outTradeNo=&paid=1`）：四阶段 `polling/paid/unpaid/closed`（`result.logic.ts` 的 `resolvePhase`，15 条单测）；**paid → 「查看订单详情」跳 `buildOrderDetailRoute(orderId)`**（详情页收 `?id=`）；**unpaid/closed → 「去我的订单」跳 `?tab=created`**（列表页读 `options.tab` 直接当 `GET /order/list?businessStatus=` 入参，中间别加映射表）；轮询 1.5s × 10 ≈ 15s，`onUnload` 必清表；**到顶不说「支付失败」**。⚠️ `orderNo` 与 `outTradeNo` **不是同一个值**。

**3. API 层已写好，直接 import 别重写**（`@/api/gz-jp/order`）：`fetchJpOrderDetail(orderId)`（已带 `hideErrorToast` + `rawBizError`，适合轮询）、`GzJpOrderDetailVO/ItemVO/AddressVO` 类型镜像、`JP_ORDER_ERROR` 码表、`bizErrorCodeOf/bizErrorMsgOf`。**列表端点本卡没封**（归你），注意 **读 `res.rows` 不是 `res.data`**（D16 逮到过 6 处这类 bug）。

**4. 状态文案后端已给**（`businessStatusLabel`/`fulfillStatusLabel`），**别维护第二份映射表**。详情页按 `UI:mp.order_detail` **按履约状态分组**（方案 A），组按状态链排、同状态不同单号再分子组、**全页不出现「包裹」二字**（REQ-FULFILL-006）。

**5. 组件**：`BizCartItem` 已支持 `readonly` + `qtyText`（本卡加的），订单详情商品行可直接复用；`formatYuan()` 算金额；文案 key 全在 `@/locale/order.zh-CN.ts`（`order.*`）——**但那文件里永远不会有第二笔费用的 key**。

**6. E2E**：新页模板根**必须** `<BizScreen class="jp-screen">`；**组件内选择器一律 `deep/deepAll/deepTexts`**，写「不该存在 X」的断言时**先验一条正向锚点**；`flows/order.mjs` 抄 `checkout.mjs` 骨架，`loginIfNeeded` + `readAppToken` 拿同一会话 token 直连后端；**必须补 negative**（状态分组错位 / 单号重复出现 / 出现「包裹」字样 / 列表读了 `res.data` 导致空列表）；dev 库现有 **5 张 paid 订单 + 6 条订单行**（userId=14）做 fixture。

**7. 跑 E2E 前**：确认 8080 活着 + **devtools 本地设置里「不校验合法域名」勾着**。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅（accept #1 除外，环境阻塞），待 Tier 1B（主线程派 kevin-qa）**

- 不依赖 devtools 的现在就能跑：`pnpm test`（268）/ `node test/e2e/self-test.mjs`（69/69）/ 后端 curl 契约回归（4101/4102/4103/4104/4107 + simulate-callback）
- **模拟器 E2E 需 Kevin 先在 devtools 本地设置勾「不校验合法域名」**（一次性）
- ⚠️ 跑 `run.mjs all` 时 home/product/cart 三个 flow **预计仍会红**（组件内选择器没改 deep，风险 7），属已知待修，**不是本卡回归**

---

**结尾一句话**：**accept #1 = BLOCKED**（exit 2，devtools「不校验合法域名」GUI 开关，非代码问题，已排除七种绕法并做成带修复指引的硬 gate）、**accept #2 = PASS**（exit 0）；下单确认 + 支付流程**完整实现**——含地址选择/新增（真落库）、「已阅读不支持退款」举证勾选（双向闸门）、mock 支付走通（订单真转 `paid`、商品行进 `purchasing`、购物车被清空），全部在**真后端**上端到端验证过（LIVE 9/9 + LIVE-FLOW 全断言绿 + 268 单测 + 69 self-test），**未 commit**。
