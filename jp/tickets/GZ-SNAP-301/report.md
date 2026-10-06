# GZ-SNAP-301 实现报告

STATUS: DONE

- 代码仓：RuoYi-Vue-Plus `task/D9`，commit `b610ef4a2b76f15f6f424562b0a0b38da4b9a435`。
- 迁移：none；out of touches：none。
- 基线：HEAD cb9ffff56；唯一预存未跟踪日志保留；编译健康。实现、测试与提交均未访问真实煤炉、未切 live、未 push、未合 staging、未改主 miniapp。

## 实现

新增 `snap.gateway` 包的 GzJpGatewayClient / Properties / Configuration / Exception / GzJpSnapRiskControl；新增 GzJpSnapHealthJob、GzJpSnapRuntimeConfigMapper，扩展账号 Mapper 与现有 GzLocalJpScheduler；补 gateway yml 配置及 dev 本地调度缺省 false。pom 仅复用项目 admin 已有 mysql-connector-j 为 test scope，无新库/新生产依赖。

HMAC 对线上实际 raw path+query 与 JSON UTF-8 body SHA256 签名；search/items/purchase/reconcile/trades/health 分别 3/5/45/10/15/5s。只读接口按 endpoint 连续失败 3 次开路 60s，半开时只允许一个请求；下单不走熔断。purchase/reconcile 返回 CompletableFuture，实际 HTTP 在独立 snapPurchaseExecutor，拒绝策略不退回 Web 线程执行。

健康任务用业务租户 1001，账号未出现或出口不可达判 unreachable；调用失败保留最近成功心跳。启用账号 logged_out/challenge 写 pause 与关闭总开关。admin_enabled 仅 admin 写，故任务不改它；账号停止自动购买依据健康状态与 pause_reason。healthy 只更新健康/心跳，不清 pause 或恢复总开关。

共享 `GzJpSnapRiskControl.pause(accountCode, reason)` 锁住 sys_config 原 JSON，保留其它字段，原子关闭 enabled + 写 pausedReason/pausedAt + 账号 pause_reason；transaction commit 后通过业务租户 CacheManager 驱逐框架两级缓存。探测固定配置关键词/商品一次，失败只关闭；Redis `1001:gz:jp:snap:probe` 存 JSON {checkedAt,ok,reason?}，保留24小时。

TenantHelper.dynamic 不保存嵌套作用域：心跳先完成所有账号读写，再离开租户块调用共享 pause，避免 pause 内部 clearDynamic 影响后续账号写。config mapper 位于既有 org.dromara.**.mapper 扫描范围。

## 验证

Kevin 最新授权下只跑本卡关键测试；未重复全项目/UI/机械变异，未重启共享8080。两条accept从项目根以bash -c逐字执行成功；最后对最终源码 clean install，仍只选以下9条关键测试。

- org.dromara.gz.jp.snap.gateway.GzJpGatewayClientIT: tests=1 failures=0 errors=0 skipped=0
- org.dromara.gz.jp.job.GzJpSnapHealthJobTest: tests=8 failures=0 errors=0 skipped=0

真实 IT 先检查 driver=fake，搜索 replay 样本（含日文+空格 query），POST fake 下单（非空 body），GET 对账含 query；真实 dev MySQL 使用实际 MyBatis mapper写入/读回 healthy + 非空心跳。101 无采购账号 seed，因此事务内插入 gateway 已配置 acc01（仅不存在时），事务结束 rollback；不保留账号或改已有业务行。fake账本保留仅 IT301- 前缀测试采购记录，不影响真实订单。测试密钥优先 GZ_JP_GATEWAY_SECRET，缺省私下读取 gateway/.env；不打印、不提交。

### accept #0（exit 0）

```bash
(cd code/main/mercari-gateway && GATEWAY_DRIVER=fake docker compose up -d --build >/dev/null) && sleep 5 && \
cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpGatewayClientIT* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpGatewayClientIT -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpGatewayClientIT.xml
```

raw output:

```
 Container mercari-gateway-gateway-1  Running
Java HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
REAL_GATEWAY driver=fake search=query-signed purchase=body-signed reconcile=found; REAL_DB tenant=1001 account=acc01 health=healthy heartbeat=non-null (transaction rolled back)
```

### accept #1（exit 0）

```bash
cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapHealthJobTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapHealthJobTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapHealthJobTest.xml
```

raw output:

```
Java HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
09:35:44.906 [main] ERROR org.dromara.gz.jp.job.GzJpSnapHealthJob -- [jp-snap] gateway heartbeat failed: TIMEOUT
09:35:44.909 [main] ERROR org.dromara.gz.jp.job.GzJpSnapHealthJob -- [jp-snap] active probe failed: HTTP_STATUS (HTTP 404)
```

### 最终 clean install（exit 0）

```bash
mvn -q clean install -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapHealthJobTest,GzJpGatewayClientIT -Dsurefire.failIfNoSpecifiedTests=false
```

raw output:

```
WARNING: A terminally deprecated method in sun.misc.Unsafe has been called
WARNING: sun.misc.Unsafe::objectFieldOffset has been called by lombok.permit.Permit
WARNING: Please consider reporting this to the maintainers of class lombok.permit.Permit
WARNING: sun.misc.Unsafe::objectFieldOffset will be removed in a future release
Mockito is currently self-attaching to enable the inline-mock-maker. This will no longer work in future releases of the JDK. Please add Mockito as an agent to your build as described in Mockito's documentation: https://javadoc.io/doc/org.mockito/mockito-core/latest/org.mockito/org/mockito/Mockito.html#0.3
OpenJDK 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
WARNING: A Java agent has been loaded dynamically (/Users/wkui/.m2/repository/net/bytebuddy/byte-buddy-agent/1.17.8/byte-buddy-agent-1.17.8.jar)
WARNING: If a serviceability tool is in use, please run with -XX:+EnableDynamicAgentLoading to hide this warning
WARNING: If a serviceability tool is not in use, please run with -Djdk.instrument.traceUsage for more information
WARNING: Dynamic loading of agents will be disallowed by default in a future release
REAL_GATEWAY driver=fake search=query-signed purchase=body-signed reconcile=found; REAL_DB tenant=1001 account=acc01 health=healthy heartbeat=non-null (transaction rolled back)
09:37:02.728 [main] ERROR org.dromara.gz.jp.job.GzJpSnapHealthJob -- [jp-snap] gateway heartbeat failed: TIMEOUT
09:37:02.731 [main] ERROR org.dromara.gz.jp.job.GzJpSnapHealthJob -- [jp-snap] active probe failed: HTTP_STATUS (HTTP 404)
```

## 下游提示与范围

- 302 可直接调用 client.search(keyword,sort,page,categoryIds)、item(externalId)、seller(sellerId)、resolve(url)；返回 JsonNode 原始契约字段。HTTP_STATUS携httpStatus；TIMEOUT/IO/CIRCUIT_OPEN应按产品规则缓存兜底或暂时不可用，不返回假成功。
- 305 用 client.purchase(body) / reconcile(orderNo,externalId,accountCode) 的 future；共享 `riskControl.pause(accountCode, reason)` 只负责关开关及账号pause，queued 转人工仍由305实现。启用账号选择须同时检查 adminEnabled、healthStatus与pauseReason，健康恢复不能越过人工pause。
- Secret 仅 GZ_JP_GATEWAY_SECRET；URL GZ_JP_GATEWAY_URL；探测 GZ_JP_GATEWAY_PROBE_KEYWORD / GZ_JP_GATEWAY_PROBE_ITEM。dev默认 replay fixture；生产发布须提供真实固定探测商品/关键词。本轮不验证真实平台登录态/下单能力。
- 调度共用 gz.local-scheduler.enabled，dev默认false；周期 jp-snap-heartbeat-ms=120000、jp-snap-probe-ms=600000。本卡不新增admin API或UI。
- 自动配置真源为 sys_config键 gz.jp.snap.auto 的JSON enabled字段，不能另写 gz.jp.snap.auto.enabled 独立key。
