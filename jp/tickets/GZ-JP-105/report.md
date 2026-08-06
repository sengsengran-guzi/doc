# GZ-JP-105 完工报告 — 订单 + 订单行建表 + 下单事务 + 支付回调

> **结论：accept 三条全 PASS。** 单测 122 全绿（本卡新增 27）；gz-common 回归 220 全绿。
> **真库全链路已实跑**：登录 → 建地址 → 加购（跨两场）→ 下单 → mock 支付回调 → 订单 `paid` + 全部行 `purchasing`，含幂等、失效拦截、快照抗商品删除、**10 并发防重复提交**。**未 commit**。

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（`staging`，HEAD `fca8690c0`） | ✅ | 开工前 `git status --porcelain` 空 |
| 上游 GZ-JP-104 已 merge | ✅ | `fca8690c0 D4/GZ-JP-104: 购物车建表 + API` |
| 上游 GZ-SYS-022 已 merge | ✅ | `82af7f60f D1: 后端多 appid 底座（020/021/022/023）` |
| `PayBusinessType` 枚举位置 | ✅ | `ruoyi-gz-common/.../pay/enums/PayBusinessType.java`，原 4 值 test/preorder/gacha/pindou |
| `PayCallbackDispatcher` SPI 签名 | ✅ | `supportedBusinessType()` + `onPaid(GzPayTransaction)` + 默认 `buildShippingInfo()`；`@PostConstruct validate()` 建路由表、同 type 重复注册 fail-fast |
| Flyway append-only | ✅ | migration 目录只有 `??`（新增 2），**无 M/D/R**；活库最大 `V202608070548`，新建 `V202608070632/0633`（`date +V%Y%m%d%H%M`） |
| menu 段位空闲（本卡不占） | ✅ | `COUNT(*) WHERE menu_id BETWEEN 14015 AND 14099` → `0` |
| dict 号段空闲 | ✅ | `MAX(dict_id)=9281` / `MAX(dict_code)=92805` → 本卡取 9282-9285 / 92806-92821 |
| 编译基线 | ✅ | 改动前 `mvn -o compile -pl ruoyi-gz-jp -am` → BUILD SUCCESS |
| 权威蓝图已读 | ✅ | field-ssot `gz_jp_order`/`gz_jp_order_item`；flows `F-JP-02.step4/5/6` + `F-JP-03` + `F-JP-04`；requirements `REQ-ORDER-003/004/006/010`、`REQ-SNAP-004`、`REQ-FULFILL-003/006` |
| ADR | 无本域 ADR；沿用 `GzOrdOrderServiceImpl.submit` 范式；退款遵循 flows 里记的 ADR-0020 口径（本卡不碰退款） |

**蓝图关键约束摘录**：`total_amount_cent`「= Σ 行金额，★ 无运费项，后端重算不信前端」；`source`「batch，为二期代切 snap 预留，加值不改表」；`fulfill_status`「默认 purchasing，★ 允许跳过中间态」；`step6`「订单 paid；每个 order_item fulfill_status=purchasing」；`REQ-ORDER-004`「系统中彻底不做运费概念」；`REQ-ORDER-010`「不做店员代客下单」→ 只有 mp 写入口；`REQ-FULFILL-003/006`「状态挂行、按客人聚合跨订单」→ `order_item` 冗余 `user_id`、**不建包裹表**。

## 实现摘要（2 改 + 23 新增，+3287 行）

```
 M ruoyi-gz-common/.../pay/enums/PayBusinessType.java   +18 -2   ← 加 JP="jp" + 前缀 JPO
 M ruoyi-gz-jp/pom.xml                                  +10      ← 加 ruoyi-gz-user 依赖（地址簿，同 gz-ord 做法）
?? db/migration/V202608070632__GZ-JP-105-create-gz_jp_order-and-order_item.sql
?? db/migration/V202608070633__GZ-JP-105-seed-dict.sql
?? domain/entity/{GzJpOrder,GzJpOrderItem}.java
?? domain/enums/{GzJpOrderStatus,GzJpFulfillStatus,GzJpItemSource,GzJpRefundStatus}.java
?? domain/dto/JpOrderSnapshot.java · domain/bo/GzJpOrderSubmitBo.java
?? domain/vo/{GzJpOrderSubmitVO,GzJpOrderDetailVO,GzJpOrderItemVO,GzJpOrderListItemVO}.java
?? mapper/{GzJpOrderMapper,GzJpOrderItemMapper}.java · exception/GzJpOrderErrorCode.java
?? service/{IGzJpOrderService,impl/GzJpOrderServiceImpl}.java · service/callback/JpPayCallbackHandler.java
?? controller/applet/GzJpOrderMpController.java
?? test/.../{GzJpOrderSubmitTest,GzJpPayCallbackTest}.java
```

**未动** `PayRefundServiceImpl` / `PayRefundTxService` / `PayCallbackDispatcher` / `GzPayTransactionServiceImpl` 及拼豆/回收/预购/扭蛋任何一行 —— 新业务接入 GZ-PAY 零改动分发器。

**建表**：`gz_jp_order`（`uk_order_no(tenant_id,order_no)` + `uk_pay_transaction(tenant_id,pay_transaction_id)` + `idx_user_status` + `idx_paid_time`，**无运费列**）；`gz_jp_order_item`（`idx_user_fulfill` / `idx_order` / `idx_tracking`）。两表七件套齐，`tenant_id VARCHAR(20) DEFAULT '1001'` 且 INSERT 不显式赋值。

**字典**（dict_id 9282-9285 / dict_code 92806-92821）：`gz_jp_order_status`(5) / `gz_jp_item_source`(1) / `gz_jp_fulfill_status`(7) / `gz_jp_refund_status`(3)。**106/107/108 不要再 seed**（撞 dict_code 主键）；`gz_express_carrier`(9130) 复用不新建。

**下单事务顺序**（刻意如此）：① 拉本人勾选行 → ② 批量取商品+场（`selectOptionMap` 给生效状态，写路径认严格闸 `open`）→ ③ **全量校验后再写任何一行**，一次报全并点名商品 → ④ 地址归属 → ⑤ **后端重算金额**（`expectedAmountCent` 只做比对闸 4104，永不作为成交价）→ ⑥ `PayOrderNoGenerator.generate(JP)` → `JPO-yyyyMMdd-6位`，**一次配齐字段 insert**（`@Version` 坑）撞 UNIQUE 先 `reconcileOutTradeNoToDbMax` 再重试（5 次）→ ⑦ 逐行 insert（快照**存 file id 不存 URL**）→ ⑧ 清车（**同时是防重复提交串行点**）→ ⑨ `createBusinessOrder(business_type=jp)` 放最后（唯一可能触网）。

**支付回调**：行锁 → `markPaid`（`WHERE business_status='created'`，幂等第一道）→ affected=1 才 `activatePurchasing`（`WHERE fulfill_status='purchasing'`，幂等第二道，重放不会把已 `jp_shipped` 的行打回）。`pay_transaction_id` 存 **`gz_pay_transaction.id`（本地流水行主键）**，不是微信交易号字符串。

### ★ 实测发现并修复的真缺陷：同一份购物车可并发提交出 N 张订单

真库 10 并发提交同一份车 → **生成 10 张订单**。修复：清车实删行数与读到行数比对，不符即判重复提交整单回滚（4107）——InnoDB 的 X 锁把并发在 DELETE 处串行化。修复后重跑：**恰好 1 张 200 + 9 个 4107，DB 净增 1，无孤儿支付流水**。

### 超出 What 的最小补充

`GET /app/gz/jp/order/{id}` + `GET /app/gz/jp/order/list` —— 204/205 的 `touches` 只写了 `miniapp-jp/**`，没有后端 ticket 认领这两个读端点，不补即阻塞。纯读 + 快照还原，无新表无新菜单。

## AI 自测（Tier 1A）

### 1. accept[1] 两表建表且公共字段全集齐 ✅

```
$ for T in gz_jp_order gz_jp_order_item; do docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
    SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='ry-vue' AND table_name='$T'
    AND column_name IN ('create_by','create_time','update_by','update_time','create_dept','del_flag','tenant_id')" \
    | grep -qx 7 || exit 1; done
ACCEPT1_EXIT=0
```
```
$ flyway_schema_history（真 Flyway 应用，非手工建表）
202608070633 V202608070633__GZ-JP-105-seed-dict.sql                       1
202608070632 V202608070632__GZ-JP-105-create-gz_jp_order-and-order_item.sql 1
启动日志: Successfully applied 2 migrations to schema `ry-vue`, now at version v202608070633
          Started DromaraApplication in 11.837 seconds
SHOW TABLES: gz_jp_cart_item / gz_jp_event / gz_jp_order / gz_jp_order_item / gz_jp_product
dict: 9282 gz_jp_order_status / 9283 gz_jp_item_source / 9284 gz_jp_fulfill_status / 9285 gz_jp_refund_status
```

### 2. accept[2] 金额后端重算，前端篡改价不生效 ✅

```
$ mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dsurefire.failIfNoSpecifiedTests=false -Dtest=GzJpOrderSubmitTest
[AC2] 前端假价 1 分被拒，后端算出的正确金额=58000 分，未建任何支付单
[AC2] 后端重算金额=58000 分；Σ行金额=58000（无运费差额）
[AC3] 一单含两场：[8月上旬快闪场, 9月新番场]，合计=18800 分
[@Version] 订单 1 次 insert / 行 2 次 insert / updateById 0 次
[防重复提交] 读 2 行 / 实删 1 行 → 4107，且未建支付单
[撞号自愈] 首次撞 uk_order_no → reconcile → 第二个号成功：JPO-20260807-000009
[快照] {"productId":"1","productNo":"JPP-20260807-000001","name":"柯南 吧唧 A赏","mainImageId":"8888",
        "priceCent":12800,"deliveryDateText":"8月下旬","noticeText":"★ 日本直邮，介意瑕疵慎拍",
        "eventId":"100","eventNo":"EVT-2026-100","eventName":"8月上旬快闪场"}
[无运费] 7 个类字段全扫，无 freight / shipping / postage
Tests run: 21, Failures: 0, Errors: 0, Skipped: 0
ACCEPT2_EXIT=0
```

### 3. accept[3] 支付回调后订单转 paid 且全部行进入购买中 ✅

```
$ mvn -q test ... -Dtest=GzJpPayCallbackTest
[gz-pay] 支付回调 SPI 路由表就绪，已注册 1 个 handler：[jp]
[AC3] 建单 out_trade_no=JPO-20260807-000001 business_type=jp 订单初态=created
[gz-pay] SPI 分发支付回调 business_type=jp → JpPayCallbackHandler
[gz-jp-order] onPaid ok orderNo=JPO-20260807-000001 → paid payTxnId=7000 激活商品行=3 行
[AC3] 回调后 订单=paid pay_transaction_id=7000 商品行=[purchasing, purchasing, purchasing]
[gz-pay] 重复回调（已 paid）out_trade_no=JPO-20260807-000001
[幂等] 两次回调后 订单 version=1 行 version=[1, 1] callback_logs=4
Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
ACCEPT3_EXIT=0
```
用真 `MockWechatPayClient` + 真 `PayCallbackDispatcher` + 真 handler + 真 service，**只有 mapper 是 in-memory 且照搬了 SQL 的 WHERE 状态守卫** —— 幂等靠的就是那两道守卫，用 mock 桩替掉等于没测。

### 4. ★ 真库全链路（独立实例 `:8081`，不碰并行 agent 的 `:8080`，clientid=`mp-applet-gz-jp`）

```
1) mp 登录 → userId=14 openid=mock-jp-tester      2) 地址 → addressId=1      3) 加购 商品1×4
4) 购物车 validAmountCent = 51200
5) ★ 下单传假价 1 分 → {"code":4104,"msg":"商品价格有变动，当前应付 512.00 元，请确认后重新提交"}
6) 正常下单 → {"code":200,"data":{"orderId":"1","orderNo":"JPO-20260807-000001","totalAmountCent":51200,
   "itemCount":1,"payParams":{"packageVal":"prepay_id=mock_prepay_JPO-20260807-000002","signType":"RSA",
   "paySign":"mock_pay_sign_...","outTradeNo":"JPO-20260807-000002"}}}
7) 下单后购物车 itemCount = 0     8) 支付前 businessStatus=created；freight fields present?: []
9) mock 支付回调 {"code":200}
10) ★ 回调后 businessStatus=paid 已支付 paidTime=2026-08-07 06:56:25；items fulfill=[('1','purchasing')]
11) 幂等：同一笔回调再发一次 {"code":200}
12) 订单列表 total=1  JPO-20260807-000001 paid 款数=1 件数=4 实付=51200 图=1
```
**AC3 一单多场（真库，自建两场 fixture）**：
```
购物车 groups = [('901','GZ-JP-105 第二场（多场同单验证）',1), ('1','8月上旬快闪场',1)]
一次下单 → orderId=2 orderNo=JPO-20260807-000003 totalAmountCent=46000 itemCount=2
详情: 柯南 吧唧 A赏 | 场=8月上旬快闪场 | qty=2 | 25600 | purchasing
      第二场商品    | 场=GZ-JP-105 第二场 | qty=3 | 20400 | purchasing
Σ行金额 = 46000（== total，无运费）
```
DB 落库核对：
```
gz_jp_order: 1 JPO-…000001 14 51200 paid 32 06:56:25 1001 0 1 / 2 JPO-…000003 14 46000 paid 33 06:57:41 1001 0 1
pay_transaction_id 指向本地流水行：order_no=JPO-…000001 pay_transaction_id=32 = txn.id=32
  （out_trade_no=JPO-…000002 business_type=jp status=paid wx_txn=mock_wx_txn_…）
gz_jp_order_item: 3 行，source=batch fulfill=purchasing carrier/tracking/refund 全 NULL tenant=1001 del=0 version=1
金额守恒: 51200-51200=0 / 46000-46000=0
快照: {"productId":"901","productNo":"JPP-TMP105-000001","name":"…","mainImageId":"1","priceCent":6800,
       "deliveryDateText":"9月下旬","noticeText":"第二场注意事项：需转运","eventId":"901","eventNo":"…","eventName":"…"}
```
真库错误路径 + 快照韧性：
```
A) 场已结束   4102「…「GZ-JP-105 第二场商品」所在的场已结束」
B) 商品下架   4102「…「GZ-JP-105 第二场商品」已下架」
C) 别人地址   4103   D) 未登录 401   E) 别人订单 4105「订单不存在」   F) 空勾选 4101
G) ★ 商品与场都软删后再读订单详情 → 名/场名/单价/notice/图 全在（快照抗删除）
```
顺带被真数据验到：4104 是把预期额算错（46000 写成 45400）时**主动拦下**的，且那次失败后购物车原样保留（`itemCount = 2`）——下单失败不清车，事务边界正确。

### 5. ★ 并发 10 并发提交同一份购物车（修复前/后对照）

```
修复前：10 个响应全 200 → DB 10 张订单（JPO-…000005 … 000014）      ← 真缺陷
修复后：1 个 200（JPO-…000025）+ 9 个 4107；DB 净增 1；jp 流水 13 == jp 订单 13（无孤儿流水）
```

### 6. 回归

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp
21 GzJpOrderSubmitTest · 20 GzJpProductServiceTest · 17 GzJpEventStatusTest · 38 GzJpCartServiceTest
 · 20 GzJpProductMpQueryTest · 6 GzJpPayCallbackTest → Tests run: 122, Failures: 0, Errors: 0
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common   （因本卡改了 PayBusinessType）
Tests run: 220, Failures: 0, Errors: 0 — BUILD SUCCESS
```
中途踩到：不带 `-am` 跑 gz-jp 测试报 `IllegalArgument 未知支付业务类型: jp` —— 用的是 `~/.m2` 旧 gz-common jar。改 gz-common 后必须 `mvn clean install -pl gz-common,gz-user,gz-jp -am`。

## 风险提示 / 已知 issue

1. **⚠️ `fulfill_status` 列默认就是 `purchasing`，未支付订单的行看起来也在「购买中」**（field-ssot 定的默认值，本卡照办）。**106/108 任何「采购/推进/发货」查询必须 join `gz_jp_order` 过滤 `GzJpOrderStatus.isPaidLike`**，漏了 = 店员拿没付钱的单去日本下单。已写进 `GzJpOrderItemMapper` 类注释。
2. **拼团 GMV 不进 4% 分成**：recon 三个 service 显式只算 preorder+gacha。本卡**刻意没动对账域** —— 纳入分成属商业口径变更（合同 §4.1），须客户书面确认后另开 ticket。已写进 `PayBusinessType.JP` javadoc 防后来者顺手加。
3. **微信「订单中心」发货信息未上报**（`buildShippingInfo` 保持默认空）：拼团到货几周到几个月、发货靠店员手填顺丰单号，支付当下无可上报的发货事实。**但项目记忆里发货上报对拼豆是强制项且影响资金结算** —— 拼团是否同样被要求、要不要在置 `delivered` 时补报，**需甲方向微信商户侧确认**，建议 106 实施前拍板（要接就接在 106 的发货动作里，不是支付回调）。
4. **未支付订单靠 GZ-PAY 5 分钟超时关单，而它是 SnailJob `@JobExecutor` —— prod 未部署 SnailJob**。后果：prod 的 jp 未支付单长期停 `created`（不影响资金）。`markCancelled` 已备好，要做手动/惰性关单时接上。
5. **本卡无 admin 端点、无菜单**（14020 归 109、14030 归 108）—— 预期内。
6. **dev 库留 2 张已支付订单**（`JPO-20260807-000001` / `000003`，userId=14）作 108/109/205 的 fixture（109 accept 要 `.rows[0]`）。并发压测产生的 11 张垃圾单及流水已清（清理后 jp 流水 2 = jp 订单 2）。临时场/商品 `id=901` 已软删（客人不可见，订单详情靠快照仍完整）。
7. **待 Kevin 残留人验：N/A** —— 纯后端，无 mp/admin 页面、不碰真机原生。真机 1 分钱验证属 204 上线前节点。

## 对下游 ticket 的提示

### 给 GZ-JP-204（mp 下单确认 + 支付）

```jsonc
POST /app/gz/jp/order      // 需登录；header clientid: mp-applet-gz-jp
{ "cartItemIds":["12","13"],  // 【购物车项 id】不是商品 id；最多 50
  "addressId":"3", "userNote":"…", "expectedAmountCent":51200 }  // expected 可选，只做比对
200 { "code":200,"data":{ "orderId":"8","orderNo":"JPO-20260807-000001",
      "totalAmountCent":51200,   // ★ 后端重算的成交价，以它刷新确认页
      "itemCount":2,
      "payParams":{"timeStamp","nonceStr","packageVal":"prepay_id=…","signType":"RSA","paySign","outTradeNo"} } }
```
| code | 含义 | 前端动作 |
|---|---|---|
| 4101 | 勾选项都不属本人/车已空 | 回购物车重拉 |
| 4102 | 有商品失效（msg 点名） | **退回购物车高亮**，别原地重试 |
| 4103 | 地址无效 | 重选地址 |
| 4104 | 价格与确认页不一致（msg 带正确金额） | 刷新确认页重新确认 |
| 4107 | 重复提交（并发/双击） | **不要重试**，去「我的订单」看那张单 |
| 401 | 未登录 | 走 `ensureLoggedIn` |

- `payParams` 直接喂 `uni.requestPayment`，字段名是 **`packageVal`**（JS 保留字），调起时映射 `package: payParams.packageVal`。
- **appid 后端按 clientid 解析**（GZ-SYS-022），前端不传不管。
- dev mock 支付：`POST /app/gz/test/pay/simulate-callback?outTradeNo=<payParams.outTradeNo>`（**用户自助版 `/app/`，不是 admin 的 `/system/`**）。
- **提交按钮点一次即置灰**（4107 是后端兜底，不是让你依赖它）。
- **金额区只有商品合计与实付两行，无运费**（VO 里根本没有该字段，单测反射扫过）。

读端点（本卡已提供，205 直接用）：
```jsonc
GET /app/gz/jp/order/{id}     // R<GzJpOrderDetailVO>，读 res.data
{ "id","orderNo","totalAmountCent","businessStatus","businessStatusLabel","userNote",
  "address":{recipient,mobile,province,city,district,detail},      // 下单锁定的快照
  "items":[{ "id","productId","productNo","name","mainImageUrl"(恒非null),"deliveryDateText",
             "noticeText","eventName","qty","unitPriceCent","amountCent","source",
             "fulfillStatus","fulfillStatusLabel","carrierCode","trackingNo","shippedAt",
             "refundStatus","refundStatusLabel","refundAmountCent" }],
  "itemCount","totalQty","createTime","paidTime","cancelledTime" }

GET /app/gz/jp/order/list?pageNum=1&pageSize=10&businessStatus=created
// ★ 读 res.rows（TableDataInfo）不是 res.data —— D16 逮到过 6 处这类 bug
{ "rows":[{ "id","orderNo","totalAmountCent","businessStatus","businessStatusLabel",
            "itemCount","totalQty","thumbUrls":[…],"createTime","paidTime" }], "total":1 }
```
订单不存在/非本人 → `4105 订单不存在`（同码不泄漏）。**状态文案后端已给**，别在前端再维护映射。「待支付」tab = `businessStatus=created`；「进行中/已完成」看 `items[].fulfillStatus` 自行归组。金额单位**分**。

### 给 GZ-JP-106（履约状态机）

- **当前状态机就一句话**：下单落 `purchasing`（列默认值），支付回调显式激活一次（`activatePurchasing`，`WHERE fulfill_status='purchasing'` 幂等）。**除此没有任何转移逻辑**——状态链/合法转移/批量推进全归你。`GzJpFulfillStatus` 已定义 7 值 + `step` 位次（判倒退用；`purchase_failed` 与 `purchasing` 同为 step 1 = 分支不是前进）。**别在枚举里长第二份真源**。
- **★ 最重要**：查询必须 join 订单过滤 `isPaidLike`（见风险 1）。
- 字典 `gz_jp_fulfill_status`(9284/92812-92818) **本卡已 seed 别重 seed**；`gz_express_carrier`(9130) 复用。
- 置 `delivered` 时 `carrier_code`+`tracking_no`+`shipped_at` 必填（列 + `idx_tracking` 已建）；**不建包裹表**，同单号即同包裹。
- 批量推进传的行 id = 详情里 `items[].id`。实体是 `@Version`，自定义 UPDATE 记得 `version = version + 1`，**绝不 insert 后 updateById 补字段**。

### 给 GZ-JP-107（行级退款）

`refund_status` / `refund_amount_cent` 列已建、字典 9285(92819-92821) 已 seed、`GzJpRefundStatus` 已定义 —— 你只管链路。退款金额取**该行 `amount_cent`**（已落库）。`partial_refunded`/`refunded` 已在枚举+字典；`GzJpOrderMapper` 目前只有 `markPaid`/`markCancelled`，rollup 守卫 UPDATE 由你加（照现有 WHERE 状态守卫写法）。流水按 `business_order_no = order_no` 反查；本域 `pay_transaction_id` 存的是**流水行主键**，`selectById` 直接拿 `transaction_id`/`amount_cent`。

### 给 GZ-JP-108 / 109

菜单段位仍全空（14015-14099 → 0），父目录 14000 已由 101 建好**别重建**。dev 库已有 2 张已支付订单 + 3 条订单行喂 109 的 `.rows[0]`。109 的 `itemCount` 需 count 行 —— 本卡 mp 列表已实现同款（批量取本页所有行再分组，别逐单查 N+1），照抄即可。admin VO 建议**不复用** mp 的（mp 的不下发内部字段）。

### 编号段位现状

| 资源 | 已占 | 下一个空号 |
|---|---|---|
| `sys_menu` GZ-JP | 14000-14005、14010-14014；本卡未占 | 14020 段（109）/ 14030 段（108） |
| `dict_id` | 9280、9281、**9282-9285（本卡）** | **9286** |
| `dict_code` | 92801-92805、**92806-92821（本卡）** | **92822** |
| jp 业务错误码 | 4101-4107（本卡） | **4108** |
| Flyway | …V202608070633 | `date +V%Y%m%d%H%M` |

### 全 jp 域通用（本卡再次踩到）

- **改 gz-jp 或 gz-common 后必须 `mvn clean install`**，跑测试带 `-am`（否则用 `~/.m2` 旧 jar）。
- 单测类必须 `@Tag("dev")`。
- service 用 `Wrappers.lambdaQuery()` 时 `@BeforeAll` 要 `TableInfoHelper.initTableInfo(...)`。
- **Mockito 对已用 `thenAnswer` 桩过的方法二次改桩必须用 `doReturn(...).when(mock)`** —— `when(mock.foo(...))` 会真调一次旧 answer（本卡踩到 NPE）。
- **涉及并发的实现单测全绿不算数**，必须真库并发跑一轮（本卡正是这样逮到「一份车出 10 张订单」）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

建议覆盖：后端集成 `POST /app/gz/jp/order` 全链路（含 4101/4102/4103/4104/4107/401）+ 读端点用户隔离（A 的 token 读 B 的单必须 4105）；API 契约回归（字段名与「给 204」段逐字一致、ID 全 string、无运费字段、列表返 `rows`）；支付链路回归（`business_type='jp'` 建单+回调+重复回调幂等，**并回归拼豆/预购/扭蛋三条既有支付线未被 `PayBusinessType` 改动影响**）；并发回归（10 并发同车 → 1 张 + 9 个 4107 + 无孤儿流水）。本卡无 admin/mp 页面 → 无 Playwright / 模拟器 E2E 对象。⚠️ 跑前确认 8080 上是本卡 clean install 后的 jar（gz-common 与 gz-jp 都要重装，否则不认 `jp`）。

---

**环境交还**：起的 `:8081` 实例已关闭（`lsof :8081` → 0）；并行 agent 在用的 `:8080` 未被触碰、仍返回 200。测试脚本在 scratchpad，未污染项目目录。
