---
ticket: GZ-SNAP-301
track: SNAP
phase: D9
size: M
req_refs: [REQ-SNAP-017, REQ-SNAP-042, REQ-SNAP-044]
depends_on: [GZ-SNAP-102, GZ-SNAP-201]
touches:
  - code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-jp/**
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application.yml
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application-dev.yml
  - code/main/RuoYi-Vue-Plus/ruoyi-admin/src/main/resources/application-prod.yml
blueprint_refs:
  - FLOW:F-JP-12.step0
  - FLOW:F-JP-12.step1
  - FLOW:F-JP-11.step2
  - FLOW:F-JP-11.step3
  - FIELD:gz_jp_snap_account.health_status
  - FIELD:gz_jp_snap_account.last_heartbeat_at
  - OWN:gz_jp_snap_account
  - OWN:mercari_account_session
accept:
  - name: 跨系统：ruoyi 客户端签名被真实日本服务（fake 模式）接受，health 结果落到账号表
    form: DATA
    run: |
      (cd code/main/mercari-gateway && GATEWAY_DRIVER=fake docker compose up -d --build >/dev/null) && sleep 5 && \
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpGatewayClientIT* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpGatewayClientIT -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpGatewayClientIT.xml
    counterfeit: 签名串拼法与 F-JP-12.step0 不一致（例如 path 不含 query、body 哈希用空串）→ 日本服务回 401 → 红
  - name: 心跳与主动探测：登录态失效 / 探测失败 → 账号停用 + 自动下单总开关关闭 + 写原因
    form: STATE
    run: |
      cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapHealthJobTest* && \
      mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapHealthJobTest -Dsurefire.failIfNoSpecifiedTests=false && \
      grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapHealthJobTest.xml
    counterfeit: 探测失败只记日志不关总开关，或心跳成功时把 admin 手动关掉的总开关自动打开 → 红
---

# GZ-SNAP-301 ruoyi 侧日本服务客户端 + 心跳 + 主动探测

## §0 状态自检

1. GZ-SNAP-201 完工，本地 `docker compose up` 可起；`FLOW:F-JP-12.step0` 的签名串逐字核对。
2. 看 `GzLocalBeanScheduler` 的 `@Scheduled` + `gz.local-scheduler.enabled` 范式；看 `sys_config` 读写在本项目的封装（读 1001 租户 + 两级缓存，见 memory「新增 sys_config 必写 tenant 1001」）。
3. 配置项进 yml 只写占位与环境变量引用（`${GZ_JP_GATEWAY_SECRET:}`），**secret 不进 git**。

## What

1. `GzJpGatewayClient`（`org.dromara.gz.jp.snap.gateway`）：HMAC 签名、按接口独立超时（search 3s / items 5s / purchases 45s / reconcile 10s / trades 15s / health 5s）、
   只读接口熔断（连续失败 N 次开路 60s）、错误统一抛 `GzJpGatewayException`（区分 timeout / http_status / io）。
   下单与对账调用跑在独立线程池 `snapPurchaseExecutor`，与 Web 线程池隔离。
2. 心跳任务（每 2 分钟）：`GET /v1/health` → 按 `FLOW:F-JP-12.step1` 映射写 `health_status` / `last_heartbeat_at`；调用失败 → `unreachable`；
   任一启用账号 `logged_out` / `challenge` → 调用统一的「风控熔断」方法（关 `gz.jp.snap.auto.enabled`、写 pausedReason / pausedAt、该账号 pause_reason）。
   ★ 熔断方法在本卡实现并单测，GZ-SNAP-305 复用它，不另写。
3. 主动探测（每 10 分钟）：固定关键词搜一次 + 固定商品查一次（两者走配置）；失败 → 熔断 + error 日志；最近一次探测结果存 Redis 供 admin 页展示。
4. 账号表数据只由 ruoyi 写；日本服务只提供数据（OWN:gz_jp_snap_account）。

## AC

- 两条 accept 绿。
- 心跳 / 探测**只会关**总开关，绝不自动打开（恢复只能 admin 手动，GZ-SNAP-402）。
- 本地调度受 `gz.local-scheduler.enabled` 控制；dev 环境 gateway 地址指向本地 docker。
