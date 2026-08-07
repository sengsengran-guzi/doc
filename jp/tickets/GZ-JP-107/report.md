# GZ-JP-107 完工报告 — 行级退款（购买失败 → 微信部分退款）

> **结论：accept 三条全 PASS**（ACCEPT1_EXIT=0 / ACCEPT2_EXIT=0 / ACCEPT3_EXIT=0）。
> **★ 3 个受保护文件一行未动**（`git hash-object` 与 `HEAD` 逐字节一致，整个 `ruoyi-gz-common` 模块 0 改动）。
> 单测 **456 全绿**（gz-common 220 / gz-user 42 / gz-jp 194，本卡新增 27）。
> **真库端到端已实跑**（独立实例 `:8082`，不碰在跑的 `:8080`）：24 个业务场景 + **2 轮真并发压测**。
> ⚠️ **真并发逮到一个真缺陷**（`selectByIdsForUpdate` 索引选择导致的死锁，**106 遗留、本卡修复**）—— 详见「§ 并发压测」。
> 1 个迁移（`V202608071102`，已真库应用）。**无菜单 / 无字典**（14030 段留给 108）。**未 commit**。

---

## §0 自检结果

| 检查项 | 结果 | 证据 |
|---|---|---|
| git clean（`staging`，HEAD `e52ed8727`） | ✅ | 开工前 `git status --porcelain` 空 |
| 上游 GZ-JP-106 已 merge | ✅ | `47110b805 D5/GZ-JP-106: 履约状态机 + 批量推进/批量发货 API` |
| **`PayRefundController` 是否支持指定金额** | ✅ **不支持**（ticket 已给结论，本卡复核一致） | `RefundApplyBo` 只有 `transactionId` + `reason`，**无金额入参** |
| **`IWechatPayClient.refund` 的 record 字段** | ✅ | `record RefundRequest(String outTradeNo, String outRefundNo, long refundAmountCent, long totalAmountCent, String reason, String notifyUrl)` —— `refundAmountCent` 与 `totalAmountCent` **确是两个独立参数**（走路线②的前提成立） |
| `MockWechatPayClient.refund` 形态 | ✅ | 受理返回 `RefundResult(refundId, "PROCESSING", rawBody)`；带 `setRefundAcceptFail(boolean)` 开关，**本卡单测直接用它驱动受理失败分支**（不是 Mockito 桩） |
| `RefundCallbackDispatcher` SPI 签名 | ✅ | `IRefundCallbackHandler { String supportedBusinessType(); void onRefunded(GzPayRefund, GzPayTransaction); }`，照 `PreorderRefundCallbackHandler` 范式实现 |
| **开工前 `git status --porcelain` 基线** | ✅ **空** | 所以完工时的每一处改动都是本卡产生的，`git diff` 即完整证据 |
| Flyway append-only | ✅ | `git status -- db/migration/` 只有 1 个 `??`（新增），无 `M`/`D`/`R`；时间戳取 `date +V%Y%m%d%H%M` = `V202608071102` > 当前 max `V202608071027` |
| menu 段位（本卡不占） | ✅ | 14030 段归 108（其 accept 断言该段 `COUNT(*)>=1`），本卡若 seed 会让 108 的父级校验失败 —— 同 106 的处置 |
| 字典（本卡不新建） | ✅ | `gz_jp_refund_status`（dict_id 9285）105 已 seed 三值 `refunding/refunded/refund_failed`，本卡**直接复用**（重复 seed 会撞 dict_code 主键） |
| 编译基线 | ✅ | 动手前 `mvn -o compile -pl ruoyi-gz-jp` → BUILD SUCCESS |
| 权威蓝图已读 | ✅ | `flows.yaml` F-JP-04.step1/2/3；`field-ssot.yaml` `gz_jp_order_item.{refund_status,refund_amount_cent}`；`ui-index.yaml` `UI:admin.fulfill_board.mark_failed` |
| ADR 已读 | ✅ | **ADR-0020 §3**（本卡权威边界）+ §1（状态挂行）；沿用 ADR-0007 双状态机正交范式 |

**蓝图关键约束摘录**：
- `F-JP-04.step2`「★ 退款金额 = 该 order_item 的 `amount_cent`，**不是整单**」+「**路线已定：jp 域开独立退款入口，只共用通道层**…拼豆/回收的资金链路一行不动，风险物理隔离」
- `F-JP-04.step3`「有失败行且非全部 → 订单 `partial_refunded`；全部行失败 → 订单 `refunded`」
- `field-ssot`：`refund_status`「仅 `purchase_failed` 行会有值」/ `refund_amount_cent`「已退金额（分），正常 = `amount_cent`」
- ADR-0020 §3 验收两条：「jp 行级退款通」+「拼豆/回收退款链路零改动」（**后者用 `git diff` 证明，不是靠回归测试证明**）
- 甲方口径：「购买失败」**不是异常而是常走的路**，健壮性等同主链路

**⚠️ 发现一处蓝图内部不一致（建议 108 之前修 doc，复盘优先级 #1）**：
`flows.yaml` 的 `F-JP-04.step3` 仍写着「退款回调走 GZ-PAY 现有 `RefundCallbackDispatcher`，`business_type='jp'`」——
这是**路线②拍板之前的旧话**（step2 已按新路线改写，step3 漏改）。
拼团退款单在 `gz_jp_refund`，而 `RefundCallbackDispatcher` 只在 `PayRefundServiceImpl` 的回调链路里被触发（前提是 `gz_pay_refund` 里有对应行），
**行级退款永远走不到它**。本卡的处理是「两条都做」：主路径自建回调端点；同时**仍注册**一个 `business_type='jp'` 的 SPI handler
去堵「admin 用支付管理页对 jp 单全额退款」的旁路（见下），所以 step3 的字面描述不算全错，但会误导下一个人。

---

## §实现摘要（4 改 + 23 新增，+188 / +3013 行）

```
 M mapper/GzJpOrderItemMapper.java              +93   ← ★ FORCE INDEX(PRIMARY) 防死锁 + 退款结果投影 + rollup 两个计数 + 全额退款旁路
 M mapper/GzJpOrderMapper.java                  +41   ← selectByIdForUpdate（rollup 串行化）+ markRefundRollup（守卫 UPDATE）
 M controller/GzJpFulfillController.java        +39   ← POST /mark-failed
 M domain/enums/GzJpRefundStatus.java           +18   ← isValid（筛选参数校验，同 106 口径）

?? db/migration/V202608071102__GZ-JP-107-create-gz_jp_refund.sql   90   ← ★ 退款单表（UNIQUE(tenant_id, order_item_id)）
?? domain/entity/GzJpRefund.java                              119
?? mapper/GzJpRefundMapper.java                               198
?? service/{IGzJpRefundService, impl/GzJpRefundServiceImpl}.java   114 + 655
?? service/internal/GzJpRefundTxService.java                  504   ← ★ 事务段（写库全收在这里）
?? service/internal/GzJpRefundNoGenerator.java                 89   ← JPRF- 号段（Redis 原子 + DB MAX 播种 + 撞号自愈）
?? service/internal/dto/GzJpRefundPlan.java                   127   ← 跨事务边界的唯一传递物
?? service/callback/JpRefundCallbackHandler.java               62   ← 退款 SPI（堵 GZ-PAY 全额退款旁路）
?? controller/GzJpRefundController.java                        92   ← 退款单列表 + 重新发起
?? controller/external/GzJpRefundNotifyController.java        120   ← ★ 拼团专属退款回调端点
?? config/GzJpPayProperties.java                               33
?? domain/bo/{GzJpMarkFailedBo, GzJpRefundQueryBo}.java        45 + 52
?? domain/vo/{GzJpMarkFailedResultVO, GzJpRefundLineVO, GzJpRefundAdminVO}.java   70 + 60 + 100
?? domain/dto/GzJpRefundRow.java                               43
?? domain/enums/GzJpRefundSkipReason.java                      44
?? test/.../{GzJpRefundFixture, GzJpRefundStatusRollupTest, GzJpRefundCallbackIdempotentTest}.java   428 + 442 + 293
```

**零改动区**：`ruoyi-gz-common` **整模块 0 文件改动**（含 `PayRefund*` 三件套 / `IWechatPayClient` / `RefundCallbackDispatcher`）、
`ruoyi-gz-bean`（拼豆）/ `ruoyi-gz-ord`（预购）/ `ruoyi-gz-gacha`（扭蛋）/ `ruoyi-gz-user` / `ruoyi-gz-news` 全 0 改动、
`GzJpFulfillServiceImpl`（106 的服务层）/ `GzJpFulfillStateMachine` / `GzJpOrderServiceImpl` 一行未动。

### 架构：路线② 的落地形状

```
【拼豆 / 回收】admin → PayRefundController → PayRefundServiceImpl → PayRefundTxService → IWechatPayClient
                                                                          ↑ 本卡完全不碰
【拼团 107】  admin → GzJpFulfillController#markFailed → GzJpRefundServiceImpl ─────────→ IWechatPayClient
                                                              ↓                            ↑ 只共用这一层
                                                        GzJpRefundTxService（写 gz_jp_refund）
              微信 ──→ /api/gz/jp/pay/refund-notify（★ 拼团专属，与 /api/pay/v3/refund-notify 分开）
```

**为什么必须有自己的回调端点**（这是路线②里最容易漏、漏了最贵的一处）：
`/api/pay/v3/refund-notify` 按 `out_refund_no` 去 **`gz_pay_refund`** 找退款单，找不到就返 500。
拼团退款单在 `gz_jp_refund` —— 打过去必然 500，微信按退避策略重试到放弃，
最终**钱已经退给客人了，系统里那笔单永远停在「退款中」**。而退款请求的 `notify_url` 是**逐笔可指定**的，所以两条链路物理隔离。
回调地址解析顺序：`gz.jp.pay.refund-notify-url` → 从 `gz.pay.refund-notify-url` 的 origin 推导（**所以正常部署不用配**）→
mock 通道允许空 → **real 通道 fail-fast 拒绝发起退款**（宁可退不了款，也不能退了款却收不到回调）。

### 五道防重复退款的闸（按从硬到软排）

1. **DB 唯一键 `UNIQUE(tenant_id, order_item_id)`** —— 一个商品行至多一条退款单。并发 / 重复点击 / 回调重放全部撞在数据库上，不依赖任何应用层判断。**刻意不含 `del_flag`**：退款单是资金凭证，本域从不软删；含 `del_flag` 反而给「软删一条再退一次」留后门。
2. **退款单状态守卫 UPDATE**（`WHERE status='refunding'`）—— 回调幂等的落点，affected=0 即判定为重复。
3. **重试复用同一个 `refund_no`** —— 微信按 `out_refund_no` 幂等，换新号才会真的退两次。
4. **超退兜底**：`SUM(已占用) + 本次 ≤ 原支付单总额`，超了拒绝提交微信（4113）。`refunding` 也计入占用，否则并发第二笔会溜过。
5. **应用层查重给人话原因** —— 直接撞唯一键只会抛 `DuplicateKeyException`，admin 看不懂「已经退过了」还是「系统坏了」。

### 三个刻意决定（评审请连同理由看）

- **受理失败 / 回调失败时，绝不回滚商品行的 `purchase_failed`**（与 GZ-PAY 的「受理失败回滚 paid」语义**刻意相反**）。
  货确实没买到，这是**既成的履约事实**；退款只是它的后续动作，失败了要重试，不是把事实抹掉。
  回滚会让这一行重新出现在采购清单里，店员再去日本买一次。
- **订单 rollup 的基准是「已退款行数」而不是「购买失败行数」**。`business_status` 是**钱**的状态（ADR-0020 §1「订单只管钱」）——
  行标了失败但退款还在路上 / 退款失败了，钱都没回到客人手里，此时显示「部分退款」是在骗客人。
  用已退款数做基准还自带**自愈**：卡住那笔重试成功后再 rollup，订单自动从 `partial_refunded` 走到 `refunded`（已单测 + 真库双验）。
- **已是 `purchase_failed` 但没退过款的行会被补建退款单**。106 的 `/advance` 端点本来就允许把行推成 `purchase_failed`（不带退款，dev 库 item 24 就是），
  若这里一律拒掉，**那些行的钱永远退不出去且没有任何入口能补**。靠唯一键保证不会退第二次。

### 与「两组计数」有关的一处接口设计

返回体把**履约侧**（`markedFailed` / `alreadyFailed` / `rejected`）与**退款侧**（`refundsCreated` / `refundsAccepted` / `refundsFailed` / `refundsSkipped`）**分开**。
合成一个「成功 N 行」会掩盖最危险的情况 —— **状态标成功了但退款失败了**（客人看到「购买失败」却没收到钱）。108 的前端也要分开显示。

---

## §AI 自测（Tier 1A）

### 1. accept[1] 退款金额等于该行金额，不是整单 ✅

```
$ docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e "
    SELECT COUNT(*) FROM gz_jp_order_item
    WHERE refund_status='refunded' AND refund_amount_cent <> amount_cent AND del_flag='0'" | grep -qx 0
ACCEPT1_EXIT=0

--- 明细佐证 ---
total_refunded_rows = 3        mismatch_rows = 0
id  refund_amount_cent  amount_cent  order_total
24  25600               25600        25600
25  25600               25600        25600
27  15000               15000        15000
```

**DATA 断言只能证明「库里现在没有坏数据」，所以代码层也钉死了**：`GzJpRefundStatusRollupTest#refundAmountIsPerLineNeverOrderTotal`
断言提交给微信的报文里 `refundAmountCent = 行金额`、`totalAmountCent = 支付流水金额`，一单 51200 分三笔退 25600 / 20400 / 5200，
**Σ 才等于整单，任何一笔都不等于整单**。真库压测里更狠：单 902 十行各 10000，十笔退款 `SUM = 100000 = 订单总额`，无一笔是整单额。

### 2. accept[2] 部分行失败时订单转 partial_refunded，全失败才 refunded ✅

```
$ cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-jp -am -Dsurefire.failIfNoSpecifiedTests=false -Dtest=GzJpRefundStatusRollupTest
[accept2 部分] 3 行退 1 行：退款额 12000（行）≠ 30000（单）；订单 paid → partial_refunded；另 2 行零变化
[accept2 全部] 3 行全失败：1/3→partial 2/3→partial 3/3→refunded；逐行金额 10000/12000/8000 各归各
[accept2 未成功不 rollup] 受理被拒：refund_failed + 原因落库；行仍 purchase_failed（不回滚事实）；订单仍 paid
[accept2 自愈] 一笔失败停在 partial_refunded → admin 重试（复用同号）→ 回调 → refunded
[accept1] 分两批退 3 行：25600 / 20400 / 5200，Σ=51200=整单；单笔均 ≠ 整单
[超退兜底] 原单 10000、两行各 8000：第 1 行退 8000，第 2 行被 4113 拒（不提交微信）
[缺流水] paid 但 pay_transaction_id 为空：状态标上、退款被 4112 拒，不凭空造退款单
[未支付] 混入未支付行 91：只退 81 的 10000，91 被 ORDER_UNPAID 拒且零变化
[终态] delivered 行标失败 → 4111 没有可标记购买失败的商品行：当前已是终态，不可再变更（共 1 行被拒）
[重复退款] 同一行标 3 次：只建 1 张退款单，第 2/3 次跳过（ALREADY_REFUNDING / ALREADY_REFUNDED）
[补退款] 已是 purchase_failed 但无退款单的历史行：补建退款单并退 25600 → 订单 refunded
[不自动重发] 上次失败的行再点标记：跳过并提示去退款单列表重新发起
[防死锁] 入参 [143,141,142,141,null,143] → 实际加锁顺序 [141, 142, 143]
[跨单] 一次标两单各一行：单15 → refunded、单16 → partial_refunded，互不影响
[零元行] 不调微信、直接 refunded，且在事务内完成 rollup
[全额退款旁路] 订单 → refunded、两行补已退金额；fulfill_status 保持 delivered / customs 不变
Tests run: 16, Failures: 0, Errors: 0, Skipped: 0
ACCEPT2_EXIT=0
```
单测的数据层是**内存版且逐字照搬了 SQL 守卫**（唯一键 → 真抛 `DuplicateKeyException`、`WHERE status='refunding'`、
rollup 的 `business_status IN ('paid','partial_refunded')`），微信通道用**真的** `MockWechatPayClient`（不是 Mockito 桩）——
用 `when(...).thenReturn(1)` 把 mapper 桩掉等于把要测的东西删掉了。

### 3. accept[3] 退款回调幂等（重复回调不重复退）✅

```
$ mvn -q test ... -Dtest=GzJpRefundCallbackIdempotentTest
[accept3] 同一回调收 3 次：退款单/商品行/订单 version 均只 +1 次（2/4/2），全程 true
[accept3 多行] 21 回调 ×3 + 22 回调 ×1：金额各归各（10000/20000），订单 partial → refunded
[accept3 并发] 抢先推进后：回调仍回 true、订单 version 不变、applyRefundSuccess 第二次返回 false
[ABNORMAL] refund_failed + 原因落库；订单仍 paid；行仍 purchase_failed
[ABNORMAL 幂等] 收 3 次：退款单 version 停在 2，商品行停在 3
[终态不翻转] ABNORMAL 之后到的 SUCCESS 被当重复回调，状态与订单都不动
[未知单号] RF- 开头的 GZ-PAY 单打到拼团回调地址 → false（并写 failed 审计日志）
[坏 body] 缺 out_refund_no / 非 JSON → WechatPayVerifyException（401）
[重试×迟到回调] 重试成功后迟到的 CLOSED 被当重复回调丢弃，已退金额保持 10000
[不可重试] 已退款单点重试 → 4115 该退款单已完成，不可重复发起
[静默期] 刚发起点重试 → 4115；超过 10 分钟无回调 → 放行且复用同号 JPRF-20260807-000001
Tests run: 11, Failures: 0, Errors: 0, Skipped: 0
ACCEPT3_EXIT=0
```
**用 version 而不是 status 做断言**：status 断言只能证明「最后状态对」，version 才能证明「到底写了几次」——
重复 rollup / 重复写金额都会让 version 涨，而 status 看不出来。

### 4. ★ 真库端到端（独立实例 `:8082`，admin 超管 token；不碰在跑的 `:8080`）

**Flyway 真库应用**：
```
2026-08-07 11:26:51  org.flywaydb.core.FlywayExecutor
 - Migrating schema `ry-vue` to version "202608071102 - GZ-JP-107-create-gz jp refund"

installed_rank  version        description                     success  installed_on
155             202608071102   GZ-JP-107-create-gz jp refund   1        2026-08-07 11:26:51
154             202608071027   GZ-JP-109-seed-menu             1        2026-08-07 10:42:01

UNIQUE KEY `uk_refund_no`  (`tenant_id`,`refund_no`)
UNIQUE KEY `uk_order_item` (`tenant_id`,`order_item_id`)      ← ★ 防重复退款的物理闸
```

**mark-failed 场景**：
```
A) 未支付单的行 28,29        → 4111 没有可标记购买失败的商品行：订单未支付，不可推进（共 2 行被拒）
B) 已 delivered 的行 2       → 4111 …：当前已是终态，不可再变更（共 1 行被拒）
C) 正常标失败 27（15000）    → 200 marked=1 created=1 accepted=1 amount=15000
                                gz_jp_refund: refund_no=JPRF-20260807-000001 amount=15000 total=15000
                                              status=refunding wechat_refund_id=mock_refund_id_… attempt=1
                                item 27: purchase_failed / refunding / 已退金额仍 NULL
                                order 26: ★ 仍是 paid（受理≠到账，钱没回到客人手里）
D) 单 901 四行标失败 2 行     → 200 marked=2 created=2 accepted=2 amount=20000（另 2 行零变化）
H) 重复标同一行（已 refunded）→ 200 created=0 skipped=1 skip=该行已完成退款；退款单条数恒为 1
I) ★ 补退款 item 24          → 之前状态：purchase_failed + refund_status=NULL（106 的 /advance 留下的）
                                200 marked=0 alreadyFailed=1 created=1 accepted=1 amount=25600
```

**退款回调 + 幂等（真库）**：
```
回调 #1 SUCCESS → HTTP 200
  gz_jp_refund  : refunded / wx_refund_real_0001 / refunded_time=2026-08-07 11:28:14 / version=2
  gz_jp_order_item 27: purchase_failed / refunded / refund_amount_cent=15000（= amount_cent）/ version=4
  gz_jp_order   26   : refunded / version=2
回调 #2 #3（重复）→ HTTP 200 / 200
  ★ 三张表 version 一动不动：2 / 4 / 2
审计日志 gz_pay_callback_log(callback_type='jp_refund')：
  received → processed          （第 1 次）
  received → duplicated「退款单已终态（refunded），重复回调」（第 2、3 次）
```

**订单 rollup 两种情形（真库，单 901 四行）**：
```
标失败 2 行、受理成功            → 订单仍 paid          （★ 钱还没到账）
回调第 1 笔 SUCCESS              → 订单 partial_refunded
回调第 2 笔 SUCCESS              → 订单 partial_refunded（4 行只退了 2 行，不是全退）
★ 剩余 2 行照常走完发货：
  advance 9011→jp_shipped        → 200 advanced=1
  ship    9011,9014 SFTEST107001 → 200 advanced=2
  落库：9011/9014 = delivered + sf + SFTEST107001（refund_status 全 NULL）
        9012/9013 = purchase_failed + refunded 10000
        order 901 = partial_refunded
  ⇒ 退款线与发货线互不干扰（106 交代的「rollup 后剩余行仍能推进」成立）
```

**失败链路 + admin 可见 + 重试（真库）**：
```
① 回调 ABNORMAL → HTTP 200
   gz_jp_refund : status=refund_failed  fail_reason=微信退款回调 refund_status=ABNORMAL  attempt=1
   item 24      : purchase_failed / refund_failed / 已退金额 NULL
   order 23     : ★ 仍是 paid（钱没退出去，不显示已退款）
② GET /system/gz/jp/refund/list（★ 失败单排最前）
   #4  JPRF-20260807-000004 item=24  ¥25600/25600  st=refund_failed  retryable=True   fail=微信退款回调 refund_status=ABNORMAL
   #24 JPRF-20260807-000024 item=9022 ¥10000/100000 st=refunded       retryable=False  fail=None
③ 筛选 status=refund_failed → total=1 ；status=bogus → 500 非法的退款状态筛选值：bogus
④ POST /system/gz/jp/refund/4/retry → 200 已重新发起 status=refunding attempt=2
   回调 SUCCESS → refunded / fail_reason 清空 / attempt=2 / wechat_refund_id=wx_retry_ok
   item 24: refunded 25600 ；order 23: ★ refunded（自愈）
⑤ 已 refunded 的单再点重试 → 4115 该退款单已完成，不可重复发起
   ★ attempt_count 没涨（=1）—— 根本没调微信
⑥ 不存在的退款单 → 4114 退款单不存在: 999999
⑦ 未知 out_refund_no（模拟 GZ-PAY 的 RF- 单被错误路由到拼团回调）→ HTTP 500 + 审计 failed「拼团退款单不存在: RF-20260807-999999」
⑧ 坏 body（缺 out_refund_no）→ HTTP 401 + 审计 failed「mock 退款回调 body 缺 out_refund_no / refund_id」
```

**★ GZ-PAY 全额退款旁路（退款 SPI）真库实跑**：
```
前置：order 24 = paid / item 25 = purchasing / refund_status=NULL / 无 jp 退款单
① POST /system/gz/pay/refund/apply {"transactionId":46,...}   （走【老链路】，不经过 jp 域）
   → 200 refundNo=RF-20260807-000001   ★ RF- 前缀，与拼团的 JPRF- 各自号段，不互撞
② POST /api/pay/v3/refund-notify（GZ-PAY 自己的端点）→ HTTP 200
   日志：[gz-jp] ★ 拼团订单被 GZ-PAY 全额退款（非行级退款路径）refund_no=RF-20260807-000001 …
        [gz-jp-refund] ★ GZ-PAY 全额退款旁路同步 order_no=JPO-20260807-000038 补标 1 行 → 订单 refunded(affected=1)
③ 拼团侧被同步：order 24 = refunded / item 25 = refund_status=refunded + refund_amount_cent=25600
   ★ fulfill_status 仍是 purchasing —— 货走到哪是另一根轴（ADR-0007 双状态机正交），钱退了不代表货没买到
   ★ gz_jp_refund 里 0 条（这条路径不产生行级退款单，符合预期）
```

### 5. ★★ 真并发压测 —— **逮到一个真缺陷（106 遗留，本卡修复）**

> 105/106 的教训：**涉及并发的实现单测全绿不算数**。本卡 27 个单测全绿之后，第一轮真并发直接炸出 **3 个 500 + 18 条 deadlock**。

**轮 1（修复前）— 6 并发 `mark-failed`**（窗口重叠 60%，一半降序传 id）
```
resp_0: 500 发生未知异常   resp_3: 200 marked=1 already=4 created=1
resp_1: 500 发生未知异常   resp_4: 200 marked=6 created=6
resp_2: 500 发生未知异常   resp_5: 200 marked=3 already=2 created=3
死锁扫描 = 18
```
最终数据是对的（10 张退款单 / 10 个 distinct item / Σ=100000），但**三分之一的请求直接失败**——
对店员就是「点了报错，不知道钱退没退」。

**根因（`SHOW ENGINE INNODB STATUS` + `EXPLAIN` 定位）**：
```
*** (1) HOLDS THE LOCK(S):
RECORD LOCKS ... index idx_user_fulfill of table `ry-vue`.`gz_jp_order_item` lock_mode X
  ← 锁的是二级索引，不是主键！而且锁到了 item 1 / 2 / 9011 这些【不在 id 列表里】的行

EXPLAIN SELECT * FROM gz_jp_order_item WHERE del_flag='0' AND id IN (...) AND tenant_id='1001' ORDER BY id FOR UPDATE
  key: idx_user_fulfill    rows: 24    Extra: Using index condition; Using where; Using filesort
```
1. 多租户拦截器给这句追加 `AND tenant_id='1001'`，而 `idx_user_fulfill (tenant_id, user_id, fulfill_status)` 正好以 `tenant_id` 打头 —— **优化器挑走了二级索引**；
2. 走二级索引时 InnoDB 按 `(tenant_id, user_id, fulfill_status, id)` 的顺序加锁，而 **`fulfill_status` 恰恰是本批操作正在改的那一列** —— 并发请求看到的索引位次互不相同，加锁顺序就此错开，构成死锁环；
3. `ORDER BY id` 退化成 `Using filesort`，**排序发生在取完锁之后**，管不到加锁顺序 —— 服务层「id 去重 + 升序」的防死锁纪律**被执行计划架空了**。

**这是 GZ-JP-106 的遗留缺陷，不是本卡引入的**：`selectByIdsForUpdate` 是 106 写的，`/advance` 与 `/ship` 用的是同一句。
106 的三轮压测没炸是运气 —— 它每轮并发都推向**同一个目标状态**，索引位次整体平移；本卡的批次里混着
`purchasing` / `purchase_failed` / 已退款的行，且表里行数更多，才把不一致的加锁顺序暴露出来。

**修复**：给 `selectByIdsForUpdate` + `advanceGuarded` + `shipGuarded` 钉上 `FORCE INDEX(PRIMARY)`。
```
EXPLAIN ... FORCE INDEX(PRIMARY) ...
  key: PRIMARY    rows: 10    Extra: Using where     ← 只锁目标行，且严格按 id 升序
```
`advanceGuarded` / `shipGuarded` 当前本来就选中 PRIMARY，一并钉死是因为**加锁顺序不该交给优化器的统计信息决定**（今天选对了，明天数据分布一变就选错）。

**轮 1（修复后）— 同样的 6 并发**
```
resp_0: 200 marked=0  already=10 created=0  accepted=0  skipped=10 amount=0
resp_1: 200 marked=0  already=10 created=0  accepted=0  skipped=10 amount=0
resp_2: 200 marked=0  already=5  created=0  accepted=0  skipped=5  amount=0
resp_3: 200 marked=2  already=3  created=2  accepted=2  skipped=3  amount=20000
resp_4: 200 marked=6  already=0  created=6  accepted=6  skipped=0  amount=60000
resp_5: 200 marked=2  already=3  created=2  accepted=2  skipped=3  amount=20000
                                     ↑ marked 合计 = 10，恰好每行一次

不变量：refund_rows=10  distinct_items=10  distinct_nos=10  sum_amount=100000
        重复退款单 = 0 行
        全部 purchase_failed / refunding，version 全部 = 3（每行恰好被写 2 次）
死锁 = 0    500 = 0
```

**轮 2 — 30 个并发退款回调（10 张退款单 × 各重发 3 次）★ 打的是 rollup 竞态**
```
HTTP 状态分布：30 × 200

gz_jp_refund     : refunded ×10，version 全部 = 2      （每张恰好推进 1 次）
gz_jp_order_item : refunded ×10，Σ已退 = 100000，version 全部 = 4
★ gz_jp_order 902 : refunded / version=3                 ← 没有卡在 partial_refunded
★ accept[1] 金额恒等式：0 行不匹配
审计日志：received=30  processed=10  duplicated=20        ← 精确到个位数
rollup 日志（去重后只有两条）：
   1 × rollup order_id=902  1/10 行已退款 → partial_refunded（affected=1）
   1 × rollup order_id=902 10/10 行已退款 → refunded（affected=1）
死锁 = 0    未知异常 = 0
```
**这一轮验的是「订单 rollup 不加锁会出的事」**：10 个回调同时到，若不先 `SELECT gz_jp_order ... FOR UPDATE`，
每个都可能读到「已退 9/10」而算出 `partial_refunded`，**最后一个也不例外，订单永远到不了 `refunded`**。
锁上之后 rollup 被串行化，只有第 1 次和第 10 次真的写了库，中间 8 次因「目标态 == 当前态」直接跳过。

**压测数据已硬删**（`DELETE` 不是软删 —— 软删行仍会被 accept[1] 的全表扫描看到）：
```
残留临时单 = 0   残留临时行 = 0   残留临时退款单 = 0
残留软删行 = 0   残留软删退款单 = 0
```

### 6. 回归

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp,ruoyi-modules/ruoyi-gz-common,ruoyi-modules/ruoyi-gz-user -am
ruoyi-gz-common ... Tests run: 220, Failures: 0, Errors: 0, Skipped: 0   ← 含 PayRefundServiceImplTest（我没碰它，但必须证明没碰坏）
ruoyi-gz-user   ... Tests run:  42, Failures: 0, Errors: 0, Skipped: 0
ruoyi-gz-jp     ... Tests run: 194, Failures: 0, Errors: 0, Skipped: 0   ← 106 的 31 个测试全部重跑（我改了它的 mapper）
BUILD SUCCESS
```
**改了 106 的 mapper 所以额外做了真库回归**（单测的内存数据层照不出 SQL 层面的改动）：
```
advance 26 → customs        : 200 advanced=1
ship    26 sf SFJP107REG01  : 200 advanced=1 顺丰速运
落库：item 26 = delivered / sf / SFJP107REG01 / version=3
```

### 7. ★ 硬验收：3 个受保护文件一行未动

```
$ P1=…/pay/controller/PayRefundController.java
$ P2=…/pay/service/impl/PayRefundServiceImpl.java
$ P3=…/pay/service/internal/PayRefundTxService.java     ← ★ ticket 写的是 service/PayRefundTxService.java，
                                                          实际在 service/internal/ 下（见「§风险」第 8 条）

PayRefundController.java     存在=YES  git-diff行数=0  git-status=0  与HEAD哈希一致=YES
PayRefundServiceImpl.java    存在=YES  git-diff行数=0  git-status=0  与HEAD哈希一致=YES
PayRefundTxService.java      存在=YES  git-diff行数=0  git-status=0  与HEAD哈希一致=YES

$ git status --porcelain -- ruoyi-modules/ruoyi-gz-common/
（空）  → 改动文件数 = 0

$ git status --porcelain -- ruoyi-gz-bean/ ruoyi-gz-ord/ ruoyi-gz-gacha/ ruoyi-gz-user/ ruoyi-gz-news/
（空）  → 改动文件数 = 0
```
用 `git hash-object <file>` 与 `git rev-parse HEAD:<file>` 比对，比 `git diff` 更硬 ——
**逐字节相同**，不只是「diff 为空」。整个 `ruoyi-gz-common`（拼豆/回收共用资金链路的家）0 文件改动。

---

## §风险提示 / 已知 issue

1. **★★ admin 仍能在支付管理页对已部分退款的 jp 单发起全额退款（超退风险，无法在 jp 域内根治）**。
   拼团行级退款不写 `gz_pay_refund`，所以 `PayRefundTxService.createRefunding` 的
   「一笔支付只允许一条退款单」闸门**看不见**它们。真提交时微信会因「退款总额超过原单」拒绝（**钱是安全的**），
   但会在 `gz_pay_refund` 留一条 failed 记录，且拼团侧的 SPI handler 不会触发（回调不会来）。
   根治要动 `PayRefundTxService` —— 本卡明令不碰。**缓解**：① 108 做支付管理页时对 `business_type='jp'` 的交易禁用/隐藏「退款」按钮；
   ② 给运维文档写一条「拼团退款只走履约看板」。**建议开一张独立 ticket** 决定长期方案（ADR-0020 §3 已预告：等第三条业务线也要部分退款时，把 jp 这套上提为共用能力）。

2. **崩溃窗口：事务①提交后、调微信前进程挂掉** → 留下一张永远停在 `refunding` 的退款单（钱没退出去）。
   本项目 **prod 未部署 SnailJob**（25 个 `@JobExecutor` 一个都没跑），自动补偿任务写了也不会执行 ——
   所以兜底做成**人可操作的**：退款单列表把失败与长时间未回调的单排最前，`retryable` 字段后端算好，
   `retry` 对「超过 10 分钟仍无回调的 `refunding`」放行（微信按 `out_refund_no` 幂等，重发安全）。
   **如果将来上了 SnailJob**，加一个「扫 `refunding` 且 `triggered_time` 超期 → 调 `queryRefund` 核对」的任务即可，模型已经支持。

3. **对账中心尚未兼容拼团退款**（ADR-0020 §3 代价 3 已预告）。`GzReconBatchServiceImpl` / `GzReconDashboardServiceImpl`
   只算 `preorder` + `gacha`（合同 §4.1 口径），拼团本来就不进 4% 分成，所以**本卡不做**。
   但**若将来甲方要把拼团纳入分成**，对账要按行扣减且要同时认识 `gz_pay_refund` 与 `gz_jp_refund` 两个退款来源 ——
   那是商业口径变更，须客户书面确认。

4. **`FORCE INDEX(PRIMARY)` 不要被"优化"掉**。它写在 `selectByIdsForUpdate` / `advanceGuarded` / `shipGuarded` 上，
   看起来像多余的性能 hint，实际是**防死锁的必需品**（见「§并发压测」）。mapper javadoc 里写了完整理由，
   **任何人想摘掉它之前请先重跑 6 并发压测**。

5. **`purchase_failed` 可从任意非终态进入**（106 的判断，本卡沿用）—— 意味着**清关中甚至国内分拣中的货也能被标失败并退款**。
   业务上合理（日方缺货 / 清关退运），但误操作不可逆。108 的二次确认必须显示「将影响 N 行、退款 ¥XXX、不可撤销」。

6. **零元行**（`amount_cent <= 0`）不调微信、直接置 `refunded`（微信不接受 0 元退款）。拼团一期不会出现零元行，
   这条纯属防御。若将来加了满减 / 优惠券让行金额可能为 0，**注意它不会有回调**，rollup 在事务①内做。

7. **`@RepeatSubmit` 会挡住完全相同 payload 的连续两次请求**（返回 `500 Repeat submit is not allowed`）。
   本卡真库实测又踩了一次（连续两次 `POST /refund/{id}/retry` 空 body）。**108 写 E2E 时别用两次一模一样的 body 断言幂等。**

8. **ticket / ADR 里 `PayRefundTxService` 的路径写错了**：写的是 `pay/service/PayRefundTxService.java`，
   实际在 `pay/service/internal/PayRefundTxService.java`。用错误路径跑 `git diff` 会**静默返回空 = 假通过**。
   本报告用真实路径 + `hash-object` 比对重跑过。**建议主线程顺手修一下 ADR-0020 §3 表格里的路径。**

9. **蓝图 `F-JP-04.step3` 描述已过时**（见 §0 末尾）：「退款回调走 GZ-PAY 现有 RefundCallbackDispatcher」是路线②拍板前的旧话。
   建议改成「拼团行级退款走 jp 专属回调端点 `/api/gz/jp/pay/refund-notify`；`RefundCallbackDispatcher` 上的
   `business_type='jp'` handler 只用于堵 GZ-PAY 全额退款旁路」。**复盘优先级 #1（改权威蓝图）。**

10. **本卡无菜单、无字典**：`gz:jp:fulfill:markFailed` / `gz:jp:refund:list` / `gz:jp:refund:retry` 三个权限串由
    **108 在 14030 段 seed**。在那之前只有超管（admin）能调这三个端点，普通角色 403 —— **这是预期，不是漏做**。

11. **dev 库当前状态**（留给 108 / 205 当 fixture）：
    ```
    item order ord_st           fulfill_status   refund_status  refund_amt  amount
    1    1     paid             cn_sorting       NULL           NULL        51200
    2    2     paid             delivered        NULL           NULL        25600   ← 同一包裹 SF7654321000
    3    2     paid             delivered        NULL           NULL        20400
    24   23    refunded         purchase_failed  refunded       25600       25600   ← ★ 行级退款完整样本（attempt=2，经历过失败+重试）
    25   24    refunded         purchasing       refunded       25600       25600   ← ★ GZ-PAY 全额退款旁路样本（fulfill 未动，刻意如此）
    26   25    paid             delivered        NULL           NULL        25600   ← 回归测试发货 SFJP107REG01
    27   26    refunded         purchase_failed  refunded       15000       15000   ← ★ 行级退款完整样本
    28   27    created          purchasing       NULL           NULL        3000    ← 未支付，不该出现在看板
    29   27    created          purchasing       NULL           NULL        8000
    30   29    created          purchasing       NULL           NULL        100000

    gz_jp_refund: 2 条（JPRF-20260807-000001 / -000004），均 refunded
    ```
    ⚠️ **item 25 看起来"怪"是有意的**：`purchasing` + `refund_status=refunded`。它是 GZ-PAY 全额退款旁路的产物 ——
    钱整单退了，但货的进度是另一根轴（ADR-0007）。**别当 bug 修**。

12. **待 Kevin 残留人验：N/A** —— 纯后端，无 mp / admin 页面，不碰真机微信原生能力。
    ⚠️ **但这是资金链路**：按 CLAUDE.md §8.2，**支付 / 退款上线前必须跑一轮真钱或微信沙箱**。
    dev 全程走 `MockWechatPayClient`，**「微信真的会按行金额部分退款」这件事本卡没有真钱验证过**。
    上线前建议：真商户号下拿一笔 1 分钱的多行拼团单，标 1 行失败，确认微信侧退款金额 = 行金额而不是整单。

---

## §对下游 ticket 的提示

### 给 GZ-JP-108（admin 履约看板 + 退款页）

**① 履约看板加「批量标记购买失败」按钮**（`UI:admin.fulfill_board.mark_failed`）

```jsonc
POST /system/gz/jp/fulfill/mark-failed        权限 gz:jp:fulfill:markFailed（★ 与 advance 分开，需单独 seed）
{ "itemIds": ["24","25"], "reason": "日方缺货" }   // reason 可选、≤200 字、★ 客人在微信退款记录里看得到

200 { "code":200, "data":{
      // ── 履约侧：这些行标没标上 ──
      "requested":2, "markedFailed":2, "alreadyFailed":0, "rejected":0,
      "rejects":[{"itemId","currentStatus","currentStatusLabel","reasonCode","reason"}],
      // ── 退款侧：这些行的钱退没退（★ 必须与上面分开显示）──
      "refundsCreated":2, "refundsAccepted":2, "refundsFailed":0, "refundsSkipped":0,
      "refundAmountCentTotal":20000,
      "refunds":[{"itemId","refundId","refundNo","refundAmountCent",
                  "refundStatus","refundStatusLabel","accepted","failReason",
                  "skipReasonCode","skipReason"}] } }
```

| code | 含义 | 前端动作 |
|---|---|---|
| 200 `refundsFailed > 0` | **★ 状态标上了但钱没退成功** | **不能提示"操作成功"**！按 `refunds[].failReason` 标红那几行，引导去退款页重试 |
| 200 `refundsSkipped > 0` | 那几行之前已退 / 正在退 / 上次失败 | 按 `skipReason` 灰字说明，不算失败 |
| 200 全 accepted | 已受理，等微信回调 | 提示「已发起退款 ¥XXX，到账以微信通知为准」，**别说"已退款"** |
| 4111 | 一行都标不上且无款可退 | 红字弹 msg（含首条原因 + 被拒行数），刷新看板 |
| 4112 | 订单缺支付流水 | 提示联系技术，**不要让店员重试** |
| 4113 | 会超出原单总额 | 提示数据异常，联系技术 |

- **二次确认弹窗必须显示金额**：勾选行的 `amountCent` 之和 = 将要退的钱。ADR-0020 明写「会触发真实退款」。
- **看板列表已带退款字段**（106 的 `/fulfill/list` 本来就有，本卡把它们填上了）：`refundStatus` / `refundStatusLabel` / `refundAmountCent`。实测：
  ```
  item=24 购买失败 refundStatus=refunded label=已退款 refundAmountCent=25600
  ```
- **`terminal=true` 的行 checkbox 禁掉**，但 **`purchase_failed` 的行要允许再次勾选标失败** —— 那是「补退款」路径（它们可能还没退过钱）。建议：`fulfillStatus==='purchase_failed' && !refundStatus` 时高亮提示「未退款」。

**② 新增「拼团退款」页**（AC 明令：退款失败要 admin 可见）

```jsonc
GET /system/gz/jp/refund/list?pageNum=1&pageSize=20      权限 gz:jp:refund:list
    &status=refund_failed        // refunding / refunded / refund_failed；★ 非法值直接报错不静默忽略
    &orderNo=JPO-20260807-000001 &userId=13 &keyword=小王   // keyword 匹配昵称/手机号/用户编号，无匹配返回 total=0
    &beginDate=2026-08-01&endDate=2026-08-07               // 按【发起时间】，含首尾整天
// ★ 读 res.rows（TableDataInfo）不是 res.data
{ "rows":[{ "id","refundNo","orderId","orderNo","businessStatus","businessStatusLabel",
            "orderItemId","userId","userNickname","userMobile","userNo","outTradeNo",
            "refundAmountCent","totalAmountCent",        // ★ 两者不等 = 这是部分退款
            "wechatRefundId","status","statusLabel","reason",
            "failReason","attemptCount","triggeredBy","triggeredTime","refundedTime",
            "retryable" }], "total":14 }

POST /system/gz/jp/refund/{refundId}/retry               权限 gz:jp:refund:retry
200 { "code":200, "msg":"已重新发起", "data":<同上单条> }
4114 退款单不存在 / 4115 当前状态不允许重试
```
- **★ 后端已把 `refund_failed` 排在最前**（`ORDER BY CASE status ...`），前端**不要**再按时间倒序覆盖 —— 这张页面存在的理由就是捞失败单。
- **`retryable` 后端算好，前端别自己判状态**：`refund_failed` 恒可重试；`refunding` 只有超过 10 分钟无回调才可；`refunded` 永不可。
- `failReason` **直接显示在列表里**，别藏进详情弹窗。
- 状态 `<dict-tag>` 用字典 `gz_jp_refund_status`（**9285，105 已 seed，别再 seed**）。

**③ 菜单 seed（14030 段，全归你）** —— 本卡新增 3 个权限串需要一并 seed：
```
gz:jp:fulfill:list      gz:jp:fulfill:advance    gz:jp:fulfill:ship
gz:jp:fulfill:markFailed        ← ★ GZ-JP-107 新增（独立授权：推状态 ≠ 动客人的钱）
gz:jp:refund:list       gz:jp:refund:retry      ← ★ GZ-JP-107 新增
```

**④ 支付管理页要挡一下**：见「§风险 1」，对 `business_type='jp'` 的交易禁用/隐藏「退款」按钮。

### 给 GZ-JP-205（mp 订单详情）

- **「已退款 ¥xx」从哪读**：`GET /app/gz/jp/order/{id}` → `items[].refundStatus` / `refundStatusLabel` / `refundAmountCent`。
  **105 已经映射好了**（`GzJpOrderServiceImpl:506-508`），本卡只是把值填上，**你不需要改后端**。
- **文案对照**（`refundStatusLabel` 后端已给中文，别在前端再维护一份映射）：
  | refundStatus | Label | mp 建议文案 |
  |---|---|---|
  | `refunding` | 退款中 | 「没抢到，退款处理中 ¥XX」 |
  | `refunded` | 已退款 | 「没抢到，已退款 ¥XX 到微信」 |
  | `refund_failed` | 退款失败 | ⚠️ **别把这个词给客人看**。建议显示「退款处理中，如有疑问请联系客服」——`refund_failed` 是内部状态，客人看到会恐慌，而它多半几分钟内就被店员重试好了 |
- **`refundAmountCent` 恒等于该行 `amountCent`**（accept[1] 保证），所以详情页可以直接显示行金额，不用担心两个数字对不上。
- **订单级 `businessStatus`**：`partial_refunded`（部分退款）/ `refunded`（已退款）。
  ⚠️ **订单显示「部分退款」时，未失败的行仍在正常发货** —— 订单头部的状态标签**不能**盖掉每行的进度（ADR-0020 §1：订单只管钱、行才管货）。
- ⚠️ **可能出现「订单已退款但某行还是购买中」**：那是 GZ-PAY 全额退款旁路（见 §风险 11 的 item 25）。
  mp 端按行渲染即可，不要因为订单是 `refunded` 就把所有行都画成已退款。

### 编号段位现状

| 资源 | 已占 | 下一个空号 |
|---|---|---|
| `sys_menu` GZ-JP | 14000-14005、14010-14014、14020 段(109)；**本卡未占** | 14030 段（108） |
| `dict_id` / `dict_code` | 9280-9285 / 92801-92821；**本卡未占**（复用 9285） | 9286 / 92822 |
| jp 业务错误码 | 4101-4107（105）、4108-4110（106）、**4111-4115（本卡）** | **4116** |
| Flyway | …**V202608071102（本卡）** | `date +V%Y%m%d%H%M` |
| 退款单号前缀 | `RF-`（GZ-PAY，`gz_pay_refund`）/ **`JPRF-`（本卡，`gz_jp_refund`）** | 第三条业务线要部分退款时，**别再复制第四个前缀** —— 按 ADR-0020 §3 把 jp 这套上提为共用能力 |

### 全 jp 域通用（本卡新增 / 再次踩到）

- **★ 批量加锁的 `SELECT ... FOR UPDATE` 必须 `FORCE INDEX(PRIMARY)`**：多租户拦截器注入的 `tenant_id` 会把优化器推向以 `tenant_id` 打头的二级索引，加锁顺序随之失控，服务层的「id 升序」纪律被架空。**这是全项目通用坑**（gz_bean / gz_recycle 的批量锁查询同样以 `tenant_id` 打头建索引，值得排查一遍）。
- **涉及并发的实现，单测全绿真的不算数**：本卡 27 个单测全绿之后第一轮真并发就炸出 3 个 500。**且要压对地方** —— 轮 1 压写入竞态、轮 2 压回调 rollup 竞态，缺任一轮都照不出对应的缺陷。
- **并发断言用 `version` 不用 `status`**：status 只能证明「最后状态对」，version 才能证明「到底写了几次」。
- **「调外部支付接口」与「写库」永远不能同一个事务**，且事务段必须是**独立 Bean**（Spring `@Transactional` 走代理，同类自调用不生效）。
- **回调处理方法必须自己 `@Transactional`**：否则 `SELECT ... FOR UPDATE` 在 autocommit 下语句一结束锁就释放，等于没锁。
- **`docker exec mysql -N` 取出的多行结果直接塞进 shell `for` 循环会带上换行**，拼进 JSON body 会被 `PlusWebInvokeTimeInterceptor` 的 `readTree` 打回 500 —— 用 `while IFS= read -r` 逐行读。
- **清 `gz_jp_*` 测试数据一律 HARD DELETE**（accept[1] 是全表扫描，软删行照样被看到）。

## §AI 测试段（kevin-qa 完工后追加）

（占位）**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）**

建议覆盖：
- 后端集成 `POST /system/gz/jp/fulfill/mark-failed` 全链路（4111/4112/4113、未支付行排除、终态不可标、重复标不重复退、补退款）
- `POST /api/gz/jp/pay/refund-notify` 回调（SUCCESS / ABNORMAL / 未知单号 500 / 坏 body 401 / 重复回调 version 不变）
- `GET /system/gz/jp/refund/list` + `POST /system/gz/jp/refund/{id}/retry`（4114/4115、失败单排序、retryable 计算）
- **API 契约回归**：字段名与「给 108」段逐字一致、ID 全 string、列表返 `rows`
- **跨域回归**：`GET /app/gz/jp/order/{id}` 的 `items[].refundStatus/refundStatusLabel/refundAmountCent` 应随标失败/回调实时变化
- **106 回归**（本卡改了它的 mapper）：`/fulfill/advance` + `/fulfill/ship` 真库仍正常
- **并发回归**：6 并发 mark-failed（重叠 itemIds、一半降序）+ N 并发回调（同单多行）→ 退款单数 == 行数、每行 version 只 +1、订单终态 `refunded`、无死锁
- 权限（108 seed 前非超管应 403，别当 bug 报）

本卡**无 admin/mp 页面** → 无 Playwright / 模拟器 E2E 对象。
⚠️ 跑前确认 8080 上是本卡 `mvn clean install` 后的 jar。⚠️ 别用两次一模一样的 body 断言幂等（`@RepeatSubmit` 返 500）。

---

**环境交还**：起的 `:8082` 实例已关闭（`8082 listeners = 0`，无残留进程）；并行 agent 在用的 `:8080` 未被触碰、仍返回 200。
压测临时数据已硬删（残留 0 行）。测试脚本在 scratchpad，未污染项目目录。**未 commit**。

**accept 三条：PASS**（ACCEPT1_EXIT=0 / ACCEPT2_EXIT=0 / ACCEPT3_EXIT=0）。
**3 个受保护文件：确认零改动**（`git hash-object` 与 `HEAD` 逐字节一致；整个 `ruoyi-gz-common` 模块 0 文件改动）。
