# GZ-JP-110 完工报告：未付款订单超时自动关单

> 主线程代为落盘（impl subagent 原文回传，略有压缩）。commit：RuoYi-Vue-Plus@34e849c28（task/D7），无迁移，全部改动在 ruoyi-gz-jp。

## §0 自检
- 基线 HEAD 2c46e7f1d，干净；上游 GZ-PAY-106 已提交（`reconcilePaid` 有 LATE_PAID 分支）。
- 蓝图 FLOW:F-JP-10.step1；`markCancelled`（GzJpOrderMapper，带 `WHERE business_status='created'` 守卫）原为死代码。
- 照搬 `GzLocalBeanScheduler` 范式（`@ConditionalOnProperty(gz.local-scheduler.enabled)` + `@Scheduled`），不写 SnailJob `@JobExecutor`。

## 实现
| 文件 | 说明 |
|---|---|
| `job/GzLocalJpScheduler.java`（新） | 触发器，`fixedDelayString=${gz.local-scheduler.jp-unpaid-expire-ms:300000}`，异常只记日志，无新开关 |
| `job/GzJpUnpaidExpireJob.java`（新） | 阈值 `${gz.jp.order.unpaid-expire-minutes:15}`；`TenantHelper.ignore` 扫全租户，每批 200 |
| `service/internal/GzJpUnpaidExpireTxService.java`（新） | `cancelExpired`（markCancelled==1）/ `replayPaid`（onPaid），均 REQUIRES_NEW |
| `mapper/GzJpOrderMapper.java`（改） | `selectUnpaidExpired(deadline, limit)` |
| test：`GzJpUnpaidExpireFixture` / `GzJpUnpaidExpireJobTest`(9) / `GzJpUnpaidExpireCloseOrderTest`(8) | |

逐单：**查单 → 关微信单 → 关本地单**，任一步不通不写 cancelled。
- 本地已有 paid 流水而订单仍 created → `replayPaid`；refunding/refunded → error 跳过。
- 只查带 prepay_id 的流水；SUCCESS+本地 pending → `reconcilePaid`（同回调路径）不关单；SUCCESS+本地 timeout/closed/failed → 迟到付款，error，保持 created、不释放锁；REFUND → error 跳过；USERPAYING → 本轮不关（保守，ticket 未写）；CLOSED/REVOKED → 不再 closeOrder；NOTPAY/PAYERROR → 待关；查单异常 → 本轮跳过。
- closeOrder 任何异常（含 ORDERPAID）→ warn，本地不取消；`cancelExpired` affected=0（回调抢先）静默跳过。外部调用不在 DB 事务内。
- 未动 gz-common（只用现有 public API）。

## Accept（项目根，bash）
```
#0 EXIT=0  TEST-org.dromara.gz.jp.job.GzJpUnpaidExpireJobTest.xml: tests="9" errors="0" skipped="0" failures="0"
#1 EXIT=0  TEST-org.dromara.gz.jp.job.GzJpUnpaidExpireCloseOrderTest.xml: tests="8" errors="0" skipped="0" failures="0"
```
反例（临时只看 create_time 直接关单，已还原）：`Tests run: 17, Failures: 12`。
gz-jp 全模块：18 类 259 用例，0 failures / 0 errors。
新 SQL dev 库实跑命中 3 条 8 月遗留 created 单（id 27 / 29 / 99108）。共享脚本重启后 `Successfully validated 186 migrations`，上下文装配成功；dev 下 `gz.local-scheduler.enabled` 缺省 false，未真实触发。

## 对下游
- GZ-SNAP-304 锁释放：加在 `GzJpUnpaidExpireTxService.cancelExpired` 同一 REQUIRES_NEW 事务内，仅 affected==1 时释放。
- onPaid 扩展（写下单任务）：`replayPaid` 与 `reconcilePaid` 都会走到 `onPaid`，须幂等、不调日本服务。
- F-JP-10.step2 退款补偿调度：在 `GzLocalJpScheduler` 加 `@Scheduled` 方法即可。
- **新测试类必须加 `@Tag("dev")`**（根 pom surefire `<groups>${profiles.active}</groups>`，否则 0 条、无报告）。accept 的 `rm -f *X*` 在 zsh 下无匹配会 exit 1，须用 bash 跑。

## 风险
- 迟到付款单永久停在 created，每 5 分钟一条 error，无 admin 手动取消入口。
- 查单持续失败的单同样停留。
- 关微信单后本地支付流水仍 pending，等 PAY 超时任务标 timeout。
- REFUND 分支处理为语义推断，无真实样本。
