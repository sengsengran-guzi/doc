# GZ-SYS-007 — mp 管理端权限底座（openid 绑定 sys_user + 登录加载 RBAC）

**优先级**: P0
**复杂度**: L
**关联 PRD**: doc/02-prd.md M7.10（主理人 + 店员两级权限）
**关联 ADR**: doc/_adr/0004-mp-admin-permission-foundation.md（**必读，本 ticket 是其落地**）
**依赖**: GZ-SYS-002（mp 微信登录，已交付）/ GZ-ADMIN-001（gz_owner/gz_staff sys_user + 角色，已交付）

> **实施状态（2026-06-01）**：AC1-AC8 已实现 + 自测通过（见 [reports/GZ-SYS-007.md](../reports/GZ-SYS-007.md)）。
> 为达「D7x 零 V1.1 推诿」追加两条完整性 AC（**AC9 停用自动踢 / AC10 owner 绑定管理**），与本批次一起做完，不留尾到 V1.1。

---

## 必读权威文档

- **业务流**：doc/10 §1 微信登录（LoginUser 装载点）；ADR-0004 §决策 1（绑定 + 加载机制）
- **字段表**：doc/11 §gz_user（加列 `staff_user_id`）
- **UI 参考**：mp 个人中心 `design/mockup/`（视觉参考，条件入口区不强求逐像素）；admin 绑定管理走 ruoyi 默认审美

## What

建 mp 管理端权限底座：C 端微信用户（gz_user.openid）可绑定到 ruoyi 店员账号（sys_user）；mp 登录时若已绑定，把该 sys_user 的角色 + 权限载入当前 app_user 会话，使 mp 管理端点能直接用标准 `@SaCheckPermission`。**不另造平行 RBAC**（ADR-0004 决策 1）。权限失效要彻底（停用/解绑即时踢），且 owner 能自助管理绑定（不靠 dev 跑 SQL）。

## AC（验收标准）

### 已实现（AC1-AC8，见 reports）

- [x] AC 1：`gz_user` 加列 `staff_user_id BIGINT NULL`（指向 sys_user.user_id，NULL=纯顾客）。迁移 `V202606051000__GZ-SYS-007-add-gz_user-staff_user_id.sql`。
- [x] AC 2：mp wx-login 建 app_user LoginUser 后，若 openid 对应 staff_user_id 非空 → 加载该 sys_user 的 rolePermission + menuPermission 到 LoginUser（复用 ruoyi 装载，不手写权限串），校验同租户(1001)+status 正常+未禁用，否则降级纯顾客。
- [x] AC 3：`GET /app/gz/staff/me` 返回 isStaff + perms，供 mp 个人中心条件渲染。
- [x] AC 4：mp 管理端点 `@SaCheckPermission("gz:xxx:yyy")`：绑定且有权限的店员可调；纯顾客/无权限 → 403。
- [x] AC 5：**解绑**（staff_user_id 置 NULL）后对应 mp token 管理权限即时失效（解绑后同 token 立即 401，已验证）。
- [x] AC 6：seed 绑定 `gz_staff_chengdu`(101) 的 openid（dev 已绑 gz_user id=1 → 101 验证）。
- [x] AC 7：个人中心条件入口——店员登录显示「门店管理」区块；纯顾客不显示。
- [x] AC 8：**Tier 2 入口可达** — 绑定店员账号登 mp → 个人中心可见「门店管理」区块。

### 完整性补充（AC9-AC10，本批次必做，不推 V1.1）

- [x] AC 9：**停用 sys_user 即时踢 mp token（自动）**。**实现**：Spring AOP 切面 `SysUserStaffKickoutAspect`（放 ruoyi-gz-common，不改 ruoyi 源码），纯 `execution()` 切 `SysUserServiceImpl.updateUserStatus(Long,String)`（status='1' 停用→`kickoutByStaffUserId`）+ `deleteUserByIds(Long[])`（逐个 kick + 置 NULL 清悬挂），零新增模块依赖。**证据**：① 切面单测 7 通过（停用踢/启用不踢/0行不踢/null/异常吞/删除kick+clear/空数组）；② live 端到端 — owner 停用 sys_user 101 → 切面日志 `[gz-staff-aop] 停用 sys_user=101 → 自动踢出 1 个 mp 会话` → 同店员 token 再调 `/app/gz/staff/me` 返 `{"code":401}`，无需手动 kickout、无需等下次登录。详见 reports AC9 段。
- [x] AC 10：**owner 自助绑定管理**（admin 端）。**实现**：`GzStaffBindingController` 加 `GET /binding/list`（查 gz_user + 绑定快照，openid/手机号/userNo 搜）/ `GET /binding/candidates`（候选 sys_user）/ `POST /binding/{gzUserId}/bind`（set staff_user_id，校验同租户+正常+未删）；perms `gz:staff:binding:{list,bind,unbind}`，菜单 seed `V202606051100`（5060-5063，仅 owner 100 授权）；admin 页 `gz-common/staff-binding/index.vue` + api + zh/en i18n。**证据**：① bindStaff 单测 7 通过（校验各分支 + 改绑先踢）；② live 6 场景 — list/candidates/bind/unbind 全 200，绑不存在 sys_user 返 `{"code":500,"msg":"店员账号不存在：999"}`，店员 token 调 owner 端点返 `{"code":403}`（权限隔离）。owner 不写 SQL 即可绑/解店员身份。详见 reports AC10 段。

## Tech（端 + 范围）

- **后端**：`ruoyi-gz-common`
  - 已落：`WxLoginServiceImpl` 登录加载 / `MpStaffPermissionServiceImpl`（resolve/kickout/unbind）/ `StaffMeController` / `GzStaffBindingController`(owner 解绑+踢人)
  - AC9：ruoyi sys_user 停用/删除挂钩（找 ruoyi `SysUserService` 停用/删除入口或事件，调 `kickoutByStaffUserId`）
  - AC10：`GzStaffBindingController` 补「查 gz_user + set staff_user_id」端点 + perms `gz:staff:binding:list/bind/unbind`；菜单 seed（menu_id 5000-5999 GZ-SYS 段，挂「谷子业务」或「系统管理」下）
- **Admin**：`plus-ui/src/views/gz-*/`（AC10 绑定管理页，走 ruoyi 默认 CRUD 风格）
- **测试**：补 AC9（停用→自动踢）/ AC10（绑定 set→生效、解绑→失效）单测 + 集成

## 备注

- ⚠️ AC9/AC10 是 ADR-0004 安全红线 + 客户可操作性的完整闭环：**没有 AC9，停用店员的 mp 权限不能即时收回（安全漏）；没有 AC10，客户加店员必须找 Kevin 跑 SQL（不可运营）**。故拉进本批次，不推 V1.1。
- 真正属 V1.1 的是「**更多 mp 管理功能**」（订单/物流/资讯管理下沉 mp）——那是新功能，不是本批次欠债；底座已让其边际成本 = 加一行 `@SaCheckPermission` + 授权，无需再动底座。

---

## §revision（Kevin 批量人验后填，初始空）

<!-- 问题清单写这里，然后 @coder 修 D7x/GZ-SYS-007 revision 段 -->
