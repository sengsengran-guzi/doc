# GZ-SNAP-303 实现报告

STATUS: DONE

- 后端分支 `task/D9`；提交 `eae07b29d`（准入 / 汇率 / 报价）及 `085de99c9`（搜索摘要缺 payer 的参考价修正）。
- 迁移：none；上游301/302已在当前分支。没有 push / 合 staging，没有改主 miniapp，没有真实煤炉调用。
- 源码修改全部在 touches `ruoyi-modules/ruoyi-gz-jp/**` 内。doc 报告/证据由主线程统一提交。
- §0：初始 HEAD `bc01498f1`，原有未跟踪日志临时文件保留；基线离线 compile exit0，关联 ticket / REQ / ADR0025 / authority / backend skill / pitfalls 已读。

## 实现

1. `GzJpSnapGate` 按配置先 blocked（専用、分类、黑名单、Shops、拒代购）再 manual（标题/描述留言词、buyer到付）再 auto；非在售是独立不可购买约束。拒代购 reason 格式 `proxy_refuse:<词>@title|description|seller_intro`。配置损坏拒绝准入；卖家简介经gateway取、按seller缓存24h，取不到只按商品判并warn，其他商品字段仍来自本次gateway详情。
2. `GzJpSnapFxService` 按官方表头「货币名称」「现汇卖出价」定位日元；每100日元兑人民币。已一次确认官方页面当前结构：<https://www.boc.cn/sourcedb/whpj/>（2026-10-06显示日元4.2673，单位声明每100外币）。使用JDK HTTP/表格解析，无新依赖。30分钟调度沿用本地调度开关；失败只warn并保留旧行。未在本次验证重复执行BOC联网任务。
3. `POST /system/gz/jp/snap/fx` 手录追加 source=manual、服务器fetchedAt、校验正数/精度；权限 `gz:jp:snap:config:fx`；`GET` 最近50条权限 `gz:jp:snap:config:query`。菜单由下游403建，本卡无越界迁移。读取最新fetchedAt/id记录，超过6h或缺失/无效时error并拒报价。
4. `GzJpSnapQuoteService` 使用BigDecimal严格ceil：商品分=ceil(priceJpy×ratePer100jpy×(1+markupRatio))，再加固定分费；只有manual+buyer加到付预估运费，运费不加价。三项缺一拒报价，明确设置0可合法使用，没有新增商业默认值。
5. 详情VO保留内容、增加gateResult/gateReason，展示价格在 `price`：goodsCent/fixedFeeCent/estShippingCent/totalCent/priceJpy/quoteId/expiresAt；没有rate/markup字段。缺定价返回详情200、price=null、quoteErrorCode=4121、purchasable=false；旧/缺汇率=4122。blocked/非在售不创建报价。
6. 搜索参考价用同一公式，不创建quoteId。真实搜索摘要缺shipping_payer时仅估商品价+固定费，不猜到付运费；有buyer字段则加配置预估。这一限制已主线程确认，详情和订单金额不变。源配置三项空或无新鲜汇率时referencePriceCent=null是正确拒报价行为。

## 文件（全部后端gz-jp）

- 新增：controller/GzJpSnapFxController；domain/dto/GzJpSnapQuoteSnapshot；domain/vo/GzJpSnapPriceVO；exception/GzJpSnapQuoteErrorCode；service/internal/{GzJpSnapFxService,GzJpSnapGate,GzJpSnapQuoteService,GzJpSnapQuoteStore}。
- 修改：domain/vo/GzJpSnapDetailVO；job/GzLocalJpScheduler；service/internal/{GzJpSnapFilter,GzJpSnapReadService}。
- 测试新增：GzJpSnapGateTest / GzJpSnapQuoteTest / GzJpSnapDetailContractTest；修改Snap302Fixture以适配新构造参数与可用报价。

## Accept与测试

先完成一次clean重建（指定三个类，初始24条绿），随后按ticket原始accept逐条 `bash -c` 执行。搜索修正后只重跑受影响报价accept，新增1条摘要缺payer用例。最终关键28条：11+12+5，无扩大旧项目回归/机械变异。

| Accept | 结果 | 实际执行 |
|---|---|---|
| #0 准入 | exit0 | tests=11 errors=0 skipped=0 failures=0 |
| #1 报价（修正后） | exit0 | tests=12 errors=0 skipped=0 failures=0 |
| #2 详情契约 | exit0 | tests=5 errors=0 skipped=0 failures=0 |

命令原样（调用前设置Maven PATH；从项目根用bash -c）：

```bash
cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapGateTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapGateTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapGateTest.xml

cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapQuoteTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapQuoteTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapQuoteTest.xml

cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapDetailContractTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapDetailContractTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapDetailContractTest.xml
```

原始stdout/stderr见 evidence/accept0.log（空输出exit0）、accept1.log（负路径故意记录坏JSON/旧率日志，exit0）、accept2.log（卖家简介降级/缺定价warn，exit0）。所有测试类 @Tag("dev")。共享重启clean install会删除之前target报告，本报告保存执行条数与原始日志；不为复制产物重复跑已有效验证。

原始Surefire摘要（最终受影响报价类）：

```text
Tests run: 12, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.918 s -- in org.dromara.gz.jp.service.internal.GzJpSnapQuoteTest
```

## 真栈证据及恢复

主线程按唯一共享restart脚本起新产物；首次 `eae07b29d` / 最终 `085de99c9`；187条迁移validate通过。仅8700本地replay+fake，没有任何真实煤炉请求。临时定价仅用于测试（0.1/200/900/600），通过已有配置API使Caffeine+Redis失效；原配置整行保存在本地备份并精确恢复所有列。汇率只造服务器manual新行，验证后按精确id+tenant+source删除。派生商品行按原全行恢复/新行精确删除；报价按本次生成ID删除。

真实详情/DB验证原始输出（列表缺payer修正前；末尾列表断言红促成第二提交，见 `evidence/live-detail-before-list-fix.log`）：

```text
ORIGINAL_PRICING detail code200 gate=auto quoteErrorCode4121 purchasable=false
OWNER_FX_WRITE_DENIED code403
ADMIN_FX_APPEND/readback tenant1001 source=manual rate4.2673
LIVE_DETAIL m99000000001 gate=auto goods=3760 fee=200 shipping=0 total=3960 redisTTL=600 boundId/payer/gate/terms=ok privateTermsAbsent
LIVE_DETAIL m99000000002 gate=manual goods=3765 fee=200 shipping=900 total=4865 redisTTL=600 boundId/payer/gate/terms=ok privateTermsAbsent
LIVE_DETAIL m99000000003 gate=manual goods=3770 fee=200 shipping=0 total=3970 redisTTL=600 boundId/payer/gate/terms=ok privateTermsAbsent
LIVE_DETAIL m99000000004 gate=blocked noQuote reason=proxy_refuse:代行業者@title
LIVE_DETAIL m99000000005 gate=blocked noQuote reason=reserved:専用
LIVE_DETAIL m99000000007 gate=auto noQuote reason=item_not_on_sale
LIVE_DETAIL m99000000008 gate=blocked noQuote reason=category_not_allowed
SHOPS code4117
RESTORED fullConfigRow/items exactEqual manualFXDeleted quotesDeleted Caffeine+Redis proven original4121
```

最终只补一次必要列表请求（没有重复详情矩阵），原始输出 `evidence/live-list-final.log`：

```text
LIST_REFERENCE nonempty=4 sameFormula goodsCeil+fixedFee first=3960 payerAbsent=noShippingGuess privateTermsAbsent noQuoteId
RESTORED fullConfigRow exactEqual Caffeine+Redis configAPI=originalNullTerms listReference=null manualFXDeleted FXcount=0
```

此前API恢复已证详情4121；最终恢复后配置API取到原空三项、列表参考价null并且FX=0，证明两级缓存没有遗留临时定价。最终源码git只剩原有无关未跟踪日志文件。

装置适配：rg不可用改find/grep；Maven/Docker分别绝对路径 `/opt/homebrew/bin/mvn` / `/usr/local/bin/docker`；本地admin租户实际1001；Redis GET字符串需要两次JSON解码，BigDecimal在本项目Jackson中序列化字符串，脚本按Decimal比较；未因此修改真实商业配置/扩大联网预算。

## 下游304/403契约

- `GzJpSnapQuoteService.require(quoteId, externalId)`返回服务端 `GzJpSnapQuoteSnapshot`，检查Redis缺失/格式、expiresAt以及externalId绑定；错误4123=报价过期，4124=不属此商品。不要直接相信mp传金额，不用raw_json代替实时gateway authority。
- Redis前缀 `GzJpSnapQuoteStore.PREFIX = "1001:jp:snap:quote:"`，UUID key，TTL取配置quoteTtlSec；应用expiresAt同时检查，删除/过期不能回退到DB。
- snapshot：externalId / priceJpy / ratePer100jpy / markupRatio / goodsCent / fixedFeeCent / estShippingCent / totalCent / quotedAt / expiresAt / gateResult / shippingPayer。
- 注意快照record `ratePer100jpy` 小写j，订单权威字段 `ratePer100Jpy` 大写J，304须显式映射。将报价全部参数整体锁进订单；锁定payer/gate供到付和人工流程使用。商品描述/gateReason/mainImage原URL可由实时详情/对应落库商品取，不把公开代理图片URL误作原URL。
- 详情 `price`为公开展示VO、expiresAt毫秒epoch；订单预检需独立核对实时商品状态/价/准入，不应靠新报价缺配时的展示purchasable字段替代锁价校验。
- 403使用POST/GET汇率接口与权限config:fx/config:query；定价仍三项空，甲方填初值后才能生产报价。本次没有擅设商业参数。

风险/限制：所有煤炉HTML/profile/shortlink和图片仍为上游合成回放；图片是本地JPEG占位，未验证真实HTML/profile。当前真实定价三项与汇率均空，正式配置前不可报价。搜索未知payer参考价不含未知到付运费；真实详情为最终报价准据。
