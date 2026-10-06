# GZ-SNAP-305 实现报告

STATUS: DONE

## 交付

后端 `task/D10`：`a35da94f1` 主实现、`3788c2796` 退款拒绝守卫、`931216ced` dev 网关 URL 接线、`f8e7e9ded` 保留最后实际观察到的商品状态。无迁移、无新依赖、无 push/merge。

新增 `GzJpSnapPurchaseJob` / `GzJpSnapExecutorTx` / `GzJpSnapEvidenceService`；扩展 purchase/account mapper、301 风控、107 退款计划发送入口。

- 每 5s 取到期任务，配置锁→账号锁→任务锁；版本条件抢占与东京日期日限计数同事务。冷却/在执行中等待，无健康或日限耗尽转人工；最多两个本机在途异步调用，避免线程池排队晚执行。
- 成功推进订单行和交易状态；明确 sold_out/deleted/price_up 在商品快照→订单→订单行→任务锁序内条件落态、复用107创建退款计划并释放匹配商品锁，提交后复用旧微信发送逻辑。退款计划拒绝则回滚，不释放锁。
- unknown/异常只排 GET 对账；三轮只自动成功，未找到或调用失败不退款、不重新 POST。最后观察到的商品状态保留在 `last_error` 的 reconcile 诊断前缀，后续网络失败不抹掉此前已售出提示。
- shipping_changed/account_unpayable 转人工；后者只写账号 pause_reason、保留 admin_enabled，不关闭全局。risk/连续三个 unknown 调301统一关总开关并把 queued 转人工；健康检查不会恢复。
- ApplicationReady 与运行扫描将超过60秒的 executing 恢复 unknown，不改 queued。证据上传失败只 error；成功上传保存 file id。txt/html/json 仅 snap_evidence 可上传且 MIME/后缀匹配，OSS 文档对象用 application/octet-stream 下载；原图片白名单保持。

## 验证（按最新授权仅变更定向检查，未重复全项目）

实际绿执行：Reconcile 原6 + 新1；Executor 原8 + 资金守卫2；HealthJob8；文件服务12与控制器权限3，总40条。初始三类同一Maven调用合并执行，避免重复构建；原两个 front-matter 单测 accept 的目标类/断言均执行过。共享 clean install 随后清理原 target 报告，因此下列初始 XML 数字是当时工具读取的原始摘录；最后新增方法的 XML 已归档。

```text
GzJpSnapReconcileTest: tests="6" errors="0" skipped="0" failures="0"
GzJpSnapExecutorTest: tests="8" errors="0" skipped="0" failures="0"
GzJpSnapHealthJobTest: tests="8" errors="0" skipped="0" failures="0"
GzFileServiceImplTest: tests="12" errors="0" skipped="0" failures="0"
GzFileControllerPermissionTest: tests="3" errors="0" skipped="0" failures="0"
lastObservedSoldSurvivesLaterNetworkFailure: tests="1" errors="0" skipped="0" failures="0"
```

执行命令（均 exit 0；资金守卫两方法另定向执行且 exit 0）：

```bash
mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapReconcileTest,GzJpSnapExecutorTest,GzJpSnapHealthJobTest -Dsurefire.failIfNoSpecifiedTests=false
mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am -Dtest=GzFileServiceImplTest,GzFileControllerPermissionTest -Dsurefire.failIfNoSpecifiedTests=false
mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am '-Dtest=GzJpSnapExecutorTest#failedTransitionCreatesRefundBeforeReleasingMatchingLock+rejectedRefundRollsBackInsteadOfReleasingLock' -Dsurefire.failIfNoSpecifiedTests=false
mvn -q -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am '-Dtest=GzJpSnapReconcileTest#lastObservedSoldSurvivesLaterNetworkFailure' -Dsurefire.failIfNoSpecifiedTests=false
/opt/homebrew/bin/python3.11 -u doc/jp/_accept/snap-fault-injection.py
```

故障脚本的 `.sh` 入口只设置PATH、进入项目根并执行同一Python；实际真HTTP最终run直接调用绝对Python以避工具子进程限制。

```text
isolated fake+replay ready: /tmp/snap305-fake-ihj8bcz2
BACKEND UP (commit 3788c2796, branch task/D10)
Successfully validated 187 migrations
fresh: current JP jar and running JVM; fake gateway verified
success: order=JPO-20261006-000007 clicks=1 status=success refunds=0 evidence=13
fake success latency=2s (<60s)
timeout: order=JPO-20261006-000009 clicks=1 status=success refunds=0 evidence=NULL
disconnect: order=JPO-20261006-000011 clicks=1 status=success refunds=0 evidence=NULL
restart: fake click=1, DB executing before shared restart
BACKEND UP (commit 931216ced, branch task/D10)
Successfully validated 187 migrations
fresh: current JP jar and running JVM; fake gateway verified
restart: order=JPO-20261006-000013 clicks=1 status=success refunds=0 evidence=NULL
BACKEND UP (commit 931216ced, branch task/D10)
restored: scheduler=false, gateway=8700, exact configs/cache/accounts/fixture data; real Mercari=0
```

[evidence/fault-injection.log](evidence/fault-injection.log)、[隔离账本](evidence/fake-ledger.json)、[fake HTTP日志](evidence/fake-gateway.log)、[最后观察单测XML](evidence/last-observed-junit.xml) 为原始证据。账本四个订单均 `call_count=1`、`click_count=1`。timeout 使用真实45s客户端超时；只推进本次精确 order_item_id 的 next_action_at 加速30s等待，未改生产间隔。2min/10min由定向单测覆盖。

重启样本在调用共享restart前确为 executing；本次优雅关停先由 HTTP 中断收敛 unknown，之后仅GET对账成功。**本次未单独命中 ApplicationReady 的过期 executing 恢复分支**，不把它宣称为已真验；独立QA可用到期执行记录必要时核对。后三场景因响应中断无 evidence 是预期，成功响应 evidence=13 实际落库。

最终恢复原 sys_config 行及缓存字段、原采购账号、原商品快照、原用户；精确删除本轮 FX/地址/订单行/任务/支付与回调元数据/上传文件元数据。隔离 SQLite/ledger 保留在上述 `/tmp` 目录作证，未清空原8700历史。8711/8712 已停且 lsof 无listener；8080选项 `GZ_LOCAL_SCHEDULER_ENABLED=false`、网关8700，187迁移。

## 环境调整与限定

1. 初始本地代理创建被反向DNS阻塞，尚未造数，停止后覆盖server_bind绕DNS；共享launchd remove/submit竞态由主线程修复共享脚本。
2. 原fake账号已有购买历史使第一张success返回success(history)且零点击（符合至多一次）；该轮恢复完成，随后使用既有代码创建隔离fake+replay实例及临时SQLite，避免污染旧历史并让脚本可重复QA。
3. dev.yml硬编码8700覆盖环境URL，隔离ledger探针发现为空，该轮精确恢复。根因修为 `${GZ_JP_GATEWAY_URL:http://127.0.0.1:8700}`；最终唯一四场景run当时使用Spring JSON临时覆盖走8711，后两次restart已包含配置修复。交付脚本已移除该临时兼容覆盖，统一走共享脚本捕获的URL变量。
4. 最后观察提示新增单测最初揭示同对象mock诊断被覆盖；修为在写错误前读取已锁行旧诊断，定向重跑1条绿。该提示修复 `f8e7e9ded` **仅单测验证**；当前8080生产路径指纹仍 `931216ced`，下一次共享restart须安装最新gz-jp。四HTTP资金/点击证据可复用，不需重跑。

## 越界与下游

经主线程授权：gz-common `enums/GzFileUsageType.java`、`service/impl/GzFileServiceImpl.java` 及其服务测试（证据类型/旧admin上传守卫）；`ruoyi-admin/src/main/resources/application-dev.yml`（仅参数接线，不改框架源码）。doc新增Python/入口/报告/证据，不提交，由主线程统一提交。

306注意：`GzJpSnapExecutorTx.result` 只接自动执行 executing 与对账 unknown，人工 pending 出口须有自己的条件状态守卫；107发送入口 `dispatchSnapRefundPlan` 接受**已提交**的退款计划，切勿在事务内调用。锁序商品快照→order→item→purchase。`last_error` 可能含 `reconcile:item_status=...;` 诊断，不将它当用户文案。
