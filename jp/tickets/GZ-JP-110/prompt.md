---
ticket: GZ-JP-110
track: ORDER
phase: D7
size: M
req_refs: [REQ-ORDER-011]
depends_on: [GZ-PAY-106]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
blueprint_refs:
  - FLOW:F-JP-10.step1
  - FIELD:gz_jp_order.business_status
  - FIELD:gz_jp_order.cancelled_time
accept:
  - name: 超时未付款关单、未超时不动、微信侧已付款不关
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpUnpaidExpireJobTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpUnpaidExpireJobTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpUnpaidExpireJobTest.xml
    counterfeit: 实现只看 create_time 不查微信支付单（已付款的单也被关）→ 用例「微信侧已付款不关」红
  - name: 关单前先关微信支付单，关失败本地不取消（不能让客人在锁释放后还能付款）
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpUnpaidExpireCloseOrderTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpUnpaidExpireCloseOrderTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpUnpaidExpireCloseOrderTest.xml
    counterfeit: 实现跳过 closeOrder 直接 markCancelled，或 closeOrder 抛错仍把本地单置 cancelled → 红
---

# GZ-JP-110 未付款订单超时自动关单

## §0 状态自检

1. `git -C code/main/RuoYi-Vue-Plus branch --show-current` = `feat/jp-snap`，`status --porcelain` 记基线。
2. 读 `FLOW:F-JP-10.step1`（`authority_lint.py show FLOW:F-JP-10.step1`）与 ADR-0025。
3. 确认死代码与范式都在：
   - `grep -n "markCancelled" ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/mapper/GzJpOrderMapper.java`
   - `ruoyi-modules/ruoyi-gz-bean/src/main/java/org/dromara/gz/bean/job/GzLocalBeanScheduler.java`（`@ConditionalOnProperty(gz.local-scheduler.enabled)` + `@Scheduled(fixedDelayString=...)` 范式）
   - `IWechatPayClient.queryByOutTradeNo` / `closeOrder` 两个方法签名。
4. prod 未部署 SnailJob：**不许**写 `@JobExecutor`，一律 `@Scheduled` + `gz.local-scheduler.enabled` 开关。

## What

新建 jp 域本地调度 `GzLocalJpScheduler`（`org.dromara.gz.jp.job`），每 5 分钟扫 `business_status='created'` 且 `create_time` 早于阈值（默认 15 分钟，`gz.jp.order.unpaid-expire-minutes` 可配）的订单，逐单：

1. 有支付流水 → `queryByOutTradeNo`：
   - 已支付 → 走与支付回调相同的处理补推进（复用 `IGzJpOrderService.onPaid` 的幂等守卫），**不关**；
   - 未支付 → `closeOrder` 关掉微信侧支付单；关失败（含微信返回「已支付」）→ 本轮跳过、记 warn 日志、下轮再试，**本地不取消**。
2. 无支付流水（从未拉起支付）→ 跳过 1。
3. `markCancelled`（条件更新 `created→cancelled` + `cancelled_time`）；affected=0 说明回调抢先，静默跳过。

单测两个类：`GzJpUnpaidExpireJobTest`（时间阈值 / 已支付补推进 / 无支付流水）、`GzJpUnpaidExpireCloseOrderTest`（closeOrder 先于 markCancelled、关失败不取消、ORDERPAID 不取消）。

## AC

- 超过阈值未付款的单被关；未到阈值的不动；微信侧其实已付款的单被补推进成 paid 而不是被关。
- 关单顺序固定为「查单 → 关微信单 → 关本地单」，任一步失败不落本地 cancelled。
- 拼团单与代切单同一任务（代切单的商品锁释放由 GZ-SNAP-304 挂进同一事务，本卡不做）。
- 调度开关沿用 `gz.local-scheduler.enabled`，不新增开关。

## 口径提示

- GZ-PAY-106 让支付单 5 分钟后在微信侧过期；本卡的 `closeOrder` 是兜底，覆盖 106 上线前创建、没带过期时间的在途单。两者都要。
- 查单发现微信侧已付款但本地支付单已是 timeout（迟到付款）：不关本地订单、不释放锁，error 日志，交给 106 的「迟到付款」人工处理。
- 每单独立事务，一单失败不影响其他单。
