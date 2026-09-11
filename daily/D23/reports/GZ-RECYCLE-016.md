# GZ-RECYCLE-016 — 完工报告

---

## §0 自检结果

| 检查项 | 结果 | 备注 |
|---|---|---|
| git clean | ❌（本 ticket 改动 + D22 尚未 commit 的改动共存于工作区） | 本报告只列本 ticket 精确改动文件（见下），不与 D22 混报 |
| 上游依赖 merge | N/A | 无依赖 |
| 关键类/表/API 存在 | ✅ | 见下方硬探命令 + 输出 |
| 编译通过 | ✅ | `mvn install` 见下 |
| 权威蓝图引用完整 | N/A（甲方 8.27 新提，非原 57 ticket 索引项，复用既有 sys_config 素材模式不新增字段表段） |  |
| ADR 已读 | 无相关（复用既有模式，非新决策） |  |
| 合同范围 | V1.0（回收预约已上线功能的附加素材） |  |

## 改了哪些文件（本 ticket 精确范围）

**后端（RuoYi-Vue-Plus）**：
```
新增  ruoyi-admin/.../db/migration/V202608271147__GZ-RECYCLE-016-service-qrcode-config.sql
新增  ruoyi-admin/.../db/migration/V202608271157__GZ-RECYCLE-016-fix-service-qrcode-config-tenant.sql
改动  ruoyi-modules/ruoyi-gz-common/.../config/MpPublicConfigKeyResolver.java      (+5 行：白名单登记)
改动  ruoyi-modules/ruoyi-gz-common/.../config/MpPublicConfigKeyResolverTest.java  (+7 行：1 个新单测)
```

**小程序（miniapp）**：
```
改动  src/api/gz-common.ts               (+19 行：GZ_CONFIG_KEYS.RECYCLE_SERVICE_QRCODE + fetchRecycleServiceQrcode)
改动  src/api/gz-common.test.ts          (+31 行：4 个新单测)
改动  src/locale/recycle.zh-CN.ts        (+2 行：serviceQrHint 文案)
改动  src/pages/recycle/form.vue         (+ref/loader/onShow 挂载/模板块/样式，约 +25 行)
```

无 admin（plus-ui）代码改动——复用 ruoyi 自带「系统管理 → 参数设置」通用页，未新建 admin 页面。

## AI 自测

### 1) 后端编译 + 单测

```
$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -am -q
MVN_EXIT=0
$ ls -la ~/.m2/.../ruoyi-gz-common-5.6.1.jar
-rw-r--r--  1 wkui  staff  873200 Aug 27 11:53 ruoyi-gz-common-5.6.1.jar   ← mtime 确认真重打

$ mvn test -DskipTests=false -pl ruoyi-modules/ruoyi-gz-common -am
[INFO] Tests run: 11, Failures: 0, Errors: 0, Skipped: 0 -- MpPublicConfigKeyResolverTest
[INFO] BUILD SUCCESS
```
（11 = 原 10 个 + 新增 `recycle_service_qrcode_has_no_variant` 1 个）

### 2) mp 单测 + typecheck + lint

```
$ pnpm test -- --run
 Test Files  47 passed (47)
      Tests  529 passed (529)      ← 原 525 + 新增 4 个 fetchRecycleServiceQrcode 用例

$ npx vue-tsc --noEmit
✅ 零 TS 错误（gz-common.ts / form.vue 均不在错误列表内）

$ npx eslint src/pages/recycle/form.vue src/api/gz-common.ts src/api/gz-common.test.ts src/locale/recycle.zh-CN.ts
✖ 4 problems（全部核实为本 ticket 改动行范围之外的既有 baseline 噪音——
  `import/first` 在 vi.mock 之后的既有 import 语句、3 处 Chinese-title it/describe
  因标题以 GET/GZ_CONFIG_KEYS/JSON 等大写拉丁字母开头触发 test/prefer-lowercase-title，
  均在 git diff 范围之外，非本次引入）
```

### 3) Flyway 迁移真跑（含一次坑 + 订正）

```
$ grep -i "V202608271147" backend.log
Migrating schema `ry-vue` to version "202608271147 - GZ-RECYCLE-016-service-qrcode-config" [out of order]
Successfully applied 1 migration to schema `ry-vue`, now at version v202608271147

$ docker exec sensenran-dev-mysql mysql ... -e "SELECT config_id, tenant_id, config_key FROM sys_config WHERE config_key='gz.recycle.serviceQrcode'"
13016001  000000  gz.recycle.serviceQrcode     ← ❌ 坑：admin 单租户 1001 会话搜不到这行

（订正）新建 V202608271157 UPDATE tenant_id='1001'，重启后端：
Migrating schema `ry-vue` to version "202608271157 - GZ-RECYCLE-016-fix-service-qrcode-config-tenant"
Successfully applied 1 migration to schema `ry-vue`, now at version v202608271157

$ docker exec sensenran-dev-mysql mysql ... -e "SELECT config_id, tenant_id, config_key FROM sys_config WHERE config_key='gz.recycle.serviceQrcode'"
13016001  1001  gz.recycle.serviceQrcode      ← ✅ 订正后
```

### 4) mp 端点真调（含白名单边界回归）

```
$ curl "http://localhost:8080/app/gz/common/config/get?key=gz.recycle.serviceQrcode" -H "clientid: mp-applet-sensenran-guzi"
{"code":200,"msg":"操作成功","data":""}                          ← 空值，符合"甲方素材未配"预期

$ curl "http://localhost:8080/app/gz/common/config/get?key=sys.user.initPassword" -H "clientid: mp-applet-sensenran-guzi"
{"code":500,"msg":"非法的配置项","data":null}                    ← 白名单边界未被本次改动放宽
```

### 5) admin 真浏览器闭环（Playwright，含发现的一处 UX 边界）

```
$ 导航 http://localhost:8090/system/config → 搜索 gz.recycle.serviceQrcode
返回行：回收预约-客服微信二维码 | gz.recycle.serviceQrcode | 否 | GZ-RECYCLE-016 ...   ← 订正后可见

$ 点「修改」→ 参数键值改为 https://oss.example.com/e2e-test-qr.png → 点「确定」
DB 回查：config_value = https://oss.example.com/e2e-test-qr.png   ← 保存成功
curl 复读：{"code":200,"data":"https://oss.example.com/e2e-test-qr.png"}   ← 正常走 service 层，缓存正确失效，立即生效

$ 尝试把值改回空串 → 点「确定」
表单校验报错：「参数键值不能为空」   ← ⚠️ 发现的 UX 边界：admin 通用表单不允许清空
（记入 ticket 卡片备忘；本次未做额外设计规避——如需要"撤回二维码"需走数据库，
  不属于甲方本次诉求，未过度设计）
```

清理：最终用真裸 SQL 把测试值改回空串 + `redis-cli FLUSHALL` + 重启后端拿干净 JVM 状态，避免裸 SQL 写入被停留在某层缓存里；重启后 curl 复核确认 `data:""`，DB 复核 `tenant_id=1001 / config_value=''`。

## 已知 issue / 风险提示

1. **admin 清空 config_value 走不通表单校验**（见上）。当前状态="设置简单、撤回需要开发介入"，甲方本次只要求"放一张图"，没提撤回场景，判断不需要为此新增额外的"隐藏"标志位（如 sentinel 值），避免过度设计。若未来甲方真提出"临时下线二维码"的需求，再补。
2. **本次改动未做 mp 模拟器 E2E**（`test/e2e/run.mjs`）——衡量是这是一个纯展示性的静态图块（`v-if` + `<image>`），没有交互逻辑分支需要 UI 层断言，backend→admin→mp 端点的完整数据链路已用 curl + 真浏览器 admin 编辑 + DB 回查三层交叉验证过，风险面已覆盖；Vue 模板部分的正确性由 vue-tsc 类型检查 + 既有框架保证（`v-if`/`:src` 均是声明式绑定，无自定义渲染逻辑）。如 Kevin 认为需要，后续可补 `flows/recycle-service-qr.mjs`。
3. **图片本体仍待甲方素材**：Kevin 微信里的截图无法被本会话工具链程序化提取为文件，需 Kevin 自己把图存下来、通过 admin「系统管理 → 文件管理」（OSS）上传拿到 URL，再到「参数设置」把这行的参数键值改成那个 URL 即可生效，不需要再发版。

## 交付前须向甲方确认

无——本 ticket 完全是 Kevin 自己微信原话的直接翻译，不涉及新的业务口径判断。
