# GZ-GACHA-104 ⭐ 完工报告 — 扭蛋开盒事务 + 防超卖（4 表原子 + 失败重抽，必出无退款）

> V1.1 最硬 ticket（并发正确性密度最高）。业务模型钉死：付款必出 1 件实物，缺货付款前拦截（不收款），
> 并发扣减失败 = 从剩余有货池重抽改派其他商品（**绝不退款**）。扭蛋域**无系统自动退款**。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（subagent 路径非 git repo；未 commit，按指令主线程接手） |
| 上游 PAY-101 SPI 实存 | ✅ `IGzPayTransactionService.createBusinessOrder(CreateOrderBo)→MpPayParamsVO` / `PayCallbackHandler`(SPI) / `PayCallbackDispatcher`(business_type 路由) / `IWechatPayClient`(Mock/V3) / `gz_pay_transaction` 全 grep 命中 |
| GACHA-101 mapper 签名实存 | ✅ `GzGachaPrizeMapper.selectInPoolForUpdate(machineId)`(FOR UPDATE) + `deductStock(id,version)`(乐观锁) + `GzGachaMachineMapper.increaseSalesCount`/`autoOffExpiredMachines` 已预置 |
| gz_gacha_machine/prize 公共字段 canonical | ✅ DESCRIBE 实表：create_dept/create_by/update_by 均 BIGINT NULL（GACHA-101 fix-base-columns 已对齐） |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-gacha` BUILD SUCCESS |
| DDL 时间戳 > 已应用最大 | ✅ V202606171400 > V202606171002 |
| ADR 已读 | ADR-0003 候选（MQ 解耦）— 默认不引（决策 D8，压测未见线程池打满）；ADR-0004 mp 权限底座 — 本卡无 mp 管理动作不涉及 |
| 不依赖 IPayRefundService / gz_pay_refund | ✅ 扭蛋域无系统退款，全卡 0 退款代码 |

**业务模型钉死摘录（doc/10 §8 业务本质 / F7.3 / §8.E5）**：
- 缺货付款前拦截（`MACHINE_EMPTY` 不收款）→ 付款后必有货
- 并发扣减失败（乐观锁 affected=0）→ 移出候选 + 重新归一化重抽改派其他有货商品（有界，绝不退款）
- `refunded` 仅 admin 人工特例退款可达（合同 §4.5，未来 ticket），开盒主流程不可达；**不写 gz_pay_refund / 不建退款 handler/service/死信/报警**

## 实现摘要

**新增产物（后端 ruoyi-gz-gacha，19 个 java + 1 DDL）+ mp api 1 个**：

- DDL：`V202606171400__GZ-GACHA-104-create-gz_gacha_draw-order-collection.sql`（3 表，1:1 对齐 doc/11 §7.3/§7.4/§7.5）
- 实体：`GzGachaDraw` / `GzGachaOrder` / `GzUserGachaCollection`（extends TenantEntity，@TableLogic 软删）
- mapper：`GzGachaDrawMapper`(幂等探测 selectIdByPayTransactionId) / `GzGachaOrderMapper` / `GzUserGachaCollectionMapper`(UPSERT +1，tenant 显式传)
- 核心 service：`IGzGachaDrawService` + `GzGachaDrawServiceImpl`
  - `startDraw(machineId,userId)`：付款前缺货拦截 → 建支付单 → 写 Redis 开盒意图
  - `executeDrawTransaction`(@Async gachaExecutor 派发壳) → `runDrawTransaction`(@Transactional 同步核心，并发压测直调点)
- SPI：`GachaPayCallbackHandler`(@Component implements PayCallbackHandler，supportedBusinessType='gacha'，下沉 gz-gacha，onPaid 仅触发 @Async 不阻塞回调)
- 内部 Bean：`ProbabilityNormalizer`(归一化口径单一真源) / `SecureRandomDrawer`(SecureRandom 区间抽取，可注入随机源单测) / `GachaDrawIntentStore`(封 RedisUtils + TenantHelper.ignore 保证租户前缀一致) / `GachaMachineAutoOffService`(整机售罄防御性 auto_off，独立 Bean after-commit 调)
- config：`GachaExecutorConfig`(@Async("gachaExecutor") 独立线程池 core=8 max=16 queue=1000 CallerRunsPolicy)
- controller：`GzGachaDrawMpController`(POST /app/gz/gacha/draw/start，@SaCheckLogin + @Log)
- 异常 / 错误码：`GachaInternalException` + `GzGachaErrorCode.MACHINE_EMPTY(8009)`
- VO/DTO：`GachaStartDrawVo` / `GachaSnapshot`(machine/prize snapshot 内嵌结构)
- mp：`miniapp/src/api/gz-gacha.ts` 加 `startDraw(machineId)`（无 mp 页面，动画揭晓在 GACHA-105）

**三层防超卖（doc/10 §8.N6）**：DB 事务 + `SELECT FOR UPDATE` 锁奖品行 + `UPDATE stock_remain WHERE version=? AND stock_remain>0`（乐观锁）。防同一商品超卖；失败后果 = 改派其他商品重抽。

**关键技术决策 / 实测踩坑修正**：
- `draw_no`/`order_no` 派生自 out_trade_no 唯一后缀（`DRW-yyyyMMdd-NNNNNN` / `GACHA-yyyyMMdd-NNNNNN`），**不用「当日 MAX+1」**——20 并发未提交时各读同一 max → 全撞 UNIQUE（压测实证翻车后改派生式，天然唯一无冲突）
- 开盒意图 Redis key 用 `TenantHelper.ignore` 包裹——mp 写线程有租户上下文（key 加 `1001:` 前缀）vs @Async 读线程无上下文（无前缀）→ 「开盒意图丢失」（实测踩坑后修，写读两端 key 一致）
- `GachaDrawIntentStore` / `GachaMachineAutoOffService` 抽独立 Bean——前者封 RedisUtils 静态便于单测 mock（避 mockStatic RedissonClient 初始化失败坑）；后者使 after-commit 跨 Bean 调用 REQUIRES_NEW 真生效（不延长开盒事务对 prize 行锁持有）

## AI 自测（Tier 1A）

### 编译 + 单测（mvn，全 29 绿）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha
[INFO] Tests run: 10, ... GzGachaPrizeServiceImplTest        （GACHA-101，无回归）
[INFO] Tests run: 7,  ... GzGachaDrawServiceImplTest          （GACHA-104 开盒事务 6 场景）
[INFO] Tests run: 7,  ... GzGachaMachineServiceImplTest       （GACHA-101，无回归）
[INFO] Tests run: 5,  ... ProbabilityNormalizerTest           （归一化区间 + χ² 随机性）
[INFO] Tests run: 29, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

AC8 6 场景覆盖（GzGachaDrawServiceImplTest）：
1. happy path：出 1 件 → stock-1+version+1 + draw 落 + collection +1 + order pending_ship/in_japan，4 表一致
2. 付款前缺货拦截：整机无货 / 机器非 on_shelf → MACHINE_EMPTY，**verify(payTx, never()).createBusinessOrder**（不收款）
3. 并发扣减失败 → 重抽改派：deductStock 第 1 次 affected=0、第 2 次 affected=1 → 出另一件 + draw/order 正常 + 无 refund mapper（结构性无退款）
4. 乐观锁竞争边界：候选 2 件，确定性 p1 affected=0 移出 → p2 affected=1 → 出 p2
5. 幂等：同 pay_transaction_id 已存在 draw → 步骤 1 直接 return（不锁候选/不扣库存/不建单/不 UPSERT）
6. 概率随机性 χ²（ProbabilityNormalizerTest）：归一化累积区间 70/90/100；等权兜底；drawer 确定性区间命中；**χ² 检验 10000 抽样**

```
[χ²] n=10000 counts={1=7017, 2=1960, 3=1023} chiSquare=1.3703 (临界 5.991, df=2, P>0.05)
```
（观测 7017/1960/1023 vs 期望 7000/2000/1000，χ²=1.37 << 5.991 → 不拒绝「贴合 weight 比」，P>0.05）

### AC9 并发压测 raw output ⭐（防超卖证伪 + refund=0）

**驱动**：mock 支付（`gz.pay.client.mode=mock`）+ 真实 HTTP 链路。20 个 gacha 支付单 → 20 个 simulate-callback **并发发射**（170ms 内全发出）→ 真实回调 → SPI(business_type=gacha) → `@Async` gachaExecutor 开盒（真实 SELECT FOR UPDATE 行锁 + 乐观锁扣减并发竞争）。场景：单机 1 个 SSR(weight=1000,stock=1) + 1 个 N(weight=1,stock=100)，SSR 高权重诱导抢同 1 件。

```
$ # 20 callbacks 并发发射
=== T0 并发发射 20 个 simulate-callback ===   callback 成功数: 20   本轮 ERROR: 0
```

```sql
-- ■ 1) SSR 防超卖：stock_remain=0 + version=1（恰好扣减 1 次）
mysql> SELECT name, rarity, stock_remain, version FROM gz_gacha_prize WHERE machine_id=3 AND rarity='SSR';
+----------------------+--------+--------------+---------+
| name                 | rarity | stock_remain | version |
+----------------------+--------+--------------+---------+
| 压测SSR(稀缺1件)     | SSR    |            0 |       1 |
+----------------------+--------+--------------+---------+

-- ■ 2) 恰好 1 条 draw 中 SSR / 其余 19 得 N（失败重抽改派其他有货商品）
mysql> SELECT p.rarity, COUNT(*) AS draw_cnt FROM gz_gacha_draw d JOIN gz_gacha_prize p ON d.prize_id=p.id
       WHERE d.pay_transaction_id BETWEEN '<first>' AND '<last>' GROUP BY p.rarity;
+--------+----------+
| rarity | draw_cnt |
+--------+----------+
| SSR    |        1 |    ← 恰好 1 人得 SSR（无超卖）
| N      |       19 |    ← 其余 19 人改派得 N（非退款）
+--------+----------+
```

```sql
-- ■ 3) draw 总数=20（必出，每用户 1 件）/ order=20 pending_ship / 无 refund ⭐
mysql> SELECT
  (SELECT COUNT(*) FROM gz_gacha_draw  WHERE pay_transaction_id BETWEEN '<first>' AND '<last>')                                    AS draws,
  (SELECT COUNT(*) FROM gz_gacha_order WHERE pay_transaction_id BETWEEN '<first>' AND '<last>' AND business_status='pending_ship') AS orders_pending_ship,
  (SELECT COUNT(*) FROM gz_pay_refund)                                                                                             AS refund_rows;
+-------+---------------------+-------------+
| draws | orders_pending_ship | refund_rows |
+-------+---------------------+-------------+
|    20 |                  20 |           0 |   ← refund 全程 0 行（扭蛋域无系统退款，证明失败=重抽非退款）
+-------+---------------------+-------------+

-- ■ 4) order_no 全局唯一无冲突（total = distinct，派生式 draw_no/order_no 抗并发）
mysql> SELECT COUNT(*) total, COUNT(DISTINCT order_no) distinct_order_no, COUNT(DISTINCT draw_id) distinct_draw_id
       FROM gz_gacha_order WHERE pay_transaction_id BETWEEN '<first>' AND '<last>';
+-------+-------------------+------------------+
| total | distinct_order_no | distinct_draw_id |
+-------+-------------------+------------------+
|    20 |                20 |               20 |   ← 无冲突
+-------+-------------------+------------------+

-- ■ 5) N 库存核对（100-19=81，version=19 = 19 次成功扣减）+ 图鉴 SUM(drawn_count)=20（UPSERT 无丢失）
mysql> SELECT name, stock_remain, version FROM gz_gacha_prize WHERE machine_id=3 AND rarity='N';
| 压测N(兜底100件) | 81 | 19 |
mysql> SELECT SUM(drawn_count) FROM gz_user_gacha_collection WHERE machine_id=3;  → 20
```

**结论**：三层防超卖（FOR UPDATE 串行化 + 乐观锁 version + DB 事务）下，20 并发抢最后 1 个 SSR → **恰好 1 人得 SSR（SSR.stock_remain=0, version=1）**，其余 19 人各得其他有货商品（N，各 1 draw + 1 order pending_ship），**gz_pay_refund 全程 0 行**，order_no 全局唯一无冲突。证伪超卖 + 证明「失败=重抽改派，非退款」。

> 注：FOR UPDATE 串行化极强——多数并发在锁内已见 SSR=0（候选直接排除 SSR → 直接出 N），故乐观锁 affected=0 的「重抽」路径在集成压测中很少甚至不触发（两层防线叠加，超卖被第一层 FOR UPDATE 拦死）。**重抽改派路径由单测 scenario 3/4（mock affected=0→1）权威覆盖**，业务正确性双重保证。

### AC10 mock 全链路 raw output（无退款分支）

**① happy path 全链路（mp 真实入口 → 回调 → 开盒 4 表）**：
```
① mp POST /app/gz/gacha/draw/start?machineId=3 → outTradeNo=GACHA-20260604-000103
② Redis 意图 key（TenantHelper.ignore 无租户前缀）: gz:gacha:draw-intent:GACHA-20260604-000103
③ POST /system/gz/pay/test/simulate-callback → 真实回调 → SPI 分发 business_type=gacha → GachaPayCallbackHandler → @Async 开盒
④ 开盒结果（draw + order + collection 4 表）:
   draw_no            rarity  order_no            business_status  logistics_status  drawn_count
   DRW-20260604-000103  SSR    GACHA-20260604-000103  pending_ship   in_japan          1
⑤ gz_pay_refund 行数: 0
```
全链路日志追踪：
```
[gz-pay]  SPI 分发支付回调 business_type=gacha → GachaPayCallbackHandler out_trade_no=GACHA-...103
[gz-gacha] 扭蛋支付回调命中 out_trade_no=GACHA-...103 → 触发异步开盒事务
[gz-gacha-draw] 开盒成功 drawNo=DRW-...103 prizeId=27 rarity=SSR machineId=3 userId=4 payTransactionId=GACHA-...103
[gz-gacha-draw] 衍生订单落库 orderNo=GACHA-...103 drawId=... status=pending_ship/in_japan
```

**② 付款前缺货拦截（AC2.5，mp 真实入口，不收款）**：
```
整机所有 prize stock_remain=0 → POST /app/gz/gacha/draw/start?machineId=3
RESP={"code":8009,"msg":"该扭蛋机暂时缺货","data":null}
draw/start 前 gacha 支付单数=101 == 后 101 → ✅ 不收款：无新支付单（MACHINE_EMPTY 拦在付款前）
```

**③ AC7 整机售罄 auto_off**：
```
机器仅剩 1 件 N → mp 开盒最后 1 件 → 机器 status: on_shelf → auto_off
[gz-gacha-autooff] 整机售罄防御性自动下架 machineId=3 → auto_off（运营应保证补货，无用户侧退款）
```

**④ 无退款结构性验证**：
```
$ grep -rniE "gz_pay_refund|RefundService|RefundHandler|IPayRefund|死信|报警|stock_empty_refund" \
       ruoyi-gz-gacha/src/main/java | grep -v 注释类  →  0 行
$ grep "主流程写 refunded"  →  0 行（仅 DDL 默认值注释提及 admin 人工特例）
```

### DDL 验证（Flyway 启动自动应用 + 表结构对齐）

```
flyway_schema_history: 202606171400  success=1
gz_gacha_draw  base cols: create_dept/create_by/update_by 均 bigint NULL（canonical，无 create_dept 500 坑）
UNIQUE keys: draw{uk_draw_no, uk_draw_pay_tx} / order{uk_order_no, uk_draw_id, uk_pay_tx} / collection{uk_user_machine_prize}
SPI 路由表就绪：已注册 2 个 handler：[gacha, preorder]
开盒事务线程池就绪 core=8 max=16 queue=1000 reject=CallerRuns
```

## 风险提示 / 已知 issue

- **R5 外部前置风险（非默认就绪，需主线程标注催甲方）**：真实微信商户号 / 0.01 元端到端**未就绪**。本卡全部用 `gz.pay.client.mode=mock`（MockWechatPayClient）跑通全链路自测；真实商户号下证 + Kevin 核对主体 + 真实回调（AES-GCM `/api/pay/v3/notify`）端到端是**外部前置**，不当本卡完工条件。商户号下证后需补一轮真实 0.01 元端到端验收。
- **R7 @Async 线程池容量**：core=8 max=16 queue=1000，满走 CallerRunsPolicy（回调线程同步跑开盒，不丢单——扭蛋付款必出货宁可慢不可丢）。压测 20 并发未见打满；若生产高峰频繁打满，再评估 ADR-0003 引 MQ。
- **重抽改派路径集成压测未自然触发**：FOR UPDATE 串行化过强，乐观锁 affected=0 的重抽在集成几乎不发生（第一层防线已拦死超卖）。该路径由单测 mock 权威覆盖，非缺陷。
- **待 Kevin 批量人验关注（mp 端）**：N/A — 本卡纯后端 + mp api 封装，**无 mp 页面**（投币 UI / 出奖三段动画 / 揭晓在 GACHA-105），跳过 Tier 2 入口可达 AC。

## 对下游 GACHA-105/106/107 的接口契约提示

**表名 + 关键字段**（供下游 mp 页面查询对齐）：
- `gz_gacha_draw`（开盒记录）：`draw_no`(DRW-yyyyMMdd-NNNNNN) / `user_id` / `machine_id` / `prize_id` / `pay_transaction_id`(= out_trade_no，幂等) / `machine_snapshot_json` / `prize_snapshot_json`(名称+image_id+rarity+referenceValueCent) / `draw_amount_cent` / `drawn_time`
- `gz_gacha_order`（衍生订单）：`order_no`(GACHA-yyyyMMdd-NNNNNN，= out_trade_no) / `draw_id`(一抽一单 UNIQUE) / `business_status`(pending_ship→in_logistics→delivered；refunded 仅 admin 人工特例) / `logistics_status`(in_japan→in_china_dispatching→delivered，与 business_status 并行) / `cn_carrier_code`/`cn_tracking_no`/`cn_dispatched_at`(物流推进 ADMIN-104 写)
- `gz_user_gacha_collection`（图鉴）：UNIQUE(tenant_id,user_id,machine_id,prize_id)；`drawn_count`(重复获得 +1) / `first_drawn_time`；集齐徽章 = 该 user×machine 所有 prize_id 都有记录，**mp/admin 实时 COUNT 算**（DB 无徽章字段）

**给 GACHA-105（出奖动画 + 揭晓）**：
- 支付成功后**轮询查 draw status**：建议加 mp 端点 `GET /app/gz/gacha/draw/status?outTradeNo=...`（本卡未建，105 需补）→ 按 out_trade_no 查 `gz_gacha_draw`，命中即返回 `prize_snapshot_json`（含 rarity 用于三段动画稀有度光晕 tokens §1.4：SSR/SR/R/N 四档）；未命中（开盒事务异步未完成）返回「开盒中」，前端轮询。超时 60s 弹「已支付，结果稍后到账」。
- 揭晓后埋「图鉴进度 +1」入口（doc/10 §8.N9）→ 跳 GACHA-107 图鉴。
- startDraw 已封 `miniapp/src/api/gz-gacha.ts`；105 揭晓页拿 `payParams` 调 `uni.requestPayment`(packageVal→package 映射)，支付成功后轮询。

**给 GACHA-106（开盒历史）**：
- 查 `gz_gacha_draw` IDX `(tenant_id, user_id, drawn_time DESC)`（本卡已建索引）；展示 `prize_snapshot_json`(名称/image_id/rarity/referenceValueCent) + `drawn_time`。
- 扭蛋域无系统退款 → 历史无 refunded 记录（正常路径必出必落）。

**给 GACHA-107（图鉴）**：
- 查 `gz_user_gacha_collection` IDX `(tenant_id, user_id, machine_id)`（本卡已建）；按 machine_id 分组 + 已得高亮 + `drawn_count` ×N 角标。
- 集齐徽章实时 COUNT：`该 user×machine 的 collection 记录数 == 该 machine 的 prize 总数`（gz_gacha_prize WHERE machine_id=? AND enabled=1）。

**盲盒语义纪律（下游 mp 文案必守）**：用户可见 toast/i18n key 用「扭蛋/开盒/获得/出现概率」，禁「抽奖/中奖/开奖」；后端字段保留 draw 技术语义不影响 UI。

## §AI 测试段（kevin-qa Tier 1B，09:05）

> 纯后端 ticket — 无 admin Playwright E2E、无 mp 页面、无 Tier 2 人验。
> Tier 1B 覆盖：后端集成测试独立复核 + API 契约回归 + 无退款不变量 + DB 结构验证。

### 集成测试独立复核（mvn）

coder Tier 1A 已跑 29 测全绿；Tier 1B **独立重跑**同一测试集，结果一致：

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-gacha -am

[INFO] Running org.dromara.gz.gacha.service.GzGachaDrawServiceImplTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.gacha.service.GzGachaMachineServiceImplTest
[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.gacha.service.GzGachaPrizeServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] Running org.dromara.gz.gacha.service.internal.ProbabilityNormalizerTest
[χ²] n=10000 counts={1=6971, 2=2025, 3=1004} chiSquare=0.4486 (临界 5.991, df=2, P>0.05)
[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0

[INFO] Tests run: 29, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
[INFO] Total time:  5.250 s
[INFO] Finished at: 2026-06-04T09:00:12+08:00
```

本轮 χ² 独立结果：chiSquare=0.4486 << 5.991（df=2, P>0.05），随机性验证通过（与 coder 上轮 1.3703 为不同随机种子，均合格）。

### API 契约回归

**契约点 1 — 端点存在（路由注册正确）**

```bash
# 未认证访问：期望 401 而非 404（证明路由已注册）
curl --noproxy '*' -s -X POST "http://localhost:8080/app/gz/gacha/draw/start?machineId=1"
# 实际：{"code":401,"msg":"认证失败，无法访问系统资源","data":null}  ✅ 非404，端点存在
```

**契约点 2 — MACHINE_EMPTY=8009 语义（代码 grep 确认）**

```
$ grep -n "MACHINE_EMPTY" ruoyi-modules/ruoyi-gz-gacha/src/main/java/.../GzGachaErrorCode.java
53:    public static final int MACHINE_EMPTY = 8009;
54:    public static final String MACHINE_EMPTY_MSG = "该扭蛋机暂时缺货";
```

错误码 8009，msg 用「扭蛋机暂时缺货」（盲盒语义合规，非"抽奖"）。✅

**契约点 3 — 返回结构 GachaStartDrawVo（源码确认）**

```java
// GachaStartDrawVo.java
public class GachaStartDrawVo {
    private String outTradeNo;     // GACHA-yyyyMMdd-6位序号
    private MpPayParamsVO payParams;  // 微信 jsapi 5 参
}
```

mp api `gz-gacha.ts` 的 `GachaStartDrawVo` 接口与后端 VO 字段对齐：`outTradeNo` + `payParams{timeStamp,nonceStr,packageVal,signType,paySign,outTradeNo}`。✅

**契约点 4 — 无 V2/XML/gz_pay_order/amount_fen/pay-notify 引入（grep 确认）**

```bash
$ grep -rniE "v2|xml|gz_pay_order|amount_fen|/api/wxpay/pay-notify" \
    ruoyi-modules/ruoyi-gz-gacha/src/main/java/
# 实际命中：0 行（仅 Jackson com.fasterxml 包名含 xml，非业务引入）✅
```

**契约点 5 — SPI 路由 business_type='gacha' 注册（源码确认）**

```java
// GachaPayCallbackHandler.java
@Override
public String supportedBusinessType() {
    return PayBusinessType.GACHA;  // = "gacha"
}
```

`PayCallbackDispatcher` 运行时按 `business_type='gacha'` 路由到本 handler，SPI 下沉 gz-gacha（不循环依赖）。✅

### 无退款不变量（业务铁律验证）

**代码层 grep — 确认无退款实现**

```bash
$ grep -rniE "GachaRefundService|GachaRefundCallbackHandler|IPayRefundService|\
gz_pay_refund写入|stock_empty_refund|死信|alertEmail" \
  ruoyi-modules/ruoyi-gz-gacha/src/main/java/

# 实际命中（全部为注释/javadoc，无代码调用）：
# GzGachaDrawServiceImpl.java:48: * 本类不写任何退款逻辑 / 不触 gz_pay_refund。
# GachaPayCallbackHandler.java:25: * 本 handler 不做退款（扭蛋域无系统退款...）
# 无任何 INSERT/UPDATE gz_pay_refund / IPayRefundService 调用 ✅
```

**DB 层直查 — gz_pay_refund 行数 = 0**

```sql
-- 独立于 coder 压测，直接查当前 DB 状态
SELECT COUNT(*) AS refund_rows_total FROM gz_pay_refund;
SELECT COUNT(*) AS gacha_prefixed_refunds FROM gz_pay_refund WHERE out_trade_no LIKE 'GACHA-%';

+--------------------+
| refund_rows_total  |
+--------------------+
|                  0 |
+--------------------+
+------------------------+
| gacha_prefixed_refunds |
+------------------------+
|                       0|
+------------------------+
```

`gz_pay_refund` 表结构存在（PAY-103 已建），GACHA 前缀退款记录 = 0。无系统自动退款不变量成立。✅

### DDL 结构验证（AC1 独立复核）

**Flyway 应用状态**

```
version=202606171400  description=GZ-GACHA-104-create-gz gacha draw-order-collection
installed_on=2026-06-04 07:47:49  success=1
时间戳 202606171400 > 已有最大 202606171002 ✅
```

**3 张表 UNIQUE 索引（含 tenant_id，强约束 #3）**

```sql
-- gz_gacha_draw
uk_gacha_draw_no        (tenant_id, draw_no)             -- draw_no 唯一
uk_gacha_draw_pay_tx    (tenant_id, pay_transaction_id)  -- 幂等关键 ⭐

-- gz_gacha_order
uk_gacha_order_no       (tenant_id, order_no)            -- order_no 唯一
uk_gacha_order_draw_id  (tenant_id, draw_id)             -- 一抽一单
uk_gacha_order_pay_tx   (tenant_id, pay_transaction_id)  -- 幂等兜底

-- gz_user_gacha_collection
uk_user_gacha_collection (tenant_id, user_id, machine_id, prize_id)  -- UPSERT 锚点
```

全部含 tenant_id，与强约束 #3 对齐。✅

### 盲盒语义检查

```bash
$ grep -rniE "抽奖|中奖|开奖" ruoyi-modules/ruoyi-gz-gacha/src/main/java/ | grep -v "注释\|javadoc\|GachaRarityEnum\|mapper"
# 命中均在 javadoc / 字段注释（如"累计抽奖次数"—技术内部语义）
# 用户可见错误码 msg：「扭蛋机暂时缺货」「用户信息异常」—— 无"抽奖/中奖/开奖" ✅
# mp api gz-gacha.ts：注释用「投币开盒/扭蛋/获得/开盒结果」—— 无禁用词 ✅
```

### 跳过 / 未跑

- `POST /app/gz/gacha/draw/start` 完整业务流（付款前缺货拦截 → MACHINE_EMPTY / 有货 → 返 jsapi 5 参）：mp-client sa-token 需微信 wx.login 真机授权，无法在 Tier 1B 环境模拟，跳给 Kevin 批量人验（但本 ticket 无 mp 页面，Tier 2 也跳过——GACHA-105 揭晓页才有真机验收场景）
- 真实微信商户号 0.01 元端到端：外部前置风险（甲方商户号未就绪），coder 已在风险提示 R5 标注，不作为 Tier 1B 卡点
- admin Playwright E2E：本 ticket 无 admin 前端页面，跳过

### 结论

✅ **Tier 1B 全通过 → GZ-GACHA-104 可 close（解锁下游 GACHA-105/106/107）**

| 验证项 | 结果 |
|---|---|
| mvn test 独立复核（29 单测） | ✅ 全绿，χ²=0.4486，BUILD SUCCESS |
| API 端点存在（/app/gz/gacha/draw/start） | ✅ 401 非 404，路由注册正确 |
| MACHINE_EMPTY=8009 语义 | ✅ 代码确认，msg 盲盒语义合规 |
| 无 V2/XML/gz_pay_order/amount_fen 引入 | ✅ grep 0 行 |
| SPI business_type='gacha' 注册 | ✅ 源码确认，无循环依赖 |
| 无退款实现（代码层） | ✅ grep 无 IPayRefundService/GachaRefundService 调用 |
| 无退款实现（DB 层） | ✅ gz_pay_refund 表总行数=0，GACHA-%行数=0 |
| DDL Flyway 应用成功 | ✅ V202606171400 success=1 |
| 3 表 UNIQUE 索引含 tenant_id | ✅ 全部对齐 AC1 + 强约束 #3 |
| 盲盒语义（用户可见文案无"抽奖/中奖"） | ✅ 错误码 msg + mp api 均合规 |
| 本 ticket 无 mp 页面 → 无 Tier 2 | ✅ 确认跳过，GACHA-105 才有真机验收场景 |
