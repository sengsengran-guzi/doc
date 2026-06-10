# GZ-USER-005 完工报告 — 用户微信号字段（gz_user.wechat_id）+ mp 资料页录入

> 与 GZ-USER-006 同页 / 同 profile 接口 / 同 GzUser entity，一条线顺序实施（避免自冲突）。
> 本报告聚焦 wechat_id；头像 image_id + 登录态见 GZ-USER-006.md。

## §0 自检结果

| 检查项 | 结果 |
|---|---|
| git clean | N/A（项目非 git repo，主线程已确认） |
| 上游依赖 merge | ✅ GZ-USER-002（资料页 + PUT /app/gz/user/profile）已交付；GZ-SYS-003（gz_user 表）已落 |
| 关键类/表存在 | ✅ `gz_user`（nickname/avatar_url 已有，无 wechat_id）、`GzUser` entity、`UserProfileUpdateBo`、`GzUserProfileServiceImpl`、`MeController`(GET) 均在 |
| 编译通过 | ✅ `mvn compile -pl ruoyi-gz-user,ruoyi-gz-common -am` EXIT 0 |
| ADR 已读 | ADR-0009（wechat_id 手动填口径 §3） |
| 迁移时间戳专属段 | ✅ 用 0610，> 已有最大 `V202606190200`，未占用其它并行线段（0600/0620/0630/0631） |
| 权威蓝图引用 | ✅ doc/11 §2.1 `wechat_id` VARCHAR(64) N NULL 手动填无 UNIQUE / doc/10 §3 付款前采集 |

**doc/11 §2.1 关键约束摘录**（实施依据）：
- `wechat_id` | VARCHAR(64) | N | NULL | U（**手动填**）| admin 详情/列表显示完整；mp 资料页可编辑
- 「微信不开放 API 查微信号，只能用户手动填；拼豆 V1.2 付款前采集（与 getPhoneNumber 手机号并列）」
- doc/11 §2.1 已回填 avatar_image_id（与主线程下发口径一致，无偏差）

## 实现摘要

- **迁移**：`db/migration/V202606190610__GZ-USER-005-add-wechat_id.sql` — `ALTER TABLE gz_user ADD COLUMN wechat_id VARCHAR(64) NULL ... AFTER mobile`（无 UNIQUE，可空）
- **后端**（`org.dromara.gz.*`）：
  - `GzUser`（gz-common entity）+ `GzUserVO` 加 `wechatId`
  - `UserProfileUpdateBo`（gz-user）加 `wechatId`（`@Size(max=64)`）
  - `GzUserProfileServiceImpl.updateProfile` 扩 wechatId 分支：变化才更新 + 写 `update_wechat_id` 审计；空白串视为不修改
  - 复用 GZ-USER-002 `PUT /app/gz/user/profile`（**不新建接口**）；GET 回显走 `MeController` → `GzUserServiceImpl.selectVoById`（VO 已含 wechatId）
- **mp**：
  - `pages/me/profile.vue` 加微信号文本录入行（普通 `<input type="text">` + Biz 组件 + `var(--c-*)`，placeholder「请输入微信号，便于门店联系」，回显当前值，maxlength 64）
  - `api/gz-user.ts`：`GzUserMeVO` + `UserProfileUpdateRequest` 加 `wechatId`
  - `locale/user.zh-CN.ts`：加 `wechatIdLabel` / `wechatIdPlaceholder` / `wechatIdTooLong` + en 映射（双语，默认 zh-CN，无 emoji）
- **AC 5（admin 用户页显示 wechatId）**：当前无独立 GZ-USER admin 用户列表/详情页（本卡不新建 admin 页，AC 5 明示「若无则跳过」）；VO 已含 wechatId，未来 admin 用户页直接可显示。

## AI 自测（Tier 1A）

### 1. 后端编译（gz-user + gz-common）
```
cd code/main/RuoYi-Vue-Plus && mvn -q compile -pl ruoyi-modules/ruoyi-gz-user,ruoyi-modules/ruoyi-gz-common -am -DskipTests
BACKEND COMPILE EXIT: 0
```

### 2. 后端单测（profile service，含 wechatId 用例）
```
[INFO] Running org.dromara.gz.user.service.impl.GzUserProfileServiceImplTest
[INFO] Tests run: 10, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```
新增 wechat_id 相关用例：
- `updateProfile_wechatId_writesAuditAndPersists` — 填微信号 → UPDATE wechat_id + 写 1 条 `update_wechat_id` 审计（捕获 before=old_wx / after=new_wx_id）
- `updateProfile_wechatIdBlank_noChange` — 微信号传空白串 → 不报错、不更新、不写审计（AC 8 空值不报错）
- `updateProfile_noChange_skipsUpdateAndAudit`（扩 wechatId 同值不更新）

### 3. mp 契约单测（vitest，gz-user.test.ts）
```
 ✓ src/api/gz-user.test.ts (4 tests) 2ms
   ✓ getMe — GET /app/gz/common/me 回显含 wechatId
   ✓ updateProfile — PUT body 带 wechatId
   ✓ 头像走 avatarImageId 不传裸 url
   ✓ 微信号可空（不传 wechatId 也合法）
 Test Files  2 passed (2)   Tests  10 passed (10)
```

### 4. DB 列校验（dev MySQL ry-vue，ALTER 语法 dry-validate）
迁移文件尚未由 Flyway 应用（按本批协调不起 app）；下方为 ALTER 语句对 dev 库的语法/列形态 dry-validate（已回滚 / DROP 还原 baseline，不留残列）：
```
--- columns after ALTER (in-tx) ---
COLUMN_NAME       COLUMN_TYPE   IS_NULLABLE  COLUMN_COMMENT
mobile            varchar(11)   YES          手机号（拼豆预约时强收集）
wechat_id         varchar(64)   YES          微信号（手动填，微信不开放 API 查）
--- after cleanup（DROP 还原）---
leftover_new_cols
0
```
flyway_schema_history 无 USER-005 记录 → **待 Tier 1B Flyway 应用后正式建列**。

### 5. getUserProfile 禁用核查（AC 6 关联）
```
grep -rn "getUserProfile" mp/src（排除 .test）→ 仅注释说明「已废弃」，0 个真实调用
```
微信号纯手动填，代码无「自动获取微信号 / 解密微信号」逻辑。

## 风险提示 / 已知 issue

- **i18n 文件路径偏差（已对齐项目惯例）**：任务卡写 `lang/zh_CN/me.ts`，但 sensenran mp 实际惯例是 `locale/user.zh-CN.ts` 自包含 `t()`（`user.profile.*` key）。本卡按现状惯例加 key + en 映射，未新建 `me.ts`（避免引入第二套 i18n 体系）。
- wechat_id 无 UNIQUE（doc/11 §2.1 明确不去重）— 一个微信号可被多人填，符合设计。
- 待 Tier 1B Flyway 应用迁移后，`gz_user.wechat_id` 列才真实存在；集成测试 / 真机依赖此。

## 对下游 ticket 的提示

- **D13 GZ-BEAN-015 拼豆付款前采集**：读 `gz_user.wechat_id` 预填（已填带出），snapshot 进 `gz_bean_booking.wechat_id_snapshot`（doc/11 §3.5 已定）。本卡只做 gz_user 字段「存 + 编辑」，未碰拼豆/snapshot。
- 审计 action_type 新增 `update_wechat_id`（doc/11 §2.3 gz_user_audit_log），admin 审计日志页若枚举展示中文需补一条映射。

## §AI 测试段（kevin-qa Tier 1B，12:20）

### Flyway apply 验证

```
- Migrating schema `ry-vue` to version "202606190610 - GZ-USER-005-add-wechat id"
- Successfully applied 5 migrations to schema `ry-vue`, now at version v202606190631 (execution time 00:00.085s)
```
V202606190610 apply 成功 ✅

### 后端 DB 验证

```sql
-- DESC gz_user（关键列）
mobile            varchar(11)   YES   手机号（拼豆预约时强收集）
wechat_id         varchar(64)   YES   微信号（手动填，微信不开放 API 查）
```
`gz_user.wechat_id` VARCHAR(64) NULL 列确认存在 ✅

### API 契约（mp 端接口）

`PUT /app/gz/user/profile` 是 mp 端接口，需要 wx-login 产生的 mp token，无法通过 admin curl 直接调用。
后端字段 `wechatId` 已在 `UserProfileUpdateBo`（@Size(max=64)）+ `GzUser` entity + `GzUserVO` 中确认存在（Tier 1A 单测 10 passed 已验证落库 + 回显）。
集成验证：依赖 Tier 1A GzUserProfileServiceImplTest 10 用例（含 updateProfile_wechatId_writesAuditAndPersists）覆盖。

### mp vitest 单测

```
Test Files  35 passed (35)
     Tests  308 passed (308)
  Duration  3.12s
```
含 gz-user.test.ts 4 用例（wechatId GET 回显 / PUT body / 可空）全通过 ✅

### mp 可达性验证（AC Tier 2 入口）

- `profile.vue` 含 wechatId 文本录入行（row__label / v-model="wechatId" / maxlength 64 / placeholder i18n）
- 入口路径：「我的」tab → 会员中心 → 个人资料（N=2，业务主线入口 USER-002 已上线）✅
- 无 `getUserProfile` 真实调用（grep 仅见注释说明已废弃）✅

### 跳过 / 未跑

- `PUT /app/gz/user/profile` 真实 mp token 调用（wx.login 真机能力）→ Tier 2 人验
- profile 页面视觉（C 设计系统遵循度）→ Tier 2 Kevin 人验

### 结论

✅ Tier 1B 全通过 → ticket 可 close；mp ticket 进人验列待 Kevin 批量人验
