# GZ-SNAP-504 实现报告

STATUS: DONE（实现完成；独立 D12 QA 由根线程执行）

后端 `f89e64a65437482d665d961600de9e6346ef832d`；小程序最终 `f742beb841c07e0aa5f0d046531514710c9d280c`（主体 `1af78fe75ccff20a66c4f01b98ca704f0ea5d112`）。未 push、未合 staging、无迁移。

复用订单列表/详情 VO 和 mapper，snap 采购与退款各一次批量查询，展示六态、交易白名单、仅成功 shipping_diff 金额；ownership 在投影读取前检查。batch 新字段为空，不下发采购原状态、内部账户/费率/错误。详情 3s 轮询、最多 60s，隐藏/卸载清 timer，超限手动刷新；未支付/已取消优先订单资金状态并停止采购轮询。未成功退款不显示已退款。列表有代切标。

```text
actualcounts
backend targeted: 15 executed / 0 failures / 0 errors
  display=3 ownership=1 mixed-source=5 carrier-label=6
MP pure detail.snap.logic: 12 executed / 12 passed
type-check exit0; full lint exit0; development build exit0
最终 created/cancelled 补丁: scoped eslint exit0、logic12/12；此前 type-check exit0
真实模拟器 success 独立绿: order99101000077/JPO-20261006-000157
  UI支付→实际fake engine success→自动显示已抢到，10626ms，calls1/clicks1
真实模拟器 failed 独立绿: order99101000080/JPO-20261006-000163
  UI支付→实际fake engine failed:sold_out，19801ms，calls1/clicks0
  未退款时未显示已退款；真实JP refund-notify SUCCESS后显示已退款/full amount
  HTTP/DB/MP真实同源；failed-only正式runner 1/1 PASS
一期 orders 正式runner一次: 1/1 PASS（profile前后hash一致）
成功与失败为两次独立通过，不声称首轮完整双场景通过。
```

证据限制：首次 success 产品段的原始工具输出未持久化，当前上下文仅有摘要，无法精确归档包含首轮 finally 失败上下文的原文。因此未创建 `evidence/snap-order-success-first-run.log`，上述 success 数值不能作为可复查的独立 raw 证据；首轮整 flow 未通过。最终正式双场景由独立 QA 验证并持久化原始输出。

首轮 fixture 的退款回调误用公共支付路径、自动开关误用 config 白名单端点，随后改为 `/api/gz/jp/pay/refund-notify` 和专用暂停/恢复端点，并按写前私有快照精确恢复。失败场景最终通过，已绿 success 不重复。未 SQL 改任务成功冒充引擎，无真煤炉调用。单测覆盖公共 DTO、批量查询过滤及 ownership；成功 shipping_diff SQL 谓词和累计有定向测试。

```text
fingerprints
live gz-jp installed jar SHA256:
266f524e541db797e62fca24d04b494f4ca2fb1f1c82c677dbd9de865e3185af
Flyway: 191 validated/applied（无新增迁移）
config原始全字段+audit SHA256 before=after:
084e540ef7a3ada9cab786d878ea642a44a033906a8cc7a9db55c3a467f2c47d
profile原始全字段+audit SHA256 before=after:
02d3afab81a156e893de09df0308ce0ec788671fba0845f497d4744c92aa96ce
address SHA256: 50f45f33e119d9e85e3246ce5ee5c628f3bb8cbc796320e4a30fd95590534ae5
cart(empty) SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
raw: evidence/targeted-test-counts.txt, evidence/snap-order-failed.log, evidence/orders.log
最终源码生产/开发重建交QA；根线程此前生产构建发生在最终边界补丁之前，不计最终gate。
```

runner 对 snap-search/snap-detail/snap-checkout/snap-order/checkout/home/orders 在 preflight mock 登录前增加 profile-only 全列/audit 快照保护（mode600、异常 exit 同步恢复、raw 仅 hash），不改全项目登录业务。fixture 原有客户地址/购物车全字段保护仍保留。新坑已记录 `.dsh/knowledge/pitfalls.md` §9.6。权威 UI 契约由根线程同步至 doc `1f7b221`。

```text
cleanup / QA装置
own m504 snap items/tasks residual0；accounts inventory0
own evidence gz_file_object IDs71–78 residual0；对应MinIO逐个删除
own fake scripts/ledger/purchases/idempotency residual0
synthetic replay宿主+容器exact文件已删除；自己的quote/翻译cache exact清理
本轮新增FX删除；旧FX99030500002保留1；旧locks未动
pricing三NULL和auto=false逐字节/audit还原；两级cache失效、API读回
私有snapshot清除；profile/address/cart完整恢复
默认8080继续运行：scheduler=false，SPRING_APPLICATION_JSON absent
backend仅保留既有sys-error临时日志；MP工作区干净；没有自有额外服务
real Mercari requests=0
QA入口：MP_E2E_TIMEOUT_MS=900000 node test/e2e/run.mjs snap-order
unset MP_SNAP504_OUTCOMES（默认success+failed两个场景）
前置：gateway8700 replay/fake、空accounts、没有其他due queued/unknown/executing任务
测试启用scheduler时全局其他调度initial-delay-ms=86400000；仅采购tick运行
按finally共享restart恢复默认；模拟器串行，不并行Maven target与内部restart
QA最终production+development重建；不扩D10故障/资金并发suite，不派D13
```
