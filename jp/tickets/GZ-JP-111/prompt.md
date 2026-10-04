---
ticket: GZ-JP-111
track: FULFILL
phase: D7
size: M
req_refs: [REQ-FULFILL-008]
depends_on: [GZ-JP-110, GZ-SNAP-101]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/service/internal/**
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/src/test/java/org/dromara/gz/common/pay/**
blueprint_refs:
  - FLOW:F-JP-10.step2
  - FIELD:gz_jp_refund.refund_type
accept:
  - name: 卡在 refunding 的退款单按微信查单结果补偿（成功落账 / 失败落终态 / 未受理同号补发）
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpRefundCompensateTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpRefundCompensateTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpRefundCompensateTest.xml
    counterfeit: 补偿时生成新的 out_refund_no 补发（会双退）或不查单直接补发 → 用例「NOT_FOUND 用同一 refund_no 补发 / SUCCESS 不补发」红
  - name: 通道层新增按退款单号查单，mock 与 real 都实现
    form: API
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-common/target/surefire-reports/*WechatPayQueryRefundTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am -Dtest=WechatPayQueryRefundTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-common/target/surefire-reports/TEST-*WechatPayQueryRefundTest.xml
    counterfeit: 只在接口加方法、mock 返回 null 或 real 未实现 → 用例断返回体 status / refundId 红
---

# GZ-JP-111 退款卡单自动补偿

## §0 状态自检

1. 读 `FLOW:F-JP-10.step2`、ADR-0020 §3（jp 独立退款链路，只共用通道层）。
2. `grep -n "RefundResult refund\|record RefundResult\|queryRefund" ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/service/internal/IWechatPayClient.java`
   —— 确认现无查退款单方法；找到 mock 与 real 两个实现类。
3. `GzJpRefundServiceImpl.retry` 的放行口径与 `handleRefundNotify` 的守卫 UPDATE（本卡补偿落账必须复用它，不能另写一套）。
4. ★ `git -C code/main/RuoYi-Vue-Plus status --porcelain` 记基线。完工时 `git diff` 必须证明：
   `IWechatPayClient` 只有**新增**方法与 record、既有方法签名一行没动；`pay/controller/PayRefundController.java`、
   `pay/service/impl/PayRefundServiceImpl.java`、`pay/service/internal/PayRefundTxService.java` 一行没动（拼豆 / 回收线上资金链路）。

## What

1. gz-common 通道层：`IWechatPayClient` 新增 `RefundQueryResult queryRefund(String outRefundNo)`（status ∈ SUCCESS / PROCESSING / ABNORMAL / CLOSED / NOT_FOUND，
   含 refundId / successTime / rawBody），real 实现走微信 V3「查询单笔退款」，mock 实现按 mock 退款登记表返回。
2. jp 域：`GzLocalJpScheduler` 加一个每 5 分钟的任务，扫 `gz_jp_refund.status='refunding'` 且 `update_time` 早于 10 分钟的单：
   - SUCCESS → 走与退款回调**同一个**落账方法（幂等，回调先到则 affected=0 跳过）；
   - ABNORMAL / CLOSED → `refund_failed` + `fail_reason`；
   - NOT_FOUND → 用**同一个** `refund_no` 补发（`attempt_count+1`）；
   - PROCESSING → 不动。

## AC

- 四种查单结果各有单测；补发永远复用原 `refund_no`。
- 落账与回调走同一方法，同一退款单不会被落两次（rollup 不重复）。
- 只新增通道层方法，不改既有签名；PayRefund* 三个类零改动。

## 口径提示

- 本卡不区分 `refund_type`：两种退款单（purchase_failed / shipping_diff）都要补偿，都调共用落账方法；
  shipping_diff 在落账方法里的分支（不碰订单行、不参与 rollup）由 GZ-SNAP-306 实现。
