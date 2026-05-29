# GZ-SYS-002 — 微信登录链路（C 端）

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M1 §微信登录 / §用户故事 1
**关联拆解**: doc/02-需求拆解.md §2.1 第 189 行
**关联 mockup**: design/mockup/auth-modal.html（视觉参考，V1.0 设计冻结期不强求逐像素）
**关联 ADR**: —（无相关 ADR）
**依赖**: GZ-SYS-001 ✅

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md **§1 微信登录 + 实名认证流**（M1-A，V1.0）— 状态机 / 关键节点 / 异常分支 全读
- **字段表**：doc/11-字段权威表.md **§2.1 `gz_user` 用户主表**（本 ticket 在 SYS-003 落 DDL，但 service 层要按本 section 字段约定写 entity；本 ticket 关注 openid / unionid / session_key / login_at 这几列）
- **UI 参考**（设计冻结期降级为视觉参考）：
  - mp ticket：`design/mockup/auth-modal.html` + doc/12 §MP-SYS-AUTH 微信授权弹窗
  - admin ticket：N/A（本 ticket 不涉及 admin UI）

## What

mp 端首次进入触发微信原生授权弹窗（头像 + 昵称），调 `wx.login` 拿 code → 后端 `code2Session` 换 openId/unionId/session_key → 落库 `gz_user` 表 → 颁发 sa-token mp-client 登录态 → 持久化到 mp storage（下次自动登录）。

## AC（验收标准）

- [ ] **AC 1**：mp 端封装 `useAuth()` composable，首次进入首页 / 拼豆 tab / 我的 tab 时若未登录 → 触发 `wx.getUserProfile` 拉头像昵称 + `wx.login` 拿 code，调后端 `POST /app/gz/common/auth/wx-login`
- [ ] **AC 2**：后端 `WxLoginController.wxLogin(code, nickName, avatarUrl)` → 调微信 `code2Session`（用 ruoyi 自带 `WxOpenLoginProperties` 配置项）拿 openId/unionId/session_key → upsert `gz_user`（openId 是 UPSERT key，已存在则更新 nick/avatar/last_login_at）→ 返回 sa-token `{token, userId, nickName, avatarUrl}`
- [ ] **AC 3**：dev profile 下 wxMOCK 短路：当 `wx.appid=wxMOCK` 时，跳过 code2Session 调用，直接构造 `openId=mock-{code前 8 位}`、`unionId=mock-union-{code前 8 位}` 返回固定结果（contractual identical to real path）
- [ ] **AC 4**：mp 端登录成功后 token 写入 `uni.setStorageSync('TOKEN', token)`，全局请求拦截器自动带 `Authorization: Bearer ${token}`；后端 sa-token mp-client 配置 token 有效期 7 天（与 dongjiaoshan `mp-applet-*` 同款）
- [ ] **AC 5**：拒绝授权可继续浏览资讯（GZ-NEWS-001 路径无登录拦截）；触发预约 / 下单时弹「登录后才能预约」二次引导 → 走 AC 1 同款流程
- [ ] **AC 6**：单测覆盖 `WxLoginService.login()` happy path（mock 通道 1 个 + 真实通道 mock-`WxMpService` 1 个），可选异常路径

## Tech（端 + 范围）

- **后端**：`code/main/RuoYi-Vue-Plus/ruoyi-modules/ruoyi-gz-common/`
  - `controller/applet/WxLoginController.java`（小程序专用，路径前缀 `/app/gz/common/auth`）
  - `service/IWxLoginService.java` + `service/impl/WxLoginServiceImpl.java`
  - `service/impl/WxMockLoginAdapter.java`（mock 通道 adapter，按 `wx.appid` 路由）
  - `domain/dto/WxLoginRequest.java` + `domain/vo/WxLoginVO.java`
  - 复用 ruoyi 已有 `WxOpenLoginProperties`（in `ruoyi-common-social` 或类似）+ `WxMpService` SDK；如无则引入 `com.github.binarywang:weixin-java-miniapp:4.x`（请先确认 dongjiaoshan ruoyi-djs-common 引入版本，本日不引新版本）
  - DDL：**本 ticket 不写 DDL**（gz_user 表在 SYS-003 落地，本 ticket 只需 entity + mapper 占位，SYS-003 跑完 Flyway 后 service 才能真正 upsert）
  - **依赖管理**：先确认本 ticket service 写完时 SYS-003 schema 是否已就位；如未就位 → mock 入库（写到内存 Map 或 H2）+ 留 TODO「SYS-003 完工后切真实 DAO」。**优先做法**：本 ticket 主线程派 SYS-002 → 等 SYS-003 schema 落完再回 SYS-002 service 补 DAO；如此可保证一次性 ✅
- **小程序**：`code/main/miniapp/src/`
  - `composables/useAuth.ts`（封装 wx.getUserProfile + wx.login + 调 API + 存 token）
  - `api/gz-common.ts`（加 `wxLogin` 调用）
  - `utils/request.ts`（拦截器加 token header）
  - `pages/login/index.vue`（设计冻结期降级：mockup auth-modal 弹窗形态先用 wd-popup 模拟，不强求逐像素还原）
  - `store/user.ts`（pinia store 存 userId / nickName / avatarUrl / token）
- **测试**：mvn 单测 `WxLoginServiceImplTest`（mock WxMpService + Mock repo），至少 1 个 mock 通道 + 1 个真实通道 mock path

## 备注

### 强约束

1. **mp 路径前缀必 `/app/gz/...`**（CLAUDE.md 不变规则 + sa-token mp-client 拦截器认这个前缀）
2. **wxMOCK 短路在 dev 通过 `@ConditionalOnProperty(prefix="wx", name="appid", havingValue="wxMOCK")` 控制**，不是用 if 写死。staging/prod profile 切真实 AppID 时该 Bean 不加载
3. **token 不要存 user_id 明文**（sa-token 已加密），mp 端解码只用 sa-token API
4. **session_key 必落库**（gz_user.session_key）— 后续 GZ-USER-002 编辑手机号时需要 `wx.getPhoneNumber` 解码用
5. **不要在 mp 端硬编码 AppID**（必须读 `import.meta.env.VITE_WX_APPID`）
6. **i18n**：所有 toast / 错误 / 弹窗文案走 `t('auth.xxx')`

### 关键技术决策

| # | 决策 | 理由 |
|---|---|---|
| D1 | 用 ruoyi 已有 `weixin-java-miniapp` SDK，不引新 SDK | 与 dongjiaoshan 同款，避免依赖发散 |
| D2 | wxMOCK 短路用 ConditionalOnProperty，不写 if | 配置驱动，profile 切换零代码变更 |
| D3 | UPSERT 用 ruoyi 自带 `BaseMapperPlus.insertOrUpdate(by openid)` | 标准 mybatis-plus 范式 |
| D4 | session_key 不暴露给前端 | 仅后端 mp 解密手机号用（GZ-USER-002 / GZ-BEAN-004 强收集场景）|
| D5 | 设计冻结期 mockup auth-modal.html 只参考结构，不强求样式还原 | CLAUDE.md §7.5 设计冻结期策略 |

### 风险提示

| # | 风险 | 缓解 |
|---|---|---|
| R1 | wx.getUserProfile API 2022 起已限制（必须用户手动触发 + 仅一次）| 实施时按"首次失败容忍 → 引导用户去会员中心补"逻辑，避免阻塞 |
| R2 | gz_user schema 在 SYS-003 才落库，本 ticket service 写完无法跑通 happy path | 派单顺序：SYS-002 controller/dto 写完 → 等 SYS-003 完工 → 回 SYS-002 补 service DAO 真实落库（任务卡里写 TODO，subagent 自检发现）|

---

## §revision（Kevin testing-human 后填，初始空）

### kevin-qa Tier 1B（2026-05-28 14:30）

- **问题 1（BUG-SYS-002-01）**：mp 端拿 token 后调任何后续 mp API 均返 500（NPE） / 期望：200
  - **根因**：`WxLoginServiceImpl.issueToken()` 构造 `SaLoginParameter` 时未调用 `model.setExtra(LoginHelper.CLIENT_KEY, ...)`；`ruoyi-common-security` 的 `SecurityConfig.check` 第 68 行 `StpUtil.getExtra("clientid").toString()` 对 null 调 `.toString()` 抛 NPE
  - **已修 / 改了 `WxLoginServiceImpl.java`**（2026-05-28 15:51）：
    - 加 `resolveClientId()` 方法：优先从 `ServletUtils.getRequest()` 读 header `clientid`，缺省 fallback `"mp-applet-sensenran-guzi"`（与 mp 端 `VITE_APP_CLIENT_ID` 对齐）
    - `issueToken()` 在 `LoginHelper.login()` 前调 `model.setExtra(LoginHelper.CLIENT_KEY, clientId)`
    - 同款写法参考 `ruoyi-admin` 的 `XcxAuthStrategy.java:85` / `PasswordAuthStrategy.java:79`
  - **修复后验证**：Chain A/B/C/D 4 条端到端链路全 ✅（详 reports/GZ-SYS-002.md §revision-1）
