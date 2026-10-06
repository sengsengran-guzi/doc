# 字段表

> 本文件由 `authority_lint.py render` 从 `doc/authority/*.yaml` 自动生成。**别手改**——改权威改 YAML，手改这里下次 render 就被覆盖。

## gz_jp_cart_item.id

**锚 id**：`FIELD:gz_jp_cart_item.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_cart_item.product_id

**锚 id**：`FIELD:gz_jp_cart_item.product_id`（ticket 的 blueprint_refs 写这个）

{"comment": "商品 FK gz_jp_product.id", "name": "product_id", "nullable": false, "type": "id", "unique": "uk_user_product"}

## gz_jp_cart_item.qty

**锚 id**：`FIELD:gz_jp_cart_item.qty`（ticket 的 blueprint_refs 写这个）

{"comment": "数量", "default": "1", "name": "qty", "nullable": false, "type": "int"}

## gz_jp_cart_item.user_id

**锚 id**：`FIELD:gz_jp_cart_item.user_id`（ticket 的 blueprint_refs 写这个）

{"comment": "所属用户 FK gz_user.id", "name": "user_id", "nullable": false, "type": "id"}

## gz_jp_event.cover_image_id

**锚 id**：`FIELD:gz_jp_event.cover_image_id`（ticket 的 blueprint_refs 写这个）

{"comment": "封面图，FK gz_file_object.id（禁裸 url）", "name": "cover_image_id", "nullable": true, "type": "id"}

## gz_jp_event.description

**锚 id**：`FIELD:gz_jp_event.description`（ticket 的 blueprint_refs 写这个）

{"comment": "场简介", "length": 512, "name": "description", "nullable": true, "type": "str"}

## gz_jp_event.end_time

**锚 id**：`FIELD:gz_jp_event.end_time`（ticket 的 blueprint_refs 写这个）

{"comment": "闭场时间；到点后读时惰性判定为已结束，不依赖 cron", "name": "end_time", "nullable": false, "type": "datetime"}

## gz_jp_event.event_no

**锚 id**：`FIELD:gz_jp_event.event_no`（ticket 的 blueprint_refs 写这个）

{"comment": "场编号 EVT-yyyyMMdd-6位", "length": 32, "name": "event_no", "nullable": false, "type": "str", "unique": "uk_event_no"}

## gz_jp_event.id

**锚 id**：`FIELD:gz_jp_event.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_event.name

**锚 id**：`FIELD:gz_jp_event.name`（ticket 的 blueprint_refs 写这个）

{"comment": "场名称", "length": 128, "name": "name", "nullable": false, "type": "str"}

## gz_jp_event.sort_no

**锚 id**：`FIELD:gz_jp_event.sort_no`（ticket 的 blueprint_refs 写这个）

{"comment": "排序号，越小越前", "default": "0", "name": "sort_no", "nullable": false, "type": "int"}

## gz_jp_event.start_time

**锚 id**：`FIELD:gz_jp_event.start_time`（ticket 的 blueprint_refs 写这个）

{"comment": "开场时间", "name": "start_time", "nullable": false, "type": "datetime"}

## gz_jp_event.status

**锚 id**：`FIELD:gz_jp_event.status`（ticket 的 blueprint_refs 写这个）

{"comment": "场状态 draft未开始/open进行中/closed已结束", "default": "draft", "dict": "gz_jp_event_status", "length": 16, "name": "status", "nullable": false, "type": "dict"}

## gz_jp_event.version

**锚 id**：`FIELD:gz_jp_event.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_fx_rate.fetched_at

**锚 id**：`FIELD:gz_jp_fx_rate.fetched_at`（ticket 的 blueprint_refs 写这个）

{"comment": "取价时间（新鲜度判定：超 6h 拒报价）", "name": "fetched_at", "nullable": false, "type": "datetime"}

## gz_jp_fx_rate.id

**锚 id**：`FIELD:gz_jp_fx_rate.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_fx_rate.rate_per_100jpy

**锚 id**：`FIELD:gz_jp_fx_rate.rate_per_100jpy`（ticket 的 blueprint_refs 写这个）

{"comment": "每 100 日元兑人民币（如 4.812300）", "name": "rate_per_100jpy", "nullable": false, "type": "decimal"}

## gz_jp_fx_rate.source

**锚 id**：`FIELD:gz_jp_fx_rate.source`（ticket 的 blueprint_refs 写这个）

{"comment": "boc中国银行现汇卖出价/manual手动录入", "dict": "gz_jp_fx_source", "length": 16, "name": "source", "nullable": false, "type": "dict"}

## gz_jp_order.address_snapshot_json

**锚 id**：`FIELD:gz_jp_order.address_snapshot_json`（ticket 的 blueprint_refs 写这个）

{"comment": "收货地址快照（下单锁定，后续改地址不影响已下单）", "name": "address_snapshot_json", "nullable": false, "type": "text"}

## gz_jp_order.business_status

**锚 id**：`FIELD:gz_jp_order.business_status`（ticket 的 blueprint_refs 写这个）

{"comment": "订单状态 created待支付/paid已支付/cancelled已取消/partial_refunded部分退款/refunded已退款", "default": "created", "dict": "gz_jp_order_status", "length": 20, "name": "business_status", "nullable": false, "type": "dict"}

## gz_jp_order.cancelled_time

**锚 id**：`FIELD:gz_jp_order.cancelled_time`（ticket 的 blueprint_refs 写这个）

{"comment": "取消时间", "name": "cancelled_time", "nullable": true, "type": "datetime"}

## gz_jp_order.id

**锚 id**：`FIELD:gz_jp_order.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_order.order_no

**锚 id**：`FIELD:gz_jp_order.order_no`（ticket 的 blueprint_refs 写这个）

{"comment": "订单号 JPO-yyyyMMdd-6位，= gz_pay_transaction.business_order_no", "length": 32, "name": "order_no", "nullable": false, "type": "str", "unique": "uk_order_no"}

## gz_jp_order.paid_time

**锚 id**：`FIELD:gz_jp_order.paid_time`（ticket 的 blueprint_refs 写这个）

{"comment": "支付时间", "name": "paid_time", "nullable": true, "type": "datetime"}

## gz_jp_order.pay_transaction_id

**锚 id**：`FIELD:gz_jp_order.pay_transaction_id`（ticket 的 blueprint_refs 写这个）

{"comment": "支付流水 FK gz_pay_transaction.id", "name": "pay_transaction_id", "nullable": true, "type": "id", "unique": "uk_pay_transaction"}

## gz_jp_order.total_amount_cent

**锚 id**：`FIELD:gz_jp_order.total_amount_cent`（ticket 的 blueprint_refs 写这个）

{"comment": "订单总额（分）= Σ 行金额。★ 无运费项（全包邮），后端重算不信前端", "name": "total_amount_cent", "nullable": false, "type": "bigint"}

## gz_jp_order.user_id

**锚 id**：`FIELD:gz_jp_order.user_id`（ticket 的 blueprint_refs 写这个）

{"comment": "下单用户 FK gz_user.id", "name": "user_id", "nullable": false, "type": "id"}

## gz_jp_order.user_note

**锚 id**：`FIELD:gz_jp_order.user_note`（ticket 的 blueprint_refs 写这个）

{"comment": "客人备注", "length": 255, "name": "user_note", "nullable": true, "type": "str"}

## gz_jp_order.version

**锚 id**：`FIELD:gz_jp_order.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_order_item.amount_cent

**锚 id**：`FIELD:gz_jp_order_item.amount_cent`（ticket 的 blueprint_refs 写这个）

{"comment": "行金额（分）= unit_price_cent × qty。★ 行级退款按此金额退", "name": "amount_cent", "nullable": false, "type": "bigint"}

## gz_jp_order_item.carrier_code

**锚 id**：`FIELD:gz_jp_order_item.carrier_code`（ticket 的 blueprint_refs 写这个）

{"comment": "国内快递编码（复用现有 gz_express_carrier 字典），置 delivered 时必填", "dict": "gz_express_carrier", "length": 32, "name": "carrier_code", "nullable": true, "type": "dict"}

## gz_jp_order_item.fulfill_status

**锚 id**：`FIELD:gz_jp_order_item.fulfill_status`（ticket 的 blueprint_refs 写这个）

{"comment": "履约状态 purchasing购买中/purchase_failed购买失败/await_seller_ship等待官方发货/jp_shipped日本仓库已发货/customs清关中/cn_sorting国内分拣中/delivered发货完毕。★ 允许跳过中间态（现货无 await_seller_ship）", "default": "purchasing", "dict": "gz_jp_fulfill_status", "length": 24, "name": "fulfill_status", "nullable": false, "type": "dict"}

## gz_jp_order_item.id

**锚 id**：`FIELD:gz_jp_order_item.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_order_item.order_id

**锚 id**：`FIELD:gz_jp_order_item.order_id`（ticket 的 blueprint_refs 写这个）

{"comment": "所属订单 FK gz_jp_order.id", "name": "order_id", "nullable": false, "type": "id"}

## gz_jp_order_item.product_id

**锚 id**：`FIELD:gz_jp_order_item.product_id`（ticket 的 blueprint_refs 写这个）

{"comment": "拼团商品 FK gz_jp_product.id。★ 二期改可空（ADR-0025 §5，新迁移 ALTER）：source=batch 必填 / source=snap 恒空，应用层保证", "name": "product_id", "nullable": true, "type": "id"}

## gz_jp_order_item.product_snapshot_json

**锚 id**：`FIELD:gz_jp_order_item.product_snapshot_json`（ticket 的 blueprint_refs 写这个）

{"comment": "下单时商品快照（名/图/价/注意事项），商品后续改动不影响已下单。source=snap 时另含 snap 段：externalId / titleJa / titleZh / priceJpy / ratePer100Jpy / markupRatio / fixedFeeCent / estShippingCent / gateResult / gateReason / shippingPayer / conditionText / mainImageId / mainImageUrl / quoteId / quotedAt（mainImageUrl为转存失败兜底的原图URL，读侧必须改写为备案CDN/自有图片代理地址）；金额和汇率保留报价锁定值，gateResult 为提交时保守准入：报价或实时复查任一 manual 则 manual，实时 blocked 拒单（REQ-SNAP-021 锁价凭据）", "name": "product_snapshot_json", "nullable": false, "type": "text"}

## gz_jp_order_item.qty

**锚 id**：`FIELD:gz_jp_order_item.qty`（ticket 的 blueprint_refs 写这个）

{"comment": "数量", "name": "qty", "nullable": false, "type": "int"}

## gz_jp_order_item.refund_amount_cent

**锚 id**：`FIELD:gz_jp_order_item.refund_amount_cent`（ticket 的 blueprint_refs 写这个）

{"comment": "已退金额（分），正常 = amount_cent", "name": "refund_amount_cent", "nullable": true, "type": "bigint"}

## gz_jp_order_item.refund_status

**锚 id**：`FIELD:gz_jp_order_item.refund_status`（ticket 的 blueprint_refs 写这个）

{"comment": "退款状态 refunding退款中/refunded已退款/refund_failed退款失败。仅 purchase_failed 行会有值", "dict": "gz_jp_refund_status", "length": 20, "name": "refund_status", "nullable": true, "type": "dict"}

## gz_jp_order_item.shipped_at

**锚 id**：`FIELD:gz_jp_order_item.shipped_at`（ticket 的 blueprint_refs 写这个）

{"comment": "发货时间（置 delivered 时写入）", "name": "shipped_at", "nullable": true, "type": "datetime"}

## gz_jp_order_item.snap_item_id

**锚 id**：`FIELD:gz_jp_order_item.snap_item_id`（ticket 的 blueprint_refs 写这个）

{"comment": "★ 二期新增：代切商品 FK gz_jp_snap_item.id。source=snap 必填 / source=batch 恒空", "name": "snap_item_id", "nullable": true, "type": "id"}

## gz_jp_order_item.source

**锚 id**：`FIELD:gz_jp_order_item.source`（ticket 的 blueprint_refs 写这个）

{"comment": "来源 batch=拼团 / snap=代切（二期字典加值）。source=snap 的订单一单只有这一行（REQ-SNAP-035）", "default": "batch", "dict": "gz_jp_item_source", "length": 16, "name": "source", "nullable": false, "type": "dict"}

## gz_jp_order_item.tracking_no

**锚 id**：`FIELD:gz_jp_order_item.tracking_no`（ticket 的 blueprint_refs 写这个）

{"comment": "国内运单号，员工手工填。★ 本列即包裹标识——同单号的行属同一包裹，不另建包裹表", "length": 64, "name": "tracking_no", "nullable": true, "type": "str"}

## gz_jp_order_item.unit_price_cent

**锚 id**：`FIELD:gz_jp_order_item.unit_price_cent`（ticket 的 blueprint_refs 写这个）

{"comment": "下单时单价（分）", "name": "unit_price_cent", "nullable": false, "type": "bigint"}

## gz_jp_order_item.user_id

**锚 id**：`FIELD:gz_jp_order_item.user_id`（ticket 的 blueprint_refs 写这个）

{"comment": "冗余下单用户 id —— 履约看板主视图按客人聚合且跨订单，避免每次 join 订单表", "name": "user_id", "nullable": false, "type": "id"}

## gz_jp_order_item.version

**锚 id**：`FIELD:gz_jp_order_item.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_product.delivery_date_text

**锚 id**：`FIELD:gz_jp_product.delivery_date_text`（ticket 的 blueprint_refs 写这个）

{"comment": "预计到货时间（文本，如「8月下旬」，谷圈惯用模糊表述）", "length": 64, "name": "delivery_date_text", "nullable": true, "type": "str"}

## gz_jp_product.event_id

**锚 id**：`FIELD:gz_jp_product.event_id`（ticket 的 blueprint_refs 写这个）

{"comment": "所属场 FK gz_jp_event.id（逻辑关联，不建物理外键）", "name": "event_id", "nullable": false, "type": "id"}

## gz_jp_product.gallery_image_ids

**锚 id**：`FIELD:gz_jp_product.gallery_image_ids`（ticket 的 blueprint_refs 写这个）

{"comment": "图集，逗号分隔 file id。一期用图集承载详情，不做富文本", "length": 512, "name": "gallery_image_ids", "nullable": true, "type": "str"}

## gz_jp_product.id

**锚 id**：`FIELD:gz_jp_product.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_product.main_image_id

**锚 id**：`FIELD:gz_jp_product.main_image_id`（ticket 的 blueprint_refs 写这个）

{"comment": "主图 FK gz_file_object.id", "name": "main_image_id", "nullable": false, "type": "id"}

## gz_jp_product.name

**锚 id**：`FIELD:gz_jp_product.name`（ticket 的 blueprint_refs 写这个）

{"comment": "商品名称", "length": 128, "name": "name", "nullable": false, "type": "str"}

## gz_jp_product.notice_text

**锚 id**：`FIELD:gz_jp_product.notice_text`（ticket 的 blueprint_refs 写这个）

{"comment": "额外注意事项（甲方明确要求的独立字段，下单前须显著展示，不混进图集）", "length": 1024, "name": "notice_text", "nullable": true, "type": "str"}

## gz_jp_product.price_cent

**锚 id**：`FIELD:gz_jp_product.price_cent`（ticket 的 blueprint_refs 写这个）

{"comment": "售价（分）。★ 全包邮，此价即客人最终支付价，不叠加运费", "name": "price_cent", "nullable": false, "type": "bigint"}

## gz_jp_product.product_no

**锚 id**：`FIELD:gz_jp_product.product_no`（ticket 的 blueprint_refs 写这个）

{"comment": "商品编号 JPP-yyyyMMdd-6位", "length": 32, "name": "product_no", "nullable": false, "type": "str", "unique": "uk_product_no"}

## gz_jp_product.sort_no

**锚 id**：`FIELD:gz_jp_product.sort_no`（ticket 的 blueprint_refs 写这个）

{"comment": "场内排序号", "default": "0", "name": "sort_no", "nullable": false, "type": "int"}

## gz_jp_product.status

**锚 id**：`FIELD:gz_jp_product.status`（ticket 的 blueprint_refs 写这个）

{"comment": "商品状态 on_shelf上架/off_shelf下架。★ 一期无库存字段（集单预订不限量）", "default": "off_shelf", "dict": "gz_jp_product_status", "length": 16, "name": "status", "nullable": false, "type": "dict"}

## gz_jp_product.version

**锚 id**：`FIELD:gz_jp_product.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_refund.order_item_id

**锚 id**：`FIELD:gz_jp_refund.order_item_id`（ticket 的 blueprint_refs 写这个）

{"comment": "退的是哪一行。★ 唯一键二期由 uk_order_item(tenant_id, order_item_id) 改为 uk_item_type(tenant_id, order_item_id, refund_type)（ADR-0025 §5，Kevin 2026-10-03 确认）", "name": "order_item_id", "nullable": false, "type": "id"}

## gz_jp_refund.refund_amount_cent

**锚 id**：`FIELD:gz_jp_refund.refund_amount_cent`（ticket 的 blueprint_refs 写这个）

{"comment": "本次退款金额（分）。purchase_failed = 该行 amount_cent − 该行已成功的 shipping_diff 金额", "name": "refund_amount_cent", "nullable": false, "type": "bigint"}

## gz_jp_refund.refund_type

**锚 id**：`FIELD:gz_jp_refund.refund_type`（ticket 的 blueprint_refs 写这个）

{"comment": "★ 二期新增：purchase_failed 购买失败全额（存量行回填此值）/ shipping_diff 到付预估运费多退（REQ-SNAP-025）。一行至多各一条。★ 只有 purchase_failed 会写订单行 refund_status / refund_amount_cent 并参与订单 business_status rollup；shipping_diff 发起与回调都不碰订单行、不参与 rollup（FLOW:F-JP-08.step2）", "default": "purchase_failed", "dict": "gz_jp_refund_type", "length": 20, "name": "refund_type", "nullable": false, "type": "dict", "unique": "uk_item_type"}

## gz_jp_snap_account.account_code

**锚 id**：`FIELD:gz_jp_snap_account.account_code`（ticket 的 blueprint_refs 写这个）

{"comment": "账号编码（与日本服务配置一致的稳定业务键，如 acc01）", "length": 32, "name": "account_code", "nullable": false, "type": "str", "unique": "uk_account_code"}

## gz_jp_snap_account.admin_enabled

**锚 id**：`FIELD:gz_jp_snap_account.admin_enabled`（ticket 的 blueprint_refs 写这个）

{"comment": "admin 手动启停（只有 admin 写）", "default": "1", "name": "admin_enabled", "nullable": false, "type": "bool"}

## gz_jp_snap_account.cooldown_sec

**锚 id**：`FIELD:gz_jp_snap_account.cooldown_sec`（ticket 的 blueprint_refs 写这个）

{"comment": "两单之间最短间隔秒数", "default": "60", "name": "cooldown_sec", "nullable": false, "type": "int"}

## gz_jp_snap_account.daily_limit

**锚 id**：`FIELD:gz_jp_snap_account.daily_limit`（ticket 的 blueprint_refs 写这个）

{"comment": "每日自动下单上限", "default": "20", "name": "daily_limit", "nullable": false, "type": "int"}

## gz_jp_snap_account.health_status

**锚 id**：`FIELD:gz_jp_snap_account.health_status`（ticket 的 blueprint_refs 写这个）

{"comment": "healthy正常/challenge触发验证/logged_out登录失效/unreachable不可达/unknown —— 只由 ruoyi 心跳任务按日本服务 /v1/health 写", "default": "unknown", "dict": "gz_jp_snap_account_health", "length": 16, "name": "health_status", "nullable": false, "type": "dict"}

## gz_jp_snap_account.id

**锚 id**：`FIELD:gz_jp_snap_account.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_snap_account.last_heartbeat_at

**锚 id**：`FIELD:gz_jp_snap_account.last_heartbeat_at`（ticket 的 blueprint_refs 写这个）

{"comment": "最近一次心跳成功时间", "name": "last_heartbeat_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_account.last_purchase_at

**锚 id**：`FIELD:gz_jp_snap_account.last_purchase_at`（ticket 的 blueprint_refs 写这个）

{"comment": "最近一次自动下单时间", "name": "last_purchase_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_account.nickname

**锚 id**：`FIELD:gz_jp_snap_account.nickname`（ticket 的 blueprint_refs 写这个）

{"comment": "煤炉昵称（展示用）", "length": 64, "name": "nickname", "nullable": true, "type": "str"}

## gz_jp_snap_account.pause_reason

**锚 id**：`FIELD:gz_jp_snap_account.pause_reason`（ticket 的 blueprint_refs 写这个）

{"comment": "停用 / 熔断原因（REQ-SNAP-030）", "length": 255, "name": "pause_reason", "nullable": true, "type": "str"}

## gz_jp_snap_account.today_count

**锚 id**：`FIELD:gz_jp_snap_account.today_count`（ticket 的 blueprint_refs 写这个）

{"comment": "当日已自动下单数（today_date 换日清零）", "default": "0", "name": "today_count", "nullable": false, "type": "int"}

## gz_jp_snap_account.today_date

**锚 id**：`FIELD:gz_jp_snap_account.today_date`（ticket 的 blueprint_refs 写这个）

{"comment": "today_count 所属日期（Asia/Tokyo）", "name": "today_date", "nullable": true, "type": "date"}

## gz_jp_snap_account.version

**锚 id**：`FIELD:gz_jp_snap_account.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_snap_item.active_order_item_id

**锚 id**：`FIELD:gz_jp_snap_item.active_order_item_id`（ticket 的 blueprint_refs 写这个）

{"comment": "★ 孤品互斥锁：占用中的订单行 FK gz_jp_order_item.id；提交订单时 FOR UPDATE 判定，关单 / 失败 / 退款时置空（REQ-SNAP-041）", "name": "active_order_item_id", "nullable": true, "type": "id"}

## gz_jp_snap_item.category_id

**锚 id**：`FIELD:gz_jp_snap_item.category_id`（ticket 的 blueprint_refs 写这个）

{"comment": "煤炉分类 ID（白名单判定，REQ-SNAP-019）", "length": 32, "name": "category_id", "nullable": true, "type": "str"}

## gz_jp_snap_item.condition_text

**锚 id**：`FIELD:gz_jp_snap_item.condition_text`（ticket 的 blueprint_refs 写这个）

{"comment": "成色（日文原文，如「新品、未使用」）", "length": 64, "name": "condition_text", "nullable": true, "type": "str"}

## gz_jp_snap_item.external_id

**锚 id**：`FIELD:gz_jp_snap_item.external_id`（ticket 的 blueprint_refs 写这个）

{"comment": "煤炉商品 ID（m+数字）—— 跨系统稳定业务键", "length": 32, "name": "external_id", "nullable": false, "type": "str", "unique": "uk_platform_external"}

## gz_jp_snap_item.fetched_at

**锚 id**：`FIELD:gz_jp_snap_item.fetched_at`（ticket 的 blueprint_refs 写这个）

{"comment": "最近一次实时查询时间", "name": "fetched_at", "nullable": false, "type": "datetime"}

## gz_jp_snap_item.gate_reason

**锚 id**：`FIELD:gz_jp_snap_item.gate_reason`（ticket 的 blueprint_refs 写这个）

{"comment": "命中的规则（如 kw:専用 / proxy_refuse:<命中词>@title|desc|profile / kw:コメント必須 / shipping:buyer / category / blacklist / shops），admin 与人工队列展示", "length": 64, "name": "gate_reason", "nullable": true, "type": "str"}

## gz_jp_snap_item.gate_result

**锚 id**：`FIELD:gz_jp_snap_item.gate_result`（ticket 的 blueprint_refs 写这个）

{"comment": "准入 auto可自动下单/manual转人工/blocked不可购买（REQ-SNAP-022/023/024/048）", "dict": "gz_jp_snap_gate", "length": 16, "name": "gate_result", "nullable": false, "type": "dict"}

## gz_jp_snap_item.id

**锚 id**：`FIELD:gz_jp_snap_item.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_snap_item.item_status

**锚 id**：`FIELD:gz_jp_snap_item.item_status`（ticket 的 blueprint_refs 写这个）

{"comment": "煤炉侧状态 on_sale在售/trading交易中/sold_out已售出/deleted已删除", "dict": "gz_jp_snap_item_status", "length": 16, "name": "item_status", "nullable": false, "type": "dict"}

## gz_jp_snap_item.main_image_id

**锚 id**：`FIELD:gz_jp_snap_item.main_image_id`（ticket 的 blueprint_refs 写这个）

{"comment": "下单时转存的主图 FK gz_file_object.id（未下单过为空）", "name": "main_image_id", "nullable": true, "type": "id"}

## gz_jp_snap_item.platform

**锚 id**：`FIELD:gz_jp_snap_item.platform`（ticket 的 blueprint_refs 写这个）

{"comment": "来源平台，二期只有 mercari", "default": "mercari", "dict": "gz_jp_snap_platform", "length": 16, "name": "platform", "nullable": false, "type": "dict", "unique": "uk_platform_external"}

## gz_jp_snap_item.price_jpy

**锚 id**：`FIELD:gz_jp_snap_item.price_jpy`（ticket 的 blueprint_refs 写这个）

{"comment": "最近一次实时查询的日元价（整数日元）", "name": "price_jpy", "nullable": false, "type": "bigint"}

## gz_jp_snap_item.raw_json

**锚 id**：`FIELD:gz_jp_snap_item.raw_json`（ticket 的 blueprint_refs 写这个）

{"comment": "最近一次详情原始返回（审计 / 排障）", "name": "raw_json", "nullable": true, "type": "text"}

## gz_jp_snap_item.seller_id

**锚 id**：`FIELD:gz_jp_snap_item.seller_id`（ticket 的 blueprint_refs 写这个）

{"comment": "煤炉卖家 ID", "length": 64, "name": "seller_id", "nullable": true, "type": "str"}

## gz_jp_snap_item.shipping_payer

**锚 id**：`FIELD:gz_jp_snap_item.shipping_payer`（ticket 的 blueprint_refs 写这个）

{"comment": "运费承担 seller卖家包邮/buyer到付（REQ-SNAP-024 判定依据）", "dict": "gz_jp_snap_shipping_payer", "length": 16, "name": "shipping_payer", "nullable": false, "type": "dict"}

## gz_jp_snap_item.title_ja

**锚 id**：`FIELD:gz_jp_snap_item.title_ja`（ticket 的 blueprint_refs 写这个）

{"comment": "日文原标题", "length": 255, "name": "title_ja", "nullable": false, "type": "str"}

## gz_jp_snap_item.title_zh

**锚 id**：`FIELD:gz_jp_snap_item.title_zh`（ticket 的 blueprint_refs 写这个）

{"comment": "机翻中文标题（REQ-SNAP-016）", "length": 255, "name": "title_zh", "nullable": true, "type": "str"}

## gz_jp_snap_item.version

**锚 id**：`FIELD:gz_jp_snap_item.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_snap_purchase.account_code

**锚 id**：`FIELD:gz_jp_snap_purchase.account_code`（ticket 的 blueprint_refs 写这个）

{"comment": "执行账号 FK gz_jp_snap_account.account_code（人工 = 员工所用账号）", "length": 32, "name": "account_code", "nullable": true, "type": "str"}

## gz_jp_snap_purchase.actual_price_jpy

**锚 id**：`FIELD:gz_jp_snap_purchase.actual_price_jpy`（ticket 的 blueprint_refs 写这个）

{"comment": "实际成交日元价（低于锁定价差价不退，仅审计，REQ-SNAP-028）", "name": "actual_price_jpy", "nullable": true, "type": "bigint"}

## gz_jp_snap_purchase.actual_shipping_jpy

**锚 id**：`FIELD:gz_jp_snap_purchase.actual_shipping_jpy`（ticket 的 blueprint_refs 写这个）

{"comment": "到付实际运费（日元）：货到转运仓时日本员工点「已到仓」一并填（着払い到仓才付、才知道金额），用于多退少不补（REQ-SNAP-025）；包邮商品恒空", "name": "actual_shipping_jpy", "nullable": true, "type": "bigint"}

## gz_jp_snap_purchase.arrived_at

**锚 id**：`FIELD:gz_jp_snap_purchase.arrived_at`（ticket 的 blueprint_refs 写这个）

{"comment": "到仓时间", "name": "arrived_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_purchase.evidence_file_ids

**锚 id**：`FIELD:gz_jp_snap_purchase.evidence_file_ids`（ticket 的 blueprint_refs 写这个）

{"comment": "下单证据（截图 / 页面快照）file id 逗号分隔，usage_type=snap_evidence（REQ-SNAP-043）", "length": 512, "name": "evidence_file_ids", "nullable": true, "type": "str"}

## gz_jp_snap_purchase.executed_at

**锚 id**：`FIELD:gz_jp_snap_purchase.executed_at`（ticket 的 blueprint_refs 写这个）

{"comment": "开始执行时间", "name": "executed_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_purchase.external_id

**锚 id**：`FIELD:gz_jp_snap_purchase.external_id`（ticket 的 blueprint_refs 写这个）

{"comment": "冗余煤炉商品 ID", "length": 32, "name": "external_id", "nullable": false, "type": "str"}

## gz_jp_snap_purchase.fail_reason

**锚 id**：`FIELD:gz_jp_snap_purchase.fail_reason`（ticket 的 blueprint_refs 写这个）

{"comment": "sold_out已售出/deleted已下架/price_up涨价/manual_rejected人工谈不成/seller_cancel卖家取消/inspect_ng验货不通过", "dict": "gz_jp_snap_fail_reason", "length": 24, "name": "fail_reason", "nullable": true, "type": "dict"}

## gz_jp_snap_purchase.id

**锚 id**：`FIELD:gz_jp_snap_purchase.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_snap_purchase.last_error

**锚 id**：`FIELD:gz_jp_snap_purchase.last_error`（ticket 的 blueprint_refs 写这个）

{"comment": "最近一次调用日本服务的错误（不静默吞）", "length": 512, "name": "last_error", "nullable": true, "type": "str"}

## gz_jp_snap_purchase.locked_price_jpy

**锚 id**：`FIELD:gz_jp_snap_purchase.locked_price_jpy`（ticket 的 blueprint_refs 写这个）

{"comment": "锁定日元价 = 下单时报价；自动下单时当前价高于它即 failed(price_up)（REQ-SNAP-027）", "name": "locked_price_jpy", "nullable": false, "type": "bigint"}

## gz_jp_snap_purchase.manual_note

**锚 id**：`FIELD:gz_jp_snap_purchase.manual_note`（ticket 的 blueprint_refs 写这个）

{"comment": "人工备注", "length": 512, "name": "manual_note", "nullable": true, "type": "str"}

## gz_jp_snap_purchase.manual_operator

**锚 id**：`FIELD:gz_jp_snap_purchase.manual_operator`（ticket 的 blueprint_refs 写这个）

{"comment": "人工处理人 sys_user.user_id", "name": "manual_operator", "nullable": true, "type": "bigint"}

## gz_jp_snap_purchase.manual_reason

**锚 id**：`FIELD:gz_jp_snap_purchase.manual_reason`（ticket 的 blueprint_refs 写这个）

{"comment": "转人工原因：gate:<规则> / reconcile_sold（对账满 3 轮未查到，且最后一次看到商品已不在售——大概率要核实是否其实买到了）/ reconcile_exhausted（对账满 3 轮未查到，商品仍在售或对账调用失败）/ auto_paused（总开关关闭）/ no_account（无健康账号或都到日限；仅冷却中不转人工）/ shipping_changed（下单前发现运费改到付）/ account_unpayable（采购账号余额不足或付款方式不可用，该账号同时停用）", "length": 64, "name": "manual_reason", "nullable": true, "type": "str"}

## gz_jp_snap_purchase.mercari_txn_id

**锚 id**：`FIELD:gz_jp_snap_purchase.mercari_txn_id`（ticket 的 blueprint_refs 写这个）

{"comment": "煤炉交易号（success 必填）", "length": 64, "name": "mercari_txn_id", "nullable": true, "type": "str"}

## gz_jp_snap_purchase.mode

**锚 id**：`FIELD:gz_jp_snap_purchase.mode`（ticket 的 blueprint_refs 写这个）

{"comment": "auto自动/manual人工。入队时定，风控暂停时 auto 可批量改 manual", "dict": "gz_jp_snap_mode", "length": 16, "name": "mode", "nullable": false, "type": "dict"}

## gz_jp_snap_purchase.next_action_at

**锚 id**：`FIELD:gz_jp_snap_purchase.next_action_at`（ticket 的 blueprint_refs 写这个）

{"comment": "调度：下次执行 / 对账时间", "name": "next_action_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_purchase.order_item_id

**锚 id**：`FIELD:gz_jp_snap_purchase.order_item_id`（ticket 的 blueprint_refs 写这个）

{"comment": "FK gz_jp_order_item.id（支付回调重复推送靠此唯一键幂等）", "name": "order_item_id", "nullable": false, "type": "id", "unique": "uk_order_item"}

## gz_jp_snap_purchase.order_no

**锚 id**：`FIELD:gz_jp_snap_purchase.order_no`（ticket 的 blueprint_refs 写这个）

{"comment": "冗余订单号 = 跨系统幂等键（POST /v1/purchases 的 order_no）", "length": 32, "name": "order_no", "nullable": false, "type": "str"}

## gz_jp_snap_purchase.purchase_status

**锚 id**：`FIELD:gz_jp_snap_purchase.purchase_status`（ticket 的 blueprint_refs 写这个）

{"comment": "queued待下单/executing下单中/unknown结果不明(对账中)/manual_pending待人工/success已买到/failed未买到", "dict": "gz_jp_snap_purchase_status", "length": 20, "name": "purchase_status", "nullable": false, "type": "dict"}

## gz_jp_snap_purchase.rate_deadline_at

**锚 id**：`FIELD:gz_jp_snap_purchase.rate_deadline_at`（ticket 的 blueprint_refs 写这个）

{"comment": "评价期限 = arrived_at + rateDeadlineHours（REQ-SNAP-034）", "name": "rate_deadline_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_purchase.rated_at

**锚 id**：`FIELD:gz_jp_snap_purchase.rated_at`（ticket 的 blueprint_refs 写这个）

{"comment": "员工点「已评价」时间", "name": "rated_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_purchase.reconcile_count

**锚 id**：`FIELD:gz_jp_snap_purchase.reconcile_count`（ticket 的 blueprint_refs 写这个）

{"comment": "对账次数，满 3 次转人工（REQ-SNAP-029）", "default": "0", "name": "reconcile_count", "nullable": false, "type": "int"}

## gz_jp_snap_purchase.result_at

**锚 id**：`FIELD:gz_jp_snap_purchase.result_at`（ticket 的 blueprint_refs 写这个）

{"comment": "落终态（success / failed）时间 —— REQ-SNAP-038「1 分钟可见」按 paid_time→result_at 量", "name": "result_at", "nullable": true, "type": "datetime"}

## gz_jp_snap_purchase.snap_item_id

**锚 id**：`FIELD:gz_jp_snap_purchase.snap_item_id`（ticket 的 blueprint_refs 写这个）

{"comment": "FK gz_jp_snap_item.id", "name": "snap_item_id", "nullable": false, "type": "id"}

## gz_jp_snap_purchase.trade_status

**锚 id**：`FIELD:gz_jp_snap_purchase.trade_status`（ticket 的 blueprint_refs 写这个）

{"comment": "none未成交/await_ship待卖家发货/shipped卖家已发货/arrived已到仓/rated已评价/returned已退货/cancelled交易取消（卖家取消、已发货后丢件、事务局取消，可从 await_ship 或 shipped 进入）", "default": "none", "dict": "gz_jp_snap_trade_status", "length": 20, "name": "trade_status", "nullable": false, "type": "dict"}

## gz_jp_snap_purchase.version

**锚 id**：`FIELD:gz_jp_snap_purchase.version`（ticket 的 blueprint_refs 写这个）

{"comment": "乐观锁版本号 @Version（抢任务用条件更新）", "default": "0", "name": "version", "nullable": false, "type": "int"}

## gz_jp_snap_term.enabled

**锚 id**：`FIELD:gz_jp_snap_term.enabled`（ticket 的 blueprint_refs 写这个）

{"comment": "启用", "default": "1", "name": "enabled", "nullable": false, "type": "bool"}

## gz_jp_snap_term.id

**锚 id**：`FIELD:gz_jp_snap_term.id`（ticket 的 blueprint_refs 写这个）

{"comment": "主键", "name": "id", "nullable": false, "type": "id"}

## gz_jp_snap_term.ja_term

**锚 id**：`FIELD:gz_jp_snap_term.ja_term`（ticket 的 blueprint_refs 写这个）

{"comment": "日文词（如「ブルーロック」「缶バッジ」）", "length": 128, "name": "ja_term", "nullable": false, "type": "str"}

## gz_jp_snap_term.sort_no

**锚 id**：`FIELD:gz_jp_snap_term.sort_no`（ticket 的 blueprint_refs 写这个）

{"comment": "同一中文前缀多条命中时的优先级，越小越前", "default": "0", "name": "sort_no", "nullable": false, "type": "int"}

## gz_jp_snap_term.term_type

**锚 id**：`FIELD:gz_jp_snap_term.term_type`（ticket 的 blueprint_refs 写这个）

{"comment": "ip作品/character角色/goods品类", "dict": "gz_jp_snap_term_type", "length": 16, "name": "term_type", "nullable": false, "type": "dict"}

## gz_jp_snap_term.zh_term

**锚 id**：`FIELD:gz_jp_snap_term.zh_term`（ticket 的 blueprint_refs 写这个）

{"comment": "中文词（如「蓝色监狱」「吧唧」）", "length": 64, "name": "zh_term", "nullable": false, "type": "str", "unique": "uk_zh_term"}

## gz_user.app_id

**锚 id**：`FIELD:gz_user.app_id`（ticket 的 blueprint_refs 写这个）

{"comment": "★ 新增列：所属小程序 appid。唯一键由 (tenant_id, openid) 改为 (tenant_id, app_id, openid)；存量行回填现小程序 appid", "default": "wx2f8b93e09703f07d", "length": 32, "name": "app_id", "nullable": false, "type": "str"}

## gz_user.openid

**锚 id**：`FIELD:gz_user.openid`（ticket 的 blueprint_refs 写这个）

{"comment": "既有列，唯一约束变更为含 app_id", "length": 64, "name": "openid", "nullable": false, "type": "str", "unique": "uk_tenant_app_openid"}
