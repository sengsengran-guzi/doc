# GZ-SNAP-306 实施报告

STATUS: DONE

- 后端分支 `task/D10`：主实现 `ac990091a`；退款明细当前读收口 `54f6e9a21`。
- 新迁移：none。无新依赖、无真实煤炉请求、支付 mock、主 miniapp 全目录未改。
- §0：305 已在基线 `f8e7e9ded`；gz-jp 离线 compile exit 0；既有唯一未跟踪文件为 admin 临时日志，未动。关联 flow/field/ownership/需求/ADR-0025/P3/P13/项目技能已读。

## 实现

全部代码在 `ruoyi-modules/ruoyi-gz-jp`，10 文件，无越界代码文件：

- 新 `controller/GzJpSnapPurchaseController.java`、`service/internal/GzJpSnapManualService.java`：manual-list 按付款时间升序，返回原因、原链接、锁价、预估运费、证据 ID；写入口必须 manual_pending，交易号必填、实际价≤锁价，终态 409。权限对齐401：读 `gz:jp:snap:purchase:query`，写 `gz:jp:snap:purchase:manual`。
- `service/internal/GzJpSnapExecutorTx.java`、`mapper/GzJpSnapPurchaseMapper.java`：人工和自动共用成功/失败出口，审计操作人/备注；失败退款计划、任务状态和释放本人商品锁在同事务。锁顺序 snap→order→item→task，任务当前读；人工成功不填实际到付运费。
- `service/internal/GzJpRefundTxService.java`、`service/impl/GzJpRefundServiceImpl.java`、`mapper/GzJpRefundMapper.java`：差价按锁定快照汇率向上取整，≤0不退；发起/成功/失败/受理失败/重试均不写订单行、不rollup；失败退款扣成功差价，pending/reserved一并占预算，行/订单不能超退。查重只把purchase_failed视为失败退款记录。退款明细 FOR UPDATE 后 Java 求和，重试也查预算；主退款单affected0不写从表。
- 新 `GzJpShippingDiffRefundTest`、`GzJpSnapManualTest`；调整一期 `GzJpRefundFixture` 支持当前读锁行。

## 验证与 raw

遵循最新授权合并执行accept和直接受影响一期测试，不跑全项目与305四故障。

```sh
JAVA_TOOL_OPTIONS='-javaagent:/Users/wkui/.m2/repository/org/mockito/mockito-core/5.17.0/mockito-core-5.17.0.jar' \
/opt/homebrew/bin/mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am \
-Dtest=GzJpShippingDiffRefundTest,GzJpSnapManualTest,GzJpRefundStatusRollupTest,GzJpRefundCallbackIdempotentTest \
-Dsurefire.failIfNoSpecifiedTests=false
```

raw XML：ShippingDiff tests=6 errors=0 skipped=0 failures=0；Manual tests=4 errors=0 skipped=0 failures=0；一期Rollup tests=18 errors=0 skipped=0 failures=0；一期Callback tests=11 errors=0 skipped=0 failures=0。合计39/39。最终预算锁明细改动后只复跑前两类10/10，29条一期证据复用。完整raw见 `evidence/targeted-tests.log`、`final-targeted-tests.log` 和4份XML。

```sh
bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp
```

最终raw：

```text
BACKEND UP (commit 54f6e9a21, branch task/D10)
Successfully validated 187 migrations (execution time 00:00.105s)
```

共享重启后才跑真实本地HTTP+MySQL探针，未起第二后端。完整API证据 `/opt/homebrew/bin/python3.11 /tmp/306-live.py`（evidence/http-db-smoke.log）：

```text
artifact sha256=2f2ca9f183d1ad44c95522eb481f9a0bff8a5b81c1c89db7ddf18db49ae69efc
manual list: paid-time order, locked price, estimate and original URL present
HTTP success/reject/terminal guard + diff callback replay + failed remainder 913 + concurrent [200,409]; DB budget violations=0; live Mercari=0
exact fixture rows restored; no shared pricing/FX/account changes
```

最终产物只复验预算/并发核心：`/opt/homebrew/bin/python3.11 /tmp/306-budget.py`（evidence/final-budget-concurrency.log）：

```text
artifact sha256=29baeb9f4c14ba4f4e5a315ce1c634ad22059203f554e65124f54b632ab05b36
budget current-read probe: failed remainder 913 + concurrent [200,409]; DB budget violations=0; live Mercari=0
exact fixture rows restored; no shared pricing/FX/account changes
```

探针验证源文件mtime不晚于安装jar。首轮实际HTTP验证list字段/顺序、涨价409、人工成功订单行await_seller_ship/运费NULL/操作人1、成功终态禁止填失败、差价SUCCESS重放行退款列NULL且订单paid、失败余款913、释放锁、双并发只一笔退款、非失败退款额≤行金额。最终锁明细产物重新验证差价87+失败913=1000、并发[200,409]只一笔退款与预算零违规。临时fixture三个精确ID逐表删除恢复；共享价格/FX/采购账号未改。

环境修正：首个脚本登录误用上游默认租户000000，活库admin实际1001；未创建fixture即停止，改为1001后通过。最终退款预算按主线程建议锁明细后求和，避免aggregate锁语义与RR旧快照。文档REQ-SNAP-031旧note由主线程已回改到仓填运费，不改商业口径。

## 下游

307在到仓事务里用 `GzJpRefundTxService.createShippingDiff(orderItemId, actualShippingJpy)` 建plan，提交后调用 `dispatchSnapRefundPlan(plan, List.of())`。`GzJpRefundServiceImpl.refundShippingDiff` 是含外部dispatch的便捷入口，不能包在307外层事务中。差价处理中失败退款会明确拒绝，等差价终态后重试；失败差价在全额失败退款占预算后不能重新退款。

最终git仅遗留基线admin tmp日志；doc报告/evidence交主线程统一提交。后端保留共享单例给307继续，不由子agent停止。无已知未解决产品缺陷。
