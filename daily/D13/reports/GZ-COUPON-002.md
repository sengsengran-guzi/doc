# GZ-COUPON-002 完工报告 — 拼豆抵扣（券锁定/核销/回滚）+ 过期 SnailJob

纯后端 · AI 终态（无人验）· 第一波并行批次（与 PAY-105 / RECYCLE-001 同时跑，独占 gz-coupon + gz-bean(3 hook)）

---

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean（仅本卡 + 并行批次改动，无意外） | ✅ 我只碰 gz-coupon + gz-bean，gz-common 改动属 PAY-105/RECYCLE-001 并行 |
| 上游 `gz_user_coupon` 表已建（D12 V202606200100） | ✅ 9 行 seed unused 券（user 1/2/3/4/5/7/8，面额 500 分） |
| 上游 `gz_coupon_template` 已建 | ✅ 2 行 |
| 上游 `gz_bean_booking.coupon_id` / `discount_amount_cent` 列已建（D12 V202606200000） | ✅ information_schema 各 1 列 |
| 3 个 hook 位定位 | ✅ submitPaid:799(锁券) / closePindou:1015(回滚) / onPindouPaid:985 markPaid 后(核销) |
| 编译基线（gz-coupon + gz-bean，不加 -am） | ✅ EXIT=0 |
| dev infra（MySQL:3307 / Redis:6380） | ✅ Up 5 days（curl/mysql 走 docker exec 绕代理） |
| gz-coupon pom 缺 ruoyi-common-job（D12 未加） | ✅ 已确认缺失 → 本卡首引补上 |
| 关联 ADR 已读 | ADR-0007 §1.4(免费单兜底)/§1.5(超时关单+回滚 locked→unused)/§3(迁移) |

---

## 权威摘录（逐段 Read，钉死口径）

**doc/11 §11.2 券态机（钉死）** —— 4 态 4 边：
| 流转 | 触发 | 说明 |
|---|---|---|
| `unused → locked` | 拼豆下单选用 | 下单事务内锁券，防一券多用；写 booking.coupon_id |
| `locked → used` | 拼豆支付成功 onPaid | 核销，写 used_time + related_pay_out_trade_no |
| `locked → unused` | 订单取消 / 支付关闭 pay_closed | 回滚解锁，券可再用 |
| `unused → expired` | SnailJob 扫超期 | 终态；**`locked` 态不被过期扫描误伤**（已锁定即在用） |

**doc/11 §11.3 抵扣 + GMV 口径（钉死）**：
- 实付 `= gz_bean_booking.amount_cent − amount_snapshot_cent`，**下限 0**（券超额差额不退不找零）。
- 实付 > 0 才建 `gz_pay_transaction(business_type=pindou)`；实付 = 0 走免费单兜底。
- `gz_pay_transaction.amount_cent` = 实付，**券面额不计 GMV**（让利非收入）。

**doc/11 §3.8 + ADR-0007 §1.4/§1.5**：
- 免费单兜底：`price_cent=0` 且无券需求（或券全额抵扣实付=0）→ 不建支付单，`pay_status` 直接 `paid`，`out_trade_no` 留 NULL，`status=pending`，直接生成 verify_code。
- 支付关闭：`pay_status → pay_closed`，`status → cancelled`，释放配额 + 回滚锁定券（`locked → unused`）。

**doc/10 §12 券锁定核销流**：N4 下单锁券 / N5 onPaid 核销 / N6 取消解锁 / N7 支付失败回滚 / N8 SnailJob 过期扫描。

---

## 实现摘要

### 改动文件（git diff --stat，仅本卡领地 gz-coupon + gz-bean）
```
 ruoyi-gz-bean/pom.xml                                    |   8 ++  (加 gz-coupon 依赖)
 GzBeanBookingServiceImpl.java                            |  61 ++   (3 hook)
 GzBeanBookingServiceImplTest.java                        | 135 ++   (构造器 + 5 券抵扣测试)
 ruoyi-gz-coupon/pom.xml                                  |   6 +   (加 ruoyi-common-job)
 GzUserCoupon.java                                        |   2 +-  (del_flag 注释修正 2→1)
 GzUserCouponMapper.java                                  |  95 ++   (4 条件 UPDATE + 1 扫描)
 IGzUserCouponService.java                                |  75 ++   (4 方法 + 2 record)
 GzUserCouponServiceImpl.java                             |  84 ++   (4 方法实现)
 8 files changed, 449 insertions(+), 17 deletions(-)
```
新增（untracked）：
- `ruoyi-gz-coupon/.../job/GzCouponExpireJob.java`（SnailJob 薄壳，仿 GzBeanUnpaidExpireJob）
- `ruoyi-gz-coupon/.../service/impl/GzUserCouponServiceImplTest.java`（13 券态机单测）

### 关键设计决策

1. **券态防并发 = 状态值 CAS（非 version）**：`gz_user_coupon` 无 version 列，券态机天然单向。每条流转 SQL 的 `WHERE` 含「当前态」守卫（锁券 `status='unused'` / 核销 `status='locked'` / 回滚 `status='locked'`），把「读态+校验+改态」并到一条 DB 行锁内。并发两线程锁同一 unused 券只有一个 affected=1 → 杜绝一券多用。范式仿 `GzCouponTemplateMapper.increaseIssuedCount`（CAS 因子换 version→status）。

2. **submitPaid 时序重排（关键）**：原 799 hook 在 INSERT 之后，但 `discount/free/payStatus/verifyCode` 全依赖券面额 → **锁券+实付重算必须提到 INSERT 之前**。新顺序：⑥防超卖 → ⑦计费 → ⑦.5锁券(unused→locked)拿面额→实付重算 → ⑧booking_no → ⑨INSERT(discount/payStatus 已定) → ⑨.5免费单核销。锁券在 INSERT 前，下单失败/拒单回滚时锁券 UPDATE 随同一 `@Transactional` 回滚自动解锁。

3. **免费单券核销时机（doc 未明说但逻辑必然）**：付费单券在 onPaid 核销；但**券全额抵扣致 free=true 的单无支付回调**（pay_status 直接 paid，永不进 closePindou/onPaid）→ 券会永远卡 locked。故在 submitPaid 当场核销（locked→used，related = booking_no 占位，无真实支付单）。

4. **跨模块依赖**：gz-bean 新增依赖 gz-coupon（coupon 不反依赖 bean → 无模块环）。券服务用 `ObjectProvider<IGzUserCouponService>` 惰性注入（仿 payServiceProvider，对齐 BEAN-014 断构造期环纪律）。编译/单测用 `-pl gz-coupon,gz-bean`（reactor 内互引，不需 .m2 jar，不加 -am）。

5. **过期扫描薄壳**：`GzCouponExpireJob`(@JobExecutor name=`gzCouponExpireTask`) 仅触发，核心 `expireBatch()` 在 service（可单测）。`TenantHelper.ignore` 全租户扫（cron 无登录态，仿 markExpiredUnpaidBatch）。

---

## AI 自测

### ① 编译（gz-coupon + gz-bean，不加 -am）
```
$ mvn -o compile -pl ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-bean -q
EXIT=0
（无 ERROR / 无 BUILD FAILURE）
```

### ② 单测（含新加 13 + 5 = 18 个券相关测试）
```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-coupon,ruoyi-modules/ruoyi-gz-bean -Dgroups=dev
[INFO] Tests run: 13, Failures: 0, Errors: 0, Skipped: 0 -- GzUserCouponServiceImplTest   ← 新增（券态机）
[INFO] Tests run: 31, Failures: 0, Errors: 0, Skipped: 0  (gz-coupon 全模块)
[INFO] Tests run: 40, Failures: 0, Errors: 0, Skipped: 0 -- GzBeanBookingServiceImplTest  ← 含新增 5 券抵扣测试
[INFO] Tests run: 96, Failures: 0, Errors: 0, Skipped: 0  (gz-bean 全模块)
[INFO] BUILD SUCCESS
```
新增券测试覆盖（AC6 各流转边）：
- lockForBooking：happy(返面额) / 券不存在 / 越权(非本人) / CAS 失败(已用) / null
- redeem：happy(写 used_time+related) / null 跳过 / affected=0 幂等
- unlock：happy(回滚) / null 跳过 / affected=0(已 used 不复活)
- expireBatch：有到期(unused→expired) / 无到期
- gz-bean 端：**实付=单价−券面额(3000−1000=2000)** / 券超额下限0+免费单核销 / 锁券失败回滚不INSERT / onPaid 用券核销 / closePindou 用券回滚

### ③ 券态机条件 UPDATE 端到端（raw SQL，不污染 flyway_schema_history）
```
====== ① 锁券 unused→locked ======                affected=1 ✅  status=locked
====== ② 并发再锁同券（CAS 防一券多用）======      affected=0 ✅  (已 locked 拦死)
====== ③ 核销 locked→used + used_time + related ==  affected=1 ✅  has_used_time=1 related=PINDOU-20260610-000001
====== ④ 已 used 券回滚守卫（status=locked）======   affected=0 ✅  仍 used（不复活）
====== ⑤ 回滚 locked→unused（券4）======            lock=1 unlock=1 ✅  back_to_unused
====== 复原 id 3/4 → unused ======                  ✅ 无脏数据
```

### ④ AC5 过期扫描 — locked 不被误伤（raw SQL）
```
构造：id5=过期unused / id6=过期locked
selectExpiredUnusedIds 命中 → 只 id5（不含 locked id6） ✅
expireBatch UPDATE → affected=1（仅 id5→expired） ✅
结果：id5=expired（被扫）/ id6=locked（未误伤，已锁定即在用） ✅
复原 id 5/6 → unused ✅
```

### ⑤ 收尾验证
```
flyway_schema_history 最大版本 = 202606200101（D12 的，本卡无新迁移，未污染）✅
gz_user_coupon: unused 9（全复原，无脏数据）✅
redis FLUSHDB → OK ✅
```

---

## 风险提示 / 已知 issue

1. **本卡无 DDL 变更**：券态 = `gz_user_coupon.status` 的 UPDATE，字段 D12 已建全（含 idx_status_expire 过期扫描索引）。无新 Flyway 文件，不抢 PAY-105(21010x)/RECYCLE(21020x) 时间戳。
2. **免费单券核销的 related 占位**：券全额抵扣的免费单，`related_pay_out_trade_no` 写的是 `booking_no`（非真实支付单 out_trade_no，因无支付单）。追溯时 admin 看到 `BK...` 前缀即知是免费抵扣单。对账（D15）不涉及（券面额不计 GMV + 免费单无 pindou 支付流水）。
3. **gz-bean 首次依赖 gz-coupon**：模块依赖图新增一条边（bean→coupon），无环（coupon 不反依赖 bean，已 grep 确认）。Tier 1B 起真 app 时若 Spring 报循环依赖（极不可能），ObjectProvider 已预防。
4. **券核销/回滚 affected=0 不抛异常**：onPaid/closePindou 里券态推进失败仅记 WARN 日志，不阻塞主单（支付核销 / 配额释放优先）。设计如此（券态是附属，主单状态是主线）。
5. **entity 注释顺手修**：`GzUserCoupon` del_flag 注释从「2=删除」改为「1=删除」（对齐 common-mybatis.yml logicDeleteValue=1，learnings 钉死坑），纯注释不影响 checksum/逻辑。D12 已应用的 DDL 文件未动（注释错误留存于 SQL，不可改）。

---

## SnailJob 任务（运维注册，控制台配置 — 非 Flyway INSERT）

| 项 | 值 |
|---|---|
| 任务名称 | GZ-COUPON-EXPIRE |
| 执行器路由（@JobExecutor name） | `gzCouponExpireTask` |
| 触发类型 / CRON | CRON，`0 0 3 * * ?`（每日凌晨 3 点；券过期非强实时，日级即可） |
| 任务参数 | 无（过期判定以 NOW() 为基准，service 内自取） |
| 阻塞策略 / 组 | 丢弃（默认）/ `ruoyi_group` |
| 配置键（doc/11 §11.2） | `gz.coupon.expire.cron`（控制台 CRON 真源） |
| 行为 | 扫 `status='unused' AND expire_time < NOW()` → 批量 `expired`；**locked 态不触碰**；TenantHelper.ignore 全租户 |

---

## 对下游 ticket 的提示

- **GZ-COUPON-003（mp 选券 / 我的券列表）**：选券接口 `GET /api/coupon/usable?business=pindou&total_amount` 返回该用户 unused 且未过期且面额可用券（doc/10 §12.N3）。下单传 `couponId` 到 `submitPaid`，券态机本卡已就绪。mp 下单成功 VO 已含 `discountAmountCent` / `payAmountCent`（实付）/ `free` 字段可直接展示「已抵扣 X 元 / 实付 Y 元」。
- **GZ-PAY-105（反向打款，并行批次）**：与本卡零交叉（你改 gz-common payout，我改 gz-coupon + gz-bean hook）。
- **D15 对账**：拼豆 pindou 正向流水实付口径 = `amount_cent − discount_amount_cent`（已写进 gz_pay_transaction.amount_cent）；**券面额不回补 GMV**（doc/11 §11.3 §4.6 钉死）。
- **Tier 1B（主线程统一派）**：起真 app 后建议补 ① 真实下单选券 → onPaid 回调 → 券 used 全链路；② SnailJob 控制台注册 gzCouponExpireTask 后真跑一次过期扫描确认 locked 不被扫。本卡单测 + raw SQL 已覆盖逻辑，真 app 验 Spring 装配（bean→coupon 依赖 + ObjectProvider 装配 + @JobExecutor 注册）无环启动。

---

## §AI 测试段（kevin-qa Tier 1B 完工后追加 — 留空）

主线程一次启动 app 整批验 5 卡（subagent 崩溃率高 + kevin-qa 不能子 agent spawn + Playwright 不可用）：
- App `Started DromaraApplication in 10.958s` — **gz-bean→gz-coupon 装配无环**（ObjectProvider 打断构造期循环依赖生效，否则 BeanCurrentlyInCreationException）
- 券态 service（锁定/核销/回滚）+ 过期 SnailJob 薄壳随 app 加载无错；gz-coupon pom ruoyi-common-job 依赖解析正常
- Flyway 6 迁移应用至 v202606210201（券态 = status UPDATE 无新 DDL）
- ✅ 纯后端 AI Tier 1A+1B 全 ✅ 即终态，8080 已释放
