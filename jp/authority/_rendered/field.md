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

{"comment": "商品 FK gz_jp_product.id", "name": "product_id", "nullable": false, "type": "id"}

## gz_jp_order_item.product_snapshot_json

**锚 id**：`FIELD:gz_jp_order_item.product_snapshot_json`（ticket 的 blueprint_refs 写这个）

{"comment": "下单时商品快照（名/图/价/注意事项），商品后续改动不影响已下单", "name": "product_snapshot_json", "nullable": false, "type": "text"}

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

## gz_jp_order_item.source

**锚 id**：`FIELD:gz_jp_order_item.source`（ticket 的 blueprint_refs 写这个）

{"comment": "来源 batch=拼团。★ 为二期代切 snap 预留维度（REQ-SNAP-004），二期加值不改表", "default": "batch", "dict": "gz_jp_item_source", "length": 16, "name": "source", "nullable": false, "type": "dict"}

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

## gz_user.app_id

**锚 id**：`FIELD:gz_user.app_id`（ticket 的 blueprint_refs 写这个）

{"comment": "★ 新增列：所属小程序 appid。唯一键由 (tenant_id, openid) 改为 (tenant_id, app_id, openid)；存量行回填现小程序 appid", "default": "wx2f8b93e09703f07d", "length": 32, "name": "app_id", "nullable": false, "type": "str"}

## gz_user.openid

**锚 id**：`FIELD:gz_user.openid`（ticket 的 blueprint_refs 写这个）

{"comment": "既有列，唯一约束变更为含 app_id", "length": 64, "name": "openid", "nullable": false, "type": "str", "unique": "uk_tenant_app_openid"}
