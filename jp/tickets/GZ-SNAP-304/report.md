# GZ-SNAP-304 实现报告

状态：代码和关键单测完成；锁序补丁后定向24/24通过，最终付款边界6/6通过；新8080反stale已通过，验收快照SQL已修复，等待root代跑。

后端 `task/D9@9f6aec33a`（核心84eef029f、锁序53b6afa5b、注释1786151ac、任务原因边界45d3f927e、空配置兜底9f6aec33a），基线 `085de99c9`。未push、未合staging。无新迁移、无新依赖。主miniapp未改；唯一预存 `ruoyi-admin/logs/sys-error.2026-10-01.log180801896327291.tmp` 保持不动。

实现：登录提交仅接受quoteId/addressId/ackNoCancel/userNote。读取服务端报价，事务外实时复查已售出/涨价/运费承担/准入，并顺手更新商品缓存；随后tenant1001独立作用域与TransactionTemplate中以FOR UPDATE串行孤品。本人created复用原单与未过期pending prepay；别人占用拒4127，本人paid拒4128。新单source=snap、单行qty=1、金额取报价、version=0，INSERT前统一SourceInvariant。

onPaid仅主单created→paid affected=1时，同事务写购买任务，唯一键insertIfAbsent兜底；auto queued，manual或总开关关闭manual_pending，无日本服务下单调用。`GzJpSnapLockService.releaseSnapLock(orderItemId)`条件清锁，超时取消REQUIRES_NEW仅markCancelled affected=1后释放；一期无主动取消接口，按授权不新增。后续305/306/307在自身失败条件更新affected=1后同事务调用此方法。

图片：快照保留mainImageUrl原图凭据，mp订单列表与详情通过现有自有proxy重写；主图提交后异步经proxy下载、上传gz_file_object，明确tenant1001，不直连mercdn/Mercari；失败warn并保留兜底，成功JSON_SET补mainImageId。旧快照缺字段仍正常读。图片验证仅回放合成JPEG占位，不声称真实原图实测。

兼容调整：按root确认，提交时报价/实时复查任一manual即保守manual，金额/汇率仍锁报价；FIELD措辞由root同步澄清。错误码4125–4130位于303的4121–4124之后。

## 验证证据

一次干净构建：`mvn -q clean install -DskipTests -pl ruoyi-modules/ruoyi-gz-jp -am` exit0，仅Lombok/JDK警告。后续最终一行manual调整安装的审批超时，未启动Maven；共享restart脚本会重新clean install。

实际关键测试：

```sh
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapPaidTaskTest,GzJpSnapSubmitTest,GzJpOrderSubmitTest,GzJpPayCallbackTest,GzJpUnpaidExpireJobTest,GzJpUnpaidExpireCloseOrderTest,GzJpMixedSourceQueryTest,GzJpOrderDetailCarrierLabelTest -Dsurefire.failIfNoSpecifiedTests=false
```

exit0；Surefire原始XML属性：

```text
GzJpSnapPaidTaskTest tests=6 failures=0 errors=0
GzJpSnapSubmitTest tests=10 failures=0 errors=0
GzJpOrderSubmitTest tests=21 failures=0 errors=0
GzJpPayCallbackTest tests=6 failures=0 errors=0
GzJpUnpaidExpireJobTest tests=9 failures=0 errors=0
GzJpUnpaidExpireCloseOrderTest tests=8 failures=0 errors=0
GzJpMixedSourceQueryTest tests=5 failures=0 errors=0
GzJpOrderDetailCarrierLabelTest tests=6 failures=0 errors=0
TOTAL tests=71 failures=0 errors=0
```

新增16条均@Tag("dev")。按Kevin最新减少重复授权，复用本次合并执行的同名关键测试证据，不重复全项目测试或机械变异。

锁序补丁：submit snap→order→item；orderId仅用immutable定位普通读，状态用FOR UPDATE当前读。expire REQUIRES_NEW先按snapItemId顺序锁snap，再条件更新order，最后释放；回调order→item。避免本人重提交与付款/关单锁序反转。补丁后24条关键测试root代跑exit0（本子agent审批超时未启动Maven），Surefire核对：PaidTask 6/6、Submit 10/10、UnpaidExpireCloseOrder 8/8，failures/errors全部0。

最终HEAD `9f6aec33a`付款定向测试root执行exit0；Surefire XML：GzJpSnapPaidTaskTest tests=6 failures=0 errors=0 skipped=0（包括64码点原因与空配置边界）。

accept #0新8080指纹已通过；首次在任何测试数据创建之前的sys_config快照SELECT失败，根因为ERROR1271配置key IN字面量排序规则混用，原工具吞stderr；已保留失败SQL/stderr，并为UTF8字面量显式指定utf8mb4_bin，工具fixture比较采用确定的精确规则；脚本`doc/jp/_accept/snap-submit-race.{sh,py}`已有反stale（源码/jar/JVM启动时间/当前commit）、10真实HTTP并发、不同orderNo=1/DB有效行=1/原prepay=1，以及两次真实mock付款回调购买任务=1、mp不泄rate/markup。临时测试pricing/filter/gate、FX、地址、原gz_user、原snap_item与两级Redis指定配置字段完整保存并精确恢复；唯一userNote隔离本轮订单，异常finally精确清理，不留商业默认。

全部真实煤炉请求0。

改动均位于ticket touches `ruoyi-gz-jp/**`及`doc/jp/_accept/**`；旧测试fixture构造参数因新增collaborator适配。doc报告不commit，由root统一处理。

SysConfig缺键实际返回空串，enabled判定显式排除空白，沿用manual；既有missingConfig测试改用真实空串语义，不增加方法。

manual_reason VARCHAR64边界：写任务时按Unicode码点截到64，完整准入原因仍在订单快照；复用既有manual测试方法增加边界断言，不增加测试数量。

## 文件范围

后端新增：`GzJpSnapSubmitBo`、`GzJpSnapSubmitErrorCode`、`GzJpSnapOrderMpController`；内部服务`GzJpSnapSubmitService`、`GzJpSnapPaidTaskService`、`GzJpSnapLockService`、`GzJpSnapImageService`；测试`GzJpSnapSubmitTest`、`GzJpSnapPaidTaskTest`。

后端修改：`JpOrderSnapshot`；mapper `GzJpOrderMapper`、`GzJpOrderItemMapper`、`GzJpSnapItemMapper`、`GzJpSnapPurchaseMapper`；服务`GzJpOrderServiceImpl`、`GzJpSnapQuoteService`、`GzJpUnpaidExpireTxService`；既有fixture `GzJpUnpaidExpireFixture`、`GzJpPayCallbackTest`、`GzJpOrderSubmitTest`、`GzJpMixedSourceQueryTest`、`GzJpOrderDetailCarrierLabelTest`仅因构造collaborator/关键读路径适配。

doc新增验收：`jp/_accept/snap-submit-race.sh`、`jp/_accept/snap-submit-race.py`。本报告不提交doc；FIELD/impact同步由root负责。

独立QA发现302旧过滤测试两处any配置stub覆盖了303准入配置，修为确切gz.jp.snap.filter键；基类已有完整gate三个数组，不改产品逻辑。QA单独复跑该类。

## 最终真实验收
- D9独立QA亲跑 `_accept/snap-submit-race.py` exit0：10/10提交仅1订单、1有效行、1prepay；付款/本人续付双连接无500，两次mock付款回调仅1manual_pending任务；订单响应无汇率/加价/外网图片直链。
- raw：`regression/D9/race-r2.log`；配置/缓存/FX/地址/订单/任务/原商品与用户精确恢复，真实煤炉0。安装生产9f6aec33a，187迁移，测试修正375621d34仅限定旧Filter fixture配置key；SQL排序规则和test-only反stale调整仅测试资产，无再次重启产品。PaidTask最新6/6 failures/errors/skipped0。
