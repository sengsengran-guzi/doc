# D7 QA r1 返工报告（FAIL-1 / O2）

> 主线程代为落盘（impl subagent 原文回传，压缩）。commit：RuoYi-Vue-Plus@ca2e8c534（task/D7），无迁移。真库回归资产：`doc/jp/regression/D7/D7QaConcurrencyTest.java`（断言未改）+ 新增 `D7ReworkO2RefundRaceTest.java`。

## 改动
| 文件 | 改动 |
|---|---|
| gz-common `GzPayTransactionServiceImpl.applyPaid` | markPaid affected=0 后重读 `selectById` → `selectByIdForUpdate`（当前读） |
| gz-common test `PayLatePaidTest` | 按 RR 建模（快照读 pending / 当前读 timeout），verify 走当前读；新增「affected=0 且当前读 paid → duplicated」 |
| gz-jp `GzJpRefundTxService` | `markAcceptFailed`（签名不变）改为 markFailed affected=1 才写商品行；新增 `public boolean markAcceptFailedIfRefunding`，共用私有 `writeAcceptFailed` |
| gz-jp `GzJpRefundServiceImpl` | `resendSameRefundNo` 改调 `markAcceptFailedIfRefunding`，false → `ALREADY_SETTLED` |
| gz-jp test `GzJpRefundCompensateTest` | +2（补偿补发抛错 / admin 重试抛错，回调已先落账 → 退款单、行、订单保持 refunded） |

## FAIL-1
根因：回调事务先普通 SELECT 建立 RR 快照，markPaid（当前读）看到 timeout affected=0，同事务 `selectById` 仍读快照 pending → duplicated。修：当前读重读；markPaid 已持该行 X 锁，不新增等待。未选「回调入口全改 FOR UPDATE」（波及拼豆 / 扭蛋 / 预购三条线上回调）。
同类排查（106/110/111 新增代码）：`reconcilePaid` 入口即 FOR UPDATE；`checkOneTimeoutOrder` / `closeRemoteOrderQuietly` 在事务外；`cancelExpired` 无重读；`replayPaid`→`onPaid` 首句 FOR UPDATE；`compensateStaleRefund` 无事务、守卫 UPDATE + affected 判断；`resendSameRefundNo` 的 selectById 在事务外。结论：仅此一处。

## O2
真库复现：连接 1 在外层事务里 `handleRefundNotify(SUCCESS)` 落账不提交持锁；连接 2 `setRefundAcceptFail(true)` 后走 `compensateStaleRefund`（NOT_FOUND→补发抛错）与 `retry`，`markFailed` 等锁（data_lock_waits=1），放行后 affected=0。
修前 6/6 红：`refund={status=refunded} item={refund_status=refund_failed, refund_amount_cent=null} order=refunded`。
修后 6/6 绿：`item={refund_status=refunded, refund_amount_cent=8000}`；retry 仍向 admin 抛「重新发起退款失败」（微信调用确实失败），数据一致。

## 真库并发回归
修前（HEAD jar）：`[QA-PAY106-RACE] round=1..3 status=timeout logs={duplicated=1, received=1}` → `Tests run: 3, Failures: 3`。
修后单跑：`round=1..3 logs={late_paid=1, received=1}` → `Tests run: 1, Failures: 0`。
整类：`D7QaConcurrencyTest Tests run: 7, Failures: 0`；`D7ReworkO2RefundRaceTest Tests run: 2, Failures: 0`。
复跑：两个文件拷到 `ruoyi-admin/src/test/java/org/dromara/gz/jp/job/`，`mvn test -DskipTests=false -pl ruoyi-admin -Dtest='D7QaConcurrencyTest,D7ReworkO2RefundRaceTest' -Dsurefire.failIfNoSpecifiedTests=false`，跑完删副本。

## 变异校验
gz-common 改回 `selectById` → `PayLatePaidTest 13/1 红`；gz-jp 去守卫 → `GzJpRefundCompensateTest 13/2 红`；已还原。

## accept 重跑（bash -c，项目根）
```
106#0 PayTimeExpireTest        tests="5"  failures="0"
106#1 PayLatePaidTest          tests="13" failures="0"
111#0 GzJpRefundCompensateTest tests="13" failures="0"
111#1 WechatPayQueryRefundTest tests="16" failures="0"
```
全量：gz-common 294 / gz-coupon 56 / gz-bean 329 / gz-user 42 / gz-recycle 125 / gz-jp 266，全部 0 failures 0 errors。

## 签名 / PayRefund*
PayRefund* diff（自 D7 基线）0 行；main 代码无删改 public 行；仅新增 `markAcceptFailedIfRefunding`。

## 血缘半径
- **applyPaid affected=0 分支**（gz_pay_transaction / gz_pay_callback_log）：调用方 `handlePaymentNotify` ← `WechatPayNotifyController:69`（生产回调）/ `GzPayTestController:107` / `applet/GzTestController:112`；`reconcilePaid` ← `PayOrderQueryServiceImpl:157,192`、`GzJpUnpaidExpireJob:237`；调度 `GzLocalPayScheduler`、`PayOrderQueryJobExecutor`。gz_pay_transaction 跨 pindou / preorder / gacha / jp / test 五个 business_type（回收不用此表）。并发写入方：`markTimeout`、`markClosed`、`markFailed`、另一笔 `markPaid`。异常传播：不新增 throw，不新增等待。
- **markAcceptFailed / markAcceptFailedIfRefunding**（gz_jp_refund / gz_jp_order_item）：调用方 首次受理失败（← `GzJpFulfillController:148`）、admin `retry`（← `GzJpRefundController:90`）、补偿补发（← `GzJpRefundCompensateJob:63` ← `GzLocalJpScheduler`）。争用写入方 `applyRefundSuccess` / `applyRefundFailure`（回调 + 补偿）、`markRetrying`。两表仅 gz-jp 使用。retry 对 admin 的抛错口径不变；补偿 affected=0 由 RESEND_FAILED 改 ALREADY_SETTLED（仅统计）。
- 同类不改：`PayRefundTxService.rollbackAccepted` 两条 UPDATE 均带 `status='refunding'` 守卫，无此缺陷（且受 PayRefund* 零改动约束）。

## 清理
gz_jp_order 7770000727–747 及其行 / 退款、gz_pay_transaction 33、gz_pay_callback_log 99、gz_pay_shipping_order 同批，精确硬删（scratchpad/rework/cleanup.sql）。

## 对下游
- 守卫 UPDATE affected=0 后再 SELECT 区分原因 → 事务内一律当前读（FOR UPDATE）。
- 「先推进主单再同步从表」两步写，从表一步必须看主单 affected（GZ-SNAP-306 shipping_diff 分支沿用）。
