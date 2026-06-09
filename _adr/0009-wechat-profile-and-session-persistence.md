# ADR-0009 微信小程序资料采集（头像/昵称）持久化 + 登录态保持（sa-token 长效 + 静默续期）

- 日期：2026-06-09
- 状态：Accepted
- 决策人：Kevin（甲方 V1.2 调整需求，kevin-product 评估，kevin-coder 落地）
- 关联 ticket：GZ-USER-005（gz_user.wechat_id + 资料页手动录入）/ GZ-USER-006（chooseAvatar + nickname 持久化 + 登录态长效 + 静默续期）；依赖 GZ-SYS-002（微信登录链路）；关联 doc/11 §2.1
- 落地批次：D11（USER-005 / USER-006 并行）

---

## Context

V1.2 甲方反馈两个 C 端体验问题，根因都在微信小程序登录 / 资料能力的平台限制：

1. **拿不到头像昵称**：早期小程序用 `wx.getUserProfile` 一键拉头像 + 昵称，但微信 **2022-10 起回收该能力**，调用只返匿名「微信用户」+ 灰色默认头像，无法获得真实资料。导致后台 / 拼豆单看到的全是「微信用户」，门店无法识别到人。
2. **频繁重登体验差**：登录态若只挂在短时效 token / `session_key` 上，过期后用户被踢回登录页重新授权，拼豆这种「进店扫码就要用」的场景非常突兀。

此外微信号（wechat_id）也有平台限制：**微信不开放任何 API 获取用户微信号**（区别于手机号有 `getPhoneNumber` 一键授权），只能用户手动填。

核心问题：① 头像昵称怎么采集并持久化；② 登录态怎么做到长效且失效时不打扰用户；③ 微信号怎么收集。

## Decision

### 1. 头像 / 昵称：chooseAvatar 按钮 + nickname 输入，一次性采集持久化

替代已废弃的 `getUserProfile`，用微信现行能力组合采集，**采集一次落库，之后不重复弹窗**：

- **头像**：`<button open-type="chooseAvatar" @chooseavatar="...">` 拿到微信返回的**临时头像文件路径** → 上传**腾讯云 COS**（合同附件二指定，`gz_file_object` `usage_type='user_avatar'`）→ 写 `gz_user.avatar_image_id`（FK gz_file_object）+ 缓存可渲染 `avatar_url`。
  - **头像必须落 COS，不能存微信临时 URL**：chooseAvatar 给的是临时文件路径，会失效；存 COS 永久对象 + CDN URL（doc/11 §2.1 / F2.6）。
- **昵称**：`<input type="nickname">`（微信键盘联想昵称）采集 → 写 `gz_user.nickname`。
- **采集时机**：首登后引导一次「完善资料」（首登 onboarding），用户也可在「我的-资料」页主动改；落库后不再每次弹窗。

### 2. 登录态：sa-token 长效 token + mp 启动校验 + 失效静默 wx.login 续期

- **登录态真源 = 后端 sa-token 长效 token**（非 `session_key`）：登录成功（GZ-SYS-002 链路：`wx.login` code → `code2session` 换 openid → 建/查 gz_user → 签发 sa-token）后下发长效业务 token，mp 本地持久化（storage）。
- **token 有效期独立于 `session_key`**：`session_key` 存 Redis（doc/11 §2.1 注 `wx_session_key:{openid}` TTL 24h），仅用于解密手机号等微信能力；业务 token 有效期单独设（建议 **30 天**，最终值实施时定）。
- **mp 启动校验 + 静默续期**：每次 mp 启动 / 进入受保护页时校验本地业务 token；**失效则静默 `wx.login` 拿新 code → 后端 `code2session` 拿 openid → 按 openid 重签 sa-token**，原请求自动 retry。**openid 静默可得（wx.login 无需用户授权弹窗），所以续期对用户无感，不重登**。
- **被禁用兜底**：续期时若 gz_user `is_disabled=1` → 拒签 token，mp 回登录引导（doc/11 §2.1）。

### 3. 微信号 wechat_id：只能用户手动填

- 微信**无 API 取微信号**，`gz_user.wechat_id` 由用户在「我的-资料」页**手动录入**（GZ-USER-005）；拼豆付款前作为联系方式采集（与手机号 `getPhoneNumber` 并列，doc/11 §3.5 `wechat_id_snapshot`）。
- 区别于手机号：手机号走 `getPhoneNumber` 一键授权（code + access_token 换号，见 memory `wechat-real-integration`）；微信号无此能力，只能填。

## Rationale

- **贴合微信现行平台能力**：`getUserProfile` 已废弃，chooseAvatar + nickname input 是微信官方给的现行采集方式，不绕规、不踩废弃 API。
- **头像落 COS = 资料稳定**：临时路径会失效，落 COS 才能让后台 / 拼豆单长期稳定展示真实头像；与项目「image_id FK gz_file_object，不存裸 url」的跨层契约一致。
- **一次采集持久化 = 不反复打扰**：资料落库后不每次弹窗，符合 C 端体验预期。
- **sa-token 长效 + 静默续期 = 用户无感**：openid 静默可得是关键——续期不需要用户任何授权动作，token 过期对用户完全透明，杜绝「频繁重登」。把登录态挂业务 token（而非 `session_key`）让两者解耦，`session_key` 过期不影响登录态。
- **微信号手动填 = 平台限制下的唯一解**：没有 API，手动填是唯一合规路径；和手机号一键授权区分清楚，避免实施期误以为有 API。

## Consequences

- ✅ 后台 / 拼豆单显示用户真实头像 + 昵称，门店能识别到人；头像稳定存 COS 不失效。
- ✅ 用户资料一次采集持久化，不反复弹窗打扰。
- ✅ 登录态长效，token 过期静默 `wx.login` 续期，用户不被踢、不重登（拼豆进店即用场景顺滑）。
- ✅ 微信号采集口径明确（手动填），实施期不会误找不存在的 API。
- ⚠️ **首登需引导一次资料完善**：chooseAvatar / nickname 是用户主动触发的组件（不能后台静默拉），所以首登要有一次 onboarding 引导；用户跳过则头像昵称为空（UI 用默认占位），可后续在资料页补。
- ⚠️ **token 有效期 / 续期口径需实施钉死**：建议业务 token 30 天 + 滑动续期；`session_key` 24h（解密用）；二者解耦。具体时长 GZ-USER-006 实施时在 reports 写明。
- ⚠️ **COS 头像清理**：用户多次换头像会在 COS 留旧对象，V1.2 不做自动清理（量小可接受），留 v2 优化。

## 备选方案（被否）

| 方案 | 否决理由 |
|---|---|
| 继续用 `getUserProfile` 拉头像昵称 | 微信 2022-10 已废弃，只返匿名「微信用户」+ 灰头像，拿不到真实资料 — 不可行 |
| 头像直接存微信返回的临时 URL / 临时路径 | 临时路径会失效，后台 / 历史单展示会断图；违反「不存裸 url」跨层契约 |
| 登录态挂 `session_key` / 短时效 token | `session_key` 是微信能力密钥不是登录态；短时效 token 过期就踢用户 → 频繁重登（正是要解决的问题） |
| token 过期后弹窗让用户重新授权登录 | openid 静默可得，根本不需要打扰用户；弹窗重登是体验倒退 |
| 想办法「自动」获取微信号 | 微信无任何 API 开放微信号，技术上不可能；只能手动填 |
