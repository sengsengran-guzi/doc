# GZ-SNAP-302 实现报告

状态：DONE。三个 accept（15条）与本地真实匿名API/DB路径已通过。

代码仓：`RuoYi-Vue-Plus`，分支 `task/D9`，commit `bc01498f1e2cd0ae1d6a9cee582170a94d89efef`。未 push、未合 staging。主 miniapp 未改。

新迁移：`V202610060947__GZ-SNAP-302-seed-category-whitelist.sql`（真实创建时间，append-only），UPDATE 租户1001现有 `gz.jp.snap.filter` JSON，保留其它配置，初值745/975/980。

## 实现

- 匿名 `GET /app/gz/jp/snap/search`、`/item/{externalId}`、`/hot-terms`；后台 `POST /system/gz/jp/snap/term/normalize`，输入 `{q}`，权限 `gz:jp:snap:term:list`。
- 商品 URL/裸ID/merc.li解析转详情；Shops明确4117。词表最长匹配先于sort_no，同长度按优先级，替换结果不再次替换；未覆盖中文翻译失败原词降级。
- 官方已授权 `com.aliyun:alimt20181012:1.5.2`，既有依赖无翻译封装。Maven官方metadata与sources确认签名；[官方GetBatchTranslate文档](https://help.aliyun.com/en/machine-translation/developer-reference/api-alimt-2018-10-12-getbatchtranslate)核对结果映射。dev/test mock无key可用，基础/prod aliyun，环境变量注入Key。首次屏幕标题按缓存缺口批量翻译（<=8000字符/批、单项<=1000），标题缓存externalId+hash，7天；描述与查询同样缓存并可降级。没有发起真实阿里翻译请求。
- 搜索Redis fresh3分钟+stale24小时；按归一化串/sort/page/分类集建key；Redisson分布式锁合并同key在途请求。缓存命中仍用当前过滤规则，防运营修改后旧卡片放行。
- 统一过滤在ruoyi：Shops、非在售、分类（叶/父/根任一）、标题黑名单。空白名单全拒且搜索不调gateway。搜索卡片不含lineage时保守只接纳白名单里的末级；初值含已确认叶975/980与父745，不开放根1328。未知子类搜索默认拒绝，详情有完整lineage时按配置父级通过。
- 详情每次实时fetch并upsert快照、翻译、raw_json/fetched_at；SQL刷新元数据、增加version，保留active_order_item_id/main_image_id。出站VO显式列字段，不下发raw/seller profile。`purchasable`目前只代表302过滤通过，303必须叠加完整准入/报价；价格参考字段null。
- 图片只允许gateway支持的c2c静态域，保留原路径改到配置的自有proxy/CDN；危险路径/未知域不出图。
- 原框架 `@RateLimiter` 按user/IP提前拦，业务码4118；原框架实际URI使详情换ID可分散桶，另加详情同user/IP聚合桶，超限不调gateway。无缓存上游不可用4119，参数4120；读HTTP401/403在退出外层租户作用域后调用301 risk.pause，避免嵌套TenantHelper.dynamic坑。

## 文件范围

23文件均在ticket touches内：3个application YAML、1条新迁移、JP pom、SnapItemMapper、SearchProperties、mp/admin/advice三个controller、两个VO、错误码、6个read/normalize/filter/translate/cache/rate内部service，3个测试类+测试夹具。越界文件：none。

主线程提供纯离线gateway测试资产：`7f115a8`（9个分类/排序变体，保留对抗卡片）、`45dfa95`（原路径JPEG占位）。都明确synthetic，非真实HTML/煤炉图片证据；没有修改gateway代码或扩大真实请求预算。

## 验证

先做clean compile（包括SDK依赖解析），实际exit0；不跑无关全项目UI。第一轮测试编译发现Java17不支持List.getFirst/ExecutorService自动关闭，改为兼容语法；限流单测原尝试mockStatic RedisUtils遇无Spring初始化，改为可替换acquire接口验证拦截顺序。最终三个ticket accept原样bash执行，未改命令。

### accept #0 — PASS

从项目根以 `bash -c` 执行：

```bash
cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapNormalizeTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapNormalizeTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapNormalizeTest.xml
```

Raw output + XML suite：

```text
Java HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
09:50:38.591 [main] WARN org.dromara.gz.jp.service.internal.GzJpSnapTranslator -- Snap translation unavailable: IllegalStateException
tests=6 failures=0 errors=0 skipped=0
exit=0
```

### accept #1 — PASS

从项目根以 `bash -c` 执行：

```bash
cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapFilterTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapFilterTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapFilterTest.xml
```

Raw output + XML suite：

```text
Java HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
tests=5 failures=0 errors=0 skipped=0
exit=0
```

### accept #2 — PASS

从项目根以 `bash -c` 执行：

```bash
cd code/main/RuoYi-Vue-Plus && rm -f ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/*GzJpSnapSearchDegradeTest* && \
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapSearchDegradeTest -Dsurefire.failIfNoSpecifiedTests=false && \
grep -qE 'tests="[1-9][0-9]*" .*failures="0"' ruoyi-modules/ruoyi-gz-jp/target/surefire-reports/TEST-*GzJpSnapSearchDegradeTest.xml
```

Raw output + XML suite：

```text
Java HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended
tests=4 failures=0 errors=0 skipped=0
exit=0
```

## 本地真实链路

SIGNED_LOCAL_GATEWAY：真实HMAC请求本机8700 `q=缶バッジ&sort=created_desc&page=1&category_ids=745,975,980`，返回7个合成卡片。零外部请求。

首次共享app启动缺少签名环境变量，匿名接口按预期4119而不是500；主线程将本地未跟踪gateway `.env`单键按数据解析映射到 `GZ_JP_GATEWAY_SECRET`后统一重启，不source、不打印密钥。新迁移已应用；Redis HDEL `1001:sys_config` 对应filter（返回0），新进程本地缓存为空。数据库初值 `{"keywordBlacklist": [], "categoryWhitelist": ["745", "975", "980"]}`；三个测试商品快照基线0行。

真实匿名API raw output（脚本 `/tmp/302-live.py`，无Authorization，只有JP clientid；exit=0）：

```text
ANON_SEARCH code=200 cards=4 shops/sold/outside absent; mock translated; proxy images; quote=null
ANON_REDIRECT bare/link/shortlink=m99000000001
ANON_SHOPS_LINK code=4117
ANON_DETAIL id=m99000000001 purchasable=True reason=None raw/seller absent
ANON_DETAIL id=m99000000008 purchasable=False reason=category_not_allowed raw/seller absent
ANON_DETAIL id=m99000000007 purchasable=False reason=item_not_on_sale raw/seller absent
ANON_NOT_FOUND detail code=200 reason=item_deleted; repeated detail fetched fresh
ANON_SEARCH_RATE responses=[200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 4118, 4118, 4118, 4118, 4118, 4118] explicit SNAP_TOO_FAST=4118
```

补充 `GET /hot-terms` → `{"code":200,"msg":"操作成功","data":[]}`，当前enabled ip词表为空。

真实DB raw output（字段依次 external_id/tenant/title_zh/status/gate/reason/version/fetched_at非空/raw JSON external_id/active_order_item_id；首次行version=1证明同ID两次实时查询更新，其它两行version=0首次insert）：

```text
mysql: [Warning] Using a password on the command line interface can be insecure.
m99000000001	1001	[译]合成テスト 即購入OK	on_sale	auto	NULL	1	1	"m99000000001"	NULL
m99000000007	1001	[译]合成テスト 売り切れ	sold_out	blocked	item_not_on_sale	0	1	"m99000000007"	NULL
m99000000008	1001	[译]合成テスト 工具	on_sale	blocked	category_not_allowed	0	1	"m99000000008"	NULL
0
```

基线三个external_id为0行；验证后用精确tenant1001+platform mercari+三ID+active_order_item_id为空+本次create_time边界删除，剩余0行，未改其它业务数据。loopback search测试限流的三个精确Redis键已删除（DEL=3），避免独立QA受前一轮桶耗尽影响。

Gateway真实access log：独立签名探针一次search；实际匿名API的全部搜索（含21次缓存重搜与6次4118超限）仅一次search；短链一次resolve；五次items请求（01两次、08/07各一次、未知ID一次404）。因此缓存命中/超限未再次打gateway，详情01确实两次打gateway。runtime driver=fake/read_source=replay；日志里的Java HttpClient h2c Upgrade警告随后HTTP1请求200，不影响读源，不需要引websocket依赖。原始日志 `/tmp/302gatewaycalls.log`。

## 下游

303可复用 `GzJpSnapReadService.item` 的实时展示投影、`GzJpGatewayClient.item/seller`、`GzJpSnapFilter.reason/rules` 与译器。必须把完整准入叠加到当前filter-only purchasable与gateResult并接referencePriceCent，不得使用已落raw_json作实时权威。读取商品行可按 `(platform=mercari, external_id)` 查；mapper upsert不改互斥锁。详情controller只输出显式VO，303新增字段仍需维持raw不下发。热词返回前12个enabled ip中文字符串。错误码占用4117-4120，下一个4121。

## 已知限制

未知分类且搜索卡片无lineage时保守拒绝；完整平台分类树不在本卡引入。真实HTML/卖家简介/真实图片/真实短链以及生产阿里翻译未在线验证，本卡开发QA完全replay/mock。过滤通过不是303准入已完成；价格字段待303接入。密钥与CDN行政配置必须在部署环境提供。
