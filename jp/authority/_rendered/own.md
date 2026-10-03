# 领域主权表

> 本文件由 `authority_lint.py render` 从 `doc/authority/*.yaml` 自动生成。**别手改**——改权威改 YAML，手改这里下次 render 就被覆盖。

## 采购账号状态与限额

**锚 id**：`OWN:gz_jp_snap_account`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：ruoyi
**同步方向**：mercari-gateway → ruoyi 单向，经心跳拉取
**业务键**：account_code

ruoyi 唯一写入：admin_enabled / daily_limit / cooldown_sec 由 admin 写；health_status / last_heartbeat_at 由 ruoyi 心跳任务
按日本服务 /v1/health 的返回写（写入方仍是 ruoyi，日本服务只提供数据）；today_count 由 ruoyi 下单执行器写。
日本服务按 account_code 识别账号，不读这张表——限额与冷却由 ruoyi 调度保证。

## 代切商品缓存 + 孤品互斥锁

**锚 id**：`OWN:gz_jp_snap_item`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：ruoyi
**同步方向**：不同步
**业务键**：platform + external_id

ruoyi 唯一写入（详情实时查询后 upsert；active_order_item_id 只在提交订单 / 关单 / 失败 / 退款事务里改）。日本服务不可见。

## 代切下单任务与交易跟踪状态

**锚 id**：`OWN:gz_jp_snap_purchase`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：ruoyi
**同步方向**：不同步（日本服务看不到这张表）
**业务键**：order_no

ruoyi 唯一写入。日本服务只返回调用结果（success / failed / unknown + 证据），无权写 ruoyi 任何表；
人工代买的结果由 admin 写入同一张表。状态只进不退：success / failed 为终态，trade_status 按序推进。

## 采购账号登录态、Cookie、凭据、浏览器配置目录

**锚 id**：`OWN:mercari_account_session`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：mercari-gateway
**同步方向**：不同步；ruoyi 只经 /v1/health 拿到健康摘要
**业务键**：account_code

日本服务唯一持有；ruoyi 永不持有、永不传输账号密码或 Cookie（ruoyi 只知道 account_code）。
登录 / 重新登录由日本员工远程在日本服务的浏览器里手工完成。

## 煤炉商品实时状态（在售 / 价格 / 运费承担 / 描述）

**锚 id**：`OWN:mercari_item_live`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：mercari
**只读方**：mercari-gateway, ruoyi
**同步方向**：按需拉取（ruoyi → mercari-gateway → mercari），不推送
**业务键**：platform + external_id

唯一权威 = 煤炉。ruoyi 的 gz_jp_snap_item 只是缓存副本，可能过期：报价、提交订单、自动下单三个时点都必须以实时查询为准。
日本服务只转述不改写（不做翻译、不做过滤，过滤是 ruoyi 的规则）。

## 「这件商品在煤炉上到底买没买」这个事实

**锚 id**：`OWN:mercari_purchase_fact`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：mercari
**只读方**：mercari-gateway, ruoyi
**同步方向**：ruoyi 主动对账拉取（GET /v1/purchases/{order_no}/reconcile）
**业务键**：order_no + external_id

唯一权威 = 煤炉上采购账号的购买记录。ruoyi 的 purchase_status 是对它的**记录**，不是它本身：
两者不一致时（结果不明 / 网络断开），以日本服务对账查到的煤炉购买记录为准，ruoyi 据此改正自己的状态，再决定动不动钱。
日本服务本地的幂等记录（order_no → 交易号）只是加速缓存，丢了也不影响正确性。

## 下单证据（截图 / 页面快照）

**锚 id**：`OWN:snap_evidence`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：ruoyi
**只读方**：mercari-gateway
**同步方向**：mercari-gateway → ruoyi 单向，随 POST /v1/purchases 响应
**业务键**：order_no + 序号

日本服务产出、随调用结果回传；ruoyi 存 gz_file_object（usage_type=snap_evidence，保留 180 天）后即为权威副本。
日本服务本地副本只保留 7 天（排障用），不作凭据。

## 代切相关的钱（订单金额、支付、退款、差价）

**锚 id**：`OWN:snap_money`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：ruoyi
**同步方向**：不同步
**业务键**：order_no

ruoyi 唯一权威（gz_jp_order / gz_jp_order_item / gz_jp_refund / gz_pay_transaction）。日本服务完全不可见、不参与计算；
它只拿到「锁定日元价」这一个上限值用于下单前核价。

## 代切运营配置（定价 / 过滤 / 准入 / 交易参数 / 自动下单总开关）

**锚 id**：`OWN:snap_runtime_config`（ticket 的 blueprint_refs 写这个）
**唯一写入方**：ruoyi
**同步方向**：不同步
**业务键**：config_key

ruoyi 唯一写入（sys_config 的 gz.jp.snap.* 键；admin 写，自动下单开关另允许 ruoyi 熔断逻辑写 false）。
★ 准入判定与过滤只在 ruoyi 执行，日本服务不持有这些规则 —— 避免两边规则漂移。
