# GZ-SYS-021 access_token 按 appid 隔离 — 完工报告

> **结论**：accept 两条断言 **全 PASS**（新增 9 个单测全绿；`ruoyi-gz-common` 全模块 205 个单测全绿）。
> 另跑了**负向对照**（把 key 换回改造前的固定串）—— 同一套测试 **8/9 失败**，证明这组断言真的能逮住原 bug，
> 不是「怎么写都绿」的摆设。
> ⚠️ **环境事故级提示**：本 ticket 实施期间 **GZ-SYS-022 / 023 在同一个工作区并行写码**，见 §0.6，主线程需知悉。

---

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态（RuoYi-Vue-Plus，branch staging，HEAD `0e5d2bf7c`） | ⚠️ 非 clean —— 工作区含 GZ-SYS-020 未 commit 的全部改动（本卡的上游依赖，符合流水线预期）；实施中途又混入 022/023 的在飞改动（§0.6） |
| §0.1 `grep -n "wx:miniapp:access_token" -r ruoyi-modules/` 确认当前 key 无 appid 维度 | ✅ 改造前唯一构造点 `WxRealAccessTokenManager:51 private static final String ACCESS_TOKEN_CACHE_KEY = "wx:miniapp:access_token";` |
| §0.2 GZ-SYS-020 已就位（dispatcher 可用） | ✅ `WxAppResolver` / `WxAdapterDispatcher` 均在工作区；本类构造器已是 `WxRealAccessTokenManager(WxAppResolver)` |
| 编译健康（基线） | ✅ 开工前 `mvn -o -q test-compile -pl ruoyi-gz-common -am` EXIT=0（**注**：此后被 022/023 的在飞编辑打断过两轮，见 §0.6） |
| ADR 已读 | ✅ **ADR-0019 §2**（本卡范围，逐条落实见「实现摘要」）+ §1（上游 020）+ §3（022，刻意不碰）+ §5（`gz.pay.client-mode` 不动） |
| 蓝图引用 | ✅ `FLOW:F-JP-00.step2`；ADR-0019 §2「刷新、读取、失效重取三条路径一律按 appid 取」= 本卡验收口径 |
| Flyway 迁移自检 | N/A —— 本卡零 DDL（`gz_user.app_id` 迁移是 GZ-SYS-023 的，我没碰） |

### §0.1 raw output（改造前）

```
$ grep -n "wx:miniapp:access_token" -r ruoyi-modules/   # 已滤掉 target/ 幽灵副本
ruoyi-modules/.../wechat/impl/WxRealAccessTokenManager.java:33:  * <p>token 全局缓存（key {@code wx:miniapp:access_token}，TTL = expires_in - 余量）
ruoyi-modules/.../wechat/impl/WxRealAccessTokenManager.java:51:  private static final String ACCESS_TOKEN_CACHE_KEY = "wx:miniapp:access_token";
```

全后端**只有这一处**构造该 key（没有第二处自己拼 key 的调用方），所以改造面确实只有 `touches` 列的那一个文件。

### §0.6 ⚠️ 并行 ticket 共用同一个工作区（主线程必读）

实施到一半，`git status` 里冒出了不属于 020 也不属于我的改动 —— **GZ-SYS-022 与 GZ-SYS-023 正在同一个
`code/main/RuoYi-Vue-Plus` 工作区同时写码**（022：`PayAppidResolver` / `IWechatPayClient.buildPayParams`
/ `WechatPayV3ClientImpl` / 在 `MiniappApp` 上加 `registerSource`；023：`GzUser` / `IGzUserService.upsertByOpenid`
/ 迁移 `V202608062251__GZ-SYS-023-alter-gz_user-add-app_id.sql`）。

后果是**整个模块一度编译不过**，而断点全在别人的文件里（同一分钟内先后是 022 的
`MiniappApp.setRegisterSource` 未定义、022 的 `GzPayChannel.getClientId()` 未定义，随后是 023 的
`IGzUserService.upsertByOpenid` 签名改了但实现类还没跟上）：

```
[ERROR] .../WxMiniappProperties.java:[200,12] cannot find symbol: method setRegisterSource(String)
[ERROR] .../PayAppidResolver.java:[111,21] cannot find symbol: method getClientId() in class GzPayChannel
[ERROR] .../GzUserServiceImpl.java:[38,8] does not override abstract method upsertByOpenid(...,MiniappApp)
```

**我的处置（一个字节都没动别人的文件）**：

1. 先做**隔离验证**——用模块已有的 `target/classes` + `mvn dependency:build-classpath` 出来的依赖 classpath，
   `javac` 单独编我的测试类到 scratch 目录，再用 `junit-platform-launcher` 直接跑（详见 §AI 自测 1）。
   这条路径完全绕开别人的在飞代码，结论确定、可复现。
2. 再起一个**轮询脚本**等工作区自己收敛，收敛后跑 accept 的原命令拿「集成态」结论（attempt 1 即 GREEN）。
3. 全模块回归第一次跑出 2 个 failure，**全部落在 023 刚创建的 `GzUserMultiAppUpsertTest`**（文件 mtime
   比我这轮实施还新，是他们红→绿过程中的中间态）；单独重跑该类已自行转绿，随后全模块 205/205 全绿。
   我另外确认过该类**不碰 `SpringUtil` / `RedisUtils`**，与我测试里的 `SpringUtil` bootstrap 无交集
   （排除「是我污染了别人」这条可能）。

**给主线程的建议**：同一工作区并行派多个改同一模块的 ticket，会让每个 ticket 的「编译健康 / 全模块回归」
自检变成**别人的状态的函数** —— 绿了不一定是自己对，红了往往不是自己错。后续要么给并行 ticket 分 worktree，
要么把同模块的 SYS track 串行化。本卡的结论因为有隔离验证 + 负向对照兜底，不受此影响。

---

## 实现摘要

```
$ git diff --stat -- .../wechat/impl/WxRealAccessTokenManager.java
 .../wechat/impl/WxRealAccessTokenManager.java | 56 +++++++++++++++-------
 1 file changed, 38 insertions(+), 18 deletions(-)
   ↑ 这是相对 HEAD 的数字，含 GZ-SYS-020 在同一文件里未 commit 的改动；
     本卡自己的 delta = 下面 4 条（其余是 020 的：撤 @ConditionalOnExpression、构造器换 WxAppResolver、凭证按 app 取）

新增（untracked）：
 src/test/java/org/dromara/gz/common/wechat/WxAccessTokenIsolationTest.java   ← accept[1]，9 个用例
```

### 1. 常量：固定串 → 前缀（accept[2] 的两个断言点）

```java
// 改造前
private static final String ACCESS_TOKEN_CACHE_KEY = "wx:miniapp:access_token";
// 改造后
private static final String ACCESS_TOKEN_CACHE_KEY_PREFIX = "wx:miniapp:access_token:";
```

末尾冒号刻意做进前缀常量里（javadoc 也写明「不要省」）：省掉分隔符后 appid `wxAB` 与 `wxA`+`B`
这类前缀关系会撞进同一个槽位 —— 这正是本卡要消灭的那类故障，不能在修它的时候又埋一颗同款。

### 2. 解析前置到读缓存**之前**（ADR-0019 §2「读取」路径）

改造前是「先读缓存 → miss 了才解析 app」。key 带上 appid 之后这个顺序**必须反过来**：
不知道自己是哪个小程序，就不知道该读哪个槽位。

```java
MiniappApp app = appResolver.currentAppOrDefault();
String cacheKey = ACCESS_TOKEN_CACHE_KEY_PREFIX + app.getAppid();
if (!forceRefresh) {
    String cached = RedisUtils.getCacheObject(cacheKey);   // 读
    ...
}
...
RedisUtils.setCacheObject(cacheKey, token, Duration.ofSeconds(ttl));   // 刷新 / 失效重取
```

三条路径（读取 / 刷新 / 失效重取 `forceRefresh=true`）**共用同一个 `cacheKey` 局部变量**，
物理上不可能出现「读 A 槽写 B 槽」。

### 3. 解析口径 = `currentAppOrDefault()`（宽松，**不是** `currentApp()`）

任务卡交接说明里写的是 `currentApp()`，但工作区里 020 实际留下的、也是**正确**的那个是
`currentAppOrDefault()` —— 保持不动，理由是 GZ-SYS-020 §6 用真机复现付出过代价的那条教训：
access_token 是**共享能力**，除小程序外还会被 `@Async` 发货上报、cron、以及后台 admin
「发货信息手动补报」（`POST /system/gz/pay/shipping/{id}/retry`）调用，那些线程带的 clientid
是 plus-ui 的 PC 客户端 id、不是小程序。改成严格口径会**当场打挂后台补报按钮**（而那是影响资金结算的
唯一人工兜底）。新增的回归用例 `adminPcClientId_fallsBackToDefaultAppSlot` 把这条钉死了。

> 顺带确认一处**不会**出问题的地方：手机号解密路径 `WxRealPhoneAdapter` 自己用严格 `currentApp()`
> 取 appid，token 却来自宽松口径。两者只在「clientid 已登记」时才会同时走到，而那种情况下两个口径
> 解析出的是同一个 app；clientid 没登记时严格口径先抛错、根本走不到用 token 那一步。
> 所以不存在「拿 A 的 token 去按 B 的 appid 解密」的错配窗口。

### 4. 日志加 appid / key（这类故障的第一现场）

刷新成功日志加 `appid=` / `key=`，失败日志加 `clientid=` / `appid=`。
多小程序下「40001 到底是哪个小程序的凭证不对」全靠这两个字段，没有它们就得靠猜。

```
[wx-token] access_token 刷新成功 clientid=mp-applet-gz-jp appid=wx77c1c88d2b0f1a2c key=wx:miniapp:access_token:wx77c1c88d2b0f1a2c ttl=6900s
[wx-token] 获取 access_token 失败 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d errcode=40125 errmsg=invalid appsecret
```

### AC「刷新逻辑（提前量、并发保护）保持原语义」的兑现口径

- **提前量**：`TOKEN_EXPIRE_SAFETY_SECONDS = 300` 与 `ttl < 60 → 60` 兜底**一行没改**，
  两个用例逐值断言（7200 → `PT1H55M`；100 → `PT1M`）。
- **并发保护**：需要澄清一句 —— 原实现**本来就没有分布式锁**，所谓「并发保护」= 「所有消费方共用
  同一个缓存槽，不各自刷新互顶失效」。本卡按 appid 分槽**只隔离不同小程序之间**，同一 appid 内仍是
  单槽共享，那层保护一点没削弱（javadoc 里已把这句话写清楚，免得后人误读成「分槽 = 拆散了共享」）。
  同一 appid 内多线程并发刷新会同时写同一把 key（后写胜出）—— 这是**改造前就存在**的性质，本卡不改变，
  也不在本卡范围内（真要消灭得上分布式锁，属另开 ticket 的事）。

### 不做（守边界）

- ❌ 不动 `WechatPayV3ClientImpl:93/:125`（= GZ-SYS-022），确认过这轮 diff 里没有它。
- ❌ 不动 `gz.pay.client-mode`（ADR-0019 §5）。
- ❌ 不动 `RedisSessionKeyStore`（key 按 openid，天然跨 appid 唯一）。
- ❌ 不给 `WxMockAccessTokenManager` 加 key 维度 —— 它返固定占位串、**根本不碰 Redis**，无槽位可争。
- ❌ 不动别人在飞的文件（022/023），一个字节都没碰。

---

## AI 自测（Tier 1A）

### 1. ★ 隔离验证：绕开并行 ticket 的在飞编译错误，单独跑本卡测试

工作区当时因 022/023 的中间态整模块编译不过（§0.6），先用「模块已编译产物 + 依赖 classpath +
`junit-platform-launcher`」直接跑，拿一个**不受他人状态影响**的确定结论：

```
$ javac -cp "target/classes:target/test-classes:$(dependency:build-classpath)" \
        -d $S/isoclasses src/test/java/.../WxAccessTokenIsolationTest.java     # EXIT=0
$ java -cp "$S/isoclasses:target/classes:...:junit-platform-launcher-1.12.2.jar" \
        IsoRunner org.dromara.gz.common.wechat.WxAccessTokenIsolationTest

[wx-token] access_token 刷新成功 clientid=mp-applet-gz-jp appid=wx77c1c88d2b0f1a2c key=wx:miniapp:access_token:wx77c1c88d2b0f1a2c ttl=6900s
[wx-token] access_token 刷新成功 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d key=wx:miniapp:access_token:wx2f8b93e09703f07d ttl=6900s
[wx-token] 获取 access_token 失败 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d errcode=40125 errmsg=invalid appsecret
[wx-token] access_token 刷新成功 clientid=mp-applet-gz-jp appid=wx77c1c88d2b0f1a2c key=wx:miniapp:access_token:wx77c1c88d2b0f1a2c ttl=60s

Test run finished after 945 ms
[         9 tests found           ]
[         9 tests successful      ]
[         0 tests failed          ]
```

日志里 `key=wx:miniapp:access_token:<各自的 appid>` 两把 key 同时出现 —— 这就是 AC 要的东西的直接证据。

### 2. ★★ 负向对照：把 key 换回改造前的固定串，同一套测试必须红

「测试全绿」本身不构成证据，得先证明这组断言**逮得住原 bug**。做法：把生产源码复制一份到 scratch、
只把那一行 `cacheKey` 换回改造前的 `"wx:miniapp:access_token"`，编译进一个优先于 `target/classes`
的目录，再跑同一套测试（**原仓源码一个字节没动**）：

```
$ sed 's|String cacheKey = ACCESS_TOKEN_CACHE_KEY_PREFIX + app.getAppid();|String cacheKey = "wx:miniapp:access_token";|' ...
$ java -cp "$S/oldclasses2:<同上>" IsoRunner org.dromara.gz.common.wechat.WxAccessTokenIsolationTest

[         1 tests successful      ]
[         8 tests failed          ]
Failures (8):
  twoRealApps_readTheirOwnCacheSlot                    => AssertionError: 本用例不应触网：缓存该命中却发起了 cgi-bin/token 刷新
  refresh_writesOnlyItsOwnSlot                         => expected: <fresh-guzi-token> but was: <null>
  forceRefresh_skipsCacheAndReplacesOnlyItsOwnSlot     => expected: <refreshed-guzi-token> but was: <stale-guzi-token>
  refresh_keepsExpirySafetyMargin                      => expected: <PT1H55M> but was: <null>
  refresh_ttlFloorsAt60Seconds                         => expected: <PT1M> but was: <null>
  noRequestContext_usesDefaultAppSlot                  => AssertionError: 本用例不应触网：...
  adminPcClientId_fallsBackToDefaultAppSlot            => AssertionError: 本用例不应触网：...
  legacyScalarConfig_stillScopesKeyByAppid             => AssertionError: 本用例不应触网：...
```

9 个里 8 个红。唯一幸存的 `refreshFailure_writesNothing` 是**设计上就与 key 无关**的那条
（断言刷新失败时一把 key 都不写），它绿是对的。

### 3. accept[1]（prompt.md 原命令 + `-Dsurefire.failIfNoSpecifiedTests=false`）✅ PASS

工作区收敛后跑集成态。**先贴带计数的版本**（去掉 `-q` 才看得见 Tests run）：

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am \
      -Dsurefire.failIfNoSpecifiedTests=false -Dtest=WxAccessTokenIsolationTest
[INFO] Running org.dromara.gz.common.wechat.WxAccessTokenIsolationTest
[INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1.348 s
[INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

**再贴 accept 的字面命令**（`-q` 下只剩被测代码自己打的日志，退出码 0 即通过）：

```
$ cd code/main/RuoYi-Vue-Plus && mvn -q test -DskipTests=false \
    -pl ruoyi-modules/ruoyi-gz-common -am -Dsurefire.failIfNoSpecifiedTests=false \
    -Dtest=WxAccessTokenIsolationTest
22:58:01 [wx-token] access_token 刷新成功 clientid=mp-applet-gz-jp appid=wx77c1c88d2b0f1a2c key=wx:miniapp:access_token:wx77c1c88d2b0f1a2c ttl=6900s
22:58:01 [wx-token] access_token 刷新成功 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d key=wx:miniapp:access_token:wx2f8b93e09703f07d ttl=6900s
22:58:01 [wx-token] 获取 access_token 失败 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d errcode=40125 errmsg=invalid appsecret
22:58:01 [wx-token] access_token 刷新成功 clientid=mp-applet-sensenran-guzi appid=wx2f8b93e09703f07d key=wx:miniapp:access_token:wx2f8b93e09703f07d ttl=6900s
22:58:01 [wx-token] access_token 刷新成功 clientid=mp-applet-gz-jp appid=wx77c1c88d2b0f1a2c key=wx:miniapp:access_token:wx77c1c88d2b0f1a2c ttl=60s

accept[1] EXIT=0     ← ✅ PASS
```

> ⚠️ 与 020 报告 §0.5 同一件事：**不加 `-Dsurefire.failIfNoSpecifiedTests=false` 这条命令跑不通**
> （`-am` 把 21 个上游模块带进 reactor，`ruoyi-common-core` 里没有这个测试 → surefire 直接判失败）。
> 022 / 023 的 accept 是同款写法，同样要加。

9 个用例覆盖：两 app 各读各槽（★ 核心）· 刷新只写自己那槽不覆盖隔壁（★ 核心）· 刷新用的是本 app
自己的 appid/secret · TTL 提前量 6900s · TTL 兜底 60s · forceRefresh 不读缓存且只换自己那槽 ·
无请求上下文落 default-client-id 的槽（`@Async`/cron）· 后台 PC clientid 落默认槽且不抛错（★ 回归）·
刷新失败一把 key 都不写 · 单值配置形态下 key 仍按那个唯一 appid 拼（向后兼容）。

### 4. accept[2]（grep 断言）✅ PASS

```
$ grep -q 'ACCESS_TOKEN_CACHE_KEY_PREFIX' code/main/.../WxRealAccessTokenManager.java \
  && ! grep -qE '"wx:miniapp:access_token"' code/main/.../WxRealAccessTokenManager.java
accept[2] EXIT=0     ← ✅ PASS

# 佐证：全后端（排除 target/ 幽灵副本）已无旧固定 key 字面量
$ grep -rn '"wx:miniapp:access_token"' ruoyi-modules ruoyi-admin/src | grep -v /target/
（0 处残留）

# 佐证：全后端只有一处构造该 key，没有第二处自己拼的
$ grep -rn "wx:miniapp:access_token" ruoyi-modules ruoyi-admin/src | grep -v /target/
.../main/.../WxRealAccessTokenManager.java:28:   * key = {@code wx:miniapp:access_token:{appid}}（javadoc）
.../main/.../WxRealAccessTokenManager.java:58:   private static final String ACCESS_TOKEN_CACHE_KEY_PREFIX = "wx:miniapp:access_token:";
.../test/.../WxAccessTokenIsolationTest.java:71-72:  期望 key 的手写字面量（契约从外部锁死，不引生产常量）

# 佐证：020 留的 TODO 已清
$ grep -rn "TODO(GZ-SYS-021)" code/main | grep -v /target/
（已清）
```

### 5. 全模块回归 —— 205/205 全绿

```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am
[INFO] Tests run: 205, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

微信相关的每个测试类逐个确认（含 020 留下的全部）：

```
Tests run: 9,  ... in WxAccessTokenIsolationTest      ← 本卡新增
Tests run: 9,  ... in WxLoginAdapterDispatchTest      ← 020
Tests run: 10, ... in WxMiniappPropertiesTest         ← 020
Tests run: 6,  ... in WxMiniappLegacyConfigTest       ← 020（真起 Spring 容器）
Tests run: 9,  ... in ProdSecretGuardTest             ← 020
Tests run: 6,  ... in WxMockLoginAdapterTest
Tests run: 4,  ... in WxLoginServiceImplTest
```

> 中途出现过一次 `Tests run: 205, Failures: 2` —— 两条**都在 023 刚创建的 `GzUserMultiAppUpsertTest`**
> （他们红→绿过程中的中间态，失败信息是 `唯一键 (app_id, openid) 冲突` / `没有一次 selectOne 是按 openid 查的`，
> 纯业务断言）。单独重跑该类已 6/6 绿，随后全模块即 205/205。已确认该类不碰 `SpringUtil`/`RedisUtils`，
> 与本卡测试里的 bootstrap 无交集 —— 不是本卡污染的。

### 6. 单测怎么做到「不连 Redis 也能验 key」（给后人抄）

`RedisUtils` 有一句 `static final RedissonClient CLIENT = SpringUtils.getBean(...)`，无 Spring 环境下
类初始化就炸，直接 `mockStatic(RedisUtils.class)` 会报
**「Cannot instrument class RedisUtils because it or one of its supertypes could not be initialized」**
（这也是本仓历史上几个 service 单测写着「RedisUtils 静态依赖 Spring，单测不便 mock，归集成测试覆盖」的原因）。

破法两行：`@BeforeAll` 里先给 hutool 的 `SpringUtil` 塞一个假 `ApplicationContext`
（`when(ctx.getBean(RedissonClient.class)).thenReturn(mock(...))`），让 `RedisUtils` 的静态初始化跑完；
之后 `mockStatic(RedisUtils.class)` 就正常了，用 `Map` 假实现同时记录读了哪些 key、写了什么值和 TTL。
`@AfterAll` 把原来的上下文还回去，避免污染同一 fork 里的其他测试类（全模块 205 个一起跑已验证无污染）。
微信 HTTP 则 `mockStatic(HttpUtil.class)`；多数用例干脆让它**一触网就抛 AssertionError**——
「本该命中缓存却去刷新了」这件事本身就是失败信号，负向对照里 8 条红有 4 条正是被它逮住的。

---

## 风险提示 / 已知 issue

1. **【部署一次性影响，无需人工干预】旧 key `wx:miniapp:access_token` 变成孤儿。**
   上线后不再有人读写它，靠自身 TTL（≤ 2h）自然消亡；想立刻回收可手动 `DEL` 一次。
   代价是部署后**每个 real 小程序的第一次调用会 miss 一次、真刷一次 token**，属正常预期。
   dev 两个 app 都是 `wxMOCK` → 走 `WxMockAccessTokenManager`（返固定串、根本不碰 Redis）→ **dev 零影响**。

2. **【GZ-SYS-020 风险 #2 已解除】** 「021 落地前不要同时配置两个 real 小程序」这条限制到此为止。
   同一环境同时跑两个 real appid 现在是安全的（就 access_token 这一项而言；支付侧仍等 022，见第 4 条）。

3. **【本卡不改、但下游要知道】同一 appid 内并发刷新没有分布式锁。**
   多线程同时 miss 会各自打一次 `cgi-bin/token` 并都写同一把 key（后写胜出）。这是**改造前就有**的性质，
   AC 说的「并发保护」指的是「共用单槽不互顶」而非锁。真要消灭需另开 ticket 上分布式锁，不属本卡范围。

4. **【仍然开着的缺口，非本卡】`@Async` / cron 的发货上报没有小程序归属。**
   `WxShippingClient.UploadCommand(transactionId, openid, logisticsType, itemDesc)` 至今不带 app 维度，
   所以异步上报只能落 `default-client-id` —— 现在 token 也跟着落默认 app 的槽。
   单小程序时代这没问题；**两个小程序都要真上报时会把 B 的订单用 A 的 token/appid 报上去**。
   彻底修法是给 `gz_pay_shipping_order` 加 app 维度、`UploadCommand` 带上归属 clientid（见「对下游提示」）。

5. **【本卡零 DDL、零配置变更】** 不需要改 yml，不需要迁移，不需要 ops 动作。

6. **环境层面的真风险见 §0.6**（三个 ticket 共用一个工作区）—— 与代码无关，但会影响主线程对
   「谁的自检绿了」的判断，也影响最终 commit 的拆分（本卡的改动与 022/023 的混在同一个 working tree 里）。

7. **待 Kevin 残留人验：N/A** —— 纯后端 ticket，无 mp 页面、无 admin 页面、无真机微信原生能力。
   真机维度的验证在 appid 回补阶段（两个 real 小程序同时在线跑一轮手机号绑定 + 发货上报）。

---

## 对下游 ticket 的提示

### 给 GZ-SYS-022（支付多 appid）

- 本卡**没碰** `WechatPayV3ClientImpl:93/:125`，也没碰 `gz.pay.client-mode` —— 该地盘干净。
- 共同依赖的 `WxAppResolver` 有两个口径，**别选错**（这是 020 用真机复现换来的教训）：
  只可能被小程序调用的 → `currentApp()`（严格）；会被 admin / `@Async` / cron 走到的 → `currentAppOrDefault()`（宽松）。
  支付回调 / 查单 / 退款都在**没有原请求 header** 的线程里，ADR-0019 §3 已经说了要从下单上下文 /
  `gz_pay_channel.appid` 取，**别图省事用 `currentAppid()`**。
- accept 命令同样要加 `-Dsurefire.failIfNoSpecifiedTests=false`（同 020 §0.5）。
- 新写的单测记得 `@Tag("dev")`，否则根 pom 的 `<groups>${profiles.active}</groups>` 会让它**根本不执行**、
  却显示为「通过」。

### 给 GZ-SYS-023（gz_user 加 app_id）

- 本卡没碰 `gz_user` / `IGzUserService` / 任何迁移文件。`GzUserMultiAppUpsertTest` 只是在全模块回归里
  路过看到过（那会儿它还是红的，现在 6/6 绿）。
- 同样两条：`@Tag("dev")` + accept 加 `-Dsurefire.failIfNoSpecifiedTests=false`。

### 给「发货上报按小程序归属」的将来那张卡（目前无人认领 ⚠️）

`gz_pay_shipping_order` 需要一个 app 维度（`app_id` 或 `client_id`），`WxShippingClient.UploadCommand`
带上它，`WxRealShippingClient` 改成按该值 `appResolver.appOf(clientId)` 取 app、
`WxAccessTokenManager` 也需要一个「按指定 app 取 token」的重载（当前接口只有 `getToken(boolean)`，
槽位隐式取自当前上下文）。**在这张卡落地前，第二个小程序不要开真发货上报。**

### 给需要在单测里验 Redis key 的任何人

抄 `WxAccessTokenIsolationTest` 的 `@BeforeAll` 两行（先 bootstrap `SpringUtil` 再 `mockStatic(RedisUtils)`）
—— 本仓此前一直认为「RedisUtils 静态依赖 Spring，单测不便 mock」，其实是可以的，见 §AI 自测 6。

---

## §AI 测试段（kevin-qa Tier 1B 完工后追加）

（占位 —— 本卡为纯后端单文件改造：admin 无页面变更、mp 无页面变更、零 DDL、零配置变更。
Tier 1B 建议范围：
① 后端集成 —— 两个 real appid 同进程下各取一次 token，`redis-cli KEYS "wx:miniapp:access_token:*"`
   应看到**两把**独立 key、值不同、TTL 各自独立；
② API 契约回归 —— 手机号绑定 `/app/gz/common/auth/*` 与后台「发货信息手动补报」
   `POST /system/gz/pay/shipping/{id}/retry` 各跑一遍（这两条是 access_token 仅有的真实消费方，
   后者是 020 §6 的回归点，务必真点）；
③ 现有 mp 模拟器 E2E 登录流回归（确认 `mp-applet-sensenran-guzi` 未受影响）。
④ ⚠️ 跑之前先确认工作区里 022/023 的改动已收敛，否则起不来后端不是本卡的问题。）

---

**accept 是 PASS。**
