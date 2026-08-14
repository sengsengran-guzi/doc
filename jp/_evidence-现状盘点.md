# 取证 1

**结论**：这个产品的工程质量很高（状态机、行级部分退款、跨客人发货保护、空态/降级/失效项处理都很扎实），Kevin 感觉「太简单」不是因为做得糙，而是每一页都只实现了骨架里最窄的一条路径：客人侧几乎没有「帮我找到想买的货」的能力（零搜索、零分类、零排序、无分享），甲方侧几乎没有「帮我少干活」的能力（无采购清单、无场维度统计、无复制商品、无导出）。盘点中查到一个阻断级 bug：首页「我的订单」的路由常量写成了不存在的 `/pages/order/index`（真实路由是 `/pages/order/list`），而「我的」tab 又漏了订单入口——**客人付款离开支付结果页后，全小程序无路可回订单列表**，一期最重的履约展示模块在产品上不可达。另有两处「文案承诺了但功能不存在」（待支付 tab 无继续支付按钮、退款失败让客人联系一个已被删除的客服），以及后台履约看板按商品行分页却按客人聚合，导致「一个客人 30 款」必然被切到两页、同一包裹会被填两次运单号。建议顺序：先花一天修 P0 四条（路由/订单详情补预计到货与发货时间/看板分页/清理空承诺文案），再投 3-5 天做 P1（场内搜索、现货vs预订标、场卡信息、后台复制商品与本场采购清单），订阅消息和分享放二期——这两项才是这门集单代购生意真正的留客与获客通道。

## 🔴 阻断级：小程序里「我的订单」根本进不去（路由常量写错 + 我的 tab 没有订单入口）
首页那张「我的订单 / 查看拼团进度与物流」卡片，点下去跳的是 `/pages/order/index` —— 这个页面不存在。真实路由是 `/pages/order/list`。navigateTo 失败后被 fail 回调吞成一个 toast「订单功能即将上线」，所以现象不是报错，是「点了没反应，还告诉你没做」。

同时「我的」tab 的九宫格只有【购物车】【关于】两格，GZ-JP-205 交付时应该补的 orders 入口没补（代码注释里还留着 TODO）。

结果：客人付完钱、离开支付结果页之后，**全小程序没有任何一条路径能回到订单列表**。订单详情页、按履约状态分组、运单号复制、部分退款展示 —— 这些一期做得最重的东西，客人看不到。Kevin 觉得「拼团太简单了」，很可能就是因为他自己点的时候也只看到首页 3 张卡 + 一个点不动的订单入口。

这一条必须最先修，其它所有优化都排在它后面（修法：改 index.logic.ts 的常量指向 '/pages/order/list'，并在 me/index.vue 的 gridItems 补 orders 格 + ROUTE_MAP）。

**证据**：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/index/index.logic.ts:189 `export const ORDER_LIST_ROUTE = '/pages/order/index'`；对照 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/api/gz-jp/order.ts:36 `export const ORDER_LIST_ROUTE = '/pages/order/list'`；/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages.json:90-96 只注册了 `pages/order/list`，无 `pages/order/index`；/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/index/index.vue:207-210 `fail: () => uni.showToast({ title: t('home.orderComingSoon') })`，文案见 locale/home.zh-CN.ts:51「订单功能即将上线」；/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/me/index.vue:48-52 gridItems 只有 cart/about，:45 注释「GZ-JP-205 落订单页后在此加 { key: 'orders' … }」未执行；pages/index/index.logic.test.ts 无该常量的断言，所以单测也没拦住

**含义**：一期最核心的客户价值（付款后逐款看货到哪了）在产品上处于不可达状态。这是「感觉太简单」的第一位原因，也是唯一一条改 2 行代码就能翻盘的。

---

## 逐页盘点表（小程序 13 页 + 后台 4 页）
**小程序**

| 页面 | 客人这一步想干什么 | 页面实际给了什么 | 缺什么 | 缺失的后果 |
|---|---|---|---|---|
| 首页 pages/index/index.vue | 这是什么生意？有什么可以买？我的单到哪了 | banner 占位块 + 场卡三组（进行中/即将开始/已结束）+「我的订单」入口 | 玩法说明位、购物车入口、场卡上的商品数/价格带、订单角标真值、订单入口是坏的 | 新客看不懂在卖什么；老客回不去订单 |
| 场详情 pages/event/index.vue | 在这一场里挑货 | 场头（封面/倒计时/场编号）+ 商品两列网格 + 上拉分页 + 「共 N 件」 | 搜索、分类、排序、价格筛选、「已加购」标记 | 几十上百款只能从头滚到尾 |
| 商品详情 pages/product/detail.vue | 决定买不买 | 图集轮播 + 名 + 大字价 + 包邮标 + 预计到货 + 购买须知 + 数量 + 加购 | 现货还是预订、退款规则、本场截止倒计时、同系列其它款、分享 | 决策信息不全；一张商品都传播不出去 |
| 购物车 pages/cart/index.vue | 把一批货结掉 | 按场分组 + 失效标 + 组级/全局全选 + 合计「已包邮」+ 去结算 | 页面本身没有常驻入口（只能从商品详情底栏或「我的」进） | 客人退回首页后找不到自己的车 |
| 确认订单 pages/order/confirm.vue | 填地址、付钱 | 地址选择/新增 + 清单 + 备注 + 两行金额 + 须知勾选 + 提交拉起支付 | 每件的预计到货、地址簿管理入口 | 付钱那一刻看不到「什么时候能到」 |
| 支付结果 pages/order/result.vue | 确认到底付上没有 | 三态（已付/未付/已关闭）+ 轮询 + 两个出口 | — | 这页做得对，不用动 |
| 订单列表 pages/order/list.vue | 找到那一单 | 四 tab + 缩略图 + 款数件数 + 实付 + 订单状态 | 继续支付、取消订单、按商品名/场搜索 | 「待支付」tab 是个死 tab（见下条） |
| 订单详情 pages/order/detail.vue | 我的货到哪了 | 按履约状态分组 + 组头运单号 + 复制 + 购买失败组退款说明 | 每组的时间戳、预计到货、整单进度总览、客服/催单出口 | 只知道「在哪一格」，不知道「进去多久了、还要多久」 |
| 我的 pages/me/index.vue | 找入口 | 头像两态 + 购物车 + 关于 + 退出登录 | 我的订单、收货地址、客服、常见问题、消息 | 会员中心几乎是空的 |
| 个人资料 pages/me/profile.vue | 改头像/昵称/手机号 | 齐 | — | — |
| 关于 pages/me/about.vue | 看版本和协议 | 版本 + 服务协议 + 隐私政策链接 | 品牌名写的是「谷子宇宙」🐰，不是「谷子宇宙拼团」 | 品牌不一致 |
| 协议 pages/agreement/index.vue | 看条款 | 占位正文 | 甲方正式文本、公司全称、ICP 号 | 提审风险（GO-LIVE-CHECKLIST 已列） |
| 登录 pages/login/index.vue | — | 脚手架遗留整页登录，实际不可达（真模型是游客优先 + BizLoginSheet） | — | 无害 |

**后台（plus-ui）**

| 页面 | 甲方这一步想干什么 | 给了什么 | 缺什么 | 后果 |
|---|---|---|---|---|
| 场管理 event/index.vue | 开一场/关一场 | CRUD + 开场/关场 + 封面 + 排序 | 商品数 / 订单数 / 成交额列 | 列表上看不出哪一场是有生意的 |
| 商品管理 product/index.vue | 一场几十款上架 | 单条新建/编辑（9 字段+主图+图集）+ 批量上下架 + 客人视角预览抽屉 | 复制商品、从其它场导入、批量新建 | 上一场 60 款＝重复填 60 遍表单 |
| 订单管理 order/index.vue | 查单、对账 | 只读列表 + 详情抽屉（含支付流水） | 导出 | 对账只能截图 |
| 履约看板 fulfill/index.vue | 推状态 / 发货 / 标失败退款 | 按客人聚合的可展开表 + 三个批量操作 + 跨客人保护 + 退款抽屉 + 重试 | 分页单位错（见下条）、本场采购清单、导出 | 一个客人会被切到两页 |

**证据**：页面清单来自 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages.json:18-111（13 页）与 :113-137（tabBar 仅首页/我的两格）；后台四页 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/plus-ui/src/views/gz-jp/{event,product,order,fulfill}/index.vue

**含义**：整条链路是通的、工程质量很高（空态/错误态/降级都做了），问题不在「有没有」，在「每一页只做了骨架里最窄的一条」——所以走完全程会觉得薄。

---

## 首页：新客从进入到下单要 6 跳 9 次点击，而首页没有一句话说明这是什么生意
路径：首页 →(点场卡) 场详情 →(点商品卡) 商品详情 →(加购，弹协议同意 sheet + 微信登录) →(点底栏购物车图标) 购物车 →(去结算) 确认订单 →(选/新增地址 + 勾选购买须知) →(提交) 微信支付 → 支付结果页。**没有「立即购买」**，单件也必须过购物车。

新客会在两个地方掉队：

① **首页第一屏就掉**。顶部 banner 无配置时降级成一块「🧧 谷子宇宙拼团 / 日本现场直邮 · 一单多款」的浅色渐变占位（Kevin 截图里看到的「大片空白」就是它）——除此之外整个首页**没有任何解释「场是什么、怎么玩、多久到货、没抢到怎么办」**。谷圈老客可能懂，第一次来的人不懂「拼团场次 · 进行中 3」是什么意思。

② **场卡信息不足以决定要不要点进去**。卡上只有：封面（无图时是 🎏 emoji）、场名、简介两行、时间行（截止 12/31 23:59）、右上状态标。**没有本场商品数、没有价格区间、没有热度**。后端 GzJpEventMpVO 压根没下发 productCount。三张卡长得一模一样时，客人只能盲点。

③ 首页**没有购物车入口**（tabbar 也只有 2 格）。加完货回首页的客人，得先随便进一个商品详情、或者去「我的」，才能找到车。

④ 首页场列表一次拉 20 条就到底、**没有加载更多**。场是永久累积的，跑几个月后早期场会被静默截断。

⑤ 订单入口的角标写死常量 0，永远不出现。

**证据**：跳数：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/index/index.vue:192-197 → pages/event/index.vue:201-203 → pages/product/detail.vue:180-203（加购）→ :206-208 goCart → pages/cart/index.vue:287-296 → pages/order/confirm.vue（地址+须知+提交）→ pages/order/result.vue；banner 占位块 components/biz/BizHomeBanner.vue:46-50「谷子宇宙拼团 / 日本现场直邮 · 一单多款」；场卡字段 components/biz/BizEventCard.vue:80-89（name/description/timingText/statusLabel 四项，封面兜底 :75-77 🎏）；后端无商品数 code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/domain/vo/GzJpEventMpVO.java:26-60（无 productCount）；首页一页到底 api/gz-jp/event.ts:97-108 + :86 `HOME_EVENT_PAGE_SIZE = 20`，pages/index/index.vue:137 `fetchEventList()` 无翻页；角标常量 pages/index/index.vue:123 `const pendingOrderCount = ref(0)`

**含义**：首页是唯一的启动落地页，现在它既不做转化（没有玩法说明、没有主推商品）也不做导航（没有购物车/订单可用入口）。改造成本最低的三件：加一条 3 行的玩法说明条、场卡加「N 款商品 · ¥xx 起」、tabbar 或首页右上加购物车。

---

## 找货：零搜索、零筛选、零排序 —— 一场上百款只能从头滚到底
场详情的商品区是纯两列网格，后端按 sort_no 排好，前端一行注释写着「一期不做筛选、不做排序」，蓝图 ui-index.yaml 也确认「无筛选无排序（一期极简）；场内商品量级预计几十到上百」。

每页 20 款、上拉触底加载 —— 100 款要触底 5 次，中途返回商品详情再回来位置能保住（数组累加），但**没有任何缩小范围的手段**：
- 没有关键词搜索（想找「柯南 吧唧」得靠眼睛扫）
- 没有 IP / 角色 / 品类分类（谷圈买家几乎都是按 IP 找货的）
- 没有价格排序、没有「预计到货时间」排序
- 商品卡上没有「已加购」标记，滚到第 80 款时不记得前面加过什么

这是这门生意最直接的体验瓶颈：甲方一场上几十上百款，客人一次买 30 款（甲方自己的原话），而找货这一段是零辅助的。

注意这不违反「一期不做」的约定——一期不做的是**多规格 SKU / Excel 导入 / 库存**，搜索和分类从来没被排除过。

**证据**：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/event/index.vue:17「**一期不做筛选、不做排序**（任务卡明确）：后端已按 sort_no 排好，前端不二次排序」；/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/authority/ui-index.yaml:62-64「form: 两列网格 / note: 无筛选无排序（一期极简）；场内商品量级预计几十到上百，上拉分页」；分页 api/gz-jp/product.ts:80 `EVENT_PRODUCT_PAGE_SIZE = 20`，触底 pages/event/index.vue:250-255；商品卡字段 components/biz/BizProductCard.vue 用法见 pages/event/index.vue:364-375（name/image/price/deliveryText/ended，无「已加购」）；甲方「一个客人比如买了 30 款商品」见 doc/jp/requirements.yaml:350

**含义**：建议按这个顺序补：① 场内关键词搜索（前端本地过滤已加载数据都比现在强，后端加个 name like 更好）② 商品加一个「标签/IP」自由文本字段 + 场内标签筛选条 ③ 排序（默认/价格/到货时间）。这三项不动数据模型，是投入产出比最高的一块。

---

## 商品详情：代购客人下单前必须知道的 12 项，页面上有 7 项、缺 5 项
**有的（7）**：主图+图集轮播、商品名、大字价格、「包邮」标 + 「国际邮费与国内运费已包含在价格内」、预计到货（商家没填时兜底「下单后 7 天内发出」，这是为微信发货时效合规写的）、购买须知（琥珀底、CTA 之上、不折叠、商家没填有兜底文案）、所属场次面包屑 + 商品编号。

**缺的（5）**：
1. **现货 / 预订没有区分**。甲方原话就说了两类货性质完全不同（「线下当场拿到的现货」vs「网上预订三个月后才发货的周边」），需求文档 REQ-EVENT-002 也承认这一点，但**商品表上根本没有这个字段**，页面自然显示不出来。客人无法判断这款是 1 周到还是 3 个月到——只能看「预计到货」那个自由文本，而那是商家手填的、可以为空。
2. **退款规则在商品页不出现**。「下单后不支持退款、代购失败原路退」这段话第一次出现是在**下单确认页**的勾选项里。客人是在商品详情页做购买决策的，最关键的风险条款在两页之后才告诉他。
3. **本场截止时间不显示**。倒计时只在场详情页有；从收藏/分享/搜索直接进商品详情的人不知道还剩多久。
4. **同系列/同 IP 其它款没有串联**。一期决定「不同规格各上架一个商品」，那么同一款吧唧的 A 赏/B 赏就是几条独立商品，页面上却没有任何「本场其它商品」「同系列」的入口 —— 客人挑完一款必须退回网格重新滚。
5. **不能分享**。全项目 grep 不到一处 onShareAppMessage / onShareTimeline。集单代购是靠微信群和朋友圈传播的生意，现在一款货都发不出去。

另外「正品/来源说明」「已有多少人订」这类信任信号一个都没有。

**证据**：有的 7 项：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/product/detail.vue:265-339（轮播/名+场/价+包邮/到货/须知）+ locale/product.zh-CN.ts:19 shippingFreeHint、:37 `deliveryUnset: '下单后 7 天内发出'`、:43 noticeFallback；缺项证据 —— 现货/预订：code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/domain/entity/GzJpProduct.java 全字段无 stock/type/现货标，需求 doc/jp/requirements.yaml:111-122 REQ-EVENT-002「现货应该没有『等待官方发货』这一步」status: clarify；退款规则 locale/order.zh-CN.ts:95 `agreeText: '我已阅读并同意《拼团购买须知》，知悉商品下单后不支持退款'` 只在 pages/order/confirm.vue 出现；分享：`grep -rn 'onShareAppMessage' src/` 仅命中 types/auto-import.d.ts:56 类型声明，无任何页面实现

**含义**：最该补的是 ①（现货/预订二选一的标）和 ⑤（分享）。①只要商品表加一个 stock_type 枚举 + 商品卡/详情加个标，就同时解决了「客人不知道多久到」和「履约状态要不要跳过等待官方发货」两个问题；⑤是这门生意的获客通道，现在完全关着。

---

## 订单/履约：六段状态客人看得懂，但「我的货到哪了」只答了一半 —— 没有时间、没有预计到货、没有推送
**做对的部分**：状态文案是人话（购买中/购买失败/等待官方发货/日本仓库已发货/清关中/国内分拣中/发货完毕），订单详情按状态分组而不是平铺，组头写「发货完毕 12 款」，运单号只在组头出现一次 + 复制按钮，购买失败组有一句得体的解释「这些商品没能抢到，货款按实付金额原路退回」。这个信息架构是对的，比很多真电商做得好。

**没答上的部分**：

1. **每一格都没有时间**。客人看到「清关中 12 款」，但不知道是昨天进的还是三周前进的。后端 VO 其实已经下发了 `shippedAt`，前端订单详情的行模型里**根本没取这个字段**。
2. **预计到货在付款后消失**。`deliveryDateText` 在商品详情有，下了单之后——购物车行、确认订单清单、订单列表卡、订单详情行——**四处全都不显示**，而后端 GzJpOrderItemVO 是下发了的。代购客人付完钱唯一想知道的就是「什么时候到」，我们在付款那一刻把这个信息拿走了。
3. **没有整单进度概览**。30 款分散在 5 个状态组里，要一路滚才知道大概什么情况。缺一条「已发货 12 / 在途 15 / 未抢到 3」的顶部摘要。
4. **购买失败 + 退款是纯被动告知**。全项目没有接订阅消息（GO-LIVE-CHECKLIST 已确认「一期全项目未接 → 不需要申请」）。客人不主动打开小程序、不主动点进那一单，就永远不知道有 2 款没抢到、钱退了。对一个「没抢到是常态」的生意，这是最要命的缺口。
5. **退款文案指向一个不存在的客服**。订单详情在退款失败时会显示「如有疑问请联系客服」，但拼团小程序的客服链路在 GZ-JP-001 就被整条删掉了，「我的」里也没有客服格。客人被告知去找客服，然后找不到。
6. **「待支付」tab 是个死 tab**。tab 存在、能筛出未付订单，但订单卡上**一个操作按钮都没有**——不能继续支付、不能取消。而 locale 里有三处文案在承诺「可在『我的订单』继续支付」。（缓解因素：未付订单 5 分钟自动关单，所以窗口本来就短——那更应该把这三句文案改掉，别承诺做不到的事。）

**证据**：分组与运单号：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/order/detail.vue:257-311，失败组文案 locale/order.zh-CN.ts:238；行模型缺字段 pages/order/detail.vue:96-149（DetailRow 只有 name/image/priceYuan/qty/refund*，无 shippedAt / deliveryDateText），而后端 code/main/RuoYi-Vue-Plus/.../domain/vo/GzJpOrderItemVO.java:47 `deliveryDateText`、:95 `shippedAt` 都已下发；`grep -n 'deliveryDateText' pages/order/*.vue components/biz/BizCartItem.vue` → 0 命中；无订阅消息：`grep -rn 'requestSubscribeMessage' src/` → 0 命中，doc/jp/GO-LIVE-CHECKLIST.md 桶2「订阅消息模板：一期全项目未接 → 不需要申请。要『到货通知』是新需求新 ticket」；客服 locale/order.zh-CN.ts:236 `refundContactSupport: '如有疑问请联系客服'` vs GO-LIVE-CHECKLIST「拼团 mp 的客服链路在 GZ-JP-001 被整条删除」+ pages/me/index.vue:48-52 无 contact 格；待支付 tab pages/order/list.logic.ts:48 vs pages/order/list.vue:274-317 卡片无任何按钮，承诺文案 locale/order.zh-CN.ts:119 / :132 / :143

**含义**：①②③ 是纯前端渲染，后端数据已经有了，半天工作量能让「我的货到哪了」这一页从 50 分到 85 分。④（订阅消息：发货/到货/退款三个模板）是二期最该做的一件事，也是这门生意留客的关键 —— 甲方跑一趟日本回来发一批货，推送一响客人才会再打开小程序。⑤⑥ 是文案与现实不符，属于必须清理的债。

---

## 「我的」页只有 2 格：一个电商小程序该有的会员中心，这门生意真正需要哪几格
现状：头像/昵称 + 【🛒购物车】【ℹ️关于】+ 退出登录。就这些。

按「集单代购」这门生意的实际需要排序：

**必须有（一期就该补）**
1. **我的订单**（含四个 tab 的直达：全部/待支付/进行中/已完成）—— 现在唯一入口是首页那张坏卡
2. **收货地址管理** —— 地址 API 已经写好了（api/gz-user-address.ts），但只能在下单时的弹层里管理。老客改地址得先假装下一单
3. **联系客服** —— 代购生意问题最多（这款还有吗、我的到哪了、为什么退款）。MeGrid 组件本身已经支持 `type: 'contact'` 走微信原生客服会话，只差一个 item + 甲方开通客服

**应该有（二期）**
4. **常见问题 / 拼团玩法说明** —— 一个静态页就能吃掉大量客服量：什么是场、多久到货、没抢到怎么办、能不能退、发几个包裹
5. **消息通知 / 到货提醒** —— 配合订阅消息
6. **我的收藏 / 想要清单** —— 谷圈用户典型行为是「先收藏再等发工资」，也是下一场开场时的召回抓手

**不需要**：优惠券、积分、会员等级、邀请有礼 —— 这门生意是熟客私域集单，不靠这些。

**证据**：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/pages/me/index.vue:48-52 `gridItems` = cart + about、:55-58 ROUTE_MAP；地址 API 已存在 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/api/gz-user-address.ts 但 pages.json:18-111 无 me/address 页；客服能力已封装 components/biz/MeGrid.vue:20-21 `type?: 'nav' | 'contact'` 与 :45-49 `<button open-type="contact">`，无任何调用方

**含义**：补 1-3 格是几小时的活（地址页要新写一个，订单/客服是接线）。4（玩法说明）虽然只是静态页，但对甲方的客服负担和新客转化的作用可能超过任何一个功能。

---

## 后台：一场几十款货怎么上架 —— 现在是「一款一个弹窗、填 9 个字段、传 1+9 张图」重复几十遍
商品管理只有单条新建：所属场（下拉）/ 名称 / 主图（必填，单张上传）/ 图集（最多 9 张，一张一传）/ 价格 / 预计到货文本 / 注意事项 / 排序号 / 备注。批量能力只有「批量上架 / 批量下架」。

一期明确不做 Excel 导入（蓝图 ui-index.yaml 写死），这个约定我不推翻。但**在不碰 Excel 的前提下**，有三个改造能把上架工作量砍掉一大半，而且都是纯 admin 前端 + 一个后端接口：

1. **「复制此商品」按钮**（列表行操作加一个）—— 谷圈同系列商品的注意事项、预计到货、价格档位高度重复，复制后改名换图即可。最省力，改动最小。
2. **「从其它场导入商品」**（场维度多选导入）—— 甲方每次快闪场的货有相当比例是复购款/常驻款。选源场 → 勾一批 → 导入到当前场（价格和到货时间可批量改）。
3. **上架弹窗支持「保存并继续新增」** —— 保留所属场/预计到货/注意事项，只清名称/图/价格。省掉几十次「关弹窗→点新增→再选场」。

另外注意事项（notice_text）几乎每款都一样，但现在每款都要重填一遍 —— 可以做成**场级默认注意事项**，商品不填时继承场的。

**证据**：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/plus-ui/src/views/gz-jp/product/index.vue:117-186 新增/编辑弹窗（9 字段 + 主图 + 图集逐张上传 :130-143）、:97-109 行操作只有 详情/编辑/删除、:44-67 批量条只有上下架；一期不做 Excel 见 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/authority/ui-index.yaml:165「一期不做 Excel 导入导出、不做富文本编辑器、无库存字段」

**含义**：这是甲方每开一场都要付出的固定成本，也是他最可能抱怨「这系统用起来慢」的地方。三项里先做「复制此商品」，一个下午的事。

---

## 🟠 后台：履约看板按「商品行」分页却按「客人」聚合 —— 一个客人会被切到两页，跨订单凑包裹在页边界断裂
看板的设计意图写得很清楚：主视图按客人聚合，因为打包决策的问法就是「这个客人有哪些货到齐了」，而且允许跨订单凑同一个包裹。跨客人勾选被前后端双重拦住（一个运单号 = 一个包裹 = 一个收件人）。这个设计是对的。

但**分页单位是商品行不是客人**：后端 `selectBoardPage` 分页的是 `GzJpFulfillBoardRow`（订单商品行），前端拿到当前页的 rows 之后才在浏览器里按 userId 断组。默认 pageSize = 20。

后果：
- 甲方自己举的例子就是「一个客人买了 30 款」—— 这一个客人就占满 1.5 页。他的货**必然**被切到两页，第 21 款起在第 2 页。
- 店员在第 1 页勾了 20 行发货、填了顺丰单号；第 2 页那 10 行是同一个包裹里的，得再发一次、再填一次单号 —— 客人订单详情里就会看到「发货完毕 20 款 / SF123」和「发货完毕 10 款 / SF456」两组，而实际只有一个包裹。
- 「待处理 M」这个组头统计只统计当前页的行，跨页的客人统计是错的。
- 20 行可能只覆盖 1 位客人，翻页翻不完。

修法两种：① 后端分页单位改成 user_id（先分页取一批客人，再取这批客人的全部行）—— 正解；② 临时缓解：默认 pageSize 提到 100，并加一个「只看有待处理货的客人」筛选。

**证据**：分页在行：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/service/impl/GzJpFulfillServiceImpl.java:555 `selectBoardPage(GzJpFulfillQueryBo, PageQuery)`、:581 `Page<GzJpFulfillBoardRow> page = itemMapper.selectBoardPage(...)`；前端分组只在当前页 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/plus-ui/src/views/gz-jp/fulfill/index.vue:641-668 `groups = computed(... for (const row of rows.value) ...)`，pageSize 默认 :605-615 `pageSize: 20`；设计意图见同文件 :580-595 注释「主视图【按客人聚合】…且同一客人可跨多张订单凑同一个包裹（REQ-FULFILL-006）」；甲方原话 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/requirements.yaml:350「一个客人比如买了 30 款商品 我们发货了 20 款」

**含义**：这是后台唯一一个会直接造成「客人看到两个运单号」这种可感知错误的问题，优先级仅次于首页那个路由 bug。

---

## 后台：甲方跑完一场需要的两样东西，系统一样都没给 —— 采购清单 和 场维度的成交概览
把甲方的一场从头走一遍：开场 → 上架几十款 → 客人下单付款 → **他要飞日本去买** → 回来推状态 → 发货 → 标失败退款。

第 4 步是整条链路的核心动作，而系统里**没有任何一个页面能告诉他这一场总共要买什么、各买几件**。现在他只能进履约看板，按场筛选，展开每一位客人，人肉把「A 款 ×2、B 款 ×1」加起来。一场几十个客人就是几百行。

缺的两张表：
1. **本场采购清单**（最重要）：按商品聚合 —— 商品名 / 图 / 需采购总件数 / 涉及客人数 / 已购中·已失败。这就是他去日本要带的那张纸。数据全在 gz_jp_order_item 里，一条 group by 的事。
2. **场维度成交概览**：场管理列表现在只有 场编号/名称/起止/状态/排序/备注 —— **连商品数都没有**（蓝图 ui-index.yaml 里明确写了列要含「商品数」，实现漏了，后端 GzJpEventAdminVO 也没这个字段）。应该加：商品数 / 下单人数 / 订单数 / 成交额 / 待采购款数。

另外**全域没有任何导出**（四个 admin 页 grep 不到 export/导出/Excel）。对账、给日本同事的采购单、给客人的发货明细，全靠截图。

**证据**：场管理列 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/plus-ui/src/views/gz-jp/event/index.vue:50-63（eventNo/name/startTime/endTime/status/sortNo/remark/操作，无商品数）；蓝图要求 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/authority/ui-index.yaml:155「列：场编号 / 名称 / 起止时间 / 状态 / **商品数** / 操作」；后端 VO 无该字段 code/main/RuoYi-Vue-Plus/.../domain/vo/GzJpEventAdminVO.java:28-74；无导出：`grep -rn 'export|导出|Excel|download' plus-ui/src/views/gz-jp/` → 0 命中；无聚合统计：`grep -rn '统计|summary' ruoyi-gz-jp/**/*.java` 无任何聚合查询接口

**含义**：「采购清单」是甲方每场都要用、现在完全靠人肉的东西，做出来他会立刻感到系统变「重」了 —— 这也是回答 Kevin「哪里太简单」的一个正面答案：一期只做了「记录」，没做「让甲方少干活」。

---

## 空状态 / 异常态：这一块做得完整，不用改（唯一例外是首页角标）
抽了一个统一的 BizState 组件，四个 variant（loading / error / empty + CTA），逐页覆盖：

- 首页：加载中「正在加载场次…」/ 失败「场次加载失败 + 检查网络后重试 + 重新加载」/ 空「🧧 拼团场次即将上线 / 开场后可在这里浏览商品并下单」
- 场详情：场取数失败「该场不存在或已下线 + 返回首页」；商品空「📦 本场还没有上架商品 / 店员正在整理货单，晚点再来看看」；商品失败可单独重试（场挂了不影响商品，反之亦然）
- 商品详情：「该商品已下架 + 回上一页看看其它商品」；图片加载失败逐张兜到 🧸 占位（预签名 URL 1h 过期这个坑处理了）
- 购物车：游客态「🔒 登录后查看购物车」（不做登录墙）/ 空车「🧺 + 去逛逛」/ 失败可重试 / 失效项有独立提示条 +「清空失效商品」
- 订单列表：游客态 / 空「📭 还没有订单 / 去逛逛正在拼的场次吧」/ 失败；翻页失败不擦掉已加载的
- 订单详情：「找不到这张订单 / 可能已被删除，或不属于当前账号 + 去我的订单」
- 无封面/无图一律走内置 emoji 占位块（🎏 场 / 🧸 商品），不会出 404 白框

唯一的洞：首页订单入口的角标是写死的 0，永远不渲染（0 被 formatBadgeCount 收敛成空串）。

**证据**：组件 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/components/biz/BizState.vue；逐页：pages/index/index.vue:230-257、pages/event/index.vue:262-350、pages/product/detail.vue:245-262、pages/cart/index.vue:329-374、pages/order/list.vue:218-264、pages/order/detail.vue:184-201；文案 locale/home.zh-CN.ts:20-27、locale/event.zh-CN.ts:41-56、locale/cart.zh-CN.ts、locale/order.zh-CN.ts:162-171；角标 pages/index/index.vue:123

**含义**：工程质量不是问题所在。Kevin 感觉「太简单」不是因为做得糙，是因为每一页的功能面太窄 —— 这一点值得在跟甲方沟通时说清楚，避免把优化说成返工。

---

## 内容 / 文案层：三处口径不一致 + 一处合规内容还是占位
1. **「场」这个词没有解释**。首页「拼团场次 / 进行中 3」、场详情「本场商品」「本场已结束」—— 全站建立在一个客人可能不认识的概念上，却没有一句定义。至少首页需要一条「什么是拼团场」的说明（或者干脆换个更直白的词，比如「本期集单」）。
2. **款 / 件混用**。场详情写「共 12 件」，但那个数字其实是商品款数（product total）；订单页的口径是「N 款 · M 件」（款=SKU 数，件=数量）。同一个客人在两页看到同一个概念被叫成两个名字。
3. **两套「须知」**。商品级 notice_text（商家逐款填，有兜底）和订单级《拼团购买须知》（4 条，硬编码在前端 locale 里）。客人在商品页看一段、在下单页勾另一段，内容不一致时无法解释。而且订单级那段是我方**代拟**的，甲方正式版本还没到位。
4. **品牌名不统一**：关于页写「谷子宇宙」+🐰，小程序叫「谷子宇宙拼团」；tabbar 图标是从谷子宇宙小程序原样复制的通用图标。
5. 服务协议 / 隐私政策正文仍是占位草稿（GO-LIVE-CHECKLIST 已列为提审阻塞项）。

**证据**：「共 N 件」/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/miniapp-jp/src/locale/event.zh-CN.ts:39-40 `productCountPrefix: '共' / productCountSuffix: '件'` 而 pages/event/index.vue:353-357 绑的是 `productTotal`（款数）；订单口径 locale/order.zh-CN.ts:176-178「共 N 款 · M 件」；订单级须知硬编码 locale/order.zh-CN.ts:99-107（注释自认「甲方正式版本到位后替换本段」）vs 商品级 locale/product.zh-CN.ts:41-43 + GzJpProduct.noticeText；品牌名 pages/me/about.vue:44-47；协议占位 doc/jp/GO-LIVE-CHECKLIST.md 桶2「隐私/法务素材（要甲方提供）：协议正文仍是草拟」

**含义**：2/4 是几行文案的事；1 是产品叙事问题，值得单独做一个「拼团怎么玩」的说明页/首页说明条；3 需要甲方给正式文本，建议顺便把「商品须知继承场级默认」也一起定下来。

---

## 改造优先级建议（按投入产出比排，不含二期）
**P0 — 必须修，否则一期的价值兑现不了（合计约 1 天）**
1. 首页订单路由常量指向 `/pages/order/list` + 「我的」补【我的订单】格 ← 不修等于订单模块白做
2. 订单详情行补 `预计到货` 和 `发货时间`（后端已下发，只是没渲染）
3. 履约看板 pageSize 20 → 100 + 加「只看有待处理的客人」（正解是分页单位改成客人，那个排 P1）
4. 清掉三处「可在我的订单继续支付」和一处「请联系客服」的空承诺文案（要么补按钮，要么改文案）

**P1 — 让产品「不再显得简单」（合计约 3-5 天）**
5. 场内商品搜索 + 排序（先做搜索）
6. 商品加「现货 / 预订」二选一标（表加一列，商品卡+详情+订单行都显示）
7. 场卡加「N 款 · ¥xx 起」；首页加一条「拼团怎么玩」说明条 + 购物车入口
8. 后台：商品「复制此商品」按钮 + 「保存并继续新增」
9. 后台：**本场采购清单**（按商品聚合的采购汇总表）← 对甲方感知最强的一项
10. 后台：场管理加 商品数/订单数/成交额 三列
11. 订单详情加整单进度摘要条（已发货 N / 在途 M / 未抢到 K）

**P2 — 二期（需要甲方配合申请/提供素材）**
12. **订阅消息**（发货 / 到货 / 退款三个模板）← 这门生意留客的关键，也是「我的货到哪了」的正解
13. **分享**（场分享卡片 + 商品分享）← 集单靠私域传播，现在完全关着
14. 客服入口（需甲方开通微信客服）+ 常见问题静态页
15. 收货地址管理页、收藏/想要清单
16. 后台导出（对账 / 采购单 / 发货明细）

**明确不建议做**：成团进度条、邀请返利、阶梯价、积分会员等级 —— 这是集单代购不是社交拼团，加了只会让客人误解玩法。

**证据**：优先级依据来自本轮盘点的各条 finding（P0-1 见 pages/index/index.logic.ts:189；P0-2 见 GzJpOrderItemVO.java:47/:95 已下发而 pages/order/detail.vue:96-149 未取；P0-3 见 fulfill/index.vue:605-615 + GzJpFulfillServiceImpl.java:555；P0-4 见 locale/order.zh-CN.ts:119/132/143/236；P1-5 见 pages/event/index.vue:17；P1-6 见 requirements.yaml:111-122；P1-9 见 plus-ui/src/views/gz-jp 无任何聚合查询；P2-12 见 GO-LIVE-CHECKLIST 桶2「订阅消息：一期全项目未接」）

**含义**：P0 四条加起来约一天，做完之后这个产品的完成度会从「看着像半成品」变成「能用」。真正能回答 Kevin「哪里有问题」的是 P1：一期把所有精力放在了「记录正确」（状态机、行级退款、跨客人保护、分页降级），但几乎没做「帮客人找货」和「帮甲方少干活」，所以走完全程会觉得薄。

---

