---
ticket: GZ-SNAP-304
track: SNAP
phase: D9
size: L
req_refs: [REQ-SNAP-004, REQ-SNAP-026, REQ-SNAP-035, REQ-SNAP-037, REQ-SNAP-041, REQ-SNAP-046]
depends_on: [GZ-SNAP-303, GZ-JP-110, GZ-PAY-106]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - doc/jp/_accept/**
blueprint_refs:
  - FLOW:F-JP-06.step2
  - FLOW:F-JP-06.step3
  - FLOW:F-JP-12.step3
  - FLOW:F-JP-06.step4
  - FLOW:F-JP-06.step5
  - FLOW:F-JP-10.step1
  - FIELD:gz_jp_snap_item.active_order_item_id
  - FIELD:gz_jp_order_item.product_snapshot_json
  - FIELD:gz_jp_snap_purchase.order_item_id
  - FIELD:gz_jp_snap_purchase.mode
  - FIELD:gz_jp_snap_purchase.purchase_status
  - FIELD:gz_jp_snap_purchase.locked_price_jpy
  - OWN:gz_jp_snap_item
accept:
  - name: 孤品锁真并发：同一商品 10 个并发提交只有 1 单成功，其余在提交时被拦
    form: DATA
    run: bash doc/jp/_accept/snap-submit-race.sh
    counterfeit: 锁只在 Java 内存 / 先查后写不加 FOR UPDATE → 并发下出现 ≥2 张订单 → 脚本断「不同订单号=1 且库里该商品有效订单行=1」红
  - name: 支付回调同事务写下单任务，重复回调不重复写；准入 manual / 总开关关闭 → 直接进人工
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapPaidTaskTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapPaidTaskTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapPaidTaskTest.xml
    counterfeit: 回调里直接调日本服务下单，或重复回调写出第二条任务（缺 uk_order_item 兜底）→ 红
  - name: 报价过期 / 不属于本商品 / 未勾「不可取消」/ 实时复查已售出或涨价 一律拒单（付款前拦下）；本人未付款再提交返回原订单；关单与下单失败释放商品锁
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapSubmitTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapSubmitTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapSubmitTest.xml
    counterfeit: 超时关单后 active_order_item_id 没清（商品永远被锁）、ackNoCancel=false 仍能下单、提交时不复查（报价后已售出仍能付款）、或本人关掉收银台后再买被自己的锁挡住 / 新建了第二张单 → 红
---

# GZ-SNAP-304 代切提交订单 + 孤品锁 + 支付回调写下单任务

## §0 状态自检

1. GZ-SNAP-303 / GZ-JP-110 完工。
2. 读一期下单事务与支付回调：`IGzJpOrderService.submit` / `onPaid`、`JpPayCallbackHandler`（回调事务边界：GZ-PAY 回调事务内 REQUIRED 传播）。
3. 读 `FLOW:F-JP-06.step3` 的锁判定条件（`active_order_item_id` 非空**且该行订单仍 created/paid 且未失败**才拒——防止脏锁永久挡单）。
4. dev mp 模拟登录：`POST /app/gz/common/auth/wx-login`（带 clientid header，jp 用 `mp-applet-gz-jp`），见 memory「新建gz角色…附 dev mp mock 登录法」。

## What

1. `POST /app/gz/jp/snap/order/submit {quoteId, addressId, ackNoCancel, userNote}`（需登录）：
   **事务外先实时复查一次**（`GET /v1/items`，纸面推演 P4）：已不在售 → `SNAP_SOLD_OUT`；当前价 > 报价日元价 → `SNAP_PRICE_CHANGED`（前端回详情重新报价）；
   运费承担与报价时不一致 → `SNAP_PRICE_CHANGED`；日本服务不可用 → `SNAP_UPSTREAM_DOWN`；当前价 ≤ 报价价照常。复查结果顺手 upsert `snap_item`。
   然后一个事务内：报价校验（存在 / 未过期 / 属于该商品）→ `SELECT … FOR UPDATE` 锁 `gz_jp_snap_item` → 锁判定 →
   **占用者是本人且订单仍 created → 不新建，返回原订单并重新下发支付参数**（原支付单仍 pending 且未过期 → 复用 prepay；已过期 → 新建一笔支付单，旧的已由 GZ-PAY-106 在微信侧过期）（REQ-SNAP-046）；
   占用者是别人 → `SNAP_ITEM_LOCKED`；本人已付款 → `SNAP_ALREADY_BOUGHT`；否则
   建 `gz_jp_order` + 1 行 `gz_jp_order_item`（`source=snap`、`product_id` 空、`snap_item_id`、`qty=1`、`amount_cent=totalCent`）→
   报价整体写快照 `snap` 段 → 回写 `active_order_item_id`。`snap.mainImageUrl`保存原图兜底；读侧改写为备案CDN/自有代理地址，不直接下发煤炉外网图片URL。主图转存 `gz_file_object` 放事务提交后异步做，失败只告警，成功补`mainImageId`；旧快照缺少新字段时正常读取。
   支付拉起复用一期 jp 支付链路（`business_type='jp'`），不新建支付入口。
2. 支付回调：jp `onPaid` 里对 `source=snap` 的行同事务插入 `gz_jp_snap_purchase`：
   `mode = (gate=manual 或 auto.enabled=false) ? manual : auto`；manual → `manual_pending` + `manual_reason`（gate:<规则> / auto_paused）；
   auto → `queued`、`next_action_at=now`；`locked_price_jpy=快照 priceJpy`、`order_no` 冗余。唯一键 `order_item_id` 兜底幂等。**回调里不调日本服务。**
3. 商品锁释放点统一成一个方法 `releaseSnapLock(orderItemId)`（条件更新：只有 `active_order_item_id` 仍等于该行才置空），并挂进：
   GZ-JP-110 的关单事务、mp 主动取消订单（若一期有该入口）、后续下单失败（305 / 306 / 307 调用）。
4. 并发脚本 `doc/jp/_accept/snap-submit-race.sh`：模拟登录取 token → 对同一商品取一次报价 → 10 个并发 submit →
   断言所有成功响应里的 orderNo **只有 1 个不同值**、其余返回 `SNAP_ITEM_LOCKED`，再查库该商品 created/paid 的代切订单行恰好 1 个。
   （按「不同订单号」断言而不是「成功次数」：K1 若拍板「同一客人重复提交返回原订单」，同一用户的并发会合法地多次成功、但只能有一张单。）
   脚本自带前置：后端 8080 在跑且 jar 是当前 commit（反 stale），否则 exit 1。

## AC

- 三条 accept 绿；一期拼团下单与支付回调单测照旧绿。
- 代切订单一单只有一行；提交接口不接受数量与价格入参（全取报价）。
