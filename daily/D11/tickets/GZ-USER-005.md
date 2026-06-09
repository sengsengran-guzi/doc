# GZ-USER-005 — 用户微信号字段（gz_user.wechat_id）+ mp 资料页录入

**优先级**: P0
**复杂度**: S
**关联 PRD**: doc/02-prd.md M4 §付款前采集（手机号 + 微信号）+ M5 §个人资料（含微信号）
**关联拆解**: doc/02-需求拆解.md §3.6.2 GZ-USER-005 用户微信号字段（gz_user.wechat_id）
**关联 mockup**: design/mockup/me-profile（MP-ME-PROFILE 缺口，复用 GZ-USER-002 已建资料页 `pages/me/profile`，加一个录入项）
**关联 ADR**: —
**依赖**: 无（GZ-USER-002 个人资料编辑页已交付）

---

## 必读权威文档（缺一不可 — kevin-coder §0 自检会卡）

- **业务流**：doc/10-业务流权威图.md §3 拼豆付款前采集（`wechat_id` 与 getPhoneNumber 手机号并列采集；本卡只做「存 + 编辑」，付款前预填读取在 D13 GZ-BEAN-015）
- **字段表**：doc/11-字段权威表.md **§2.1 `gz_user.wechat_id`**（`VARCHAR(64) NULL`，**手动填**，无 UNIQUE，可空；admin 详情/列表显示完整，mp 资料页可编辑）
- **UI 参考**（设计冻结期）：
  - mp：`design/mockup/me-profile（MP-ME-PROFILE 缺口，视觉走 C 系统 Biz* 组件 + var(--c-*)；在 GZ-USER-002 资料页加一行录入项，不重画整页）`

## What

`gz_user` 表 ALTER 加 `wechat_id VARCHAR(64) NULL`（**用户手动填，微信不开放 API 查微信号**）；mp 个人资料页（GZ-USER-002，`pages/me/profile`）增加微信号录入框（可空，手动填）；复用已有 `PUT /api/user/profile` 更新接口扩字段 + i18n。供下游 D13 GZ-BEAN-015 拼豆付款前采集预填使用。

## AC（验收标准）

- [ ] **AC 1**：Flyway 迁移 `V<时间戳 ≥ 202606190600>__GZ-USER-005-add-wechat_id.sql`——`ALTER TABLE gz_user ADD COLUMN wechat_id VARCHAR(64) NULL COMMENT '微信号（手动填，微信不开放 API 查）' AFTER <phone 附近列>`（**新建更大时间戳文件，不改已应用迁移**）。无 UNIQUE 约束（一个微信号可被多人填，不去重）。
- [ ] **AC 2**：后端 `GzUser` entity + `GzUserVo` + `GzUserBo`（或 profile DTO）加 `wechatId` 字段；mp 资料更新接口 `PUT /api/user/profile`（GZ-USER-002 已有）扩 `wechatId` 入参（可空），更新到 `gz_user.wechat_id`；获取资料接口 `GET /api/user/profile` 回显 `wechatId`。
- [ ] **AC 3**：mp 资料页 `pages/me/profile` 加微信号录入项——普通文本 `<input>`（Biz 表单项 / `var(--c-*)` token，**不直接撒 `<wd-*>`**），placeholder「请输入微信号，便于门店联系」；初始回显当前 `wechatId`（可空显示 placeholder）；保存走已有「保存资料」按钮一并提交。
- [ ] **AC 4**：可空 + 长度校验——`wechat_id` 可空（不填不报错）；填写时前端 + 后端 Bo 校验长度 ≤ 64（`@Size(max=64)`）；微信号格式不强校验（允许字母/数字/下划线/连字符等常见微信号字符，不做严格正则）。
- [ ] **AC 5**：admin 用户列表/详情（GZ-USER 已有 admin 页若存在）显示 `wechatId` 完整值（doc/11 §2.1：admin 显示完整）；若无 admin 用户页则跳过此项（本卡不为此新建 admin 页）。
- [ ] **AC 6**：**不调任何微信 API 获取微信号**——`wechat_id` 仅来自用户手动输入（doc/11 §2.1 + README §3）；代码中不出现「自动获取微信号 / 解密微信号」逻辑。
- [ ] **AC 7**：i18n 全覆盖（mp `zh_CN/me.ts` + `en_US/me.ts`，key 如 `me.profile.wechatId` / placeholder）；默认 zh-CN，不混 emoji。
- [ ] **AC 8**：单测 / 集成——更新 profile 带 wechatId → DB 落库；获取 profile → 回显 wechatId；wechatId 传空 → 不报错（covered by GZ-USER-002 既有 profile 测试扩一条）。
- [ ] **AC N: Tier 2 入口可达**（**mp ticket 强制**，CLAUDE.md §8.3）— Kevin 从 mp **底部 tab「我的」→「个人资料」（GZ-USER-002 已上线页，N=2）** 进入资料页，看到微信号录入框，可录入/编辑/保存，重进回显。
  - 入口路径：mp 启动 → 底部 tab「我的」→「个人资料」入口 → 资料页（微信号录入项在此页）
  - 业务主线入口**已建**（GZ-USER-002 资料页已上线），**无需临时入口**——录入框直接加在现成资料页上。

## Tech（端 + 范围）

- **后端**：`ruoyi-modules/ruoyi-gz-user/`（包名 `org.dromara.gz.user.*`）
  - DDL：`ruoyi-admin/src/main/resources/db/migration/V<时间戳 ≥ 202606190600>__GZ-USER-005-add-wechat_id.sql`（ALTER gz_user 加列）
  - `domain/GzUser.java` 加 `wechatId`；`domain/vo/GzUserVo.java` / profile VO 加 `wechatId`；`domain/bo/GzUserProfileBo.java`（或 GZ-USER-002 已有 profile bo）加 `wechatId`（`@Size(max=64)`）
  - `service` profile 更新逻辑扩 `wechatId`（复用 GZ-USER-002 已有 `updateProfile`，不新建接口）
- **Admin**：`code/main/plus-ui/src/views/gz-user/*`（若已有用户列表/详情页则加 wechatId 列/字段；无则跳过，不新建）
- **小程序**：`code/main/miniapp/src/`
  - `pages/me/profile.vue`（GZ-USER-002 已建）：加微信号录入项 + 回显 + 保存
  - `api/gz-user/*.ts`（profile update/get 接口扩 wechatId 入参/返回）
  - `lang/zh_CN/me.ts` + `en_US/me.ts`（wechatId label / placeholder）
- **测试**：单测扩 profile update/get（AC 8）+ kevin-qa Tier 1B mp vitest unit + 可达性检查（资料页录入框可见）

## 备注

- **手动填硬约束**（doc/11 §2.1 + ADR 无关）：微信不开放 API 查微信号，`wechat_id` 只能用户手填。任何「自动获取微信号」实现都是错的（§0 自检 / QA 打回项）。
- **wechat_id 无 UNIQUE**：一个微信号可被多个用户填（家人共用 / 输入重复），不做唯一约束、不去重。
- **下游衔接**：D13 GZ-BEAN-015 拼豆付款前采集页会读 `gz_user.wechat_id` 预填（已填则带出），并 snapshot 进 `gz_bean_booking.wechat_id_snapshot`（doc/11 §3 已定）。本卡只做 gz_user 字段的「存 + 编辑」，不碰拼豆/snapshot。
- **复用 GZ-USER-002 资料页 + 接口**：不新建资料页、不新建 profile 接口，仅扩字段。MP-ME-PROFILE 在 doc/12 标「缺口」是指 mockup 缺，页面本身 GZ-USER-002 已实现，本卡在其上加一行。
- `tenant_id` 自动填充（gz_user 已是 TenantEntity）；本卡 ALTER 加列不涉 tenant_id/UNIQUE。

---

## §revision（Kevin 批量人验后填，初始空 —— ticket 已 close 也可回填）

<!--
当 Kevin 测试不过时，在这里写问题清单，然后 `@coder 修 D11/GZ-USER-005 revision 段`：

- 问题 1：<现象> / 期望：<期望>
- 问题 2：...

AI 修完会在每条后追加"已修 / 改了 <文件>"。

revision 轮次 ≥ 3 时应停下来：是 ticket 边界没切对？是 AC 写模糊？是不是该拆 ticket？
-->
