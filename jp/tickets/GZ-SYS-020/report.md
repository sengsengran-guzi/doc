# GZ-SYS-020 微信小程序配置多 appid 化 + real/mock 运行时分派 — 完工报告

> **结论**：accept 两条断言 **全 PASS**（19 + 6 = 25 个新单测全绿，全模块 188 个单测全绿）。
> 实施中自查逮到并修掉了**一个会打挂后台「发货信息手动补报」的真回归**，详见 §6。
> ⚠️ **但 prompt.md frontmatter 里 accept 命令的字面写法跑不通**（与本次代码无关的命令形态问题，
> 已用改造前就存在的测试对照证明），修法见 §0.5，**GZ-SYS-021/022/023 的 accept 是同款写法，同样需要修**。

---

## §0.5 ⚠️ accept 命令形态问题（先看这条，影响 SYS track 全部 4 张卡）

prompt.md 里的 accept 命令：

```bash
cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
  -pl ruoyi-modules/ruoyi-gz-common -am \
  -Dtest=WxMiniappPropertiesTest,WxLoginAdapterDispatchTest 2>&1 | tail -5
```

`-am`（also make）会把 21 个上游模块一起带进 reactor，而 `-Dtest=X` 对**每个**模块生效 ——
第一个上游模块 `ruoyi-common-core` 里没有叫这个名字的测试，surefire 3.5.3 直接判定失败：

```
[ERROR] Failed to execute goal org.apache.maven.plugins:maven-surefire-plugin:3.5.3:test
  (default-test) on project ruoyi-common-core: No tests matching pattern
  "WxMiniappPropertiesTest, WxLoginAdapterDispatchTest" were executed!
  (Set -Dsurefire.failIfNoSpecifiedTests=false to ignore this error.)
```

**对照实验（证明不是本 ticket 代码的问题）** —— 换成改造前就存在、且现在也照样通过的测试，同一命令形态照样炸：

```
$ mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am -Dtest=WxRealShippingClientTest
[ERROR] Failed to execute goal ... on project ruoyi-common-core:
  No tests matching pattern "WxRealShippingClientTest" were executed!
```

**修法（加一个参数即可，本项目历史 ticket D08/D09 就是这么跑的）**：

```bash
cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
  -pl ruoyi-modules/ruoyi-gz-common -am -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=WxMiniappPropertiesTest,WxLoginAdapterDispatchTest 2>&1 | tail -5
```

本报告 §AI 自测里两条 accept 都是**先跑字面命令、再跑修正命令**，两份 raw output 都贴了。
未改 prompt.md（ticket 归主线程管），请主线程决定是否统一修 021/022/023 的 accept 段。

---

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态（RuoYi-Vue-Plus，branch staging） | ✅ 开工前 clean，HEAD `0e5d2bf7c feat: new admin` |
| §0.1 `@Conditional` 注解位计数 == 8 | ✅ **恰好 8**，构成也对：real 侧 4 × `@ConditionalOnExpression` + mock 侧 4 × `@ConditionalOnProperty` |
| §0.1 两处不在 `wechat/` 下 | ✅ 确认 `pay/shipping/impl/` 下 2 处（`WxMockShippingClient` / `WxRealShippingClient`），只 grep `wechat/` 会得 6 → 假 STOP |
| §0.2 `properties.getAppid()` 全部读点 | ✅ 已列全（见下），改造覆盖微信侧 3 处；支付侧 2 处**刻意不动**（GZ-SYS-022 范围） |
| §0.3 现有 miniapp 能正常登录（改造前基线） | ✅ dev 后端起得来 + `wx-login` 返 200 / openid=`mock-dev-tester` / userId=11（改造后同样值，见 §AI 自测 4） |
| 编译健康（基线） | ✅ 改动前 `mvn test-compile -pl ruoyi-gz-common -am` EXIT=0 |
| ADR 已读 | ✅ ADR-0019（§1 本卡范围 / §2 §3 §4 下游 / §5 `gz.pay.client-mode` **刻意不动**） |
| 蓝图引用 | ✅ `FLOW:F-JP-00.step1 / step2`（doc/jp/authority/flows.yaml） |
| Flyway 迁移自检 | N/A —— 本卡零 DDL（`gz_user.app_id` 是 GZ-SYS-023） |

### §0.1 raw output（改造前）

```
$ grep -rn '^@Conditional' \
    ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/wechat/ \
    ruoyi-modules/ruoyi-gz-common/src/main/java/org/dromara/gz/common/pay/shipping/ | wc -l
       8

$ grep -rn '^@Conditional' <同上两个目录>
wechat/impl/WxRealLoginAdapter.java:51:@ConditionalOnExpression("'${wx.miniapp.appid:wxMOCK}' != 'wxMOCK'")
wechat/impl/WxMockPhoneAdapter.java:19:@ConditionalOnProperty(prefix = "wx.miniapp", name = "appid", havingValue = "wxMOCK", matchIfMissing = true)
wechat/impl/WxRealPhoneAdapter.java:39:@ConditionalOnExpression("'${wx.miniapp.appid:wxMOCK}' != 'wxMOCK'")
wechat/impl/WxMockAccessTokenManager.java:18:@ConditionalOnProperty(prefix = "wx.miniapp", name = "appid", havingValue = "wxMOCK", matchIfMissing = true)
pay/shipping/impl/WxMockShippingClient.java:19:@ConditionalOnProperty(prefix = "wx.miniapp", name = "appid", havingValue = "wxMOCK", matchIfMissing = true)
wechat/impl/WxMockLoginAdapter.java:37:@ConditionalOnProperty(prefix = "wx.miniapp", name = "appid", havingValue = "wxMOCK", matchIfMissing = true)
wechat/impl/WxRealAccessTokenManager.java:38:@ConditionalOnExpression("'${wx.miniapp.appid:wxMOCK}' != 'wxMOCK'")
pay/shipping/impl/WxRealShippingClient.java:41:@ConditionalOnExpression("'${wx.miniapp.appid:wxMOCK}' != 'wxMOCK'")
```

### §0.2 appid / secret 读点全清单（改造前）

| 位置 | 处置 |
|---|---|
| `WxRealLoginAdapter:68,69` appid+secret | ✅ 改为 `appResolver.currentApp()` 按小程序取 |
| `WxRealAccessTokenManager:68,69` appid+secret | ✅ 改为 `appResolver.currentApp()` 按小程序取 |
| `WxRealPhoneAdapter` `isMockPhoneFallback()` | ✅ 改为 `currentApp().isMockPhoneFallbackEnabled()`（可按 app 覆盖） |
| `WxMockLoginAdapter` `getMockStableOpenid()` | ✅ 改为 `currentApp().getMockStableOpenid()`（两个小程序 dev mock 用户可区分） |
| `WxLoginServiceImpl:58` `DEFAULT_MP_CLIENT_ID` 常量 | ✅ 删常量 → 配置项 `wx.miniapp.default-client-id` |
| `WechatPayV3ClientImpl:93` 统一下单 appid | ⏸ **刻意不动** = GZ-SYS-022 范围（ADR-0019 §3） |
| `WechatPayV3ClientImpl:125` 调起签名 appid | ⏸ **刻意不动** = GZ-SYS-022 范围（ADR-0019 §3，最易漏的一处） |
| `ProdSecretGuard:45` 读 `wx.miniapp.appid` | ⚠️ **本卡顺手修了**（不改会成 prod 地雷，理由见「实现摘要 §5」） |

---

## 实现摘要

```
 ruoyi-admin/src/main/resources/application-dev.yml  |  23 ++-
 ruoyi-admin/src/main/resources/application-prod.yml |   8 +-
 .../gz/common/config/ProdSecretGuard.java           |  49 ++++-
 .../pay/shipping/impl/WxMockShippingClient.java     |  10 +-
 .../pay/shipping/impl/WxRealShippingClient.java     |  19 +-
 .../gz/common/service/impl/WxLoginServiceImpl.java  |  50 +----
 .../gz/common/wechat/WxMiniappProperties.java       | 201 ++++++++++++++++++---
 .../wechat/impl/WxMockAccessTokenManager.java       |   8 +-
 .../gz/common/wechat/impl/WxMockLoginAdapter.java   |  14 +-
 .../gz/common/wechat/impl/WxMockPhoneAdapter.java   |   9 +-
 .../wechat/impl/WxRealAccessTokenManager.java       |  26 ++-
 .../gz/common/wechat/impl/WxRealLoginAdapter.java   |  32 ++--
 .../gz/common/wechat/impl/WxRealPhoneAdapter.java   |  20 +-
 .../gz/common/config/ProdSecretGuardTest.java       |  44 +++++
 .../service/impl/WxLoginServiceImplTest.java        |   4 +-
 .../common/wechat/impl/WxMockLoginAdapterTest.java  |   6 +-
 16 files changed, 376 insertions(+), 147 deletions(-)

新增（untracked）：
 wechat/WxAdapterDispatcher.java                      ← @Primary 运行时分派门面
 wechat/WxAppResolver.java                            ← clientid → 小程序解析器
 test/.../wechat/WxMiniappPropertiesTest.java         ← accept[1]
 test/.../wechat/WxLoginAdapterDispatchTest.java      ← accept[1]
 test/.../wechat/WxMiniappLegacyConfigTest.java       ← accept[2]
```

### §1 `WxMiniappProperties`：标量 → `Map<clientid, MiniappApp>`（含单值兼容包装）

- 新增 `Map<String, MiniappApp> apps`（key = 请求 header `clientid`）+ `String defaultClientId`
  （默认 `mp-applet-sensenran-guzi`，即 miniapp `.env` 的 `VITE_APP_CLIENT_ID`）。
- **保留全部原有标量字段**（`appid` / `secret` / `mockPhoneFallback` / `mockStableOpenid` / 两个 TTL）。
  `apps` 为空时 `resolveApps()` 自动包装成 `{defaultClientId: 单值}` 单元素 Map → 旧配置零改动、行为不变。
- `MiniappApp.mockPhoneFallback` / `mockStableOpenid` 用**包装类型**（null = 继承全局标量），
  所以 dev yml 里两个开关仍写在全局层、两个小程序自动继承，需要区分时再各自覆盖。
- `resolveApp(clientId)`：clientid 为空 → 落 `defaultClientId`；**登记不到 → 抛 `ServiceException`**
  （AC 要求：不静默落默认 app）。异常信息带上出错的 clientid + 已登记清单，便于一眼定位。
- `resolveApps()` **每次调用重新物化、不缓存**：调用点全是 IO 级操作（微信 HTTP / Redis），
  开销可忽略；换来的是「改标量立即生效」+ 绑定对象永不被写脏（单测里两条都断言了）。
- 实现 `InitializingBean`：配了 `apps` 但 `default-client-id` 不在其中 → **启动直接失败**。
  这条 fail fast 堵的是「无请求上下文的调用（`@Async` 发货上报 / cron）解析不到小程序」的运行期炸点。
- 启动日志打一行摘要（appid + 通道），是排查「哪个小程序走了哪条通道」的第一现场：
  `[wx-miniapp] 小程序注册 clientid=mp-applet-gz-jp appid=wxMOCK channel=mock`

### §2 撤 8 处条件 Bean → `WxAdapterDispatcher` 运行时分派

- 8 个实现（real/mock × login/phone/accessToken/shipping）全部改成无条件 `@Component`，**同时在容器里**。
- 新增 `WxAdapterDispatcher`：`@Primary`，同时实现 4 个能力接口
  （`WxLoginAdapter` / `WxPhoneAdapter` / `WxAccessTokenManager` / `WxShippingClient`）。
  业务侧（`WxLoginServiceImpl` / `UserBindMobileController` / `GzPayShippingServiceImpl`）
  **注入点一行没改**，按接口注入拿到的就是这个门面。
- `channel()` 在 `WxLoginAdapter` 与 `WxPhoneAdapter` 上是同签名方法，门面里一个实现即可
  —— 两者取值恒等于当前 app 的 mode。
- **循环依赖的坑**：`WxRealPhoneAdapter` / `WxRealShippingClient` 原本注入 `WxAccessTokenManager` 接口，
  而该接口的 `@Primary` 实现现在就是 dispatcher，会构成 `dispatcher → realPhoneAdapter → dispatcher`
  构造器环（Spring Boot 3 默认禁止、启动即失败）。改成直接依赖具体的 `WxRealAccessTokenManager`
  —— 语义上也更准：real 通道只在当前 app 是 real 时被选中。

### §3 `DEFAULT_MP_CLIENT_ID` 常量 → 配置项

`WxLoginServiceImpl` 删掉常量与私有 `resolveClientId()`，改注入 `WxAppResolver`。
clientid 解析口径与改造前**逐字一致**（header `clientid` 优先 → 拿不到回落默认；`ServletUtils.getRequest()`
无请求上下文返 null，try/catch 兜底），只是搬了个家并把默认值配置化。
登录日志加了 `clientid=` / `appid=` 两个字段（多小程序下没有这两个字段，日志根本分不清是哪个小程序）。

### §4 yml

- **dev**：切成 `apps` 形态，登记两个小程序（谷子宇宙保留 `${WX_MA_APPID:wxMOCK}` env 覆盖口径不变；
  拼团 `mp-applet-gz-jp` 恒 mock + 自己的 `mock-stable-openid: jp-tester`）。
  这样 GZ-JP-001 的 mp 脚手架一起来就能登录，不用回头改后端配置。
- **prod**：**保持单值形态不动**（零风险），只加注释说明「拿到拼团 appid/secret 后怎么改成 apps 形态」
  以及「未登记的 clientid 一律拒绝，所以拼团 mp 上线前必须先补这里」。

### §5 顺手修的 prod 地雷：`ProdSecretGuard`

`ProdSecretGuard`（D16 B3，prod 漏配 fail-fast 守卫）原本直接读 `environment.getProperty("wx.miniapp.appid")`。
配置一旦切到 `apps` 形态，这个 key 就不存在了 → 守卫读到 null → **prod 启动被自己的守卫拒绝**，
且报错信息指向一个已经不存在的配置项，排查会被带偏；更糟的绕法是运维补一个假标量把守卫骗过去，
而 `apps` 里真正生效的 appid 是不是占位值就再也没人检查了 —— 那正是这个守卫当初要防的「鉴权静默降级」。

改法：守卫改为遍历 `WxMiniappProperties.resolveApps()` 的**每一个**小程序校验 appid，
单值形态解析出来就是一个元素 → 行为与改造前完全一致（旧的 6 个单测一行没改、全绿），
Map 形态下任一小程序漏配都会拒绝启动并**点名是哪个 clientid**。新增 3 个单测覆盖。

### 不做（守 ADR 边界）

- ❌ 不动 `RedisSessionKeyStore`（key 按 openid，天然跨 appid 唯一 —— 任务卡明示）
- ❌ 不动 `gz.pay.client-mode`（ADR-0019 §5：进程级全局开关，与 `wx.miniapp.appid` 正交，
  一期刻意不 Map 化；`IWechatPayClient` 是单例注入，运行时切换会拿到错误实现）
- ❌ 不动 `WechatPayV3ClientImpl:93/:125`（ADR-0019 §3 = GZ-SYS-022）
- ❌ 不动 `access_token` 缓存 key（ADR-0019 §2 = GZ-SYS-021），只留了带 ticket 号的 TODO

---

## AI 自测（Tier 1A）

### 1. accept[1]「两个 clientid 各自解析到自己的 appid」

**先跑 prompt.md 的字面命令**（失败，原因见 §0.5，与本次代码无关）：

```
$ cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-common -am \
    -Dtest=WxMiniappPropertiesTest,WxLoginAdapterDispatchTest 2>&1 | tail -5
[ERROR] For more information about the errors and possible solutions, please read the following articles:
[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/MojoFailureException
[ERROR]
[ERROR] After correcting the problems, you can resume the build with the command
[ERROR]   mvn <args> -rf :ruoyi-common-core

# 完整报错（被 tail -5 截掉的那行）：
[ERROR] Failed to execute goal org.apache.maven.plugins:maven-surefire-plugin:3.5.3:test
  (default-test) on project ruoyi-common-core: No tests matching pattern
  "WxMiniappPropertiesTest, WxLoginAdapterDispatchTest" were executed!
  (Set -Dsurefire.failIfNoSpecifiedTests=false to ignore this error.)
```

**修正命令（= 实际断言结论 ✅ PASS）**：

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am \
    -Dsurefire.failIfNoSpecifiedTests=false \
    -Dtest=WxMiniappPropertiesTest,WxLoginAdapterDispatchTest
[INFO] Tests run: 9,  Failures: 0, Errors: 0, Skipped: 0 -- in org.dromara.gz.common.wechat.WxLoginAdapterDispatchTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0 -- in org.dromara.gz.common.wechat.WxMiniappPropertiesTest
[INFO] Tests run: 19, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

覆盖：两 clientid 各自 appid/secret/通道 · 未知 clientid 抛错 · 空 clientid 落默认 · 单值包装 ·
dev 开关继承/覆盖 · 不缓存不写脏 · default-client-id fail fast ·
四种能力（login/phone/token/shipping）各自按 clientid 选 real/mock · 同一实例换 clientid 立刻切通道。

### 2. accept[2]「旧单值配置不改仍能启动（向后兼容）」

**字面命令**同样炸在 `ruoyi-common-core`（同 §0.5，不重复贴）。**修正命令（✅ PASS）**：

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am \
    -Dsurefire.failIfNoSpecifiedTests=false -Dtest=WxMiniappLegacyConfigTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0 -- in org.dromara.gz.common.wechat.WxMiniappLegacyConfigTest
[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

这 6 个用 `ApplicationContextRunner` **真起 Spring 容器**（只装微信相关 Bean，不依赖 DB/Redis）：
prod 旧单值（真 appid+secret）→ 起得来且仍 real ·
dev 旧单值（wxMOCK + 两个 dev 开关）→ 仍 mock 且开关仍生效（`mock-dev-tester` / `13800000000` 逐字断言）·
完全不配 → 默认 mock ·
8 个 real/mock Bean 同时在容器里且 4 个接口注入点都解析到 `@Primary` 门面（不抛 `NoUniqueBeanDefinitionException`）·
`apps.<clientid>` 松散绑定（key 含连字符）可用 · default-client-id 配错 → 启动失败。

### 3. 全模块回归（无一处旧测试被改坏）

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am
[INFO] Tests run: 188, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

（改造前 183 → 现 188：新增 25 个（10+9+6）、`ProdSecretGuard` 新增 3 个；
`WxLoginServiceImplTest` / `WxMockLoginAdapterTest` 只改构造器入参，断言一行没动，仍全绿。）

全仓编译（含依赖 gz-common 的 7 个业务模块 + ruoyi-admin 打包）：

```
$ mvn -o clean install -DskipTests -Dmaven.test.skip=true
[INFO] ruoyi-gz-common .................................... SUCCESS [  2.268 s]
[INFO] ruoyi-gz-coupon .................................... SUCCESS [  0.596 s]
[INFO] ruoyi-gz-bean ...................................... SUCCESS [  1.960 s]
[INFO] ruoyi-gz-user ...................................... SUCCESS [  0.836 s]
[INFO] ruoyi-gz-news ...................................... SUCCESS [  0.426 s]
[INFO] ruoyi-gz-gacha ..................................... SUCCESS [  0.704 s]
[INFO] ruoyi-gz-ord ....................................... SUCCESS [  0.881 s]
[INFO] ruoyi-gz-recycle ................................... SUCCESS [  0.796 s]
[INFO] ruoyi-admin ........................................ SUCCESS [  2.512 s]
[INFO] BUILD SUCCESS
```

### 4. 真启动 + 真 HTTP 回归（单测照不出装配问题，必须真起容器）

**4a. 旧单值配置（改 yml 之前的原样）真启动 → 行为与改造前逐字一致**

```
$ java -jar ruoyi-admin/target/ruoyi-admin.jar --spring.profiles.active=dev
 - Started DromaraApplication in 10.203 seconds
 - [wx-miniapp] 小程序注册 clientid=mp-applet-sensenran-guzi appid=wxMOCK channel=mock
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功   ლ(´ڡ`ლ)ﾞ

# A) 现小程序 clientid（回归）
$ curl -X POST localhost:8080/app/gz/common/auth/wx-login -H 'clientid: mp-applet-sensenran-guzi' \
       -d '{"code":"smoke-code-020a","nickName":"回归测试",...}'
{"code":200,...,"userId":"11","openid":"mock-dev-tester","nickName":"回归测试",...}
   ↑ token payload 里 clientid=mp-applet-sensenran-guzi、tenantId=1001、userId=11 —— 与改造前同

# B) 不带 clientid header（curl / @Async / cron 场景）
{"code":200,...,"userId":"11","openid":"mock-dev-tester",...}     ← 落 default-client-id，不炸

# C) 未登记 clientid
{"code":500,"msg":"未配置的小程序客户端 clientid=mp-applet-gz-jp，请在 wx.miniapp.apps 中登记（已配置：[mp-applet-sensenran-guzi]）"}
   ↑ AC「不静默落到默认 app」在真 HTTP 层面成立
```

**4b. 新 apps 形态（dev yml 登记两个小程序）真启动 → 两个小程序各自独立**

```
 - [wx-miniapp] 小程序注册 clientid=mp-applet-sensenran-guzi appid=wxMOCK channel=mock
 - [wx-miniapp] 小程序注册 clientid=mp-applet-gz-jp appid=wxMOCK channel=mock

A) clientid: mp-applet-sensenran-guzi → {'code': 200, 'openid': 'mock-dev-tester', 'userId': '11'}
B) clientid: mp-applet-gz-jp          → {'code': 200, 'openid': 'mock-jp-tester',  'userId': '12'}
C) clientid: mp-applet-bogus          → {'code': 500, 'msg': '未配置的小程序客户端 clientid=mp-applet-bogus，
                                          请在 wx.miniapp.apps 中登记（已配置：[mp-applet-sensenran-guzi, mp-applet-gz-jp]）'}

# 后端日志（clientid/appid 已进日志，多小程序可分辨）
 - [wx-login] clientid=mp-applet-sensenran-guzi appid=wxMOCK adapter=mock openid=mock-dev-tester ...
 - [wx-login] clientid=mp-applet-gz-jp          appid=wxMOCK adapter=mock openid=mock-jp-tester ...
```

**4c. ★ 同一个 JVM 进程内「A real + B mock」——ADR-0019 §1 的核心断言，改造前物理上做不到**

```
$ WX_MA_APPID=wx2f8b93e09703f07d WX_MA_SECRET=<故意给假的> java -jar ruoyi-admin.jar --spring.profiles.active=dev
 - [wx-miniapp] 小程序注册 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d channel=real
 - [wx-miniapp] 小程序注册 clientid=mp-applet-gz-jp          appid=wxMOCK             channel=mock
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功

# A) 拼团 mp（mock）—— 隔壁是 real 也完全不影响它
{'code': 200, 'openid': 'mock-jp-tester'}

# B) 谷子宇宙 mp（real）—— 真的打到了微信 jscode2session，微信用真 appid 校验了那个假 secret
{'code': 500, 'msg': '微信登录失败: invalid appsecret, rid: 6a749750-5e1986fe-2b1ac58f'}

# 后端日志（证明用的是「这个 app 自己的」appid，不是全局标量）
 - [wx-real] jscode2session errcode=40125 errmsg=invalid appsecret, rid: ...
             clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d
```

微信返 **40125 invalid appsecret**（而不是 appid 不存在）= 真 appid 被正确带过去了、走的确实是 real 通道；
同一进程里拼团那个仍稳稳走 mock。**这是本卡最有说服力的一条证据。**

### 5. 改造后残留扫描（防回归）

```
$ grep -rn '^@Conditional' <wechat/ 与 pay/shipping/ 两个目录> | wc -l
       0                                    ← 8 处条件 Bean 已全部撤除

$ grep -rn --include="*.java" "DEFAULT_MP_CLIENT_ID" ruoyi-modules/ ruoyi-admin/src/main/java
wechat/WxMiniappProperties.java:59:     * ...（原 {@code WxLoginServiceImpl.DEFAULT_MP_CLIENT_ID} 常量）。
       ↑ 仅剩 javadoc 里的一处溯源说明，常量本体已删

$ grep -rn --include="*.java" "getAppid()" ruoyi-modules/ruoyi-gz-common/src/main
pay/service/internal/WechatPayV3ClientImpl.java:93    ← 刻意保留 = GZ-SYS-022
pay/service/internal/WechatPayV3ClientImpl.java:125   ← 刻意保留 = GZ-SYS-022（最易漏的一处）
其余 8 处全部是 MiniappApp.getAppid()（按小程序取）
```

后台进程已收尾：`lsof -iTCP:8080 -sTCP:LISTEN` 无输出，`pgrep -f ruoyi-admin.jar` 无残留。

### 6. ★ 自查逮到的真回归（已修 + 已加回归测试）—— 后台「发货信息手动补报」被打挂

**怎么发现的**：完工后按纪律对 diff 做了一轮对抗式 review（关注点：现有小程序 / 现有功能会不会坏）。

**根因（我自己的设计缺陷）**：`clientid` 是 ruoyi 的**认证客户端 id**，不等于**小程序 id** ——
小程序的 clientid 只是它的一个子集。plus-ui 后台给**每一个**后台请求都注入 PC 客户端 id：

```
$ grep -rn "clientid" code/main/plus-ui/src/utils/request.ts
22:    clientid: import.meta.env.VITE_APP_CLIENT_ID
27:  axios.defaults.headers['clientid'] = import.meta.env.VITE_APP_CLIENT_ID;
$ grep -rn "CLIENT_ID" code/main/plus-ui/.env.production
33:VITE_APP_CLIENT_ID = 'e5cd7e4891bf95d1d19206ce24a7b32e'
```

而我第一版 `WxAppResolver.currentClientId()` 把「请求 header 里的 clientid」无条件当作小程序路由键，
于是任何**非 mp 的已认证调用方**打到共享能力就会撞上「未配置的小程序客户端」。
唯一被波及的真实路径：`WxShippingClient`（+ 它依赖的 access_token）——
`GzPayShippingController` 的后台**手动补报**端点是同步在请求线程里调的：

```
POST /system/gz/pay/shipping/{id}/retry   → retryOne() → doUpload() → shippingClient.uploadShippingInfo()
POST /system/gz/pay/shipping/retry-all    → backfillPending() → 同上（有 per-row try/catch）
```

（`@Async` 上报和 cron 没有请求上下文、走的是默认回落，**不受影响** —— 所以这个坑只在后台按钮上暴露。）

**真机复现（修之前，dev 真起后端 + 真 admin 登录）**：

```
# 先把一条 success 行临时置 failed 让它能真正走到上报（事后已原值还原）
$ curl -X POST localhost:8080/system/gz/pay/shipping/12/retry -H "Authorization: Bearer <admin>" \
       -H "clientid: e5cd7e4891bf95d1d19206ce24a7b32e"
{"code":500,"msg":"未配置的小程序客户端 clientid=e5cd7e4891bf95d1d19206ce24a7b32e，
                   请在 wx.miniapp.apps 中登记（已配置：[mp-applet-sensenran-guzi, mp-applet-gz-jp]）"}

$ curl -X POST localhost:8080/system/gz/pay/shipping/retry-all -H "Authorization: Bearer <admin>" ...
{"code":200,"msg":"补报完成","data":{"scanned":1,"success":0,"failed":1}}
   ↑ 更阴的一条：批量补报不报错，只是把每一行都记成「上报失败」并把这条无关的错写进 last_error，
     看上去像微信侧的问题 —— 而这个按钮正是历史 74 单卡单（影响资金结算）留下的唯一人工兜底。
```

**修法（区分两种解析口径，不是简单放宽）**：

| 能力 | 调用来源 | 口径 |
|---|---|---|
| 登录 `WxLoginAdapter` / 手机号 `WxPhoneAdapter` | **只可能是小程序**（控制器挂 `/app/**`） | **严格** `currentApp()` —— 未登记 clientid = 真配置错误（新小程序忘了登记），必须立刻抛错，绝不能静默拿另一个小程序的 appid/secret 去调微信 |
| 发货上报 `WxShippingClient` / `WxAccessTokenManager` | 支付回调 `@Async` + cron + **后台手动补报** | **宽松** `currentAppOrDefault()` —— 认不出只说明「调用方不是小程序」，落 `default-client-id`，**这正是多 appid 改造前的行为**（当时整个进程只有一个 appid） |

AC「未知 clientid 明确抛错、不静默落默认 app」**在它真正该管的地方（mp 登录/手机号）原样保留**。

**修完复验（同一套真机路径）**：

```
=== 修复后：admin 单条补报 ===
{"code":200,"msg":"上报成功","data":null}
=== 修复后：admin 补报全部 ===
{"code":200,"msg":"补报完成","data":{"scanned":1,"success":1,"failed":0}}
=== mp 侧严格口径仍在（没有被放宽掉）===
clientid=mp-applet-gz-jp    → {'code': 200, 'openid': 'mock-jp-tester'}
clientid=mp-applet-bogus    → {'code': 500, 'msg': '未配置的小程序客户端 clientid=mp-applet-bogus...'}
```

**回归测试已落**（`WxLoginAdapterDispatchTest` 新增 2 个，带 ★ 标记）：
后台 PC clientid 调 `shippingClient()` / `accessTokenManager()` 不许抛错且落默认 app ·
默认 app 是 mock 时后台补报能走完整条 · 同时断言 mp 专属能力（login/phone/channel）**仍然**抛错。

**用于复现的 dev 数据已原值还原**：

```
$ SELECT id,upload_status,attempt_count,uploaded_time,last_error FROM gz_pay_shipping_order WHERE id=12;
id=12  upload_status=success  attempt_count=1  uploaded_time=2026-07-07 14:19:56.615  last_error=NULL
$ SELECT upload_status, COUNT(*) FROM gz_pay_shipping_order GROUP BY upload_status;
success  12          ← 与开工前一致
```

**教训（值得进 learnings）**：把「ambient 请求头」当业务路由键时，必须先问一句
**「这个 header 只有我关心的那类调用方会带吗？」** —— `clientid` 的答案是否，它是全端通用的认证客户端标识。
单测照不出这个：`GzPayShippingServiceImplTest` 在 `WxShippingClient` 接口边界 mock 掉了，
根本走不到解析逻辑；也没有任何一个 fixture 模拟「非 mp 的已认证调用方」。

---

## 风险提示 / 已知 issue

1. **【行为变更，需知会】未登记的 clientid 从「静默放行」变成「明确报错」。**
   改造前 clientid 只写进 token extra、不参与通道选择，任何值都能登录；现在必须在
   `wx.miniapp.apps`（或单值形态的 default-client-id）里登记。
   现有 mp `.env` 的 `VITE_APP_CLIENT_ID = 'mp-applet-sensenran-guzi'` 与 prod/dev 默认值一致（已核对），
   **prod 不受影响**；但任何用别的 clientid 打 `/app/gz/**` 微信相关端点的脚本会开始报错 —— 这是 AC 明确要的。

2. **【GZ-SYS-021 落地前】不要在同一环境同时配置两个 real 小程序。**
   `access_token` 缓存 key 仍是不带 appid 的全局串（ADR-0019 §2 = GZ-SYS-021 范围），
   两个 real app 会互相覆盖 token → 手机号解密 / 发货上报**间歇性** 40001。
   代码里已留 `TODO(GZ-SYS-021)` + 类 javadoc 警示。当前 dev/prod 都只有一个 real，不构成现实风险。

3. **【设计口径，下游必须沿用】共享能力（发货上报 / access_token）走宽松解析，mp 专属能力（登录 / 手机号）走严格解析。**
   新增会被 admin / `@Async` / cron 触发的微信能力时，一律用 `WxAppResolver.currentAppOrDefault()`；
   只可能被小程序调用的才用 `currentApp()`。用错方向 = 要么打挂后台按钮（见 §6），要么静默拿错小程序的凭证。

4. **【已知边界】`@Async` 发货上报没有请求上下文 → 按 `default-client-id` 取通道和 token。**
   本卡的 fail-fast（default-client-id 必须在 apps 里）保证它至少解析得到；但两个小程序都要真上报时，
   发货任务必须自己带上归属 clientid —— 归 GZ-SYS-021/022（`gz_pay_shipping_order` 需要一个 app 维度）。

5. **prod yml 仍是单值形态（有意为之）**：拼团小程序在 prod 会被拒（报错清晰可定位）。
   prod 切 apps 形态是「appid 回补阶段」的动作，注释已写在 `application-prod.yml` 里。

6. **微信支付侧一行未动**：`WechatPayV3ClientImpl:93/:125` 仍读全局 `props.getAppid()`。
   拼团小程序在 GZ-SYS-022 落地前**不能真收款**（会拿到属于旧 appid 的 prepay_id）。

7. 待 Kevin 残留人验：**N/A** —— 纯后端 ticket，无 mp 页面、无真机微信原生能力。
   （真机维度的验证在 GZ-SYS-022 的「真钱 1 分单」和 appid 回补阶段。）

---

## 对下游 ticket 的提示

### 与 prompt.md 描述不一致 / 需要下游知道的实际情况

| 下游以为 | 实际 |
|---|---|
| `@Conditional` 8 处都在 `wechat/` | 6 处在 `wechat/impl/`、**2 处在 `pay/shipping/impl/`**（任务卡 §0 已提醒，属实） |
| 只改 `wechat/**` 就够 | 还必须改 **`config/ProdSecretGuard.java`**（读 `wx.miniapp.appid`）—— 本卡已改；下游改配置形态时留意还有没有别的 `environment.getProperty("wx.miniapp.*")` 读点 |
| accept 命令可直接跑 | ❌ 见 §0.5，`-am` + `-Dtest` 必须加 `-Dsurefire.failIfNoSpecifiedTests=false`；**021/022/023 三张卡同款写法，同样要加** |
| 单测 `@Tag` 随便写 | ❌ 根 pom surefire 配了 `<groups>${profiles.active}</groups>`，**不写 `@Tag("dev")` 的测试根本不会被执行**（会静默"通过"）。新测试务必带 `@Tag("dev")` |

### ⚠️ 给所有下游：新增微信能力时先选对解析口径（§6 的教训）

- 只可能被小程序调用（控制器挂 `/app/**`）→ `WxAppResolver.currentApp()`（严格，未登记抛错）
- 会被 admin 后台 / `@Async` / cron 调用 → `WxAppResolver.currentAppOrDefault()`（宽松，落默认 app）
- 判断依据不是「这个能力属不属于微信」，而是**「调用线程的 clientid 一定是小程序吗」** ——
  plus-ui 给每个后台请求都注 `clientid=e5cd7e4891bf95d1d19206ce24a7b32e`，那不是小程序。

### ⚠️ ops 缺口（GZ-SYS-022 / appid 回补阶段要补）

`script/docker/docker-compose.deploy.yml:105-106` 只往容器里透传了 `WX_MA_APPID` / `WX_MA_SECRET`，
**没有** `WX_JP_MA_APPID` / `WX_JP_MA_SECRET` 透传。也就是说 `application-prod.yml` 里我写的那段
「拿到拼团 appid 后改成 apps 形态」的注释，光改 yml 还驱动不起来 —— 必须同时给 compose 补两行 env 透传。
本卡没动 deploy 配置（不在 touches，且 prod 本期仍走单值形态）。

### 给 GZ-SYS-021（access_token 按 appid 隔离）

- 直接用 `WxRealAccessTokenManager` 里已有的 `MiniappApp app = appResolver.currentApp();`，
  key 拼 `app.getAppid()` 即可；`ACCESS_TOKEN_CACHE_KEY` 常量改名成你 accept 断言要的
  `ACCESS_TOKEN_CACHE_KEY_PREFIX`，并**删掉**字面量 `"wx:miniapp:access_token"`（你的 accept[2] grep 查这个）。
- 该类的构造器现在是 `WxRealAccessTokenManager(WxAppResolver)`（不再是 `WxMiniappProperties`）。
- 类 javadoc 里留了 `TODO(GZ-SYS-021)` 说明，改完记得删。
- 单测要造两个 app 的话，抄 `WxLoginAdapterDispatchTest.setUp()` 的 fixture
  （含 `MockHttpServletRequest` + `RequestContextHolder` 造 clientid header 的写法）。

### 给 GZ-SYS-022（支付多 appid）

- **不要**把 `gz.pay.client-mode` 一起 Map 化（ADR-0019 §5；`IWechatPayClient` 单例注入，运行时切会拿错实现）。
- 取当前小程序 appid 的现成入口：`WxAppResolver#currentAppid()` / `WxAdapterDispatcher#currentApp()`。
  但**支付链路更应该从下单上下文 / `gz_pay_channel.appid` 取**（ADR-0019 §3），
  因为回调、查单、退款都发生在没有原请求 header 的线程里 —— 别图省事用 `currentAppid()`。
- `:93`（统一下单）和 `:125`（调起签名 5 参）两处都要改，**`:125` 是最易漏的**：只改 `:93` 的话
  下单接口返 200、日志全绿，前端调起时才报签名错，排查方向会被日志带偏。
- `payer.openid` 必须与所用 appid 同源（openid 是 appid 维度的），否则微信返「openid 与 appid 不匹配」。

### 给 GZ-SYS-023（gz_user 加 app_id）

- 登录链路里取 appid 的入口已就位：`WxLoginServiceImpl` 已注入 `WxAppResolver`，
  直接 `appResolver.currentAppid()` 传给 `upsertByOpenid` 即可（字段已在，无需改构造器）。
- 现小程序 appid = `wx2f8b93e09703f07d`（`application-prod.yml` 默认值），存量行回填用它。
- ⚠️ **dev 库现在多了两条 mock 用户**（本卡真机回归跑出来的）：
  `openid=mock-dev-tester`(userId=11) 与 `openid=mock-jp-tester`(userId=12)，
  两条都属于现小程序 appid（dev 两个 app 目前都是 wxMOCK）。回填 `app_id` 时会一起填成现小程序 appid
  —— 数据没问题，但**别拿它当「两个小程序各自的用户」的验证样本**（那要等 dev 配上真 JP appid）。
- 迁移文件时间戳用 `date +V%Y%m%d%H%M` 当下真实时间，append-only 铁律（CLAUDE.md §5）。

### 给 GZ-JP-001（拼团 mp 脚手架）

- 后端**已经**认 `clientid: mp-applet-gz-jp`（dev yml 已登记，恒走 mock）。
  mp 侧 `.env` 的 `VITE_APP_CLIENT_ID` **必须**写成 `mp-applet-gz-jp`，写错会收到
  「未配置的小程序客户端 clientid=xxx」而不是静默串到谷子宇宙那个小程序。
- dev 下拼团 mp 登录会拿到固定 openid `mock-jp-tester`（与谷子宇宙的 `mock-dev-tester` 区分开），
  改这个值的开关是 `WX_JP_MA_MOCK_OPENID`。
- 拿到真 appid/secret 后：dev 注入 `WX_JP_MA_APPID` / `WX_JP_MA_SECRET` 即切 real，**不用改代码**。

---

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

（占位 —— 本卡为纯后端改造：admin 无页面变更、mp 无页面变更。
Tier 1B 建议范围 = 后端集成 + API 契约回归（`/app/gz/common/auth/wx-login` 三种 clientid 场景）
+ 现有 mp 模拟器 E2E 登录流回归（验证 `mp-applet-sensenran-guzi` 未受影响）
+ **admin Playwright：支付管理 → 发货信息 → 「手动补报」单条 / 全部两个按钮**（§6 回归点，
  是本卡唯一被 admin 触及的路径，务必真点一遍）。）
