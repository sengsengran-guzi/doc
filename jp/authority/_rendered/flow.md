# 业务流权威图

> 本文件由 `authority_lint.py render` 从 `doc/authority/*.yaml` 自动生成。**别手改**——改权威改 YAML，手改这里下次 render 就被覆盖。

## 多小程序（多 appid）底座

**锚 id**：`FLOW:F-JP-00`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SYS-004, REQ-SYS-005, REQ-SYS-001

新小程序有独立 appid，而现有后端把微信 appid 建模成单值标量、real/mock 用启动期条件 Bean
全局互斥，**不改造则新小程序无法登录、更无法调起支付**。这是一期唯一硬阻塞，须先于业务开发完成。
改造后按 clientid 路由到对应 appid 配置；gz_user 加 app_id 维度隔离两小程序的用户。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-00.step1` | 系统 | 小程序请求带 clientid header（新小程序 = mp-applet-gz-jp） |  | clientid 校验是纯字符串比对不查 sys_client 表（SecurityConfig:66-74），新客户端零成本
 |
| `FLOW:F-JP-00.step2` | 后端 | 按 clientid 解析出该小程序的 appid / secret / real-or-mock 模式 | FIELD:gz_user.app_id | wx.miniapp 配置由标量改 Map<clientid, app>；8 处启动期条件 Bean 的 real/mock 全局互斥 改为运行时按 app 分派。★ 这 8 处是**两种注解**：real 侧 4 处 @ConditionalOnExpression （SpEL 表达式 "'${wx.miniapp.appid:wxMOCK}' != 'wxMOCK'"），mock 侧 4 处 @ConditionalOnProperty（havingValue=wxMOCK, matchIfMissing=true）—— @ConditionalOnProperty 不支持 NOT 语义所以 real 侧才用 SpEL。 对应 Login / Phone / AccessToken / Shipping 四种能力各一对。
 |
| `FLOW:F-JP-00.step3` | 后端 | 微信登录 —— 按 app_id + openid upsert 用户 | FIELD:gz_user.app_id, FIELD:gz_user.openid | 唯一键 (tenant_id, app_id, openid)。同一自然人在两个小程序 = 两条独立记录， 互不干扰（不做 unionid 合并，列为后续增强）
 |
| `FLOW:F-JP-00.step4` | 后端 | 调起支付 —— 用当前小程序的 appid 做统一下单与 5 参签名 |  | ★ WechatPayV3ClientImpl:125 的签名 appid 必须来自下单上下文。 写死则新小程序 uni.requestPayment 必失败。落点：激活 gz_pay_channel.appid 列做真源 （该列已存在但 seed 值是 'wx_placeholder_appid'，建了从未被读过）。 ★ **支付另有一套独立开关 gz.pay.client-mode（mock/real），与 wx.miniapp.appid 无关**， 它是**进程级全局**、不是 per-app：同一环境下两个小程序 mock/real 状态必然相同 （dev 全 mock、prod 全 real），一期无需 Map 化。仅当将来要「一个小程序 mock 收款、 另一个 real 收款」时才需拆开——那时才动它。
 |

## 开场与上架

**锚 id**：`FLOW:F-JP-01`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-EVENT-001, REQ-PROD-001, REQ-PROD-003, REQ-PROD-004, REQ-PROD-005

店员在 admin 建一个「场」（一次快闪活动，带起止时间）→ 在场内上架具体商品
（名称/图/价/预计到货/注意事项）→ 开场 → 客人可见可下单 → 到期或手动关场后不可再下单。
商品无库存概念（集单预订本质不限量），无多规格（不同规格各上架一个商品）。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-01.step1` | 店员(admin) | 新建场，填名称/封面/起止时间 | FIELD:gz_jp_event.name, FIELD:gz_jp_event.start_time, FIELD:gz_jp_event.end_time | 场 status=draft，客人不可见 |
| `FLOW:F-JP-01.step2` | 店员(admin) | 在场内逐个上架商品 | FIELD:gz_jp_product.event_id, FIELD:gz_jp_product.price_cent, FIELD:gz_jp_product.notice_text, FIELD:gz_jp_product.delivery_date_text | 商品 status=on_shelf；未开场时仍不可见 |
| `FLOW:F-JP-01.step3` | 店员(admin) | 开场 | FIELD:gz_jp_event.status | 场 status=open，小程序首页可见，场内 on_shelf 商品可下单 |
| `FLOW:F-JP-01.step4` | 系统 / 店员(admin) | 到 end_time 后视为已结束；店员亦可手动关场 | FIELD:gz_jp_event.status | 场 closed，不可再下单。★ 判定走「读时惰性」——查询时比对 end_time 实时判定， 并允许店员手动置 closed。不依赖 cron（SnailJob 在 prod 未部署，cron 全哑）。
 |

## 客人下单与支付

**锚 id**：`FLOW:F-JP-02`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-ORDER-003, REQ-ORDER-004, REQ-ORDER-005, REQ-ORDER-006, REQ-ORDER-010

客人在小程序浏览进行中的场 → 进场挑商品 → 加入购物车（一次可选几十款）→
去结算 → 选收货地址 → 提交订单（全款、包邮、无运费行）→ 微信支付 →
支付回调后订单转 paid，所有商品行进入「购买中」。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-02.step1` | 客人(mp) | 首页浏览场列表，进场看商品，看商品详情（含注意事项） |  | 无写入 |
| `FLOW:F-JP-02.step2` | 客人(mp) | 加入购物车 / 改数量 / 删除 | FIELD:gz_jp_cart_item.qty | 购物车项。跨场可共存于同一购物车 |
| `FLOW:F-JP-02.step3` | 客人(mp) | 结算 —— 选地址、填备注、确认合计 |  | 合计 = Σ(单价 × 数量)，**无运费行**（全包邮）。 下单前校验：场仍 open、商品仍 on_shelf、价格与购物车快照一致
 |
| `FLOW:F-JP-02.step4` | 系统 | 提交订单 —— 生成订单 + 逐行商品快照 + 调 GZ-PAY 统一建单 | FIELD:gz_jp_order.order_no, FIELD:gz_jp_order.business_status, FIELD:gz_jp_order_item.product_snapshot_json, FIELD:gz_jp_order_item.source | 订单 business_status=created；金额后端重算不信前端； order_item.source='batch'（为二期代切 snap 预留维度，见 REQ-SNAP-004）
 |
| `FLOW:F-JP-02.step5` | 客人(mp) | 微信支付 |  | 复用现有 GZ-PAY 通道，business_type='jp' |
| `FLOW:F-JP-02.step6` | 系统 | 支付回调 —— 订单转 paid，全部商品行进入履约起点 | FIELD:gz_jp_order.business_status, FIELD:gz_jp_order.paid_time, FIELD:gz_jp_order_item.fulfill_status | 订单 paid；每个 order_item fulfill_status=purchasing（购买中） |

## 履约推进与发货

**锚 id**：`FLOW:F-JP-03`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-FULFILL-001, REQ-FULFILL-002, REQ-FULFILL-003, REQ-FULFILL-004, REQ-FULFILL-006, REQ-FULFILL-007, REQ-EVENT-002

店员在 admin 履约看板按客人/状态/场筛出商品行，**勾选一批 → 一次性推进状态**。
推到最后一步「发货完毕」时必须填一个顺丰单号，这批行一起显示该单号。
状态挂在商品行上（不是订单上），一单内各款进度可不同。允许跳过中间态（现货无「等待官方发货」）。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-03.step1` | 店员(admin) | 履约看板按客人/状态/场筛选商品行 |  | ★ 按客人聚合是主视图 —— 打包决策是「这个客人有哪些货到齐了」， 可跨订单（REQ-FULFILL-006）
 |
| `FLOW:F-JP-03.step2` | 店员(admin) | 勾选一批商品行 → 批量推进到下一状态 | FIELD:gz_jp_order_item.fulfill_status | 状态链：购买中 → 等待官方发货 → 日本仓库已发货 → 清关中 → 国内分拣中 → 发货完毕。 **允许跳过中间态**（线下现货直接跳到日本仓库已发货）。不可回退（一期不做回退）
 |
| `FLOW:F-JP-03.step3` | 店员(admin) | 勾选已到齐的一批 → 填一个顺丰单号 → 一起置为发货完毕 | FIELD:gz_jp_order_item.fulfill_status, FIELD:gz_jp_order_item.carrier_code, FIELD:gz_jp_order_item.tracking_no, FIELD:gz_jp_order_item.shipped_at | ★ **不建包裹表** —— tracking_no 本身就是包裹标识，按它天然聚合。 单号由员工手工填，不接快递 API；客人自行复制到顺丰查询
 |
| `FLOW:F-JP-03.step4` | 客人(mp) | 在订单详情看每款商品各自的状态与单号 |  | 客人只看到自己每款货走到哪 + 单号；**不展示包裹概念**（REQ-FULFILL-006）
 |

## 购买失败与行级退款

**锚 id**：`FLOW:F-JP-04`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-FULFILL-005

店员把没买到的商品行标为「购买失败」→ 系统按该行金额向微信发起**部分退款** →
退款回调后该行转已退款；订单在有失败行时转「部分退款」，全部行失败则转「已退款」。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-04.step1` | 店员(admin) | 勾选没买到的商品行 → 标记购买失败（可批量） | FIELD:gz_jp_order_item.fulfill_status | 该行 fulfill_status=purchase_failed（分支终态，不再往下走） |
| `FLOW:F-JP-04.step2` | 系统 | 按行金额发起微信部分退款 | FIELD:gz_jp_order_item.refund_status, FIELD:gz_jp_order_item.refund_amount_cent | ★ 退款金额 = 该 order_item 的 amount_cent，不是整单。 ⚠️ **现有 GZ-PAY 退款链路只支持「一单一次全额」，不支持部分退款**（D0 实测，2026-08-06）： `RefundApplyBo` 无金额入参（javadoc「仅全额退款」）、`PayRefundServiceImpl.apply` 两个金额位 都传全额、`PayRefundTxService.createRefunding` 的 countActiveByTransactionId>0 即拒 （一笔支付只允许一条退款单）、`gz_pay_transaction` 的 refunded 是终态。 **通道层 `IWechatPayClient.refund` 本身支持**（record 已含 refundAmountCent + totalAmountCent）。 ⇒ 行级退款 = **支付域实质改造**，不是复用现成接口。且拼豆/回收共用同一条链路， 放宽重复退款闸门须同步补金额校验（已退总额+本次 ≤ 原单总额）并回归既有业务。 **路线已定（Kevin 2026-08-06）：jp 域开独立退款入口，只共用通道层** ——  新建 jp 专用退款 Service + 退款单表，直接调 `IWechatPayClient.refund`（它本就支持指定金额）。 **拼豆/回收的资金链路一行不动**，风险物理隔离。代价：退款逻辑两套、对账中心要兼容两个来源。
 |
| `FLOW:F-JP-04.step3` | 系统 | 退款回调 —— 该行转已退款，订单状态按剩余行重算 | FIELD:gz_jp_order_item.refund_status, FIELD:gz_jp_order.business_status | 有失败行且非全部 → 订单 partial_refunded；全部行失败 → 订单 refunded。 退款回调仍走 GZ-PAY 的 RefundCallbackDispatcher SPI（business_type='jp' 的 handler）， 但因 jp 退款单落在独立的 gz_jp_refund 表（不是 gz_pay_refund），通知地址必须是 独立端点 /api/gz/jp/pay/refund-notify（不能复用 PayRefundController 共享的回调路径， 那条按 out_refund_no 去 gz_pay_refund 查单会 404）。GZ-JP-107 已实现。
 |

## 代切找货（搜索 / 贴链接 / 详情）

**锚 id**：`FLOW:F-JP-05`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SNAP-002, REQ-SNAP-003, REQ-SNAP-005, REQ-SNAP-012, REQ-SNAP-013, REQ-SNAP-014, REQ-SNAP-015, REQ-SNAP-016, REQ-SNAP-017, REQ-SNAP-018, REQ-SNAP-019, REQ-SNAP-040, REQ-SNAP-022, REQ-SNAP-023, REQ-SNAP-024

客人在小程序输入中文 / 日文关键词或粘贴煤炉链接 → ruoyi 归一化（链接→商品 ID；中文→词表→机器翻译→日文）→
ruoyi 同步调日本服务实时搜索 → 过分类白名单 + 关键词黑名单 → 标题机翻中文 → 结果网格。
点进详情：ruoyi 实时查一次单件（不走缓存）→ 落 gz_jp_snap_item → 准入判定 → 出报价。
★ 实时透传查询，不建全量索引、不批量爬（REQ-SNAP-017）。日本服务挂了 → 搜索给最近缓存或提示「煤炉暂时访问不了」，拼团不受影响。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-05.step1` | 客人(mp) | 在代切搜索页输入关键词，或粘贴煤炉商品链接 / 商品 ID |  | 识别 `jp.mercari.com/item/m\d+` 与裸 `m\d+` → 直接进详情（step5）；其余按关键词搜（step2）
 |
| `FLOW:F-JP-05.step2` | ruoyi | 关键词归一化 —— 中文先按词表最长匹配替换成日文，未覆盖部分走阿里云机器翻译；纯日文原样 |  | 日文查询串。词表读 gz_jp_snap_term（enabled=1，按 sort_no）；翻译结果 Redis 缓存 7 天； 翻译接口失败 → 降级原词直搜，不阻断（REQ-SNAP-014/015）
 |
| `FLOW:F-JP-05.step3` | ruoyi → 日本服务 | 实时搜索（只查在售），结果 Redis 缓存 3 分钟，同查询串在途请求合并为一次 |  | GET /v1/search（HMAC 签名，超时 3s 熔断）→ items[]：external_id / title_ja / price_jpy / thumb / category_id / status。 日本服务侧：网页版 JSON 接口为主，失效自动降级无头浏览器解析（ADR-0025 §3）
 |
| `FLOW:F-JP-05.step4` | ruoyi | 过滤 + 翻译 + 出图 |  | ① category_id 不在白名单 → 丢弃 ② 标题命中关键词黑名单 → 丢弃 ③ 首屏标题批量机翻中文（按 external_id+标题 hash 缓存） ④ 图片 URL 改写为 CDN（甲方备案域名）地址，CDN 回源日本服务 /v1/img 图片代理。 ★ 过滤在 ruoyi 做、不信任日本服务（白名单 / 黑名单是 ruoyi 的配置）
 |
| `FLOW:F-JP-05.step5` | ruoyi → 日本服务 | 详情实时查询（不走缓存）→ upsert gz_jp_snap_item → 准入判定 → 报价 | FIELD:gz_jp_snap_item.external_id, FIELD:gz_jp_snap_item.price_jpy, FIELD:gz_jp_snap_item.item_status, FIELD:gz_jp_snap_item.shipping_payer, FIELD:gz_jp_snap_item.gate_result, FIELD:gz_jp_snap_item.gate_reason, FIELD:gz_jp_snap_item.fetched_at | 准入（REQ-SNAP-022/023/024）：标题含「専用」或分类 / 黑名单不过 → blocked（详情可看、按钮置灰写原因）； 标题 / 描述含「コメント必須」「即購入不可」类，或 shipping_payer≠seller（到付）→ manual（可下单，付款后进人工队列）； 其余 → auto。item_status≠on_sale → 不可下单。报价见 FLOW:F-JP-06.step1
 |

## 代切报价、锁商品与支付

**锚 id**：`FLOW:F-JP-06`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SNAP-020, REQ-SNAP-021, REQ-SNAP-025, REQ-SNAP-035, REQ-SNAP-037, REQ-SNAP-041, REQ-SNAP-004, REQ-SNAP-007

详情页出报价（10 分钟有效）→ 立即购买（不进购物车，一单一件）→ 下单确认页勾「抢到后不可取消」→
提交：校验报价未过期 + 商品锁 → 建订单（行 source=snap）→ 主图转存 → 微信支付 →
支付回调同事务写一条下单任务，订单行进「购买中」。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-06.step1` | ruoyi | 报价 —— 人民币价 = ceil(日元价 × 汇率/100 × (1 + 加价比例) × 100 分) + 固定服务费 [+ 到付预估运费] |  | 报价存 Redis（key=quote:{quoteId}，TTL 600s）：external_id / price_jpy / rate_per_100jpy / markup_ratio / fixed_fee_cent / est_shipping_cent（仅 gate=manual 且到付时 >0）/ total_cent / quoted_at。 汇率取 gz_jp_fx_rate 最新一条；超过 6h 未更新 → 拒绝报价并告警（REQ-SNAP-020/021/025）。 ★ 三个参数任一未配置 → 拒绝报价（REQ-SNAP-061 上线前甲方填）
 |
| `FLOW:F-JP-06.step2` | 客人(mp) | 详情页点「立即购买」→ 下单确认页选地址、勾选「已知悉抢到后不可取消」→ 提交 |  | 未勾选不可提交（REQ-SNAP-037）；报价剩余时间在确认页可见，过期提示重新报价 |
| `FLOW:F-JP-06.step3` | ruoyi | 提交订单 —— 报价校验 + 商品锁 + 建单（同一事务） | FIELD:gz_jp_snap_item.active_order_item_id, FIELD:gz_jp_order.order_no, FIELD:gz_jp_order_item.source, FIELD:gz_jp_order_item.snap_item_id, FIELD:gz_jp_order_item.product_snapshot_json, FIELD:gz_jp_order_item.amount_cent | ① 报价不存在 / 过期 / 不属于本商品 → 拒（前端重新报价） ② `SELECT … FROM gz_jp_snap_item WHERE id=? FOR UPDATE`；active_order_item_id 非空且该行订单仍为 created/paid 且未失败 → 拒「已被其他用户下单」（REQ-SNAP-041） ③ 建 gz_jp_order + 1 行 gz_jp_order_item（source=snap、product_id 空、snap_item_id 有值、qty=1、amount_cent=报价 total_cent） ④ 报价整体写进 product_snapshot_json 的 snap 段 ⑤ 回写 active_order_item_id ⑥ 主图转存 gz_file_object（失败不阻断，快照留原 URL 兜底）
 |
| `FLOW:F-JP-06.step4` | 客人(mp) | 微信支付（复用 GZ-PAY，business_type='jp'） |  | 与拼团同一支付链路；未付款 15 分钟后由 FLOW:F-JP-10.step1 关单并释放商品锁 |
| `FLOW:F-JP-06.step5` | ruoyi | 支付回调 —— 订单 paid、行 purchasing，同事务写下单任务 | FIELD:gz_jp_order.business_status, FIELD:gz_jp_order_item.fulfill_status, FIELD:gz_jp_snap_purchase.order_item_id, FIELD:gz_jp_snap_purchase.mode, FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.locked_price_jpy | mode = gate_result=manual 或 自动下单总开关关闭 → manual（purchase_status=manual_pending）；否则 auto（queued, next_action_at=now）。 ★ 回调里**不调**日本服务（ADR-0025 §2：回调超时 → 微信重推 → 重复下单）。任务唯一键 order_item_id，重复回调幂等
 |

## 自动下单与结果判定

**锚 id**：`FLOW:F-JP-07`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SNAP-006, REQ-SNAP-026, REQ-SNAP-027, REQ-SNAP-028, REQ-SNAP-029, REQ-SNAP-030, REQ-SNAP-036, REQ-SNAP-039, REQ-SNAP-042, REQ-SNAP-043, REQ-SNAP-064

本地调度按账号串行取 queued 任务 → 同步调日本服务下单（45s）→ 结果三态：
success 进交易跟踪；failed 判失败、行级全额退款、释放商品锁；unknown 不退不重试、三次对账、仍不明转人工。
任何风控信号 → 该账号停用 + 自动下单总开关关闭 + 所有 queued 转人工。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-07.step1` | ruoyi(本地调度) | 每 5s 扫 queued 且 next_action_at≤now 的任务，选一个 admin_enabled=1 且 health=healthy、未超日限、过了冷却的账号，置 executing | FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.account_code, FIELD:gz_jp_snap_purchase.executed_at | 走 GzLocalSchedulerConfig（prod 未部署 SnailJob）。抢任务用条件更新（WHERE purchase_status='queued' AND version=?）防多实例双取。 无可用账号 → 任务转 manual_pending（不排队等，REQ-SNAP-030）。执行线程池独立于 Web 线程池
 |
| `FLOW:F-JP-07.step2` | ruoyi → 日本服务 | POST /v1/purchases {order_no, external_id, max_price_jpy, account_code}（超时 45s） |  | 日本服务内部：① 按 order_no 查本地幂等记录，有 → 直接返回原结果 ② 查账号购买记录有该商品 → success ③ 打开商品页核对在售 / 当前价 ≤ max_price_jpy / 送料込み ④ 进购买页确认默认付款方式与收货地址 → 点「購入する」 ⑤ 判结果：跳交易页 = success（取交易号）；売り切れ / 削除 = failed；当前价 > max = failed(price_up)；其他任何情况 = unknown ⑥ 每步截图 + 页面快照回传（REQ-SNAP-043）⑦ 遇验证码 / 登录验证 / 短信验证 → 返回 unknown + risk_signal=true
 |
| `FLOW:F-JP-07.step3` | ruoyi | success → 任务成功、订单行进交易跟踪 | FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.mercari_txn_id, FIELD:gz_jp_snap_purchase.actual_price_jpy, FIELD:gz_jp_snap_purchase.trade_status, FIELD:gz_jp_order_item.fulfill_status, FIELD:gz_jp_snap_account.today_count | purchase_status=success、trade_status=await_ship、fulfill_status purchasing→await_seller_ship； actual_price_jpy 落库，低于锁定价差价不退（REQ-SNAP-028）；商品锁保持（商品已归我们）
 |
| `FLOW:F-JP-07.step4` | ruoyi | failed → 任务失败、行级全额退款、释放商品锁 | FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.fail_reason, FIELD:gz_jp_order_item.fulfill_status, FIELD:gz_jp_order_item.refund_status, FIELD:gz_jp_snap_item.active_order_item_id | fulfill_status=purchase_failed → 复用 GZ-JP-107 行级退款，退 amount_cent 全额（含固定费 / 预估运费，REQ-SNAP-036）； 涨价也走这里（REQ-SNAP-027）。active_order_item_id 置空
 |
| `FLOW:F-JP-07.step5` | ruoyi | unknown → 不动钱，排对账；对账最多 3 次（+30s / +2min / +10min） | FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.reconcile_count, FIELD:gz_jp_snap_purchase.next_action_at | 对账 = GET /v1/purchases/{order_no}/reconcile：found → 按 step3；not_found 且商品已非在售 → 按 step4； not_found 且商品仍在售 / 对账本身失败 → reconcile_count+1；3 次后仍不明 → manual_pending。 ★ unknown 状态下**绝不**再次 POST /v1/purchases（REQ-SNAP-029/039）
 |
| `FLOW:F-JP-07.step6` | ruoyi | 风控熔断 —— risk_signal / 连续 3 次非业务失败 / 心跳登录态失效 | FIELD:gz_jp_snap_account.health_status, FIELD:gz_jp_snap_account.pause_reason | 该账号 health=challenge；sys_config gz.jp.snap.auto.enabled=false（写 pausedReason / pausedAt）； 所有 queued 任务批量转 manual_pending。只能 admin 手动恢复（REQ-SNAP-030/042）
 |

## 人工代买

**锚 id**：`FLOW:F-JP-08`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SNAP-023, REQ-SNAP-024, REQ-SNAP-025, REQ-SNAP-031

日本员工在 admin 人工代买队列处理 manual_pending 任务：和卖家沟通 / 在煤炉 App 手工下单 → 回后台填结果。
填成功 = 与自动成功同一出口；填失败 = 与自动失败同一出口。到付商品按实际运费多退少不补。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-08.step1` | 日本员工(admin) | 队列按付款时间升序，显示入队原因（准入转人工 / 对账不清 / 风控暂停）+ 商品原链接 + 锁定日元价 + 到付预估运费 |  | 入队原因写在 fail_reason 之外的 manual_reason（准入 = gate_reason；对账 = reconcile_exhausted；暂停 = auto_paused） |
| `FLOW:F-JP-08.step2` | 日本员工(admin) | 填成功 —— 煤炉交易号（必填）+ 实际日元价 + 实际到付运费（日元，到付商品必填） | FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.mercari_txn_id, FIELD:gz_jp_snap_purchase.actual_price_jpy, FIELD:gz_jp_snap_purchase.actual_shipping_jpy, FIELD:gz_jp_snap_purchase.manual_operator | 出口同 FLOW:F-JP-07.step3。到付：多退 = est_shipping_cent − ceil(actual_shipping_jpy × 锁定汇率/100 × 100)，>0 时按行部分退款 （gz_jp_refund 新增一条 reason=shipping_diff，行 fulfill_status 不变）；≤0 不补收（REQ-SNAP-025）
 |
| `FLOW:F-JP-08.step3` | 日本员工(admin) | 填失败（谈不成 / 已售出 / 卖家拒绝）+ 备注 | FIELD:gz_jp_snap_purchase.purchase_status, FIELD:gz_jp_snap_purchase.fail_reason, FIELD:gz_jp_snap_purchase.manual_note | 出口同 FLOW:F-JP-07.step4（全额退款、释放商品锁，REQ-SNAP-031） |

## 代切交易跟踪、到仓验货与评价

**锚 id**：`FLOW:F-JP-09`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SNAP-004, REQ-SNAP-032, REQ-SNAP-033, REQ-SNAP-034

煤炉下单成功后到「评价」之前是代切独有的一段：卖家发货 → 到日本转运仓 → 验货 → 员工在煤炉 App 评价。
期间卖家取消 → 自动退款；验货不通过 → 员工在煤炉走退货 → 退款。评价完成后订单行接回一期履约链（FLOW:F-JP-03）。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-09.step1` | ruoyi(本地调度) → 日本服务 | 每 20 分钟巡检 trade_status ∈ {await_ship, shipped} 的交易（GET /v1/trades?account=） | FIELD:gz_jp_snap_purchase.trade_status | 卖家已发货 → shipped；卖家取消 → cancelled → 订单行 purchase_failed（★ 状态机放开 await_seller_ship→purchase_failed， 仅限 source=snap）→ 行级全额退款 + 释放商品锁（REQ-SNAP-032）。巡检失败只记日志、不改状态
 |
| `FLOW:F-JP-09.step2` | 日本员工(admin) | 货到转运仓 → 点「已到仓」 | FIELD:gz_jp_snap_purchase.trade_status, FIELD:gz_jp_snap_purchase.arrived_at, FIELD:gz_jp_snap_purchase.rate_deadline_at | rate_deadline_at = arrived_at + 评价期限小时数（配置，默认 48h，REQ-SNAP-034） |
| `FLOW:F-JP-09.step3` | 日本员工(admin) | 验货通过 → 在煤炉 App 手工评价 → 后台点「已评价」 | FIELD:gz_jp_snap_purchase.trade_status, FIELD:gz_jp_snap_purchase.rated_at | trade_status=rated；订单行仍是 await_seller_ship，此后由店员在履约看板按一期流程推进（jp_shipped → … → delivered）。 ★ 系统不自动评价（REQ-SNAP-054 不做）
 |
| `FLOW:F-JP-09.step4` | 日本员工(admin) | 验货不通过 → 在煤炉 App 走退货 → 后台点「退货完成」 | FIELD:gz_jp_snap_purchase.trade_status, FIELD:gz_jp_snap_purchase.fail_reason | trade_status=returned、fail_reason=inspect_ng → 订单行 purchase_failed → 行级全额退款（REQ-SNAP-033） |
| `FLOW:F-JP-09.step5` | 系统 | 评价超时提醒 —— rate_deadline_at 前 12h 未评价的交易在 admin 代切看板置顶 + 菜单角标 |  | 不做站外推送（REQ-SNAP-050 不做） |

## 未付款超时关单与退款补偿（一期遗留，代切下变成主路径）

**锚 id**：`FLOW:F-JP-10`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-ORDER-011, REQ-FULFILL-008

两个本地调度任务：① created 超 15 分钟未付款 → 关单 + 释放代切商品锁；② gz_jp_refund 卡在 refunding 超 10 分钟无回调 →
先查微信退款单状态，已成功按回调处理、已失败落 refund_failed、未受理再补发。拼团单与代切单同一套任务。

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-10.step1` | ruoyi(本地调度) | 每 5 分钟扫 business_status=created 且 create_time 早于 15 分钟前的订单 → 关单 | FIELD:gz_jp_order.business_status, FIELD:gz_jp_order.cancelled_time, FIELD:gz_jp_snap_item.active_order_item_id | 激活 GzJpOrderMapper.markCancelled（条件更新 created→cancelled，防与支付回调竞态）；关单前先查支付单—— 已支付按回调补处理，不关（REQ-ORDER-011）
 |
| `FLOW:F-JP-10.step2` | ruoyi(本地调度) | 每 5 分钟扫 gz_jp_refund.status=refunding 且超过 10 分钟的单 → 查单 → 补偿 |  | 调 IWechatPayClient 查退款单：SUCCESS → 走与回调相同的落账（幂等）；ABNORMAL/CLOSED → refund_failed； NOT_FOUND → 用同一 out_refund_no 补发（微信按 out_refund_no 幂等）（REQ-FULFILL-008）
 |

## 代切运营配置、汇率与运维探测

**锚 id**：`FLOW:F-JP-11`（ticket 的 blueprint_refs 写这个）
**对应需求**：REQ-SNAP-020, REQ-SNAP-030, REQ-SNAP-042, REQ-SNAP-044, REQ-SNAP-019, REQ-SNAP-040, REQ-SNAP-022, REQ-SNAP-023, REQ-SNAP-061

代切的可调参数全部在 admin 配置（sys_config 的 gz.jp.snap.* 键，JSON 值），后端定时抓汇率、定时探测日本服务与煤炉可用性、
定时拉账号心跳。配置键（config_id 用 1404xxxx 段）：
  gz.jp.snap.pricing  = {markupRatio, fixedFeeCent, estShippingCent, quoteTtlSec=600}
  gz.jp.snap.filter   = {categoryWhitelist[], keywordBlacklist[]}
  gz.jp.snap.gate     = {blockKeywords[専用…], manualKeywords[コメント必須 / 即購入不可…]}
  gz.jp.snap.auto     = {enabled, pausedReason, pausedAt}
  gz.jp.snap.trade    = {rateDeadlineHours=48, patrolMinutes=20}

| 步 | 谁 | 做什么 | 写什么 | 产出 |
|---|---|---|---|---|
| `FLOW:F-JP-11.step1` | ruoyi(本地调度) | 每 30 分钟抓中国银行外汇牌价日元现汇卖出价（每 100 日元）写 gz_jp_fx_rate；admin 可手动录入覆盖 | FIELD:gz_jp_fx_rate.rate_per_100jpy, FIELD:gz_jp_fx_rate.source, FIELD:gz_jp_fx_rate.fetched_at | 抓取失败保留上一条；最新一条超 6h → 报价拒绝 + admin 告警（REQ-SNAP-020） |
| `FLOW:F-JP-11.step2` | ruoyi(本地调度) → 日本服务 | 每 2 分钟拉 /v1/health（各账号登录态 + 出口 IP 可用）→ 写账号 health_status / last_heartbeat_at | FIELD:gz_jp_snap_account.health_status, FIELD:gz_jp_snap_account.last_heartbeat_at | 登录态失效 → 走 FLOW:F-JP-07.step6 熔断 |
| `FLOW:F-JP-11.step3` | ruoyi(本地调度) → 日本服务 | 每 10 分钟主动探测 —— 固定关键词搜一次、固定商品查一次详情 |  | 失败 → admin 账号页告警 + error 日志 + 自动下单总开关关闭（REQ-SNAP-044） |
