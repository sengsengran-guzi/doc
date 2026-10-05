# GZ-JP-111 退款卡单自动补偿 · 完工报告

> 主线程代为落盘（impl subagent 原文回传，略有压缩）。commit：RuoYi-Vue-Plus@197d4e20b（task/D7），无迁移。

## §0 自检
- 基线 HEAD e3bc65aa1，干净；上游 PAY-106 / SNAP-101 / SNAP-102 / JP-110 均在分支上。
- `IWechatPayClient` 原无查退款方法；实现类仅 `MockWechatPayClient`、`WechatPayV3ClientImpl`。
- 回调 `handleRefundNotify` → `txService.applyRefundSuccess`（`markRefunded … WHERE status='refunding'`，affected=0 不写行不 rollup）；补偿复用同一方法。
- retry 口径：超过 `REFUNDING_SILENCE`（10 分钟）允许以同一 refund_no 重发；常量上移到 `IGzJpRefundService` 共用。
- 蓝图 FLOW:F-JP-10.step2、FIELD:gz_jp_refund.refund_type（补偿不区分类型）。SDK wechatpay-java 0.2.17 `RefundService.queryByOutRefundNo`。

## 改动
- gz-common `IWechatPayClient`（+56/-0）：新增 `queryRefund(outRefundNo)` + record `RefundQueryResult`（SUCCESS/PROCESSING/ABNORMAL/CLOSED/NOT_FOUND）。
- `MockWechatPayClient`（+70/-0）：mock 退款登记表（`putIfAbsent` 登记 PROCESSING）；测试注入 `setQueryRefundStatus` / `setQueryRefundFail`。
- `WechatPayV3ClientImpl`（+39/-0）：仅业务码 `RESOURCE_NOT_EXISTS` → NOT_FOUND，其余异常照抛（裸 404 不算）。
- test `WechatPayQueryRefundTest`（`@Tag("dev")`）：mock 7 + real 6（真实 SDK + 桩 HttpClient，断言 `GET /v3/refund/domestic/refunds/{no}` 与映射）+ 签名不变断言。
- gz-jp `GzJpRefundMapper.selectStaleRefunding`（status=refunding 且 `COALESCE(update_time,create_time) < deadline`，不按类型过滤）。
- `IGzJpRefundService`：`REFUNDING_SILENCE`、`compensateStaleRefund`、`CompensateOutcome`。
- `GzJpRefundServiceImpl.compensateStaleRefund`（不开事务，查单在事务外）：SUCCESS → `applyRefundSuccess`（affected=0 记 ALREADY_SETTLED）；ABNORMAL/CLOSED → `applyRefundFailure`；NOT_FOUND → 重读仍 refunding 后以**原 refund_no** 补发 + `markAccepted`，补发失败 `markAcceptFailed`；PROCESSING 不动；三种终态写 `gz_pay_callback_log`(type=jp_refund)。
- `job/GzJpRefundCompensateJob`（新）+ `GzLocalJpScheduler.refundCompensate()`（`${gz.local-scheduler.jp-refund-compensate-ms:300000}`）。
- test `GzJpRefundFixture`（payClient 改 spy、内存 selectStaleRefunding、update_time 对齐）、`GzJpRefundCompensateTest`（11，`@Tag("dev")`）。
- 受保护：`PayRefundController` / `PayRefundServiceImpl` / `PayRefundTxService` diff 0 行；三个通道类删除行 0。

## AI 自测
```
accept#0 exit=0  GzJpRefundCompensateTest tests="11" errors="0" skipped="0" failures="0"
accept#1 exit=0  WechatPayQueryRefundTest tests="16" errors="0" skipped="0" failures="0"
```
全量 `-pl gz-common,gz-bean,gz-recycle,gz-jp -am`：gz-common 293 / gz-coupon 56 / gz-bean 329 / gz-user 42 / gz-recycle 125 / gz-jp 264，全部 0 failures 0 errors，BUILD SUCCESS。
dev 库 EXPLAIN 可跑；dev 现有 refund：refunded 4 / refunding 3（均 purchase_failed）。共享脚本重启 `validated 186 migrations`。

## 风险
- 补发受理失败落 `refund_failed`（同 retry 口径），需 admin 再点「重新发起」；不选每轮重试以免永久错误每 5 分钟打微信。
- 107 遗留：受理超时但微信已受理 → 本地 refund_failed，后到 SUCCESS 回调因终态被当 duplicated；补偿只扫 refunding，覆盖不到。
- 静默期按 `update_time`（补发后刷新）；admin「可重试」按 `triggered_time`，两者都是 10 分钟。

## 对下游
- GZ-SNAP-306：shipping_diff 分支（不碰订单行、不参与 rollup）要加在 `applyRefundSuccess` / `applyRefundFailure` / `markAcceptFailed` 三处；`selectByOrderItemIds` 不区分类型的隐患仍在。
- 上线挂在 `gz.local-scheduler.enabled`（prod 默认 true）；real 模式补发需能解析退款回调地址。
