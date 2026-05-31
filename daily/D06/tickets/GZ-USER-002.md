# GZ-USER-002 — mp 个人资料编辑

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M5 §关键页面 §个人资料展示
**关联拆解**: doc/02-需求拆解.md §2.4 第 447 行
**关联 mockup**: design/mockup/me-profile.html（仅布局参考；视觉以 C 设计系统为准，doc/13；doc/12 §5.1 排 3 标"待新画"是历史 — 当前文件已存在）
**关联 ADR**: —
**依赖**: GZ-SYS-002 ✅(D02) + GZ-SYS-005 ✅(D02)

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§4 会员中心占位流** §个人资料编辑分支（拉取微信资料 / 手机号解码 / 写 audit_log）
- **字段表**：doc/11-字段权威表.md **§2.1 `gz_user`**（写：avatar_url / nick_name / phone_num） + **§2.3 `gz_user_audit_log`**（本 ticket 写操作日志的目标表）
- **UI 参考**（视觉走 C 日漫海报浓墨：页面用 Biz* 组件 + var(--c-*)，见 doc/tokens.md + doc/13；旧 mockup 仅作布局参考，以 c-tokens.scss 的 rpx 为准）：doc/12-UI-权威索引.md **§MP-ME-PROFILE** + mockup `me-profile.html`

## What

用户修改昵称 / 头像 / 手机号；昵称头像可一键拉取微信资料覆盖（不强制）；手机号编辑用 `wx.getPhoneNumber` 解码；任何修改写入 `gz_user_audit_log`（不是 admin 操作日志，是用户行为审计）。

## AC（验收标准）

- [ ] **AC 1**：路由 `/pages/me/profile`，表单字段：头像（点击上传走 OSS — D02 SYS-005 `OssClient`）/ 昵称（input）/ 手机号（特殊编辑组件）；保存调 `PUT /app/gz/user/profile`
- [ ] **AC 2**：表单顶部"一键拉取微信资料"按钮 → 触发 `wx.getUserProfile` → 拉头像 + 昵称覆盖当前表单（不入库，需用户点保存才落库）
- [ ] **AC 3**：手机号编辑用 `<button open-type="getPhoneNumber">` → 后端 `POST /app/gz/user/profile/decode-phone` 用 session_key 解码 → 返回明文手机号填入表单；session_key 过期（解码失败 errcode=40029）→ 前端引导重新登录
- [ ] **AC 4**：保存成功后写 `gz_user_audit_log`（user_id / action_type=`profile_update` / changed_fields JSON / created_at）；前端 pinia user store 同步更新；toast"保存成功"后返回上一页
- [ ] **AC 5**：i18n 走 `t('user.profile.xxx')`
- [ ] **AC 6**：单测覆盖 `GzUserProfileService.updateProfile()` happy path + decode-phone session_key 过期 path

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-user/`
  - `controller/applet/GzUserProfileMpController.java`（mp 路径 `/app/gz/user/profile`）
  - `service/IGzUserProfileService.java` + `service/impl/GzUserProfileServiceImpl.java`
  - `service/IGzUserAuditLogService.java` + impl（如 SYS-003 已建则复用）
  - `domain/dto/UserProfileUpdateDTO.java` + `domain/dto/DecodePhoneDTO.java`
  - DDL：**本 ticket 不写 DDL**（gz_user 表 SYS-003 已落，gz_user_audit_log 若未在 SYS-003 落则本 ticket 落 `V202606031000__GZ-USER-002-create-gz_user_audit_log.sql` — 实施时 §0 自检确认）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/profile.vue`
  - `components/biz/AvatarUpload.vue`（业务组件，包 wd-upload + OSS 调用）
  - `api/gz-user.ts` 加 `updateProfile()` / `decodePhone()`
  - `locales/zh_CN/user.ts` 加 profile 段
- **测试**：mvn 单测 + mp 端 vitest（手机号编辑 + 头像上传两个关键路径）

## 备注

### 强约束

1. **session_key 解码后端独占**：mp 端拿不到 session_key 明文（D02 SYS-002 D4 决策）
2. **audit_log 写入不在 Controller 写**：在 Service 层 + `@Transactional` 保证原子（profile 写失败时 audit 不落）
3. **头像上传走 OSS 不存 base64**：D02 SYS-005 `OssClient.upload(file)` 返回 url，仅 url 写入 gz_user.avatar_url
4. **手机号字段加密**：gz_user.phone_num 走 ruoyi 自带 `@EncryptField` 注解（如 SYS-003 schema 已声明则保留；未声明则报 Kevin 确认是否补加密）
5. **i18n 强制**：所有 toast / 表单 label / placeholder / 错误文案走 `t('user.profile.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 拉取微信资料用 `wx.getUserProfile`（非 `wx.getUserInfo`，后者已废弃）| 微信 2022 后规范 |
| D2 | 一键拉取不直接落库 | 用户可能想改完再保存，避免被覆盖造成困惑 |
| D3 | audit_log 表如 SYS-003 未落则本 ticket 补 | 不留 TODO；§0 自检发现则立即补 DDL |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | session_key 过期是常态（7 天 TTL）→ 解码经常失败 | AC 3 已明确：errcode=40029 → 引导重新登录 |
| R2 | 头像上传失败（OSS 网络 / 文件过大）→ 用户卡住 | 前端 onError 友好 toast + 保留原头像不变（不清空表单） |
| R3 | `gz_user_audit_log` 表 SYS-003 是否已落 — 不清楚 | §0 自检 grep DDL migration 文件夹 + ruoyi-gz-user 模块 entity，未确认则补 DDL |

---

## §revision（Kevin testing-human 后填，初始空）

<!--
- 问题 1：<现象> / 期望：<期望>
-->
