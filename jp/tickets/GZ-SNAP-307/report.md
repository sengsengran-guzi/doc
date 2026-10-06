# GZ-SNAP-307 实现报告

STATUS: DONE
COMMIT: RuoYi-Vue-Plus@366dad57b（task/D10）
MIGRATIONS: none；启动校验187条迁移。

## 实现

新增交易控制器 `/system/gz/jp/snap/trade`、交易事务与外层dispatch service、按账号巡检job。
- await_ship→shipped→arrived→rated；cancelled仅await_ship/shipped；returned仅arrived；同目标幂等，倒退/越级409。
- 到付到仓必填非负日元金额；包邮金额恒NULL。到仓/评价时间与配置期限同事务落库；到仓调用306 `createShippingDiff` 建plan，提交后dispatch且传空item ids，差价不触发行状态/rollup。
- 取消seller_cancel、退货inspect_ng保持purchase_status=success（双状态机正交），共用305共享系统失败出口→行purchase_failed/退款预留/释放仅本人active锁，不走admin守卫。
- 交易短事务按snap→order→item→task当前读；saveTrade版本affected必须1，之后才退款/释放。
- 巡检只取success且await_ship/shipped行、按账号一次GET trades，交易号与商品ID双匹配；只处理shipped/cancelled，不自动评价。巡检失败记日志不改状态；默认20分钟，读取gz.jp.snap.trade.patrolMinutes。沿用既有gz.local-scheduler.enabled装置开关，默认关闭；测试未启用真实巡检。
- 履约advance/ship在锁行后执行统一mapper守卫；mark-failed通过事务服务adminEntry=true执行同守卫。snap且未rated/缺task整批409并列出行id。内部四参数退款方法不启用守卫。一期batch转移规则未改。
- list分页按rate_deadline_at/id升序；reminder-count取arrived且deadline≤当前+12h（包含已逾期）。权限读purchase:query、写purchase:trade，对齐401菜单。

改动10个生产文件：controller/GzJpSnapTradeController.java；job/GzJpSnapTradeJob.java；mapper/GzJpOrderItemMapper.java、GzJpSnapPurchaseMapper.java；service/impl/GzJpFulfillServiceImpl.java、GzJpRefundServiceImpl.java；service/internal/GzJpRefundTxService.java、GzJpSnapExecutorTx.java、GzJpSnapTradeService.java、GzJpSnapTradeTx.java。
新增3个测试文件：job/GzJpSnapTradeJobTest.java；service/internal/GzJpSnapTradeTest.java；service/impl/GzJpFulfillSnapGuardTest.java。
全部在touches的ruoyi-gz-jp内，OUT_OF_TOUCHES: none。未修改主miniapp、无新依赖、无push、无合staging、真实煤炉请求0。

## 验证

基线task/D10、306 54f6e9a21存在；compile exit0。基线仅未跟踪admin tmp日志，未清理。

```sh
export PATH=/opt/homebrew/bin:$PATH
export JAVA_TOOL_OPTIONS='-javaagent:/Users/wkui/.m2/repository/org/mockito/mockito-core/5.17.0/mockito-core-5.17.0.jar'
mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapTradeTest,GzJpFulfillSnapGuardTest,GzJpFulfillStateMachineTest,GzJpFulfillStateMachineSnapTest,GzJpShippingDiffRefundTest,GzJpSnapExecutorTest -Dsurefire.failIfNoSpecifiedTests=false
mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapTradeJobTest -Dsurefire.failIfNoSpecifiedTests=false
```

实际53/53，errors=failures=skipped=0。新增trade8、guard5、patrol2；直接受影响一期履约18+snap4、差价6、共享失败出口10。accept#0 trade8 pass，accept#1 guard5 pass，一期履约22 pass。raw XML和日志在evidence；不全项目重跑、不机械三轮/变异。复用306其余29条退款callback/rollup有效证据、305四HTTP故障证据，不重跑外部请求。

```text
TEST-org.dromara.gz.jp.service.internal.GzJpSnapTradeTest.xml tests=8 failures=0 errors=0 skipped=0
TEST-org.dromara.gz.jp.service.impl.GzJpFulfillSnapGuardTest.xml tests=5 failures=0 errors=0 skipped=0
TEST-org.dromara.gz.jp.job.GzJpSnapTradeJobTest.xml tests=2 failures=0 errors=0 skipped=0
TEST-org.dromara.gz.jp.service.impl.GzJpFulfillStateMachineTest.xml tests=18 failures=0 errors=0 skipped=0
TEST-org.dromara.gz.jp.service.impl.GzJpFulfillStateMachineSnapTest.xml tests=4 failures=0 errors=0 skipped=0
TEST-org.dromara.gz.jp.service.impl.GzJpShippingDiffRefundTest.xml tests=6 failures=0 errors=0 skipped=0
TEST-org.dromara.gz.jp.service.internal.GzJpSnapExecutorTest.xml tests=10 failures=0 errors=0 skipped=0
```

提交后仅共享脚本clean install/restart：

```sh
/bin/bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp
```

```text
BACKEND UP (commit 366dad57b, branch task/D10)
Successfully validated 187 migrations (execution time 00:00.102s)
```

真实本地HTTP+MySQL必要CRUD/退款对账与一轮双连接竞争：

```sh
/opt/homebrew/bin/python3.11 /tmp/307-live.py
/opt/homebrew/bin/python3.11 /tmp/307-race.py
```

完整可复验脚本及raw日志均在evidence（脚本不含secret/token，运行登录即时取得token）。使用真实Spring controller/service/mapper/MySQL/Redis，只有微信mock通道；没有真实煤炉请求。probe确认生产源文件mtime≤安装jar，sha256如下。

```text
artifact sha256=ffc6a47f0010d74f2e180178295f2ad74919ce10bb0aa4db8199f4f4e57b4cdf
list+manual purchase→shipped→arrived→rated + guards all three mixed-batch paths 409; owner read/write403; cancellation1000; pending diff return rolls back; callback replay diff87 + returned913 =1000; released own locks; budget violations0; live Mercari0
exact fixture rows restored; no shared pricing/FX/account changes
artifact sha256=ffc6a47f0010d74f2e180178295f2ad74919ce10bb0aa4db8199f4f4e57b4cdf
two independent HTTP/DB transactions arrival vs cancel: codes=[409, 200]; final=cancelled:purchase_failed:0; one refund reservation=1000; budget<=1000; live Mercari0
exact fixture rows restored; no shared pricing/FX/account changes
```

四个业务临时fixture+一个竞争fixture均只用精确ID逐表恢复；无共享FX/定价/采购账号改动。退款差价pending时returned业务拒绝且整事务回滚，差价SUCCESS callback重放后返回退款913；取消/退货都通过系统出口且不超退。admin三个混批入口全拒，batch行零写；rated后snap+batch按一期推进。非授权gz_owner读取/写交易403（待401菜单授权）。

普通装置处理：一条Maven命令误在项目根执行，改到后端仓/显式-f后成功；已有Mockito jar作为javaagent避免沙箱自附加，无新依赖。未降低产品判据。没有其余环境障碍。

## 下游

401/405读写权限使用gz:jp:snap:purchase:query与gz:jp:snap:purchase:trade。UI消费list的TableDataInfo rows/total，reminder-count的R<Long> data；交易动作路径见controller。包邮arrived可无body或{}，到付传actualShippingJpy；成功重复点击在RepeatSubmit窗口可能受装置限制，业务层同目标幂等。已到仓取消返回409，走returned；shipping_diff未到终态时returned明确拒绝，等回调/补偿终态重试。

后端保留同sha共享单例给D10独立QA，未自行停止。最终git只剩基线admin tmp日志。无已知未解决产品缺陷；真实平台交易巡检和真钱通道未验证，沿用本轮既定fake/mock外部替身边界。
