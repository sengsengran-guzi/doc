# GZ-USER-006 完工报告 — 微信资料完善（chooseAvatar + nickname 持久化）+ 登录态保持

> 与 GZ-USER-005 同页 / 同 profile 接口 / 同 GzUser entity，一条线顺序实施。
> 承接 **ADR-0009**（chooseAvatar + nickname 一次性采集持久化 / 头像存 COS image_id / sa-token 长效 + 静默续期）。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（项目非 git repo） |
| 上游依赖 merge | ✅ GZ-USER-002（资料页 + AvatarUpload chooseAvatar + nickname input 已存在）/ GZ-SYS-005（COS 上传 `/app/gz/common/file/upload` + 预签名 URL）/ 微信登录链路（WxLoginServiceImpl + code2session）均已交付 |
| 关键类/表存在 | ✅ `gz_user`（nickname/avatar_url 已有，无 avatar_image_id）、`GzFileService`(upload+getPresignedUrl)、`WxLoginServiceImpl`、`WxMiniappProperties`、mp `AvatarUpload.vue` / `store/token.ts` / `http.ts` 均在 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-user,ruoyi-gz-common -am` EXIT 0；mp `vue-tsc --noEmit` EXIT 0（0 error） |
| ADR 已读 | ✅ ADR-0009 全文（§1 头像/昵称 / §2 登录态 sa-token 长效+静默续期 / Consequences token 30天口径） |
| 迁移时间戳专属段 | ✅ 用 0620，> 0610，未占用其它并行线段 |
| 权威蓝图引用 | ✅ doc/11 §2.1 avatar_image_id / avatar_url 语义 / F2.6；doc/10 §11.N6 付款前采集 + 登录态续期流 |

**doc/11 §2.1 关键约束摘录**（实施依据）：
- `avatar_image_id` | BIGINT UNSIGNED | N | NULL | FK→gz_file_object.id；chooseAvatar 临时头像 → 上传 COS（`usage_type='user_avatar'`）→ 存 file_object id（**头像落 COS 不存微信临时 URL**）
- `avatar_url` | VARCHAR(512) | N | NULL | 由 avatar_image_id 对应 COS 对象拼可渲染 URL 缓存（不再存微信 CDN 临时 URL）
- ADR-0009 Consequences：业务 token 30 天；session_key 24h；二者解耦。具体时长「GZ-USER-006 实施时在 reports 写明」→ **本报告钉死见下**。

## 实现摘要

### 头像 / 昵称持久化（ADR-0009 §1）
- **迁移**：`db/migration/V202606190620__GZ-USER-006-add-avatar_image_id.sql` — `ALTER TABLE gz_user ADD COLUMN avatar_image_id BIGINT NULL ... AFTER avatar_url`（nickname 已存在不新加；avatar_url 保留不动）
- **头像真源 = avatar_image_id（不存裸 url）**：
  - mp `AvatarUpload.vue` chooseAvatar/相册 → 上传 COS（GZ-SYS-005 `uploadFile`，usageType=user_avatar）→ `emit('change', { fileId, url })`（fileId 落库，url 即时预览）
  - `pages/me/profile.vue` 收 fileId 存 `avatarImageId` ref，保存时提交 `avatarImageId`（仅本次新选才提交，未改不传）
  - 后端 `UserProfileUpdateBo` 加 `avatarImageId`；`GzUserProfileServiceImpl` 优先落 `avatar_image_id`（即便前端同时传 url 也忽略 url，存 image_id 不存裸 url），写 `update_avatar` 审计
- **持久化回显（不重复弹采集）**：读侧 `GzUserServiceImpl.selectVoById`（MeController GET + profile 更新返回共用）按 `avatar_image_id` 调 `IGzFileService.getPresignedUrl` 重生成 **1h 签名 URL** 回填 `avatarUrl`；签名失败不抛错（保留旧缓存，资料读取不因头像 500）
- **昵称**：`<input type="nickname">`（GZ-USER-002 已是此实现）→ 存 `gz_user.nickname`
- **getUserProfile 禁用**：`grep getUserProfile` 仅注释说明已废弃，0 个真实调用；AvatarUpload 用 `open-type="chooseAvatar"`，昵称用 `type="nickname"`

### 登录态长效 + 静默续期（ADR-0009 §2）
- **token TTL 钉死 = 30 天（2592000s）**：`WxMiniappProperties.tokenTtlSeconds` 默认 + `application-dev.yml` + `application-prod.yml`（`WX_MA_TOKEN_TTL:2592000`）全改；session_key 仍 24h（解密手机号用，解耦）
- **activeTimeout 对齐绝对 TTL**：`WxLoginServiceImpl.issueToken` 原 `activeTimeout=30min` 改为 `=tokenTtlSeconds`（避免 30 分钟空闲就过期 → 频繁续期；C 端「进店即用」顺滑）
- **静默续期（不踢用户）**：
  - 续期端点复用现有 `/app/gz/common/auth/wx-login`（UPSERT 幂等，openid 静默可得 → 重签 sa-token），**不新建一套鉴权**
  - mp 新增 `tokenStore.silentWxRenew()`：静默 `wx.login → code2session` 重签，全程无 toast / 无授权弹窗 / 不跳登录页；mock appid 短路 dev 账号续期
  - `http.ts` 单 token 401 分支由「直接 logout + 跳登录」改为「先 `silentWxRenew` → 成功重放挂起请求队列；仅续期也失败（openid 都拿不到 / 账号禁用）才 logout + 回登录页」
- **api 类型**：`GzUserMeVO` + `UserProfileUpdateRequest` 加 `avatarImageId`；i18n `chooseAvatar`/`nickname`/`avatarUpload*` key（双语）

## AI 自测（Tier 1A）

### 1. 后端编译 + mp typecheck
```
cd code/main/RuoYi-Vue-Plus && mvn -q compile -pl ruoyi-modules/ruoyi-gz-user,ruoyi-modules/ruoyi-gz-common -am -DskipTests
BACKEND COMPILE EXIT: 0

cd code/main/miniapp && npx vue-tsc --noEmit
=== vue-tsc EXIT: 0 ===   --- error count --- 0
```

### 2. 后端单测（gz-common 100 + gz-user 42 全通过；含头像 image_id 用例）
```
[INFO] org.dromara.gz.common.service.impl.GzUserServiceImplTest      Tests run: 10, Failures: 0, Errors: 0
[INFO] org.dromara.gz.common.service.impl.WxLoginServiceImplTest     Tests run: 4,  Failures: 0, Errors: 0   (activeTimeout/TTL 改后仍过)
[INFO] org.dromara.gz.user.service.impl.GzUserProfileServiceImplTest Tests run: 10, Failures: 0, Errors: 0
[INFO] Tests run: 100, Failures: 0, Errors: 0, Skipped: 0   (gz-common)
[INFO] Tests run: 42,  Failures: 0, Errors: 0, Skipped: 0   (gz-user)
[INFO] BUILD SUCCESS
```
新增头像 image_id 用例：
- `GzUserServiceImplTest.selectVoById_withAvatarImageId_resolvesPresignedUrl` — 有 avatar_image_id → 调 getPresignedUrl 重生成签名 URL 覆盖旧缓存
- `GzUserServiceImplTest.selectVoById_avatarResolveFails_doesNotThrow` — 文件被删/COS 异常 → 不抛错，保留旧缓存 URL
- `GzUserServiceImplTest.selectVoById_validId_returnsMapperResult` — 无 image_id → 不调文件服务（never）
- `GzUserProfileServiceImplTest.updateProfile_avatarImageId_persistsImageIdNotRawUrl` — 传 avatarImageId（同时塞 url 干扰）→ 落 image_id=99，avatar_url 不被裸 url 覆盖
- `GzUserProfileServiceImplTest.updateProfile_avatarImageIdSame_noChange` — image_id 同值 → 不更新（幂等）

### 3. mp 静默续期单测（vitest，token.test.ts，ADR-0009 AC 5/8）
```
 ✓ src/store/token.test.ts (6 tests) 6ms
   ✓ silentWxRenew — 真实 appId：wx.login → wx-login 重签 token，返 true 不踢用户
     （断言 _wxLogin({code:'fresh-code-123'}) 调用 + validToken='renewed-token-7777' + hasLogin=true）
   ✓ silentWxRenew — mock appId：短路 dev 账号续期，返 true
   ✓ silentWxRenew — 续期失败（wx.login reject）返 false，不抛异常
   ✓ logout(skipBackend) / validToken 过期/未过期（原 3 用例回归过）
```

### 4. mp 全量 vitest 回归（触及 http.ts / token / AvatarUpload / locale / gz-user）
```
 Test Files  35 passed (35)
      Tests  308 passed (308)
```
（stderr 的 network/401/JSON fallback 日志均为负向用例的预期 console 输出，非失败。）

### 5. DB 列校验（dev MySQL ry-vue，ALTER dry-validate + 还原）
```
--- columns after ALTER (in-tx) ---
COLUMN_NAME       COLUMN_TYPE   IS_NULLABLE  COLUMN_COMMENT
avatar_url        varchar(512)  YES          头像 URL（微信侧 CDN URL，不下载到 OSS）
avatar_image_id   bigint        YES          头像文件 id（FK gz_file_object，存 COS，不存裸 url）
nickname          varchar(64)   YES          昵称（...）   ← 已存在，本迁移不新加
--- after cleanup（DROP 还原 baseline）---
leftover_new_cols = 0
```
flyway_schema_history 无 USER-006 记录 → 待 Tier 1B Flyway 应用后正式建 `avatar_image_id` 列。

## 风险提示 / 已知 issue

- **avatar_url 是 1h 签名缓存，读时重生成**：每次 GET /me / profile 更新返回都会按 avatar_image_id 调一次 COS 预签名（单用户读，非列表）。admin 用户列表 `selectPageList` **未**逐行重生成（避免 N 次签名开销），admin 显示用库里 avatar_url 缓存 + avatarImageId；如 admin 需精确头像可后续在 admin 详情单独调 /file/url。
- **mp 兜底兼容**：`UserProfileUpdateBo.avatarUrl` 保留作旧链路兜底（仅当未传 avatarImageId 时生效，如非微信端直传）；新链路全走 avatarImageId。
- **静默续期时序**：`http.ts` 单 token 401 用 `refreshing` 标志 + `taskQueue` 串行化（与原双 token 刷新同款），并发 401 只触发一次 silentWxRenew，其余请求挂队列重放。
- **首登 onboarding**（ADR-0009 Consequences ⚠️）：chooseAvatar/nickname 是用户主动触发组件，首登需引导一次完善资料；用户跳过则头像昵称为空（UI 默认占位），可后续在资料页补。本卡聚焦资料页采集 + 持久化 + 登录态；首登强引导浮层若需独立体验由后续 ticket（或 USER-001 会员中心头部「点击完善头像昵称」入口已提供路径）。
- 待 Tier 1B Flyway 应用迁移后，`gz_user.avatar_image_id` 列才真实存在。

## 对下游 ticket 的提示

- 头像渲染统一口径：**任何展示用户头像的端（admin 拼豆单 / 历史订单快照）都用 image_id 换签名 URL，不依赖裸 url**（跨层契约 #5）。下游若 join gz_user 展示头像，读 avatar_image_id → 调 /file/url。
- token TTL 已统一 30 天（dev/prod 同口径）；下游不要再各自设短 TTL。
- 审计 action_type `update_avatar`（头像 image_id 变更）沿用既有枚举。

## Tier 2 入口可达（AC N）

- 入口路径：mp 启动 → 底部 tab「我的」（GZ-ADMIN-005 5 tab 已上线）→ 会员中心头部 / 「个人资料」入口（GZ-USER-002 已上线，N=2）→ 资料页
- 资料页一屏含：头像 chooseAvatar 按钮 + 昵称 nickname input + 性别 + 手机号 getPhoneNumber + **微信号文本框（USER-005）**，共用同一「保存资料」按钮
- 业务主线入口**已建**（USER-002 资料页 + 登录链路 + 5 tab 均上线），**无需临时入口**——头像区改造 + 微信号框直接加在现成资料页上
- 登录态：长时间后再进资料页，token 静默续期透明，不被踢登录

## §AI 测试段（kevin-qa Tier 1B，12:20）

### Flyway apply 验证

```
- Migrating schema `ry-vue` to version "202606190620 - GZ-USER-006-add-avatar image id"
- Successfully applied 5 migrations to schema `ry-vue`, now at version v202606190631 (execution time 00:00.085s)
```
V202606190620 apply 成功 ✅

### 后端 DB 验证

```sql
-- DESC gz_user（关键列）
avatar_url        varchar(512)  YES   头像 URL（签名 URL 缓存）
avatar_image_id   bigint        YES   头像文件 id（FK gz_file_object，存 COS，不存裸 url）
nickname          varchar(64)   YES   昵称（...）← 已存在，本迁移不新加
```
`gz_user.avatar_image_id` BIGINT NULL 列确认存在 ✅

### 后端 API 验证（admin token 范围）

`PUT /app/gz/user/profile` 是 mp 端接口需 mp token，无法 curl 直接调用。
集成覆盖依赖 Tier 1A：GzUserProfileServiceImplTest.updateProfile_avatarImageId_persistsImageIdNotRawUrl + selectVoById_withAvatarImageId_resolvesPresignedUrl（10+10 用例全通过）。

### mp vitest 静默续期单测

```
src/store/token.test.ts (6 tests)
  ✓ silentWxRenew — 真实 appId：wx.login → 续期 token，返 true
  ✓ silentWxRenew — mock appId：短路 dev 账号续期，返 true
  ✓ silentWxRenew — 续期失败（wx.login reject）返 false，不抛异常
  ✓ logout / validToken 过期/未过期（3 用例回归）
```
token.test.ts 6 用例全通过（含 silentWxRenew）✅

### mp vitest 全量回归

```
Test Files  35 passed (35)
     Tests  308 passed (308)
  Duration  3.12s
```
全通过 ✅

### mp 实现验证

```bash
grep -n "wechatId|avatarImageId|chooseAvatar|silentWxRenew" src/pages/me/profile.vue
# profile.vue: wechatId ref、avatarImageId ref、chooseAvatar 按钮（AvatarUpload）
grep -n "silentWxRenew" src/http/http.ts
# http.ts: 401 handler 调 tokenStore.silentWxRenew()，refreshing + taskQueue 串行化
grep -rn "getUserProfile" src/ | grep -v "注释|废弃|已废"
# 0 个真实调用
```
头像走 chooseAvatar → COS → avatarImageId ✅；静默续期 401 hook ✅；无 getUserProfile ✅

### mp 可达性

- 入口：「我的」tab → 会员中心 → 个人资料（N=2，USER-002 已上线）✅
- 资料页一屏：头像 chooseAvatar 按钮 + 昵称 type=nickname + 微信号文本框（USER-005）✅

### 跳过 / 未跑

- chooseAvatar 真机弹框（微信原生能力）→ Tier 2 人验
- 静默续期真机 30 天 token 过期场景 → Tier 2 人验（真机才能构造过期 token）
- profile 页面视觉（C 设计系统）→ Tier 2 Kevin 人验

### 结论

✅ Tier 1B 全通过 → ticket 可 close；mp ticket 进人验列待 Kevin 批量人验
