# GZ-BEAN-010 完工报告 — mp 拼豆首页（C 端入口落地页）

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（本项目当前非 git repo，主线程指令跳过 git 步骤） |
| 上游依赖 GZ-BEAN-003 merge | ✅ 占位页 + select 页已在（D04） |
| 关键类/表存在 | ✅ `ConfigService`（ruoyi-common-core SPI）/ `sys_config` 表 / `useAuth`(@/hooks) / `useNavGuard` / Biz 组件齐全 |
| 编译通过 | ✅ 后端 `mvn compile` 无错 + `mvn install` exit=0 / mp `build:mp-weixin` 产物生成 |
| ADR 已读 | 无相关（ticket 关联 ADR 为 —；ADR-005 未登录守卫机制经 useNavGuard 复用，未新增 ADR） |
| Tier2-entry-temp 清理 | ✅ grep 全 mp 无残留（本 ticket 是指定清理者） |

### §0 关键对账修正（卡里过时假设 → 真实状态）

- **AC 1「修改 pages.json tabBar」无需做**：`pages/bean/index` 已在 pages 列表 + tabBar pagePath 已指向（GZ-ADMIN-005 已配）。仅重写 index.vue 内容。
- **后端读 sys_config 方案修正**：卡里说"复用 ISysConfigService" —— 但 `ISysConfigService` 在 ruoyi-system 模块，**gz-common pom 不依赖 ruoyi-system**，无法注入。改用 ruoyi-common-core 的 **`ConfigService` 跨模块 SPI**（`SysConfigServiceImpl implements ISysConfigService, ConfigService`，gz-common 已依赖 common-core）。`getConfigValue(key)` 等价。
- **不走 ruoyi 自带 `/system/config/configKey/{key}`**：该端点要 admin 登录态，给它加 @SaIgnore 会污染 ruoyi 自带源码（铁律 #1）。新建 `/app/gz/common/config` + @SaIgnore 薄包装，满足 AC 6 匿名可读。

## 实现摘要

改动 / 新增文件：
```
后端（gz-common）:
  A  ruoyi-modules/ruoyi-gz-common/.../controller/applet/GzConfigMpController.java   （新建，@SaIgnore 公开 sys_config 读取）
  A  ruoyi-admin/src/main/resources/db/migration/V202606020020__GZ-BEAN-010-default-banner-config.sql （新建，INSERT sys_config gz.bean.home.banner）

mp 端:
  M  miniapp/src/pages/bean/index.vue        （占位页 → 正式落地页；删 Tier2-entry-temp + goSelect 临时入口）
  A  miniapp/src/api/gz-common.ts            （新建，getSysConfig + fetchBeanHomeBanner 兜底）
  M  miniapp/src/locale/bean.zh-CN.ts        （beanEntryZhCN 临时文案 → beanHomeZhCN 落地页文案）
```

落地页结构（自上而下）：报头 masthead → 顶部 banner（sys_config 拉取，无素材降级占位图 + MOCK 水印 + 默认文案）→ 主 CTA「立即预约」朱红 BizButton size=lg block → 次级「我的预约」弱按钮卡 → 规则说明卡片（3 条 i18n 文案）→ 客服浮层。

白名单机制最终方案：**`@SaIgnore` 注解**（与同目录 `WxLoginController` 同款），不动 `application.yml` 的 `security.excludes`，不动 ruoyi 自带 SysConfigController。`/app/` 前缀 + `@SaIgnore` 即放行未登录访问。

## AI 自测（Tier 1A）

### 后端编译 + install
```
$ mvn compile -pl ruoyi-modules/ruoyi-gz-common -am -q
（无错误输出 — BUILD SUCCESS）

$ mvn install -DskipTests -pl ruoyi-modules/ruoyi-gz-common -am -q
=== install exit=0 ===
-rw-r--r-- ... ruoyi-gz-common-5.6.1.jar   （15:42 更新，新 controller 进 jar）
```

### mp typecheck（我的文件干净；2 个既有错误不在本 ticket 文件）
```
$ pnpm type-check  (vue-tsc --noEmit)
src/components/biz/BizCustomerServiceFab.vue(92,5): error TS2322  ← GZ-SYS-004 既有，非本 ticket
src/pages/login/index.vue(35,50): error TS2339                    ← GZ-SYS-002 既有，非本 ticket
（pages/bean/index.vue / api/gz-common.ts / locale/bean.zh-CN.ts 均无 error）
```

### mp 构建产物（dist/build/mp-weixin）
```
$ pnpm build:mp-weixin  → dist/build/mp-weixin/pages/bean/
  index.js   2758B   index.wxml 3977B   index.wxss 3060B   （落地页产出）

# wxml 结构 grep:
  11 banner    2 cta    5 myboo    13 rules
# index.js 引用 grep:
  1 bean/my-list   1 bean/select   1 ensureLoggedIn   1 fetchBeanHomeBanner
# 新文案落点:
  locale/bean.zh-CN.js + api/gz-common.js 含「成都拼豆店开张啦」「到店前可随时取消」
# 旧临时文案清除验证:
  grep「体验选座流程」「进入选座」全 dist → 无结果（已彻底清除）
```

### curl 烟雾测试（待后端启动后跑 — 本机后端当前未运行 :8080 空）
后端编译期已保证 controller 注册；运行期验证命令（Kevin 起 `mvn spring-boot:run -pl ruoyi-admin` 后执行）：
```bash
# DDL 先跑（Flyway 未接入，手工导入 — 与 GZ-SYS-004 同款流程）:
mysql -uroot -p<pwd> -h127.0.0.1 -P3306 ry-vue \
  < ruoyi-admin/src/main/resources/db/migration/V202606020020__GZ-BEAN-010-default-banner-config.sql

# 公开端点未带 token 应返 200 + JSON 串:
curl -s 'http://localhost:8080/app/gz/common/config/get?key=gz.bean.home.banner'
# 期望: {"code":200,"msg":"操作成功","data":"{\"imageUrl\":\"\",\"title\":\"成都拼豆店开张啦\",\"link\":\"\"}"}

# 不存在的 key 应返 200 + 空串(不报错):
curl -s 'http://localhost:8080/app/gz/common/config/get?key=gz.not.exist'
# 期望: {"code":200,"msg":"操作成功","data":""}
```

## 风险提示 / 已知 issue

- **R1（DDL 未自动跑）**：本项目 Flyway 尚未接入，DDL 需手工导入（与既往 V*.sql 一致）。Kevin testing 前需跑上面 mysql 导入命令，否则 banner 端点返空串 → mp 走默认文案兜底（不报错，但不是 DDL 配的值）。
- **R2（甲方运营素材未到位）**：banner imageUrl 默认空 → mp 降级占位图（彩纸 tint + MOCK 水印 + 🧩 emoji + 默认文案）。素材到位后 admin 改 sys_config 一行即生效，零代码变更。
- **R3（my-list 路由同日 BEAN-006 建）**：「我的预约」navigateTo `/pages/bean/my-list`，该路由本日晚些由 BEAN-006 注册到 pages.json。BEAN-006 merge 前点该入口会 navigateTo fail（toast 网络错误）。我**未动 pages.json**（避免与 BEAN-006 并行注册冲突）。
- **后端 2 个既有 typecheck 错误**（BizCustomerServiceFab / login）非本 ticket 引入，不阻塞本 ticket 产物构建。

## 待 Kevin 批量人验关注（mp 端）

- 拼豆 tab 落地页 happy path（已登录）：tab 切「拼豆」→ 看到 banner 占位 + 主 CTA →「立即预约」跳选座页。
- AC 6 未登录：useNavGuard 在 onShow 拦截弹「登录后才能预约拼豆」（GZ-ADMIN-005 已定守卫）；点 CTA 也走 ensureLoggedIn 二次兜底。
- banner 占位图视觉（C 设计系统遵循度：粗墨边 + 网点 + MOCK 水印）。
- 规则卡 3 条文案语感。

## 对下游 ticket 的提示

- **GZ-BEAN-006（我的预约列表，同日）**：① 需在 pages.json 注册 `pages/bean/my-list` 路由（本 ticket 未动 pages.json）；② 本落地页「我的预约」入口已 navigateTo `/pages/bean/my-list`，BEAN-006 建好即天然可达，无需再加入口。
- **运营/admin 侧**：banner 配置 key = `gz.bean.home.banner`，value 是 JSON `{imageUrl,title,link}`。若后续做 admin banner 配置页，复用该 key。
- **其它需匿名读 sys_config 的 mp 落地页**：直接复用 `GET /app/gz/common/config/get?key=` + mp `getSysConfig(key)`，已是通用公开端点。

## §AI 测试段（Tier 1B）

> 说明：本 ticket **无 admin 端**（纯后端公开端点 + mp 落地页），故无 Playwright admin E2E。
> Tier 1B 的 mp vitest unit + API 契约回归 + 可达性检查由 kevin-coder 代行（当前会话工具集无独立 spawn kevin-qa 能力）。
> 真机 wx 原生调用（守卫弹窗 / getUserProfile / 真机渲染）按规约跳给 Kevin 批量人验。

### vitest unit（新 banner 兜底链路 + API 契约回归）
```
$ pnpm test src/api/gz-common.test.ts src/api/gz-bean.test.ts src/api/customer-service.test.ts

 ✓ src/api/gz-common.test.ts (7 tests) 6ms
 ✓ src/api/customer-service.test.ts (3 tests) 7ms
 ✓ src/api/gz-bean.test.ts (12 tests) 3ms

 Test Files  3 passed (3)
      Tests  22 passed (22)
```
（gz-common.test.ts 新增 7 用例覆盖：query 透传 / 正常 JSON 解析 / 空串兜底 / 非法 JSON 兜底 / 缺字段独立兜底 / http 抛错兜底 / BEAN_HOME_BANNER 常量 key。stderr 的 Error 是用例**故意触发**的兜底路径 console.warn，非失败。）

### API 契约回归（既有 mp api 测试无破坏）
```
$ pnpm test src/api/gz-bean.test.ts
 ✓ src/api/gz-bean.test.ts (12 tests) 3ms
 Test Files  1 passed (1)
      Tests  12 passed (12)
```

### Tier 2 可达性检查（CLAUDE.md §8.3）
```
$ grep -rn "Tier2-entry-temp|bean.entry|tempEntry|goSelect" src/   → 无残留（exit 1）
  ✅ GZ-BEAN-003 临时入口已被本 ticket 清理（用真落地页 CTA 替换，可达路径不断）

可达路径（已验证产物含目标路由）:
  拼豆 tab → /pages/bean/index（落地页本身，N=0 直达，tabBar 已配）
  「立即预约」→ /pages/bean/select（已存在，N=1 可达，index.js 含该 navigateTo）
  「我的预约」→ /pages/bean/my-list（index.js 含该 navigateTo；BEAN-006 注册路由后 N=1 可达）
```

### 后端契约自检（@SaIgnore 公开 + ConfigService SPI）
```
GzConfigMpController:
  @SaIgnore + @RequestMapping("/app/gz/common/config") + GET /get?key=
  注入 org.dromara.common.core.service.ConfigService（gz-common 已依赖 common-core）
  mvn compile + install 均通过（见 Tier 1A）
未带 token 访问验证 → 待后端启动后 curl（命令见 Tier 1A §curl 段；编译期已保证路由注册）
```

### Tier 1B 结论
- mp vitest unit + API 契约回归：✅ 22/22 通过
- Tier 2 可达性：✅ 临时入口已清理 + 3 条路径产物验证
- 后端公开端点契约：✅ @SaIgnore + ConfigService 编译期保证
- 待 Kevin 批量人验（真机）：未登录守卫弹窗交互 / banner 占位视觉 / CTA 跳转真机走通
