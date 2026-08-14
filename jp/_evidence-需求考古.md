# 取证 2

**结论**：拼团一期的工程质量很高（24 ticket 全绿、权威锚点齐、资金链路物理隔离），但产品建在一份从未被甲方签字的确认单上：甲方最后一次输入是 2026-08-05，此后 doc 仓 30 个 commit 全是我方自问自答，4 条待确认（含自标「越晚改代价越大」的多规格）一条都没回。Kevin 说的「太简单」有确切来源——这门生意是「集单→去日本买→逐款履约」，而系统只做了收单和打包发货两段，中间最值钱的采购那段完全没有系统承载：没有按商品聚合的进货清单、没有场维度经营数据、没有任何通知能力（甲方自己说过「增加粘性」）、甲方自述的唯一壁垒「能线下买」在产品里零表达。另有 5 处实现比 REQ 窄的静默缩水（预计到货与注意事项付款后即消失、首页角标硬编码 0、我的页没订单入口和客服、买 30 款每款要跳 3 次且看不到购物车），以及 2 处真实的资金合规风险（微信发货上报的 48h 兜底重试对拼团结构性失效；预计到货是可空自由文本撑不起微信预售豁免）。

## 甲方 8/05 之后零输入，整个一期建在未签字的确认单上
确认单状态机器可读地停在 pending，4 条待确认全部无答复。doc 仓 08-06 起 30 个 commit（GZ-JP-001 到 301 全部完工报告 + 上线清单）没有一条源自甲方。change-log 最后一行甲方记录是 2026-08-05「推翻运费改全包邮」，之后全是 Kevin / subagent 实测回流 / 干净 QA subagent。24 个 ticket、18 人日的产品形态，是在甲方三轮微信原话的快照上单方向推完的。

**证据**：/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/doc/jp/_manifest.json — confirmation_sheets.一期范围.status = "pending"，needs_human.route = "client"；doc/jp/change-log.md 最后一条甲方行 = 2026-08-05；git -C doc log --since=2026-08-05 共 30 条全为我方产出

**含义**：这是其它 finding 的根因。恢复动作不是再发一份确认单（上次就没回），而是拿能跑的产品做 10 分钟录屏走查让甲方挑毛病，并把多规格单独拎成唯一必答题。

---

## 多规格 REQ-PROD-007 是自标「越晚改代价越大」的那条，至今甲方未表态
我方在确认单里列为 ★ 最要紧、明写「这条如果要改，越晚改代价越大——订单的结构要跟着动」，请甲方优先回。甲方没回。Kevin 2026-08-06 单方拍板一期不做。现在 gz_jp_order_item 已建表、product_snapshot_json 已定型、下单/履约/行级退款全链路已落地，反悔就是 102+105 结构性返工。

**证据**：doc/jp/requirements.yaml REQ-PROD-007：status: deferred + note「★ 注意这是 Kevin 暂定、甲方未表态（甲方原话只有「上架具体商品」）…属结构性返工，需重新排期」；doc/16-日本代购需求确认单.md:11-20；doc/jp/GO-LIVE-CHECKLIST.md §4.5 #4

**含义**：谷子的吧唧/立牌天然是同一款多角色，一场几十上百款很可能第一场就撞上。下次接触甲方时当成唯一封闭式问题问：「同一款吧唧 A/B/C 三个角色，您想上架成 1 个商品还是 3 个商品？」不要再夹在 4 条里发。

---

## 甲方主动说要补的一句话被丢了（传递中丢失，第三类）
甲方原话「代切也是包邮的（但是代切还涉及到一个问题 我写到最后）」——他自己承诺后面会写，没写。我方在 doc/16 §一.4 回问「您还没写完」，然后归档二期、标 clarify、不阻塞一期。这是本次考古唯一确凿的「甲方想说的话在传递过程中丢掉」实例。虽属代切（二期），但它是甲方主动标记为「有问题」的点，很可能是代切能否做成的关键约束。

**证据**：doc/jp/requirements.yaml REQ-SNAP-009：status: clarify，clarify 字段原文「甲方原话「代切还涉及到一个问题 我写到最后」但未写完，需补充」；doc/16-日本代购需求确认单.md:34-38

**含义**：二期开工前必须追回，且用甲方自己的措辞去问（「您上次说代切还涉及到一个问题，是指什么？」），不要再给三个猜测选项让他选编号——确认单已经这么试过一次，没换来答复。

---

## 核心业务环节缺失：没有任何「采购清单 / 按商品聚合」的产出
这门生意的价值链是「集单 → 甲方去日本买 → 逐款履约」。系统做了收单和打包发货（按客人聚合的履约看板），中间的采购那一段完全没有系统承载。后端 gz-jp 模块 grep 不到任何 汇总/统计/导出/Excel；四个 admin 页（场/商品/订单/履约看板）没有一个能回答「这场我一共要买哪几款、每款几件」。甲方去日本前只能打开履约看板逐个客人展开手工加总。商品管理列表连一列「已订数量」都没有。

**证据**：grep -rn '汇总|采购|统计|export|Excel' ruoyi-gz-jp/src/main/java → 0 命中；/Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/plus-ui/src/views/gz-jp/product/index.vue:70-109 列 = 编号/主图/名称/所属场/价格/预计到货/状态/排序/操作，无已订数量；doc/jp/authority/ui-index.yaml:176-199 UI:admin.fulfill_board 是打包视角非采购视角

**含义**：这是 Kevin「说不上哪里有问题」的最大来源——系统看着功能齐全，但甲方真正要用它干的第一件事（拿着单子去日本买货）它帮不上忙。落地：admin 商品管理加「已订件数」列 + 场管理加「采购清单」页（商品/图/已订件数/下单人数/单价/预计金额，支持导出打印），数据源 = gz_jp_order_item GROUP BY product_id WHERE order.business_status='paid'。本轮性价比最高的一条。

---

## 通知能力为零，而甲方自己说过要「增加粘性」
履约周期数周到数月，期间 4 个关键时刻（新场开场 / 购买成功或失败 / 发货填单号 / 退款到账）客人都需要知道，但全项目 grep 不到 requestSubscribeMessage，一条都没接。客人唯一的知情方式是自己打开小程序刷订单详情。甲方在解释为什么要做代切时的原话就是「后续加的 增加粘性」——他本人对留存是有意识的。

**证据**：grep -rln 'requestSubscribeMessage|订阅消息' miniapp-jp/src miniapp/src ruoyi-modules → 0 业务命中；doc/jp/GO-LIVE-CHECKLIST.md 桶2「订阅消息模板：一期全项目未接（grep 不到 requestSubscribeMessage）→ 不需要申请。要「到货通知」是新需求新 ticket」；doc/jp/requirements.yaml REQ-SYS-003 甲方原话「增加粘性」

**含义**：快闪场是间歇性的，场与场之间客人没理由打开小程序；履约期又长到客人会忘记买过。建议二期第一优先接微信订阅消息：下单成功时一次性授权，覆盖「购买失败已退款」「已发货（带单号）」两个模板，「新场开场」做长期订阅。要甲方去微信后台申请模板，需提前启动。

---

## 场维度经营数据为零，甲方无法回答「这场做得怎么样」
admin 场管理列表只有 场编号/场名称/开场时间/闭场时间/状态/排序/备注/操作，连权威蓝图自己承诺的「商品数」列都没实现。没有任何地方显示一场的成交额、订单数、下单人数、哪款最好卖、失败率。甲方决定下一场进什么货、开多久、定什么价，拿不到任何自家数据。

**证据**：doc/jp/authority/ui-index.yaml:150-157 UI:admin.event 承诺「列：场编号 / 名称 / 起止时间 / 状态 / 商品数 / 操作」；实际 /Users/wkui/Project/profile/project/freelance/projects/sensenran-guzi/code/main/plus-ui/src/views/gz-jp/event/index.vue:50-64 无商品数列，多出 排序/备注；GzJpEventController 只有 list/getInfo/add/edit/open/close/remove，无统计端点

**含义**：落地：场管理列表补 商品数 / 已付订单数 / 成交额三列（一次 GROUP BY），点场名进「场看板」显示 Top 商品、失败率、客单价。注意拼团 GMV 目前刻意不进 4% 分成（recon 只算 preorder+gacha），做统计页要显式标注它是经营数据不是分成口径。

---

## 「一次选几十款」的动线与甲方原话直接冲突：每款 3 跳且看不到购物车
甲方场景原话是「一个客人比如买了 30 款商品」，REQ-ORDER-005 就是从这句推导的。实际动线是：场详情两列网格 → 点进商品详情 → 加购 → 返回 → 点下一个。商品卡不能直接加购；场详情页零处 cart（grep 计数 0），无悬浮购物车、无件数角标；tabbar 只有 首页/我的 两格，购物车没有常驻位。购物车角标只在商品详情页底部才看得见。买 30 款 = 90 次跳转，全程不知道已选多少件多少钱。

**证据**：code/main/miniapp-jp/src/pages/event/index.vue grep -c cart → 0；code/main/miniapp-jp/src/components/biz/BizProductCard.vue Props 无任何加购相关（仅 name/image/price/deliveryText/ended）；code/main/miniapp-jp/src/pages.json tabBar.list 仅 2 项；code/main/miniapp-jp/src/pages/cart/index.vue:4-6「入口两处：商品详情底部 CTA 条左侧的购物车图标 /「我的」页入口格」

**含义**：UI 权威索引没写错，是拆 ticket 按页拆导致的跨页动线塌陷。落地：① 商品卡右下角加「+」直接加购；② 场详情页加悬浮购物车球（件数+合计）；③ tabbar 加第三格「购物车」。三条都不动后端契约。

---

## 实现比 REQ 窄①：预计到货时间付完钱就消失
REQ-PROD-004「货物需要有日期」。deliveryDateText 只渲染在商品卡和商品详情。购物车、下单确认、订单详情一处都不显示——而后端 GzJpOrderItemVO 明明带了该字段、快照 JpOrderSnapshot 也存了。数据取到前端却没用。客人付完钱后再也无法在订单里看到「这款预计什么时候到」。

**证据**：grep -n 'deliveryDateText|delivery' pages/order/detail.vue pages/order/confirm.vue pages/cart/index.vue → 0 命中；ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/domain/vo/GzJpOrderItemVO.java:46-47 已含 private String deliveryDateText

**含义**：3 个月履约期里「什么时候到」是客服最高频问题，系统里有答案却不给客人看。改动极小：订单详情商品行加一行灰字预计到货；下单确认页同样该显示（最后一次风险告知机会）。

---

## 实现比 REQ 窄②：注意事项只在商品详情出现一次
REQ-PROD-005 是甲方明确点名的字段，权威索引自己写「★ 甲方明确要求的额外注意事项…这是下单前的风险告知位」。但 noticeText 全项目只在 pages/product/detail.vue:337 渲染一处。购物车、下单确认、订单详情零渲染，即使快照存了、VO 也带了。客人一次结算 30 款时，30 条注意事项一条都不复述。

**证据**：grep -rn noticeText pages/ → 仅 product/detail.vue:117-118,337 + 测试夹具；doc/jp/authority/ui-index.yaml:75-79 UI:mp.product_detail.notice「必须在 CTA 之上、默认展开不折叠…这是下单前的风险告知位」；ruoyi-gz-jp/.../domain/dto/JpOrderSnapshot.java:67 已存 noticeText

**含义**：「日本线下采购，包装可能有磨损，介意慎拍」恰是纠纷时唯一的挡箭牌，却只出现在客人最不注意的位置（浏览时），缺席在最该出现的位置（付款前 + 事后回看）。建议下单确认页折叠成一条「N 款商品有购买须知，展开查看」，订单详情行内保留可展开须知。

---

## 实现比 REQ 窄③：首页订单角标是硬编码常量 0
UI:mp.home.order_entry 承诺「我的订单入口 + 待收货款数角标」。实际代码 const pendingOrderCount = ref(0)，注释自陈是占位、待 GZ-JP-205 替换成订单统计接口——GZ-JP-205 已完工，这里没改。0 被 formatBadgeCount 收敛成空串，角标永远不渲染，看起来像「设计上就没有角标」而不是「漏了」。

**证据**：code/main/miniapp-jp/src/pages/index/index.vue:117-124 —— 注释「⚠️ 本卡是占位常量 0 …GZ-JP-205 实施时把这里换成订单统计接口的返回值即可」，紧接 const pendingOrderCount = ref(0)

**含义**：典型的跨 ticket 交接项无人认领，本项目还有同构一处（我的页订单入口）。建议 closing 时对 miniapp-jp 全仓 grep「实施时 / 待 GZ-JP- / 占位常量」，把跨卡待办一次性收口。

---

## 实现比 REQ 窄④：「我的」页既没有订单入口也没有客服入口
me/index.vue 的入口格只有 购物车 和 关于 两项。文件里写着「GZ-JP-205 落订单页后在此加 { key: 'orders' … } 并在 ROUTE_MAP 补 orders 路由」——205 已完工，没加。结果整个小程序进订单只有首页那一个入口。客服同理：MeGrid 组件支持 type='contact'（原生微信客服会话）但没有任何 item 用它。

**证据**：code/main/miniapp-jp/src/pages/me/index.vue:44-53 —— 注释指明要加 orders，gridItems 实际只有 cart + about；code/main/miniapp-jp/src/components/biz/MeGrid.vue:20-21,45-49 支持 contact 但无消费方

**含义**：一个需要客人在数月里反复回来查进度的产品，「我的」页没有订单入口，这条最直观地解释了「太简单」的观感。客服缺席更严重：代购天然高纠纷（没抢到/到货晚/包装磨损），客人在小程序里找不到任何人。客服要先跟甲方定形态（微信客服会话 vs 留电话 vs 引导加微信）。

---

## 收货地址在数月履约期里被冻结且双方都改不了
下单时 address_snapshot_json 锁定（设计正确）。但 mp 没有独立地址管理页（pages/me 下只有 index/about/profile），地址只能在下单确认页新增和选择，没有编辑没有删除；admin 订单管理是只读抽屉，店员也改不了收货地址。客人在 3 个月履约期里搬家或填错门牌，唯一出路是改库。

**证据**：find miniapp-jp/src/pages/me → index.vue / about.vue / profile.vue，无 address 页；code/main/miniapp-jp/src/api/gz-user-address.ts 只导出 fetchAddressList / saveAddress / setDefaultAddress（无删除无更新）；doc/jp/authority/ui-index.yaml:168-174 UI:admin.order「只读查询列表 + 详情抽屉」

**含义**：拼豆是当天到店核销，地址不是问题；拼团是数月后寄实物，地址是核心。落地：① mp 我的页加「收货地址」管理页（增删改）；② admin 订单详情在未发货状态下允许改收货地址并写审计日志。第 ② 条尤其重要，客人一定会打电话来改。

---

## 微信发货上报的 48h 兜底重试对拼团结构性失效（资金结算风险）
拼团发货上报挂在店员点发货那一刻（正确，支付时没有可上报的发货事实），但那是支付后数周到数月。而 gz-common 的兜底重试写死 WINDOW_HOURS=47、windowStart=now.minusHours(47)——jp 的上报任务创建时就已远超窗口，retryPending 永远扫不到它。于是拼团只剩「即时 @Async 一次」，失败即永久卡，与拼豆当年 74 单全卡待发货的失败模式完全同构。只有人工 backfillPending（不受窗口约束）能救。

**证据**：ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/service/impl/GzPayShippingServiceImpl.java:53-54「上报窗口（小时）：微信要求支付后 48h 内发货，留 1h 余量，超窗不再重试」private static final int WINDOW_HOURS = 47;，:437 LocalDateTime windowStart = LocalDateTime.now().minusHours(WINDOW_HOURS);；jp 上报入口 ruoyi-gz-jp/.../service/impl/GzJpFulfillServiceImpl.java:338 ShippingInfo.physicalPackage(...)

**含义**：好消息是 plus-ui 已有 views/gz-pay/shipping/index.vue + /retry-all 人工补报页，不是死局。要么把窗口按 business_type 放宽（jp 不设窗口），要么明确写进运维 SOP：拼团每次批量发货后去发货管理页确认全部 success。不修则失败会静默累积，等甲方收到微信警告才发现。

---

## 预计到货是可空自由文本，撑不起微信预售的 48h 豁免
我方查证结论：普通商品 48h、预售商品按商家承诺周期上限 330 天，且以商品详情页展示的最短时效为准，所以拼团发货那一刻才上报是对的。但这个豁免的前提是详情页真的展示了一个周期——而 delivery_date_text 在 field-ssot 里 nullable、在 GzJpProductBo 里只有 @Size(max=64) 没有 @NotBlank、admin 表单非必填，甲方不填时兜底文案是「待定（以店内通知为准）」，不构成承诺时效。

**证据**：doc/jp/tickets/GZ-JP-301/report.md:225-233「商品页的预计到货 deliveryDateText 商家不填时兜底是「待定（以店内通知为准）」，那不构成承诺时效 → 可能被按 48h 判。需做成 admin 必填、或换成明确周期（数得甲方给）」；doc/jp/authority/field-ssot.yaml:68 delivery_date_text nullable: true；GzJpProductBo.java:66-68 仅 @Size

**含义**：改动很小（admin 商品表单设为必填 + 预设 chip 如「1 个月内 / 2 个月内 / 3 个月内」），但要先跟甲方对口径：他习惯写「8月下旬」这类模糊表述，微信要的是可判定周期。建议拆成两个字段：面向客人展示的自由文本 + 面向微信承诺的结构化天数。

---

## 甲方自述的唯一竞争壁垒「能线下买」在产品里零表达
甲方原话：「代切为主的那几家公司也在做拼团…他们拼团只能代买官网上发售的东西 等于是代拍日本官网的货 我拼团是可以线下买 本质上压制 线下买的是主要需求 网上买的 哪家都可以」。这条被归档为「产品定位约束，非独立功能」，落到 GZ-JP-102（一张商品表）。结果小程序里没有任何地方告诉客人这些货是我们的人在日本线下现场抢的——没有现货标识、没有采购现场图、没有对应文案位，只有 locale 里两句兜底话和登录页副标题。

**证据**：doc/jp/requirements.yaml REQ-PROD-006 全文 + note「产品定位约束，非独立功能…对系统的影响 = 商品无需绑定任何外部货源系统，纯人工上架」；grep -rn '线下|现场' miniapp-jp/src/locale/*.ts 仅 auth.zh-CN.ts:13 / product.zh-CN.ts:43 / order.zh-CN.ts:103 三处兜底文案；商品表无现货/线下采购标识字段

**含义**：甲方花钱做这个系统，本质是想把「我能线下买」变现。系统把它翻译成了「所以不用接外部货源 API」——技术判断对，商业价值全丢。落地：① 商品加「现货 / 官网预订」标识（正好复用 REQ-EVENT-002 已做的「现货可跳过等待官方发货」状态链差异，字段几乎白送）；② 场详情/商品详情给「日本现场直击」图位；③ 现货商品显示更短的履约路径本身就是最好的证据。

---

## 新小程序的品牌视觉从没被问过甲方，结果与谷子宇宙完全同皮
REQ-SYS-001 原文是「新小程序叫什么、要不要独立的品牌视觉 —— 谷子宇宙拼团」，甲方只回答了名字，后半句从未被回答；doc/16 确认单的 4 个问题里也没有这一条，即从未再问过。note 直接写「甲方未要求独立视觉」，把沉默当成同意。附带一处 doc 与代码脱节：权威锚 UI:global.theme 写「主色 #c8452f 朱红」，实际 c-tokens.scss 是 #33b36b 绿（从 miniapp 复制时它早已换过皮）。

**证据**：doc/jp/requirements.yaml REQ-SYS-001 text + note「视觉一期沿用现有清爽风 c-tokens，甲方未要求独立视觉」；doc/16-日本代购需求确认单.md §一 四问中无视觉项；doc/jp/authority/ui-index.yaml:14-26「主色 #c8452f 朱红 · 底 #f5f3ef 米白」 vs code/main/miniapp-jp/src/style/c-tokens.scss:29 --c-red: #33b36b;「品牌主色＝清新绿」

**含义**：这是「太简单」的直接观感来源之一：打开新小程序，它看起来就是谷子宇宙少了几个功能，而不是一个新生意。日本代购/快闪场有明确气质（限时、稀缺、日系）。建议把「要不要独立视觉」重新问一次，带两张对比图而不是文字。同时把 UI:global.theme 的色值改成与 c-tokens.scss 一致，否则下一个 agent 会照着朱红写组件。

---

## 我方判断砍掉的 4 项从没被甲方确认过一个字
「这一期不做的」表里 7 项：代切 / 运费 / 店里当面下单 是甲方主动砍的（有原话，清晰）；库存数量 / 商品多规格 / Excel 批量导入 / 状态推错回退 这 4 项是我方判断砍的，理由分别是「您从没提过库存」「等您确认」「先手工录」「推错了我帮您改」。这 4 条全部写在确认单里请甲方过目，甲方一条都没回。

**证据**：doc/16-日本代购需求确认单.md:79-90「四、这一期不做的」表；doc/jp/GO-LIVE-CHECKLIST.md §4.5 #7「无库存 = 无超卖保护。「卖完」靠店员手动下架，有人工滞后窗口。需求侧刻意选择」

**含义**：风险排序：① 库存最危险——线下现场抢货天然有量上限（甲方说的「线下买」正意味着数量有限），客人下单甲方买不到就得退款，退款多了口碑就没了，而系统连「限量 N 件」都不支持；② Excel 导入次之，一场几十上百款手工录第一场就会疼；③ 状态回退第三，「推错了我帮您改」意味着每次误操作都要 Kevin 改库。建议至少把限量当封闭式问题问甲方：「有些货现场只能抢到有限的量，要不要设个上限，卖完自动下架？」

---

