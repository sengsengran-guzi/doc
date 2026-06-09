# GZ-USER-006 — 微信资料完善（chooseAvatar + nickname 持久化）+ 登录态保持

**优先级**: P0
**复杂度**: M
**关联 PRD**: doc/02-prd.md M5 §完善微信资料（chooseAvatar + nickname）+ §登录态保持（sa-token 长效 + 静默续期）+ §关键字段（用户资料）
**关联拆解**: doc/02-需求拆解.md §3.6.2 GZ-USER-006 微信资料完善 + 登录态保持
**关联 mockup**: design/mockup/me-profile（MP-ME-PROFILE 缺口，复用 GZ-USER-002 已建资料页 `pages/me/profile`，头像区改 chooseAvatar 按钮 + nickname input）
**关联 ADR**: **doc/_adr/0009-wechat-profile-and-session-persistence.md（必读，微信资料采集 + 登录态保持 — chooseAvatar/nickname 持久化 + sa-token 长效 + 静默 wx.login 续期）**
**依赖**: 无（GZ-USER-002 个人资料页已交付 + GZ-SYS-005 COS 上传已交付 + 微信登录链路已交付）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §11.N6 付款前采集（头像昵称采集与本卡持久化口径一致）+ 微信登录 / 资料采集 / 登录态续期流（启动校验 token → 失效静默 wx.login → code2session 续期，openid 静默可得）
- **字段表**：doc/11-字段权威表.md **§2.1 `gz_user`**（`nickname` / `avatar_image_id` FK gz_file_object 头像存 COS **不存裸 url** / `wechat_id` 见 GZ-USER-005；登录态非持久字段走 sa-token 自身存储）
- **ADR**：**ADR-0009**（微信资料采集 + 登录态保持，必读 — chooseAvatar + nickname input 一次性采集持久化 / getUserProfile 已废弃不可用 / sa-token 长效 token / mp 启动静默 wx.login 续期不踢用户）
- **UI 参考**（设计冻结期）：
  - mp：`design/mockup/me-profile（MP-ME-PROFILE 缺口，视觉走 C 系统 Biz* 组件 + var(--c-*)；在 GZ-USER-002 资料页头像区改 chooseAvatar 按钮 + 昵称 <input type="nickname">，不重画整页）`

## What

mp 个人资料页（GZ-USER-002，`pages/me/profile`）的头像 / 昵称采集改为微信 `chooseAvatar` 按钮 + `<input type="nickname">` 一次性采集并**持久化**（头像上传 COS 存 `gz_user.avatar_image_id`，昵称存 `gz_user.nickname`，落库后不重复采集）；`getUserProfile` 已被微信废弃，不再使用。登录态改为 **sa-token 长效 token + mp 启动静默 wx.login 续期**：启动校验本地 token，失效则静默 `wx.login → code2session` 续期（openid 静默可得），用户无感知保持登录，不再频繁重登。本卡承接 ADR-0009。

## AC（验收标准）

- [ ] **AC 1**：mp 资料页头像区改 `chooseAvatar` 按钮（`<button open-type="chooseAvatar" @chooseavatar="...">`）+ 昵称 `<input type="nickname">`（Biz 表单项 / `var(--c-*)` token，**不直接撒 `<wd-*>`**）；选头像 → 临时路径上传 COS（复用 GZ-SYS-005 上传）→ 存 `gz_user.avatar_image_id`（FK gz_file_object，**不存裸 url**）；昵称 → 存 `gz_user.nickname`。
- [ ] **AC 2**：**不再调 `getUserProfile`**（微信已废弃，§0 自检 / QA 打回项）；头像昵称仅来自 chooseAvatar + nickname input。代码中不出现 `wx.getUserProfile` / `getUserInfo` 弹一键授权逻辑。
- [ ] **AC 3**：持久化回显——头像昵称落库后再进资料页直接回显（头像按 avatar_image_id 拼 COS 签名 URL 显示，昵称回填 input），**不重复弹采集**；与 GZ-USER-005 微信号同页编辑、同「保存资料」按钮一并提交。
- [ ] **AC 4**：登录态长效 token——后端 sa-token 配置长有效期（具体时长按 ADR-0009 口径）；token 续签 / 校验复用现有微信登录链路，不新建一套鉴权。
- [ ] **AC 5**：静默续期——mp 启动（或受保护接口 401）时校验本地 token，失效则**静默 `wx.login` → 后端 code2session 续期**（openid 静默可得，无需用户操作）→ 续签 token → 用户无感知保持登录；**不弹重新登录授权**。
- [ ] **AC 6**：后端 `gz_user` 资料更新 / 获取接口（复用 GZ-USER-002 `PUT/GET /api/user/profile`）扩 `avatarImageId` / `nickname`；获取接口回 avatar 签名 URL（或 image_id 由前端拼）+ nickname。续期接口（如 `POST /api/auth/wechat-login` 静默分支）按 ADR-0009 落地。
- [ ] **AC 7**：i18n 全覆盖（mp `zh_CN/me.ts` + `en_US/me.ts`，key 如 `me.profile.chooseAvatar` / `me.profile.nickname`）；默认 zh-CN，不混 emoji。
- [ ] **AC 8**：单测 / 集成——更新 profile 带 avatarImageId + nickname → DB 落库；获取 profile → 回显（avatar 签名 URL + nickname）；token 失效 → 静默续期签发新 token（mock wx.login / code2session）不返 401 踢用户。
- [ ] **AC N: Tier 2 入口可达**（**mp ticket 强制**，CLAUDE.md §8.3）— Kevin 从 mp **底部 tab「我的」→「个人资料」（GZ-USER-002 已上线页，N=2）** 进入资料页 → 用 chooseAvatar 选头像 + 填昵称 → 保存 → 重进回显（头像 + 昵称 + 微信号）；长时间后再进**不被踢登录**（token 静默续期透明）。
  - 入口路径：mp 启动 → 底部 tab「我的」→「个人资料」入口 → 资料页（chooseAvatar + nickname + 微信号录入项在此页）
  - 业务主线入口**已建**（GZ-USER-002 资料页 + 登录链路已上线），**无需临时入口**——头像区改造直接加在现成资料页上。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`（包名 `org.dromara.gz.user.*`）+ 微信登录链路（`org.dromara.gz.common.*` / auth）
  - DDL：如 `gz_user.avatar_image_id` / `nickname` 列已存在则**无新迁移**（§0 自检 `DESC gz_user` 确认）；若缺列才新建 `V<时间戳 ≥ 202606190600>__GZ-USER-006-*.sql`（ALTER 加列，新建更大时间戳，不改已应用迁移）
  - `domain/GzUser.java` + profile VO / Bo 扩 `avatarImageId` / `nickname`（`@Size` 校验）
  - profile 更新 / 获取逻辑（复用 GZ-USER-002 `updateProfile`/`getProfile`）扩头像昵称
  - 微信登录链路：sa-token 长效 token 配置 + 静默续期分支（code2session，openid 静默续期），承接 ADR-0009
- **Admin**：不动（admin 用户页若显示头像/昵称按现有；本卡不为此改 admin）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/profile.vue`（GZ-USER-002 已建）：头像区改 chooseAvatar 按钮 + 昵称 nickname input + 回显 + 保存
  - 启动 / 鉴权拦截：token 校验 + 失效静默 wx.login 续期（app 启动钩子 / 请求拦截器 401 分支）
  - `api/gz-user/*.ts`（profile update/get 扩 avatarImageId/nickname）+ 登录续期 api
  - `lang/zh_CN/me.ts` + `en_US/me.ts`（chooseAvatar / nickname label）
- **测试**：单测扩 profile update/get（AC 8）+ token 静默续期单测 + kevin-qa Tier 1B mp vitest unit + 可达性检查（资料页 chooseAvatar 可见可存）

## 备注

- **getUserProfile 已废弃硬约束**（ADR-0009）：微信已下线 `getUserProfile`，头像只能 chooseAvatar 按钮、昵称只能 `<input type="nickname">`。任何 getUserProfile / getUserInfo 一键授权实现都是错的（§0 自检 / QA 打回项）。
- **头像存 COS 不存裸 url**（强约束 #12 风格 + doc/11 §2.1）：chooseAvatar 拿到的是临时路径，必须上传 COS 存 `avatar_image_id`（FK gz_file_object），不直接把临时 url 落库。
- **登录态静默续期不踢用户**（ADR-0009）：token 失效走静默 wx.login（openid 静默可得，无需用户授权弹窗）续期；只有 openid 都拿不到 / 用户主动退出才回登录页。
- **与 GZ-USER-005 同页**：GZ-USER-005（wechat_id 录入）+ 本卡（头像昵称 chooseAvatar）都在 GZ-USER-002 资料页上加，复用同一「保存资料」提交 + 同一 profile 接口，**不新建资料页 / 不新建 profile 接口**，仅扩字段 + 改头像采集方式。
- `tenant_id` 自动填充（gz_user 已是 TenantEntity）。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D11/GZ-USER-006 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
