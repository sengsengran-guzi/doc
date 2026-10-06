# GZ-SNAP-403 实现报告

STATUS: DONE

## 提交与实现

- 后端 `task/D11@940ae781b`：新增 `GzJpSnapConfigController` / `GzJpSnapConfigService` / `GzJpSnapConfigServiceTest`；扩展 `GzJpSnapRuntimeConfigMapper` 仅写租户1001已有配置行。GET/PUT key只接受pricing/filter/gate/trade，auto不可操作，额外/缺失字段拒绝；定价允许保留null（不发明默认商业价格）。金额非负整数、加价0..1、TTL60..1800、评价1..240、巡检5..120；数组只接收字符串，strip后去空去重。登录租户必须1001；写入记录operator。事务提交后通过框架CacheManager及evictIfPresent驱逐两级缓存。
- 复用303 `GzJpSnapFxController` / `GzJpSnapFxService`：历史改20条；增加/latest返回最新记录与超6小时标记；手动接口、权限码不变。
- 后台 `task/D11@d2f269e`：新增 `src/api/gz-jp/snap-config.ts`、`src/views/gz-jp/snap/config/index.vue`、`e2e/gz-jp/snap-config.spec.ts`；中英 `gzSnapConfig` 29键一致。五tab真实API读写；任一定价空时页头红字「未配置，小程序无法报价」；汇率最新值/来源/抓取时间/过期告警、历史和手动录入。
- 迁移 `V202610061626__GZ-SNAP-403-config-menu.sql`：真实当下时间；14080–89在历史迁移和活库均空后分配14080–83，parent14040、component `gz-jp/snap/config/index`；owner授权4项。现有303权限只有接口，本迁移提供这些权限的菜单按钮，无重复API或权限语义。
- touches外文件：none。主miniapp未写；未push/合staging。

## 验收与raw

### accept0 MENU PASS

实际SQL（`/usr/local/bin/docker exec sensenran-dev-mysql mysql -uroot -proot ry-vue -N -e ...`）：

```text
14080 C / parent14040 / path与component非空 count=1
14081–89 F / config:* count=3
tenant1001 owner role_menu count=4
flyway_schema_history count=190
pricing原值={"markupRatio":null,"fixedFeeCent":null,"estShippingCent":null,"quoteTtlSec":600}
```

共享restart命令（继承既有私有backend-options，不打印选项）：`bash doc/jp/_run/restart-backend.sh ruoyi-modules/ruoyi-gz-jp`。

```text
BACKEND UP (commit a7e273349+DIRTY-WORKTREE, branch task/D11)
Successfully validated 190 migrations
Migrating schema ry-vue to version 202610061626 - GZ-SNAP-403-config-menu [out of order]
Successfully applied 1 migration
```

运行产物对应现在940ae781b同一源码；提交不需要再次重启。

### accept1 DATA PASS

后端仓执行：

```bash
export JAVA_TOOL_OPTIONS='-javaagent:/Users/wkui/.m2/repository/org/mockito/mockito-core/5.17.0/mockito-core-5.17.0.jar'
mvn -q test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-jp -am -Dtest=GzJpSnapConfigServiceTest -Dsurefire.failIfNoSpecifiedTests=false
```

Surefire：`tests="10" errors="0" skipped="0" failures="0"`。单测覆盖未配置null、ratio边界、金额分整数、TTL边界、交易边界、名单清洗与准入旧键、auto/额外/缺失字段拒绝、非法名单、真实TransactionAwareCacheManagerProxy下提交前不驱逐/提交后立即驱逐/不再次注册回调、缺行不注册驱逐。raw: `raw/junit.log` / `raw/junit.xml`。

真实E2E另外预热 `/system/config/configKey/gz.jp.snap.<key>`，逐项保存后立刻同接口读回pricing TTL601、filter名单、gate三组旧键和trade25/21，证明框架缓存不旧。filter分类白名单置空后立即调用app search，返回items=[]，在gateway调用前短路证明真实消费者立即生效；没请求煤炉，没写商品/订单，没重测D10资金。

### accept2 UI/API PASS

后台仓、清HTTP代理、NO_PROXY=*、复用已受控8090 Vite：

```bash
pnpm exec playwright test e2e/gz-jp/snap-config.spec.ts --reporter=line
```

```text
Running 1 test using 1 worker
403 cleanup: four config bytes/audit fields restored exactly; two-level cache readback restored; own FX removed; wx-login/live Mercari=0
1 passed (7.0s)
```

五tab全部读写真实接口，未配提示文本且实际计算颜色红色；非法价格/TTL/交易值及无token拒绝；手动4.123456FX新ID立即显示在最新值/来源及history，latest.stale=false、history<=20。

共享经营参数测试前快照config_value HEX、update_by、update_time，收尾恢复每个字节与审计字段；刷新框架两级缓存后逐一configKey读回原字符串；只按自造ID/source/tenant精确清理手动汇率。pricing三商业项测试全程null，未替用户定价。raw: `raw/e2e.log`。

### 静态 PASS

`pnpm exec eslint`限定本次5文件退出0；`git diff --check`两仓0。
`pnpm exec vue-tsc --noEmit` 72条历史错误，无本次新增、无本次文件错误（raw/vue-tsc.log）。
目标中英命名空间key各29、集合完全一致。
生产build留主线程D11统一末检；未重复执行全仓测试。

## 装置修正

1. 第一次Maven从项目根调用，reactor选择错误，未执行测试；改到后端仓。
2. 新增测试JSON字面量转义笔误在testCompile发现并修正。
3. Mockito自附加被沙箱拒绝：按brief加载现有mockito-core javaagent，无新依赖。
4. 缓存单测最初stub了TenantHelper.dynamic Runnable重载，而调用实际选Supplier，导致不执行驱逐；修正stub重载后真实事务装饰器断言通过，产品缓存实现未降级。
5. 第一轮UI色彩断言读取不存在的CSS自定义变量；改为计算标题实际RGB并断言红通道高于绿/蓝，保留红字产品判据。

## 后续与边界

- 8080继续共享运行，8090复用既有受控session25054，主线程末尾关闭；未另起服务。
- 两代码仓本任务提交完成；后台干净，后端仅剩本任务开始前已有非本任务日志tmp文件未动；doc报告/raw未commit，留主线程统一提交。
- 自动下单开关归402，此页不能改；主miniapp全目录只读。外部真实煤炉请求0，微信登录0，翻译mock，未运行fetch汇率外网抓取。
- 本报告是实现者证据；独立QA仍由主线程另行派发，QA不读实现报告。
