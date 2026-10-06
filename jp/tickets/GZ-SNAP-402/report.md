# GZ-SNAP-402 实施报告

STATUS: DONE
COMMITS: RuoYi-Vue-Plus@a7e273349; plus-ui@c831c06
MIGRATION: V202610061613__GZ-SNAP-402-account-menu.sql
OUT_OF_TOUCHES: none

## 结果

采购账号列表/新增/编辑、adminEnabled启停、解除暂停，以及总开关读/手动恢复/暂停均已接入真实后端。账号编码新增后不可编辑，DTO不接受健康写入与凭据字段；编辑SQL只改nickname/dailyLimit/cooldownSec，启停只改adminEnabled，不盲写心跳健康/计数。创建默认停用且不可达，须日本服务心跳后才可用。今日计数按Asia/Tokyo日期展示，旧日期展示0而不修改执行器计数。

恢复须confirmed=true，所有账号无challenge，且至少一个healthy+adminEnabled+无pauseReason账号。恢复只写sys_config，不改变manual队列。解除暂停需要页面二次确认且不修改健康；暂停复用GzJpSnapRiskControl.pause(null,reason)，其queued→manual_pending出口保持不变。资金出口306/307未改。

菜单14060 path=account/component=gz-jp/snap/account/index、父级14040；按钮14061/62/63对应query/edit/switch，owner授权。401顶部真实跳Account14060已E2E证明。页面全部新增可见固定文本走gzSnapAccount，中英各39key精确相同。

## 文件（按仓）

后端（8个）：
- ruoyi-admin/src/main/resources/db/migration/V202610061613__GZ-SNAP-402-account-menu.sql
- ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/controller/GzJpSnapAccountController.java
- ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/service/internal/GzJpSnapAccountAdminService.java
- ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/mapper/GzJpSnapAccountMapper.java
- ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/mapper/GzJpSnapRuntimeConfigMapper.java
- ruoyi-modules/ruoyi-gz-jp/src/main/java/org/dromara/gz/jp/snap/gateway/GzJpSnapRiskControl.java
- ruoyi-modules/ruoyi-gz-jp/src/test/java/org/dromara/gz/jp/service/internal/GzJpSnapAutoSwitchTest.java
- ruoyi-modules/ruoyi-gz-jp/src/test/java/org/dromara/gz/jp/job/GzJpSnapHealthJobTest.java

后台（5个）：
- src/views/gz-jp/snap/account/index.vue
- src/api/gz-jp/snap-account.ts
- src/lang/zh_CN.ts
- src/lang/en_US.ts
- e2e/gz-jp/snap-account.spec.ts

## 定向验证（raw在本目录raw/）

accept #0 PASS：/usr/local/bin/docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e SELECT...；menu.log实数1（C父级/非空path/component）、3（F账号权限）、4（owner role_menu）、0（自有测试账号剩余）。菜单分配前查活库和所有既有迁移：14060–69均空。

accept #1 PASS：
```bash
export PATH=/opt/homebrew/bin:$PATH
export JAVA_TOOL_OPTIONS=-javaagent:/Users/wkui/.m2/repository/org/mockito/mockito-core/5.17.0/mockito-core-5.17.0.jar
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapAutoSwitchTest,GzJpSnapHealthJobTest -Dsurefire.failIfNoSpecifiedTests=false
```
实际AutoSwitch11 tests/failures0/errors0/skipped0，Health8 tests/failures0/errors0/skipped0，共19/19。所有新增JUnit含@Tag(dev)。恢复无确认、空池、disabled健康、paused健康、challenge（含停用challenge）、logged_out均拒；healthy恢复仅改config；Tokyo当前/旧日期和字段独立写验证通过。Health共享risk暂停依然调用pauseQueued，事务感知缓存回归通过。

accept #2 PASS：
```bash
export PATH=/Users/wkui/.nvm/versions/node/v24.11.1/bin:/opt/homebrew/bin:$PATH
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY='*'
pnpm exec playwright test e2e/gz-jp/snap-account.spec.ts --reporter=line
```
真实8080+MySQL+8090，Chrome/workers1/data-test，1 passed (14.0s)。页面新增编辑/编码不可改/启停，dailyLimit7+cooldown25真库写回；昨日todayCount6页面0/7，Tokyo今日显示6/7；无启用健康、paused、challenge、confirmed=false恢复均拒；解除暂停和恢复二次确认、取消不恢复、恢复只写当天运行开关，手动暂停显示新原因；anonymous接口拒绝。暖缓存经/system/config/configKey/gz.jp.snap.auto真实false→true→false，覆盖Caffeine与Redis驱逐。

测试仅admin/owner登录，不调用wx-login，未写id14，未创建订单/资金夹具，不动主miniapp。所有账号状态事前快照并逐项恢复、config原值字节一致、自有snap402_e2e账号准确删除；E2E cleanup断言通过。真实煤炉请求0。

静态：限定5个后台文件eslint exit0；vue-tsc既有72→72、账号文件无新增；gzSnapAccount中英39=39；两个仓git diff --check通过。prod build按D11主线程授权留统一末检。共享脚本clean install/restart后189 migrations validated，新菜单迁移仅初次应用1条。

## 本轮发现与修复

补warm-cache断言发现DB已恢复enabled=true但缓存依旧false（cache-before-fix-failure.log留痕）。原riskControl与新resume在afterCommit中调用cache.evict；框架TransactionAwareCacheDecorator仍处同步期，evict又注册afterCommit，已错过当前回调列表，驱逐不发生。两处改用evictIfPresent，保留提交后执行避免旧数据回填，框架Caffeine装饰器与Redis立即失效。仅修gz-jp内两处；查其它afterCommit无其它cache.evict同坑，未改框架。Health原测试从裸ConcurrentMapCacheManager升级TransactionAwareCacheManagerProxy，保留事务前缓存和提交后不存在的断言。

普通装置问题自主解决：首次Mockito自动attach受沙箱限制，改用既有javaagent（不新增依赖）；共享restart首次短模块名不识别，改完整ruoyi-modules/ruoyi-gz-jp；vue-tsc缺useI18n显式导入已修；新evictIfPresent返回boolean使TenantHelper.dynamic选Supplier重载，Health静态mock补Supplier执行，不改框架。字段长度按已建表code32/nickname64校准。

## 下游与运行资源

- 8090为本轮唯一受控服务session25054，日志/tmp/snap402-vite.log，交主线程后续复用及最终关闭。
- 8080共享launchd正常，默认dev调度false、gateway8700，189迁移；未额外起后端。
- 403继续相同菜单目录，不复用14060–63。新配置写入应提交后即时evictIfPresent，避免afterCommit内再次defer。
- 代码双仓已仅提交自身路径，后端剩余无关未追踪日志ruoyi-admin/logs/sys-error.2026-10-01.log180801896327291.tmp未动，plus-ui干净。doc报告/raw未commit，交主线程。
- 真实平台采购、真登录态/资金实测不在本ticket范围；本ticket通过无外网账号页及相关权限/开关验证，不重复D10资金故障回归。
