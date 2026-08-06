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
| `FLOW:F-JP-00.step2` | 后端 | 按 clientid 解析出该小程序的 appid / secret / real-or-mock 模式 | FIELD:gz_user.app_id | wx.miniapp 配置由标量改 Map<clientid, app>；8 处 @ConditionalOnExpression 的 real/mock 全局互斥改为运行时按 app 分派
 |
| `FLOW:F-JP-00.step3` | 后端 | 微信登录 —— 按 app_id + openid upsert 用户 | FIELD:gz_user.app_id, FIELD:gz_user.openid | 唯一键 (tenant_id, app_id, openid)。同一自然人在两个小程序 = 两条独立记录， 互不干扰（不做 unionid 合并，列为后续增强）
 |
| `FLOW:F-JP-00.step4` | 后端 | 调起支付 —— 用当前小程序的 appid 做统一下单与 5 参签名 |  | ★ WechatPayV3ClientImpl:125 的签名 appid 必须来自下单上下文。 写死则新小程序 uni.requestPayment 必失败。落点：激活 gz_pay_channel.appid 列做真源
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
| `FLOW:F-JP-04.step2` | 系统 | 按行金额发起微信部分退款 | FIELD:gz_jp_order_item.refund_status, FIELD:gz_jp_order_item.refund_amount_cent | ★ 退款金额 = 该 order_item 的 amount_cent，不是整单。 复用现有 PayRefundController；**实施前须硬查该接口支持指定金额**（见 ticket §0 自检）
 |
| `FLOW:F-JP-04.step3` | 系统 | 退款回调 —— 该行转已退款，订单状态按剩余行重算 | FIELD:gz_jp_order_item.refund_status, FIELD:gz_jp_order.business_status | 有失败行且非全部 → 订单 partial_refunded；全部行失败 → 订单 refunded。 退款回调走 GZ-PAY 现有 RefundCallbackDispatcher，business_type='jp'
 |
