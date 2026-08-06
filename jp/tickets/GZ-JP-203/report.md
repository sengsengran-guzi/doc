# GZ-JP-203 完工报告 — 小程序购物车

**accept #1（`node test/e2e/run.mjs cart`）= BLOCKED**（exit 2 = preflight 阻塞；7 项体检 6 绿 1 红，红的只有 `devtools-login` → `cli islogin` 独立复核仍 `{"login":false}`，与 D1/D2/201/202/D3-QA 同一个人工扫码阻塞，代码侧无需改动）
**accept #2（`! grep -qE '运费|freight|shipping.?fee' .../cart/index.vue`）= PASS**（exit 0，逐字执行）
**购物车页 + 真加购接入 = 两件都做完了。**

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| miniapp-jp 起手 clean | ✅ `main` @ `426a1b4`（202 已 commit） |
| 上游 GZ-JP-104 已 merge 且可调 | ✅ RuoYi `fca8690c0`；四端点逐个 curl 通 |
| 未登录 `cart/list` | ✅ `{"code":401,...}` —— 四端点确实需登录 |
| 后端起手状态 | ✅ 8080 已在跑（104 留的 PID 18978），**本会话未重启未新起** |
| dev fixture | ✅ 场 1 open / 2 draft；商品 1 on_shelf(12800) / 3 off_shelf / 4 draft场 |
| 蓝图已读 | ✅ `UI:mp.cart`+`.group`+`.summary` / `FLOW:F-JP-02.step2/3` / `REQ-ORDER-004/005` / `design-options/mp-cart.md`（方案 A 已拍板） |
| 兄弟仓 0 污染 | ✅ plus-ui/miniapp 0 改动；**RuoYi 的 25 处全是并行 105 的订单后端**，本卡一行没碰 |

**蓝图关键约束摘录**：`UI:mp.cart.summary` ★ 只有商品合计一行；`REQ-ORDER-004` 系统里彻底没有第二笔费用概念；`design-options/mp-cart.md` Kevin 2026-08-06 拍板**方案 A 按场分组 + 组级全选**（理由：场有截止时间，快闭场那批要能优先结）；104 报告「给 203」段：能不能勾选**只看 `item.invalid`**、分组已排好序前端不重排、stepper 是**绝对赋值**、改数量后**整车重拉**。

## 改动文件

新增（`code/main/miniapp-jp/`）：
```
src/api/gz-jp/cart.ts               186   购物车 API + 3 个 VO 镜像 + CART_ROUTE
src/locale/cart.zh-CN.ts             98
src/pages/cart/index.logic.ts       367   ★ 纯逻辑（勾选状态机/合计/去结算闸门/结算路由）
src/pages/cart/index.logic.test.ts  457   48 条单测
src/pages/cart/index.vue            676   ★ 购物车页
src/components/biz/BizCartItem.vue  304   购物车行（横向形态，没硬套 BizProductCard）
test/e2e/flows/cart.mjs             441   ★ accept #1 的 flow
```
修改：
```
src/pages/product/detail.vue  +135  ★ 接真加购 + CTA 条购物车入口(带角标)
src/pages/me/index.vue         +11  购物车常驻入口(需登录)
src/locale/product.zh-CN.ts      8  占位文案 → addToCartSuccess
src/locale/user.zh-CN.ts         2  entryCart
test/e2e/mp-e2e.mjs            +53  登录态治具 loginIfNeeded / readAppToken
test/e2e/run.mjs                +1  FLOWS 注册 cart
test/e2e/flows/smoke.mjs        +4  PAGES 加购物车页（AC X(a) 落点）
test/e2e/self-test.mjs        +311  cart 场景机(内存版后端) + 16 条用例
test/e2e/README.md             +24
```
**未 commit**。doc / RuoYi-Vue-Plus / plus-ui / miniapp 四仓一行没碰。

## 购物车入口

**没有预留入口，新加了两处，都是业务主线真入口（不是临时入口）**：

1. **商品详情底部 CTA 条最左** `.jp-product-cta__cart`（🛒 + 款数角标）—— 加购后角标就在旁边变，客人看得见「东西进去了」；**首页→场→商品→购物车 = 三跳可达**
2. **「我的」页入口格**第一项 —— 常驻入口（不看商品时也能回去），进了 `LOGIN_REQUIRED_KEYS` 所以游客点它先弹协议 sheet

角标复用 201 的 `formatBadgeCount`（0 → 空串，不显示误导性的「0」）。购物车**不进 tabbar**（tabBar 只有首页/我的，本卡没动）。

## 关键实现决策（值得复核的 6 条）

1. **★ 勾选态一条规则统一「首次全选」与「刷新保留」**：`syncSelection(cart, prevSelected, prevKnown)` —— 失效项永不勾 / 已消失的摘掉 / **本次新出现的可勾选行默认勾上**。首次加载 `prevKnown` 为空 ⇒ 所有行都"新出现" ⇒ 等价于默认全选；此后刷新只有真正新加的（刚加购那件）自动勾上，**客人手动取消过的不会被刷新偷偷勾回来**。写成一条规则而不是「两分支 + isFirstLoad 布尔」，因为那布尔在 `onShow` 反复触发下极难维护对。
   **副产品**：首次全选时前端合计**恒等于后端 `validAmountCent`** → 成了一条前后端对账断言，E2E 拿它当 oracle。
2. **默认全选（有效项）** —— 甲方场景是「一次买 30 款」，默认不选要点 30 下。AC「未勾选时置灰」由 E2E 主动取消全选来验（比被动默认态更强，还能验反方向）。**这是产品决策不是 AC 要求，Kevin 可推翻**，改一处即可。
3. **改数量 = 乐观本地更新 + 350ms 防抖 PUT + 整车重拉**。合计立刻变（AC「实时刷新」），连点合并成一发；后端 PUT 是**绝对赋值**语义所以合并天然正确。无论成败都整车重拉（失效状态是后端实时算的）。`onHide`/`onUnload` 都 flush。
4. **失效判定只认 `item.invalid`，不看 `group.eventBookable`**（有单测锁：组 `eventBookable=false` 但行没标失效时该行**仍可勾选**）。`isSelectable` 对缺字段按**可勾选**处理 —— 与加购放行方向**相反**，因为代价不对称（勾选拦错 = 把还能买的商品变成勾不动的死行）。
5. **两层拦失效行**（组件禁点 + `toggleItem` 再拦）→ 勾选集合里永远混不进失效行，合计与闸门都不用再判 `invalid`。
6. **「去结算」只带 id 不带金额**（防篡改 + 两页之间价格可能已变）。

`onAddToCart()` 里 **`ctaDisabled` 那条分支一行没动**（编译后 wxml 复核 `is-disabled` 绑定还在），且「注意事项在 CTA 之上」在真 wxml 里仍成立（`jp-product-notice @3580 < jp-product-cta @3956`）。

## AI 自测（Tier 1A）

**1. accept #2（逐字）**
```
$ ! grep -qE '运费|freight|shipping.?fee' code/main/miniapp-jp/src/pages/cart/index.vue
ACCEPT#2 EXIT=0
```

**2. 单测 212 全绿（164 存量 + 48 本卡）**
```
✓ src/pages/cart/index.logic.test.ts   (48 tests)   ← 本卡
✓ src/pages/index/index.logic.test.ts  (41) / event (37) / product/detail (27)  ← 201/202 原样绿
Test Files 11 passed (11)   Tests 212 passed (212)   VITEST_EXIT=0
```
48 条分布：取子集 4 / `isSelectable` 5 / `syncSelection` 7 / 三态 5 / 开关 7 / ★合计 7 / ★去结算闸门 6 / 结算路由 4。关键边界含：候选集为空 → `none` 不是 `all`（整组失效时全选框不该显示勾中）、`toggleAll` 永不勾失效项、只勾着失效/已消失 id 仍置灰、脏 `amountCent` 按 0 计不出 `¥NaN`、跨场混选一起结算。

**3. ★ LIVE 全链路（真后端 → 真 logic → 真 flow 断言）** —— accept #1 的核心替代证据。临时 vitest 用 curl 打真后端，**tap 打真接口**（加购真 POST / 改数量真 PUT），渲染值全用页面实际在用的 logic + locale 算，喂给 cart flow 的**真断言主体 `runWith`**：
```
[LIVE] wx-login → {"userId":"14","openid":"mock-jp-tester"}
  ✓ 起点已清空购物车（清掉 0 款残留）
  ✓ 前置两跳：首页 → 场详情 → 商品详情
  ✓ ★ 加购真落库：后端车里 1 款「柯南 吧唧 一番赏 A赏」× 1（productId=1）
  ✓ CTA 条购物车角标 = 1
  ✓ ★ 第 3 跳：商品详情 → 购物车（pages/cart/index）—— 从首页三跳可达
  ✓ 按场分组，组名来自后端真数据：["8月上旬快闪场"]
  ✓ ★ 合计与后端 validAmountCent 一致：¥128（12800 分）
  ✓ ★ 底部只有商品合计一行 + 「已包邮」标注（无第二笔费用）
  ✓ ★ 改数量实时刷新合计：¥128 → ¥256（后端 qty=2）
  ✓ ★ 「去结算」闸门双向正确：全不选→置灰(合计 ¥0)，全选→可点(合计 ¥256)
[LIVE] 去结算路由 = /pages/order/confirm?ids=44
```

**4. ★★ AC1 跨场共存 + AC3 失效项 真库直验**（dev 只有 1 个场 → 临时克隆一个，验完物理删）
```
建：gz_jp_event 23 EVT-TMP203-000001 open / gz_jp_product 68 event_id=23 on_shelf 6800

[LIVE-CROSS] 分组 = [{"场":"GZ-JP-203 跨场共存对照场","款":1},{"场":"8月上旬快闪场","款":1}]
[LIVE-CROSS] ★ 跨场共存：2 组 / 合计 ¥324        ← 12800×2 + 6800

mysql> UPDATE gz_jp_event SET status='closed' WHERE event_no='EVT-TMP203-000001'; → 1
[LIVE-CROSS] 关场后 = [{"场":"8月上旬快闪场","bookable":true,"行":[{...invalid:false,金额:25600}]},
                      {"场":"GZ-JP-203 跨场共存对照场","bookable":false,
                       "行":[{invalid:true,reason:"event_closed",text:"本场已结束",金额:6800}]}]
                                    ↑ ★ 已结束场排到后面（后端排序，前端不重排）
[LIVE-CROSS] ★ 失效行不可勾选、不计入合计（合计 ¥256，非 ¥324）
   真 logic 断言：invalidIds==[该行] / selectableIds 不含它 / syncSelection 把上轮勾中的它摘掉 /
                 toggleItem(它,true) 纹丝不动 / toggleAll 不勾它 / checkoutIds 不带它

mysql> UPDATE gz_jp_event SET status='closed' WHERE id=1; → 1
[LIVE-CROSS] ★ 两场全关 → 一个勾不上 → 去结算置灰、合计 ¥0

清理：DELETE 临时 event/product（物理删）→ diff BEFORE/AFTER 逐列
EVENT 逐列一致 ✅   PRODUCT 逐列一致 ✅   软删残留 event=0 product=0 cart_rows=0
上游契约回归：event/list total=1 / product/list on_shelf / event/2→"该场不存在" /
             product/3、4→"该商品已下架"      全部原样
```
两个临时脚本已删（`ls src/pages/cart/` 只剩 `index.logic.{ts,test.ts}` / `index.vue`）。

**5. 购物车四端点契约 curl 核对**
```
POST /cart {"productId":"1","qty":2}  → {"code":200,"data":2}    # 累加后数量
GET  /cart/list → item{id,productId,productNo,name,mainImageUrl,priceCent,qty,amountCent,
                        eventId,invalid,invalidReason,invalidText}
                  group{eventId,eventNo,eventName,eventStatus,eventBookable,items}
                  汇总 itemCount/invalidCount/validQty/validAmountCent
PUT  qty=5 → 200 ｜ qty=0 → 500 数量至少为 1 ｜ qty=100 → 500 单款商品最多 99 件
POST productId=3(off_shelf) → 500 该商品已下架
POST productId=4(draft场)   → 500 本场已结束，无法加入购物车
DELETE /cart/43 → {"code":200,"data":1} → list groups:[] 无残留
```
前端 VO 镜像逐字段对齐，ID 全 string，**无任何费用类字段**。

**6. self-test 46/46（30 negative；本卡 16 条里 14 条 negative）**
```
✓ cart / 三跳可达 + 加购真落库 + 分组 + 合计 + 改数量 + 去结算闸门双向 → 通过
✓ cart / 车里已有一件失效商品（标「已失效」+ 不计入合计）→ 通过
✓ cart / ★★ 点加购但没真落库（还是占位 toast）→ 必须 fail
✓ cart / ★加购按钮是置灰态（fixture 的场已结束）→ 必须 fail
✓ cart / ★第 3 跳跳错页 → 必须 fail
✓ cart / ★显示前端 mock 组名 / ★mock 商品名 → 必须 fail
✓ cart / ★★ 底部出现「运费」行 → 必须 fail
✓ cart / ★底部没有「已包邮」标注 → 必须 fail
✓ cart / ★改数量没落库 / ★后端变了页面合计不跟 → 必须 fail
✓ cart / ★★ 取消全选后仍可点 / ★永远置灰 → 必须 fail（两个方向各一条）
✓ cart / ★失效商品没标「已失效」/ ★★被算进合计 → 必须 fail
✓ cart / ★角标与后端款数对不上 → 必须 fail
[self-test] 46/46 通过   SELFTEST_EXIT=0
```
cart 的假件比前几个复杂一档：带**内存版后端**，假 app 的 tap 写它、假页面从它渲染、flow 的 `readCart` 也读它 → 「页面与后端对得上」在假件里同样有内容，negative 只要让两者脱钩就必然 fail。

**7. 产物核对**：`app.json` 里 `pages/cart/index` 已自动注册；11 个 E2E 选择器全在编译产物里；`app/gz/jp/cart/list`+`app/gz/jp/cart` 已进 bundle；locale「已包邮/去结算/全选/已失效/已加入购物车/清空失效/登录后查看购物车」全在；**旧占位文案「购物车即将上线」已消失** ← 加购确实换成真的了。

**8. 工程健康**：`pnpm type-check` exit=0 / `pnpm lint` exit=0 / `pnpm test` exit=0 / `self-test` exit=0 / `build-dist development` exit=0。

## 风险提示

1. **★ 本卡未跑过真模拟器**，两个页面的**实际渲染**没被人或机器看过一眼。尤其 **CTA 条现在有 4 个元素**（购物车入口 + 数量标签 + stepper + 加购按钮），750rpx 下主按钮估算还剩约 310rpx（够放 5 个字），但**这是算出来的不是看出来的**。
2. **默认全选是产品决策**（非 AC），Kevin/甲方可推翻 —— 改 `syncSelection` 一处，3 条单测跟着改。
3. 改数量有 350ms 防抖窗口，客人点完**立刻杀进程**（非返回）会丢那一次；`onHide`/`onUnload` 已 flush。
4. 商品详情每次 `onShow` 多拉一次 `/cart/list` 刷角标（仅登录态）—— 换的是「从购物车删完返回，角标跟着降」。
5. 图是 MinIO 预签名 1h 过期（同 202），行组件 `@error` 兜占位块。
6. dev mock 登录恒同一用户（`userId=14`）→ 用户隔离在 mp 侧验不了（后端 104 已验）。
7. **cart flow 会清空 `userId=14` 的购物车**拿确定性起点（README 已写明）。
8. 「清空失效商品」是自加的（AC 没要求，零新端点 + modal 二次确认），觉得多余可删模板那段。
9. 孤儿组（商品被删）在 dev 库没造（会污染 `del_flag`），有 3 条单测 + 后端 104 已验下发形态。
10. 未 commit（主线程统一收尾）。

**残留进程**：后端 8080（PID 18978）是 GZ-JP-104 起的，**本卡未重启未新起，保留运行**（下游 kevin-qa 与并行的 105 都要用）。本会话无常驻进程残留，临时文件在 `/tmp/gzjp203-*`。dev 库 fixture 已逐列还原，`gz_jp_cart_item` 已清空。

## 对下游 GZ-JP-204 的提示（最重要那段）

**1. 入参 = 一串购物车项 id**：`/pages/order/confirm?ids=39,40`（逗号分隔，已 encodeURIComponent）。常量在 `src/pages/cart/index.logic.ts`：`CHECKOUT_ROUTE = '/pages/order/confirm'` + `buildCheckoutRoute(ids)`，**要建的文件就是 `src/pages/order/confirm.vue`**（有单测锁着这个常量，改名要同步）。
- **id 是「购物车项 id」不是「商品 id」** —— 后端 `selectByUserAndIds(userId, ids)` 收的就是这组。
- **刻意不传金额/数量/商品信息**：URL 带金额是最经典的篡改面，且两页之间价格可能已变。

**2. 商品清单**：调 `fetchCart()`（`@/api/gz-jp/cart`）拉整车按 ids 过滤，**别新建端点**。拉回来后**必须重新检查 `invalid`**（客人停留期间店员可能刚关场）→ 按 `UI:mp.order_confirm` 退回购物车并提示具体哪件失效。

**3. 金额**：★ 只有「商品合计」与「实付」两行，**不得有第三行**（accept #2 grep 同款）。复用 `formatYuan()`（`@/api/gz-jp/format`，返回不带 ¥ 的纯数字串）+ `t('cart.totalIncluded')`=「已包邮」。**最终金额以后端重算为准**。

**4. 勾选态不会带过去**（后端不落库、URL 也不带）—— 确认页没有再改勾选的语义，要改回购物车改。

**5. 下单成功后购物车由后端清（105 的 `deleteItems`）**，客人返回购物车页 `onShow` 会自动变空车 —— **不用通知购物车页，也别去改它的状态**。

**6. ★ 别忘了「已阅读不支持退款」勾一次**（202 报告点名，`design-options/mp-product-detail.md` 方案 A 的配套举证手段），本卡没做，归 204。

**7. 组件**：`BizCartItem` 带 stepper + 删除，确认页是只读清单 —— 建议给它加 `readonly` prop（`v-if` 掉 `.biz-cart-item__ops`）或新写只读行；别把购物车行为改坏（self-test 守着）。

**8. E2E**：`run.mjs checkout` 抄 `flows/cart.mjs` 骨架 —— `loginIfNeeded(mp)` + `readAppToken(mp)`（本卡新增在 `mp-e2e.mjs`）拿**同一会话** token 直连后端当独立数据源；`run`/`runWith` 拆两个函数好让 self-test 零环境跑；**必须补 negative**（金额区出现第三行 / 未勾「已阅读」却能提交 / 提交后没拉起支付 / 后端说失效却照常提交）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1B 提示**：不依赖 devtools 的部分现在就能跑（`pnpm test` 212 / `node test/e2e/self-test.mjs` 46 / 后端 curl 契约回归）；模拟器 E2E 需先由 Kevin 扫码恢复 devtools 登录，恢复后跑 `node test/e2e/run.mjs all`（smoke+login+home+product+cart）。跑前确认 8080 后端活着且 `gz_jp_event`/`gz_jp_product` 有可下单 fixture。

---

**一句话结论**：accept #1 BLOCKED（devtools 登录，非代码问题）；accept #2 PASS；购物车页（按场分组/全选/失效标注/实时合计/去结算闸门）+ 商品详情真加购接入全部完成，212 单测 + 46 self-test（30 negative）+ 真库跨场/失效直验全绿，dev fixture 已逐列还原。
