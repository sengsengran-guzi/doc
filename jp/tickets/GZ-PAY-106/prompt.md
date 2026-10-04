---
ticket: GZ-PAY-106
track: PAY
phase: D7
size: M
req_refs: [REQ-ORDER-012]
depends_on: []
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/test/java/org/dromara/gz/common/pay/**
  - code/main/plus-ui/src/views/gz-pay/**
  - code/main/plus-ui/src/lang/zh_CN.ts
  - code/main/plus-ui/src/lang/en_US.ts
blueprint_refs:
  - FLOW:F-JP-06.step4
  - FLOW:F-JP-06.step4b
accept:
  - name: 统一下单带 time_expire 且等于本地 expire_time（mock 与 real 两个实现都传）
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-common/target/surefire-reports/*PayTimeExpireTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am -Dtest=PayTimeExpireTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-common/target/surefire-reports/TEST-*PayTimeExpireTest.xml
    counterfeit: 只在 record 里加了字段，real 实现没把 time_expire 放进请求体（微信侧仍可无限期付款）→ 断请求体的用例红
  - name: 本地超时同时关微信单；超时后到达的成功回调 / 查单不再被吞，记 late_paid 并报错
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-common/target/surefire-reports/*PayLatePaidTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am -Dtest=PayLatePaidTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-common/target/surefire-reports/TEST-*PayLatePaidTest.xml
    counterfeit: timeout 单收到 SUCCESS 回调仍记 duplicated 静默返回，或把 timeout 单直接改成 paid 并分发业务（订单可能已被关、锁已释放）→ 红
---

# GZ-PAY-106 支付单过期即不可付 + 迟到付款不再被吞（共享支付通道）

## 背景（纸面推演 K1，Kevin 2026-10-03 拍板 D7 修）

现状（已核实代码）：`createOrderInternal` 只在本地写 `expire_time = now + 5min`，`UnifiedOrderRequest` 没有过期时间；
`payExpire` → `markTimeout` 只改本地状态、不关微信单；回调里 `markPaid … WHERE status='pending'` 对 timeout 单 affected=0，
被记成 `duplicated` 静默返回。⇒ 客人在收银台停留超过 5~10 分钟再付款：扣款成功、业务单不变、无告警。

已查 prod（2026-10-03，只读）：432 笔 timeout 单全是拼豆，没有任何一笔收到过付款回调 —— 历史无实际损失，这次是堵洞。

## §0 状态自检

1. ★ 这是拼豆 / 回收线上在用的收款链路。`git -C code/main/RuoYi-Vue-Plus status --porcelain` 记基线；
   完工时 `git diff` 必须证明：既有 public 方法签名一行没改；`PayRefund*` 三个类零改动。
2. 读 `GzPayTransactionServiceImpl`（`createOrderInternal` / `handlePaymentNotify` / `applyPaid` / `reconcilePaid` / `expireTimeoutOrders`）、
   `GzPayTransactionMapper.markPaid` / `markTimeout`、`IWechatPayClient` 的 real / mock 实现、`PayOrderQueryServiceImpl`。
3. 微信 V3 JSAPI 下单 `time_expire` 格式（RFC3339，带时区）——用 context7 或官方文档确认，别凭记忆。

## What

1. `UnifiedOrderRequest` 新增 `timeExpire`（`OffsetDateTime`，可空；保留旧构造方式以免改动调用方）；real 实现写进请求体，mock 实现记录下来供测试断言。
   `createOrderInternal` 传入 `expire_time`。
2. `markTimeout` 成功后调 `closeOrder`（失败只记 warn，不回滚本地 timeout）——覆盖本卡上线前创建、没带过期时间的在途单。
3. 迟到付款：回调 `handlePaymentNotify` 与查单 `reconcilePaid` 遇到「微信 SUCCESS + 本地 timeout / closed」→
   回调日志 `process_status='late_paid'`（带金额、transaction_id）+ `log.error`；**不改**交易状态、**不分发**业务（业务单可能已关、孤品锁可能已给别人）。
   查单任务的扫描范围加上「近 24 小时内 timeout 的单」，让迟到付款即便回调丢失也能被发现。
4. admin 支付流水列表（`views/gz-pay/`）加「迟到付款」筛选（按 callback_log `late_paid` 关联），标红提示「需在商户平台人工原路退款或补单」。
5. 单测：`PayTimeExpireTest`、`PayLatePaidTest`。

## AC

- 两条 accept 绿。
- 拼豆 / 回收的支付与退款行为零变化（只多了过期时间与迟到兜底）：gz-common / gz-bean / gz-recycle / gz-jp 全部单测照旧绿，
  现有小程序 `code/main/miniapp` 支付相关 E2E 不回归（D7 QA 门跑）。
- 部署后真机验一次：下单后等 6 分钟再付，微信提示订单已过期（进 D15 演练 R7 一起做）。
