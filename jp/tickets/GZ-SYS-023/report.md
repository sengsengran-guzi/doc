# GZ-SYS-023 gz_user 加 app_id 维度 — 完工报告

> **结论：accept 三条全 PASS**（DDL ✅ / DATA ✅ / STATE ✅）。除单测外还做了**真 DB 唯一键探针** + **真 HTTP 两个 clientid 登录** + **单测变异验证**。
> ⚠️ 有一条 **dev 存量数据副作用**必须先看：风险 §1（prod 不受影响）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git 状态（RuoYi-Vue-Plus，`staging`，HEAD `0e5d2bf7c`） | ✅ 工作区含 GZ-SYS-020/022 未提交改动（并行卡），本卡未 commit |
| 找到原始建表迁移 + 唯一键现状 | ✅ `V202605281000__GZ-SYS-003-create-gz_user.sql:55` `UNIQUE KEY uk_tenant_openid (tenant_id, openid)` |
| Flyway append-only 铁律（CLAUDE.md §5/§6 #5） | ✅ 新建文件，**未改/未删/未复用**任何已应用迁移 |
| 迁移目录 git 状态（只许 `A`） | ✅ 开工前空输出，完工后只多 `??` 新文件 |
| 时间戳取当下真实时间 | ✅ `date +V%Y%m%d%H%M` → `V202608062251`（> 当时最大 `V202607272121`） |
| 编译健康 | ✅ 改动前后 `mvn -o clean install -DskipTests` 全 34 模块 SUCCESS |
| ADR 已读 | ✅ ADR-0019 §4 +「被否决的方案：unionid 合并」+「影响面」末行 |
| 蓝图引用 | ✅ `FLOW:F-JP-00.step3`（flows.yaml:183-189）+ `FIELD:gz_user.app_id`（field-ssot.yaml:144-152） |

```
$ grep -rn "uk_tenant_openid" ruoyi-admin/src/main/resources/db/migration/
V202605281000__GZ-SYS-003-create-gz_user.sql:55:    UNIQUE KEY uk_tenant_openid  (tenant_id, openid),
$ git status --short -- ruoyi-admin/src/main/resources/db/migration/
（空 —— append-only 未被破坏）
$ date +V%Y%m%d%H%M
V202608062251
```

**蓝图关键约束摘录**：唯一键 `(tenant_id, app_id, openid)`、同一自然人两小程序 = 两条独立记录、不做 unionid 合并；`app_id str(32) NOT NULL default wx2f8b93e09703f07d`；ADR-0019「影响面」要求**回填与约束在同一迁移里有序完成** + 回填后核对总行数 == 去重行数。

> ⚠️ **蓝图编号与任务卡不一致（按任务卡走）**：`field-ssot.yaml:148` 把迁移写成 `GZ-SYS-024-...`，本卡 id 是 **023**。CLAUDE.md §6 #5 要求文件名带本 ticket id，故用 023。建议顺手把 field-ssot 那行改掉，否则按文件名反查 ticket 会扑空。

## 实现摘要

```
 application-dev.yml                       (+5)   JP app 加 register-source
 application-prod.yml                      (+4)   apps 形态注释补 register-source
 domain/entity/GzUser.java                 (+13)  appId 字段
 service/IGzUserService.java               (+21)  upsertByOpenid 新签名 + 契约说明
 service/impl/GzUserServiceImpl.java       (+27)  查询条件带 app_id / 落 appId + registerSource
 service/impl/WxLoginServiceImpl.java      (+6)   解析一次 app 传下去
 wechat/WxMiniappProperties.java           (+25)  register-source（全局默认 + 按 app 覆盖）
 test/.../GzUserServiceImplTest.java       (+9)   适配 + 断言 app_id 落库
 test/.../WxLoginServiceImplTest.java      (+13)  适配 + 断言传的是解析出的 app
新增：
 db/migration/V202608062251__GZ-SYS-023-alter-gz_user-add-app_id.sql   42 行
 test/.../GzUserMultiAppUpsertTest.java                               253 行（accept[STATE]，6 用例）
```
（`git diff --stat` 数字更大是因为 GZ-SYS-020/022 也还没 commit；上表是本卡净增量。）

**§1 迁移 —— 一条 ALTER 干三件事**
```sql
ALTER TABLE gz_user
    ADD COLUMN app_id VARCHAR(32) NOT NULL DEFAULT 'wx2f8b93e09703f07d' ... AFTER openid,
    DROP INDEX uk_tenant_openid,
    ADD UNIQUE KEY uk_tenant_app_openid (tenant_id, app_id, openid);
```
- 存量回填**不写 UPDATE**：`NOT NULL DEFAULT` 在 ADD COLUMN 当下即回填，天然满足「回填先于唯一键」。
- 三步必须同一条 ALTER：MySQL DDL 无事务，拆开中途失败会留下「列加了但唯一键没换」的半截状态。
- 脏数据守卫不另写校验 SQL：建 UNIQUE 本身就是那道闸（有重复即 1062，迁移失败、应用起不来）。
- DEFAULT 永久保留（field-ssot 明写）：兜住不经登录链路的写入点（gz-bean 代客「线下散客」占位用户），已实测。

**§2 `upsertByOpenid` 新签名（★ 与任务卡字面不同）**
```java
GzUser upsertByOpenid(WxJscode2SessionResult session, String nickname, String avatarUrl, MiniappApp app);
//  MiniappApp = org.dromara.gz.common.wechat.WxMiniappProperties.MiniappApp
//  调用：WxLoginServiceImpl → MiniappApp app = appResolver.currentApp();  （严格口径）
//  查询：.eq(GzUser::getAppId, appId).eq(GzUser::getOpenid, openid)   ← 漏第一行 = 跨小程序串户
```
任务卡写「签名加 appId」，实际传整个 `app`：写库需要该小程序**两个**属性 —— `appid`（落 `app_id`）与 `registerSource`（落 `register_source`）。只传 appid 字符串的话 service 得反查配置，而 **dev 两个小程序 appid 都是 `wxMOCK`**，按 appid 反查必然解析错来源。传 app 对象后全链路只解析一次、无反查歧义、service 不用注入配置，也比「两个相邻 String 参数」更不容易传反。新增前置校验：app/appid 为空 → `IllegalArgumentException`，**不静默回落默认小程序**（回落 = 把 B 的用户写进 A 的命名空间）。其余行为逐字未变。

**§3 `REGISTER_SOURCE` 常量 → 按小程序取值**：常量降级为 `REGISTER_SOURCE_FALLBACK`（只兜底不写空），真值来自新配置 `wx.miniapp[.apps.<clientid>].register-source` —— 谷子宇宙 `mp_wechat`（不配即继承全局默认 = 历史值，**存量与线上零变化**）/ 拼团 `mp_wechat_jp`（dev yml 已配，prod 注释已补）/ 代客占位 `admin`（gz-bean 原有，未动）。**为什么还需要它**：`app_id` 只在两个 appid 真不同时才能分来源，dev 都是 `wxMOCK` 时 `register_source` 是唯一能分辨来源的列，且 admin 本来就显示它。启动日志加了这一维。

**不做**：不动 `WechatPayV3ClientImpl:93/:125`（022 范围）/ 不做 unionid 合并 / 不给 `GzUserVO` 加 appId（admin 靠 register_source 已能分来源，加了要连带改 plus-ui 类型 + i18n）/ 不动 gz-bean 写入点（DEFAULT 已兜住）。

## AI 自测（Tier 1A）

**1. accept[1] DDL ✅**
```
$ ... column_name='app_id'            → 1
$ ... index_name='uk_tenant_app_openid' → tenant_id,app_id,openid
任务卡原样 && 串联命令：accept[1] EXIT=0
$ ... index_name='uk_tenant_openid'   → （空，旧键已 DROP）
app_id  varchar(32)  NO  wx2f8b93e09703f07d  所属小程序 appid（…）；存量行 = 谷子宇宙小程序
```
迁移是**真由 Flyway 跑进 dev 库**（非手工 SQL）：
```
 - Migrating schema `ry-vue` to version "202608062251 - GZ-SYS-023-alter-gz user-add-app id" [out of order]
 - Successfully applied 2 migrations to schema `ry-vue`, now at version v202608062251
(♥◠‿◠)ﾉﾞ  RuoYi-Vue-Plus启动成功
```
（另一条是并行卡 GZ-SYS-022 的 `V202608062249`，同次启动一起补跑；out-of-order 属 CLAUDE.md §5 已开的正常路径。）

**2. accept[2] DATA ✅**
```
accept[2] EXIT=0
app_id                register_source  cnt
wx2f8b93e09703f07d    mp_wechat        10
wx2f8b93e09703f07d    admin             1     ← gz-bean 线下散客占位用户
```

**3. ADR-0019 §4 去重核对 ✅**　`total_rows 11 / distinct_keys 11` —— 一致，存量无脏数据。

**4. accept[3] STATE ✅** —— 先跑字面命令（炸在 `ruoyi-common-core`：`No tests matching pattern ... (Set -Dsurefire.failIfNoSpecifiedTests=false)`，与本卡代码无关，同 GZ-SYS-020 §0.5），修正命令：
```
$ mvn -o test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am \
      -Dsurefire.failIfNoSpecifiedTests=false -Dtest=GzUserMultiAppUpsertTest
EXIT=0    [INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0    BUILD SUCCESS
[gz-user] INSERT id=1001 appId=wx2f8b93e09703f07d openid=o-collision-same-person registerSource=mp_wechat
[gz-user] INSERT id=1002 appId=wxJP0000000000jp   openid=o-collision-same-person registerSource=mp_wechat_jp
```
**★ 变异验证（证明测试不是恒绿）**：临时删掉实现里 `.eq(GzUser::getAppId, appId)` 再跑 →
```
[ERROR] sameOpenid_twoApps_createsTwoIndependentRows:174 同 openid 不同 app 必须是两条独立记录（1 条 = 串户） ==> expected: <2> but was: <1>
[ERROR] upsertQuery_constrainsBothAppIdAndOpenid:214 UPSERT 查询条件必须含 app_id，实际：(openid = #{ew.paramNameValuePairs.MPGENVAL1})
BUILD FAILURE   → 已还原
```
做法：按 `(app_id, openid)` 索引的**内存假表**顶替 mapper，wrapper 无 app_id 约束时退化成「只按 openid 查」→ 命中另一小程序的行，串户被断言逮住。踩坑：MP wrapper 参数**懒物化**，`eq()` 只存 `ISqlSegment` lambda，`getParamNameValuePairs()` 必须先调一次 `getSqlSegment()` 才有值；后者要 `@BeforeAll` 手动 `TableInfoHelper.initTableInfo(...)` 才能把 `GzUser::getAppId` 解析成列名。

**5. ★ 真 DB 唯一键探针（单测照不出唯一键建对没）**
```
同 openid + 不同 app_id → rows_kept 2                    ✅ 可共存
同 openid + 同 app_id   → ERROR 1062 Duplicate entry '1001-wxPROBE_AAA-o-uk-probe' for key 'gz_user.uk_tenant_app_openid'   ✅
探针行已硬删（probe_left 0）
不带 app_id 的 INSERT   → app_id=wx2f8b93e09703f07d      ✅ DEFAULT 兜住 gz-bean 代客路径
```

**6. 真 HTTP 端到端**
```
clientid: mp-applet-sensenran-guzi → {"code":200,"userId":"13","openid":"mock-dev-tester"}
clientid: mp-applet-gz-jp          → {"code":200,"userId":"14","openid":"mock-jp-tester"}
[gz-user] INSERT id=14 appId=wxMOCK openid=mock-jp-tester  registerSource=mp_wechat_jp
[gz-user] INSERT id=13 appId=wxMOCK openid=mock-dev-tester registerSource=mp_wechat
admin GET /system/gz/user/list → code=200 total=13
  [{'id':14,'openid':'mock-jp-tester','registerSource':'mp_wechat_jp'}, {'id':13,...,'mp_wechat'}, ...]
admin GET /system/gz/user/13   → 200
mp    GET /app/gz/common/me    → 200（VO 映射正常）
```

**7. 全模块回归 + 全仓编译**
```
mvn -o test ... -pl ruoyi-gz-common -am   → Tests run: 205, Failures: 0, Errors: 0   BUILD SUCCESS
mvn -o clean install -DskipTests          → gz-common/coupon/bean/user/news/gacha/ord/recycle/admin 全 SUCCESS
```
后台进程已收尾：8080 无监听、`pgrep -f ruoyi-admin.jar` 无残留。

## 风险提示

**1. ⚠️【dev 数据，需知会 Kevin】dev 存量 mock 用户被「换号」—— prod 不受影响**
dev 里 `mock-dev-tester` 登录后 **userId 11 → 13**、`mock-jp-tester` **12 → 14**，老行还在但不再被命中。根因：迁移回填的是**现小程序 prod appid**（ADR/field-ssot 指定，prod 正确），而 **dev 跑 mock 哨兵 `wxMOCK`** → 查不到存量行 → 建新行。prod 存量 app_id == prod 运行时 appid，**登录行为零变化**。影响：Kevin dev 里挂在 user 11 的拼豆/券测试数据在 mp「我的」看不到了；不影响 Tier 1B（e2e flows 未硬编码 userId，已 grep 确认，mock 用户自愈重建）。
**未替 Kevin 改这批数据**（是 Kevin 的 dev 数据 + 语义选择，且会让 accept[2] 的「DEFAULT 回填」证据失真）。要接回旧数据，**只在 dev** 跑：
```sql
DELETE FROM gz_user WHERE app_id='wxMOCK' AND openid IN ('mock-dev-tester','mock-jp-tester');
UPDATE gz_user SET app_id='wxMOCK' WHERE app_id='wx2f8b93e09703f07d';
```

**2.【口径】登录链路必须用严格 `currentApp()`**，不许 `currentAppOrDefault()` —— 宽松回落会把 B 小程序用户写进 A 的命名空间，DB 层再看不出是错的。

**3.【已知边界，暂不修】gz-bean 代客预定按手机号找用户是跨小程序的**：`resolveProxyBookingUserId` 的 `.eq(GzUser::getMobile, mobile).last("LIMIT 1")` 不带 app_id。拼团有真实用户后，同一手机号可能把代客单挂到拼团那条 gz_user 上（顾客在谷子宇宙 mp 看不到该单）。当前无现实风险（拼豆是谷子宇宙独有 + 拼团无真实用户），不在 touches 内。修法 = 补 `.eq(GzUser::getAppId, <拼豆所属小程序 appid>)`，留给拼团上线 checklist。同方法里 openid 占位用户查询不受影响（全库仅一条）。

**4.【本卡不管】** deploy compose 仍没透传 `WX_JP_MA_*`（SYS-020 已记）；新小程序**必须**配自己的 `register-source`。

**5. 待 Kevin 残留人验：N/A** —— 纯后端 + DDL，无页面变更、不碰真机微信原生能力。

## 对下游的提示

**迁移文件名**：`ruoyi-admin/src/main/resources/db/migration/V202608062251__GZ-SYS-023-alter-gz_user-add-app_id.sql`（dev 库已真跑，`flyway_schema_history` 现最高版本 `v202608062251`）。**不要改/不要复用这个版本号**。

**给 GZ-JP-002 —— `upsertByOpenid` 新签名**：
```java
GzUser upsertByOpenid(WxJscode2SessionResult session, String nickname, String avatarUrl, MiniappApp app);
// MiniappApp = org.dromara.gz.common.wechat.WxMiniappProperties.MiniappApp
// 取法：WxAppResolver#currentApp()   ★ 不是 currentAppid()，也别用 currentAppOrDefault()
```
- 与 GZ-SYS-020 报告那句「直接传 `currentAppid()`」**不同**（理由见 §2）；已按 String 写的改成 `currentApp()` 即可。
- **多数情况根本不用调它**：拼团 mp 登录复用现成 `POST /app/gz/common/auth/wx-login`，app 维度已在里面处理好。
- 后端已认 `clientid: mp-applet-gz-jp`，dev 恒 mock、固定 openid `mock-jp-tester`、register_source 落 `mp_wechat_jp`（本卡实测）。
- **dev 目前验不出「两小程序各自独立用户」**（两个 app 都是 `wxMOCK`，app_id 相同、只是 openid 不同）。真隔离要等 `WX_JP_MA_APPID` 注入；本卡隔离性证据来自真 DB 唯一键探针 + 单测变异验证，不依赖那两条 mock 用户。

**给所有新增「按 openid 查 gz_user」的代码**：必须带 app_id。按 id/mobile/nickname 查的（admin 列表、券筛选、订单回填）不受影响 —— 那些本就是跨小程序的运营视角。

**顺手改的权威 doc（CLAUDE.md §9.5 #1 先改源头）**：`doc/11-字段权威表.md` §2.1 新增 `app_id` 行、`openid` UNIQUE 改三元组、`register_source` 改成按小程序区分的真实口径。

## §AI 测试段（kevin-qa Tier 1B 完工后追加）
（占位 —— 纯后端 + DDL。建议范围：① 后端集成 `wx-login` 两 clientid 各一轮 + 未登记 clientid 仍拒绝；② 契约回归 `/system/gz/user/list` + `/{id}` + `/app/gz/common/me`；③ mp 模拟器 E2E 登录流回归（注意 dev mock 用户 userId 已变，见风险 §1）；④ gz-bean 代客建单一轮 —— 唯一不经登录链路写 gz_user 的路径。）

---

**Tier 1A 全 ✅，待 Tier 1B（主线程派 kevin-qa）。未 commit。**
